"""STRATUM local convenience prep — non-authority, non-target-specific setup.

Creates only passive/local scaffolding under ``.builder/`` so operator keys
(e.g. G) can fail-closed for *real* reasons rather than missing folders or a
missing default read-only Goose manifest.

Does not start Goose, does not grant authority, does not touch target source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Stable path so re-runs refresh one auto file instead of littering.
AUTO_GOOSE_MANIFEST_NAME = "stratum-auto-readonly.json"

_BUILDER_SUBDIRS = ("artifacts", "goose", "receipts")


def ensure_builder_scaffold(builder_root: Path) -> None:
    """Ensure standard ``.builder`` subdirs exist (idempotent)."""
    for name in _BUILDER_SUBDIRS:
        (builder_root / name).mkdir(parents=True, exist_ok=True)


def _resolve_target_name(settings: Any) -> str:
    """Pick a safe default target for auto-prep without requiring operator choice.

    Prefer an explicit profile on settings when present and valid. Otherwise
    use ``builder`` when this tree looks like builder-II, else ``generic``.
    """
    from builder_ii.lifecycle.setup.target_profiles import target_names

    valid = set(target_names())
    for attr in ("target_profile", "default_target", "target"):
        val = getattr(settings, attr, None)
        if val is None:
            continue
        name = getattr(val, "name", None) if not isinstance(val, str) else val
        if isinstance(name, str) and name in valid:
            return name

    project_root = getattr(settings, "project_root", None)
    if isinstance(project_root, Path) and (project_root / "builder_ii").is_dir():
        return "builder"
    return "generic"


def _default_agent_profile() -> str:
    """Read-oriented default for a read_only session."""
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
    """Return ``(path, note)``. Creates a default ``read_only`` manifest if none is usable.

    ``note`` is a short operator-facing explanation of what happened.
    Prefer any existing valid ``read_only`` manifest; only mint
    ``stratum-auto-readonly.json`` when none exists.
    """
    from builder_ii.adapters.goose.goose_session import (
        create_goose_session_manifest,
        validate_goose_session_manifest,
        validate_goose_session_manifest_file,
        write_goose_session_manifest,
    )

    ensure_builder_scaffold(builder_root)
    goose_dir = builder_root / "goose"

    candidates = sorted(goose_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
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
        # Mark auto-prep without inventing authority (immutable-style new dict).
        base_gov = manifest.get("governance") if isinstance(manifest.get("governance"), dict) else {}
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
        # write_goose_session_manifest uses parents=True, exist_ok=True
        write_goose_session_manifest(manifest, out)
        disk_errors = validate_goose_session_manifest_file(out)
        if disk_errors:
            return None, f"auto-prepared file failed validation: {disk_errors[0]}"
        return out, f"auto-prepared read-only manifest → {out.name}"
    except Exception as exc:
        return None, f"auto-prepare failed: {exc}"
