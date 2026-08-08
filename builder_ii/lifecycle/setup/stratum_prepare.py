"""STRATUM local convenience preparation — passive artifacts only.

This module may write local ``.builder`` scaffolding on behalf of the TUI, whose own
source tree is intentionally file-write-free.  It never starts a runtime or grants
authority.

The legacy auto-readonly manifest keeps its stable convenience path because it represents
one reusable default.  Task-bound governed-run manifests are different: each requested task
is immutable run input, so those manifests are content-addressed and never overwrite one
another.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

AUTO_GOOSE_MANIFEST_NAME = "stratum-auto-readonly.json"
GOVERNED_GOOSE_MANIFEST_DIR = "governed-manifests"

_BUILDER_SUBDIRS = ("artifacts", "goose", "receipts")


def ensure_builder_scaffold(builder_root: Path) -> None:
    for name in _BUILDER_SUBDIRS:
        (builder_root / name).mkdir(parents=True, exist_ok=True)


def _resolve_target_name(settings: Any) -> str:
    from builder_ii.lifecycle.setup.target_profiles import target_names

    valid = set(target_names())
    for attr in ("target_profile", "default_target", "target"):
        value = getattr(settings, attr, None)
        if value is None:
            continue
        name = getattr(value, "name", None) if not isinstance(value, str) else value
        if isinstance(name, str) and name in valid:
            return name

    project_root = getattr(settings, "project_root", None)
    if isinstance(project_root, Path) and (project_root / "builder_ii").is_dir():
        return "builder"
    return "generic"


def _default_agent_profile() -> str:
    try:
        from builder_ii.routing.agent_profiles import agent_profile_names

        names = set(agent_profile_names())
        if "repo_mapper" in names:
            return "repo_mapper"
        return next(iter(sorted(names)), "patch_planner")
    except Exception:
        return "patch_planner"


def ensure_readonly_goose_manifest(
    *,
    settings: Any,
    builder_root: Path,
    task: str = "stratum read-only session",
) -> tuple[Path | None, str]:
    """Return an existing valid read-only manifest or mint the stable local default."""
    from builder_ii.adapters.goose.goose_session import (
        create_goose_session_manifest,
        validate_goose_session_manifest,
        validate_goose_session_manifest_file,
        write_goose_session_manifest,
    )

    ensure_builder_scaffold(builder_root)
    goose_dir = builder_root / "goose"

    candidates = sorted(
        goose_dir.glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True
    )
    for candidate in candidates:
        if validate_goose_session_manifest_file(candidate):
            continue
        try:
            data = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, ValueError):
            continue
        if isinstance(data, dict) and data.get("requested_runtime_mode") == "read_only":
            return candidate, f"using existing read-only manifest ({candidate.name})"

    target = _resolve_target_name(settings)
    agent = _default_agent_profile()
    project_root = getattr(settings, "project_root", None)
    generic_repo = project_root if isinstance(project_root, Path) else None

    try:
        manifest = create_goose_session_manifest(
            settings,
            target_name=target,  # type: ignore[arg-type]
            agent_profile=agent,  # type: ignore[arg-type]
            runtime_mode="read_only",
            task=task,
            generic_repo=generic_repo if target == "generic" else None,
        )
        base_gov = (
            manifest.get("governance")
            if isinstance(manifest.get("governance"), dict)
            else {}
        )
        manifest = {
            **manifest,
            "governance": {
                **base_gov,
                "stratum_auto_prepared": True,
                "artifact_is_authority": False,
            },
        }
        errors = validate_goose_session_manifest(manifest)
        if errors:
            return None, f"could not auto-build manifest: {errors[0]}"

        out = goose_dir / AUTO_GOOSE_MANIFEST_NAME
        write_goose_session_manifest(manifest, out)
        disk_errors = validate_goose_session_manifest_file(out)
        if disk_errors:
            return None, f"auto-prepared file failed validation: {disk_errors[0]}"
        return out, f"auto-prepared read-only manifest → {out.name}"
    except Exception as exc:
        return None, f"auto-prepare failed: {exc}"


def _manifest_digest(manifest: dict[str, Any]) -> str:
    """Digest the canonical serialized manifest bytes used for the content-addressed path."""
    from builder_ii.adapters.goose.goose_session import dumps_goose_session_manifest

    return hashlib.sha256(dumps_goose_session_manifest(manifest).encode("utf-8")).hexdigest()


def ensure_governed_goose_manifest(
    *,
    settings: Any,
    builder_root: Path,
    task: str,
) -> tuple[Path | None, str]:
    """Mint an immutable content-addressed ``read_only`` manifest for one task.

    Exact duplicate content is idempotently reused only after validating the bytes already
    on disk.  Different tasks or settings cannot collide by pathname, and a stale/mutated
    file at the expected digest path is a refusal rather than an overwrite.
    """
    from builder_ii.adapters.goose.goose_session import (
        create_goose_session_manifest,
        dumps_goose_session_manifest,
        validate_goose_session_manifest,
        validate_goose_session_manifest_file,
        write_goose_session_manifest,
    )

    cleaned = task.strip()
    if not cleaned:
        return None, "a governed run needs a task"

    ensure_builder_scaffold(builder_root)
    target = _resolve_target_name(settings)
    project_root = getattr(settings, "project_root", None)
    generic_repo = project_root if isinstance(project_root, Path) else None

    try:
        manifest = create_goose_session_manifest(
            settings,
            target_name=target,  # type: ignore[arg-type]
            agent_profile=_default_agent_profile(),  # type: ignore[arg-type]
            runtime_mode="read_only",
            task=cleaned,
            generic_repo=generic_repo if target == "generic" else None,
        )
        base_gov = (
            manifest.get("governance")
            if isinstance(manifest.get("governance"), dict)
            else {}
        )
        manifest = {
            **manifest,
            "governance": {
                **base_gov,
                "stratum_auto_prepared": True,
                "artifact_is_authority": False,
            },
        }
        errors = validate_goose_session_manifest(manifest)
        if errors:
            return None, f"could not build governed manifest: {errors[0]}"

        digest = _manifest_digest(manifest)
        directory = builder_root / "goose" / GOVERNED_GOOSE_MANIFEST_DIR
        directory.mkdir(parents=True, exist_ok=True)
        out = directory / f"{digest}.json"
        expected_text = dumps_goose_session_manifest(manifest)

        if out.exists():
            try:
                existing_text = out.read_text(encoding="utf-8")
            except OSError as exc:
                return None, f"existing governed manifest is unreadable: {exc}"
            if existing_text != expected_text:
                return None, (
                    "content-addressed governed manifest path contains unexpected bytes; "
                    "refusing to overwrite evidence"
                )
        else:
            write_goose_session_manifest(manifest, out)

        disk_errors = validate_goose_session_manifest_file(out)
        if disk_errors:
            return None, f"governed manifest failed validation: {disk_errors[0]}"
        observed = hashlib.sha256(out.read_bytes()).hexdigest()
        if observed != digest:
            return None, "governed manifest content digest does not match its filename"
        return out, f"governed manifest → {out.name}"
    except Exception as exc:
        return None, f"could not build governed manifest: {exc}"
