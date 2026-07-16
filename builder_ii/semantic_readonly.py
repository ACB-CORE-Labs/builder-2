"""V.1 semantic / structural read-only lane (doctor | map | preview).

Reuses:
- ``create_repo_map`` (pure walk, no subprocess)
- ``tool_registry.check_tools`` for serena / ast-grep / rg detect-only
- in-process AST symbol extract when available (CodeVault)

Does **not**:
- write to scanned target tree
- invoke Serena rewrite / ast-grep apply
- enable MCP edit tools
- grant authority

Promotion ceiling: ``validation_only`` / advisory artifacts only.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from builder_ii.repo_map import create_repo_map, validate_repo_map
from builder_ii.tool_registry import check_tools
from builder_ii.workflow_records import canonical_digest

SEMANTIC_DOCTOR_KIND = "builder_ii.semantic_doctor_report"
SEMANTIC_MAP_KIND = "builder_ii.semantic_map"
SEMANTIC_PREVIEW_KIND = "builder_ii.semantic_preview"

# Tools that matter for this RO lane (detect-only).
_SEMANTIC_TOOL_NAMES = frozenset({"serena", "ast-grep", "rg", "fd"})


def _tool_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for check in check_tools():
        if check.tool.name not in _SEMANTIC_TOOL_NAMES:
            continue
        rows.append(
            {
                "name": check.tool.name,
                "tier": check.tool.tier,
                "integration": check.tool.integration,
                "status": check.status,
                "path": check.path,
                "required": check.tool.required,
                "install": check.tool.install,
            }
        )
    return rows


def doctor_semantic(*, repo_path: Path | str | None = None) -> dict[str, Any]:
    """Detect-only health for semantic/structural RO stack.

    Does not fail solely because serena/ast-grep are missing (optional).
    ``ok`` is True when in-process repo_map path works (always if repo exists).
    """
    tools = _tool_rows()
    by_name = {t["name"]: t for t in tools}
    serena = by_name.get("serena", {})
    ast_grep = by_name.get("ast-grep", {})
    rg = by_name.get("rg", {})

    root = Path(repo_path).resolve() if repo_path else Path.cwd()
    map_ok = root.is_dir()
    map_error = None
    if map_ok:
        try:
            sample = create_repo_map(root, target_name="builder", max_files=5)
            map_ok = len(validate_repo_map(sample)) == 0
        except Exception as exc:  # noqa: BLE001 — doctor must not crash
            map_ok = False
            map_error = str(exc)

    report = {
        "kind": SEMANTIC_DOCTOR_KIND,
        "schema_version": 1,
        "artifact_state": "VALIDATION_ONLY",
        "capability_state": "validation_only",
        "scan_state": "READ_ONLY",
        "grants_authority": False,
        "mutates_target_repo": False,
        "executes_shell": False,
        "invokes_serena_rewrite": False,
        "invokes_ast_grep_apply": False,
        "repo_path": str(root),
        "in_process_repo_map_ok": map_ok,
        "map_error": map_error,
        "tools": tools,
        "serena_status": serena.get("status", "missing"),
        "ast_grep_status": ast_grep.get("status", "missing"),
        "rg_status": rg.get("status", "missing"),
        "external_tools_optional": True,
        "ok": map_ok,
        "notes": (
            "Doctor is detect-only. serena/ast-grep may be missing without failing ok. "
            "Map uses pure create_repo_map (no subprocess). Preview is in-process only in V.1."
        ),
    }
    report["digest"] = canonical_digest(report)
    return report


def map_semantic(
    repo_path: Path | str,
    *,
    target_name: str = "builder",
    max_files: int = 200,
) -> dict[str, Any]:
    """Bounded read-only structural file map (repo_map wrapped as semantic_map)."""
    root = Path(repo_path)
    repo_map = create_repo_map(root, target_name=target_name, max_files=max_files)
    errors = validate_repo_map(repo_map)
    if errors:
        raise ValueError(f"invalid repo_map: {'; '.join(errors)}")

    files = repo_map.get("files") if isinstance(repo_map.get("files"), list) else []
    # Optional in-process symbol peek for a few source files (no external tools).
    symbol_samples: list[dict[str, Any]] = []
    try:
        from builder_ii_code_vault.code_vault.symbol_extractor import extract_symbols_from_file
    except ImportError:
        extract_symbols_from_file = None  # type: ignore[assignment]

    if extract_symbols_from_file is not None:
        for entry in files[:20]:
            if not isinstance(entry, dict):
                continue
            if entry.get("role") != "source":
                continue
            rel = entry.get("path") or entry.get("rel_path")
            if not isinstance(rel, str):
                continue
            full = root.resolve() / rel
            if not full.is_file() or full.suffix != ".py":
                continue
            try:
                symbols = extract_symbols_from_file(full)
            except Exception:  # noqa: BLE001
                continue
            if symbols:
                symbol_samples.append({"path": rel, "symbol_count": len(symbols)})

    art = {
        "kind": SEMANTIC_MAP_KIND,
        "schema_version": 1,
        "artifact_state": "ARTIFACT_ONLY",
        "capability_state": "validation_only",
        "scan_state": "READ_ONLY",
        "grants_authority": False,
        "mutates_target_repo": False,
        "executes_shell": False,
        "target_name": target_name,
        "repo_path": str(root.resolve()),
        "repo_map_digest": repo_map.get("digest"),
        "file_count": len(files),
        "files": files,
        "symbol_samples": symbol_samples,
        "external_index": None,
        "notes": (
            "V.1 map = create_repo_map + optional in-process symbol counts. "
            "No Serena/ast-grep index in this version."
        ),
    }
    art["digest"] = canonical_digest(art)
    return art


def preview_semantic(
    repo_path: Path | str,
    *,
    query: str,
    target_name: str = "builder",
    max_hits: int = 25,
    max_files: int = 200,
) -> dict[str, Any]:
    """Dry-run path/name substring preview over repo_map (no external rewrite tools)."""
    if not query or not str(query).strip():
        raise ValueError("query must be non-empty")
    q = str(query).strip().lower()
    mapped = map_semantic(repo_path, target_name=target_name, max_files=max_files)
    hits: list[dict[str, Any]] = []
    for entry in mapped.get("files") or []:
        if not isinstance(entry, dict):
            continue
        path = str(entry.get("path") or entry.get("rel_path") or "")
        role = str(entry.get("role") or "")
        if q in path.lower() or q in role.lower():
            hits.append(
                {
                    "path": path,
                    "role": role,
                    "match": "path_or_role",
                }
            )
        if len(hits) >= max_hits:
            break

    art = {
        "kind": SEMANTIC_PREVIEW_KIND,
        "schema_version": 1,
        "artifact_state": "VALIDATION_ONLY",
        "capability_state": "validation_only",
        "scan_state": "READ_ONLY",
        "grants_authority": False,
        "mutates_target_repo": False,
        "executes_shell": False,
        "invokes_serena_rewrite": False,
        "invokes_ast_grep_apply": False,
        "query": query,
        "hit_count": len(hits),
        "hits": hits,
        "map_digest": mapped.get("digest"),
        "notes": (
            "V.1 preview is substring match over repo_map paths/roles only. "
            "Not Serena symbol graph; not ast-grep structural query."
        ),
    }
    art["digest"] = canonical_digest(art)
    return art


def validate_semantic_doctor(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["semantic doctor must be an object"]
    if record.get("kind") != SEMANTIC_DOCTOR_KIND:
        errors.append(f"kind must be {SEMANTIC_DOCTOR_KIND}")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("mutates_target_repo") is not False:
        errors.append("mutates_target_repo must be false")
    return errors


def validate_semantic_map(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["semantic map must be an object"]
    if record.get("kind") != SEMANTIC_MAP_KIND:
        errors.append(f"kind must be {SEMANTIC_MAP_KIND}")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("mutates_target_repo") is not False:
        errors.append("mutates_target_repo must be false")
    if not isinstance(record.get("files"), list):
        errors.append("files must be a list")
    return errors


def validate_semantic_preview(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["semantic preview must be an object"]
    if record.get("kind") != SEMANTIC_PREVIEW_KIND:
        errors.append(f"kind must be {SEMANTIC_PREVIEW_KIND}")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("invokes_serena_rewrite") is not False:
        errors.append("invokes_serena_rewrite must be false")
    if record.get("invokes_ast_grep_apply") is not False:
        errors.append("invokes_ast_grep_apply must be false")
    return errors


__all__ = [
    "SEMANTIC_DOCTOR_KIND",
    "SEMANTIC_MAP_KIND",
    "SEMANTIC_PREVIEW_KIND",
    "doctor_semantic",
    "map_semantic",
    "preview_semantic",
    "validate_semantic_doctor",
    "validate_semantic_map",
    "validate_semantic_preview",
]
