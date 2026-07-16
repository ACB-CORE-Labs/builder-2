"""W4 / F4 — ExperienceStore (MAAP reference).

Stores trajectory exemplars and success signals as digest-bound artifacts.
Does not mutate live routing authority.
"""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.artifacts import (
    EXPERIENCE_STORE_KIND,
    base_envelope,
    finalize_wrp_artifact,
    validate_wrp_artifact_envelope,
)


def create_experience_store(*, store_id: str = "default") -> dict[str, Any]:
    return base_envelope(
        kind=EXPERIENCE_STORE_KIND,
        artifact_state="RECORDED_ONLY",
        capability_state="wrp_recorded_only",
        extra={
            "store_id": store_id,
            "exemplars": [],
            "frozen": False,
            "version": 0,
            "parent_digest": None,
            "grants_authority": False,
            "updates_live_routing": False,
        },
    )


def version_store(store: dict[str, Any], *, notes: str = "") -> dict[str, Any]:
    """Return a new store revision with version+1 and parent_digest linkage (immutable).

    Used by P4 R* apply lineage. Does not freeze and does not grant live routing.
    """
    if store.get("frozen") is True:
        raise ValueError("experience store is frozen; cannot version")
    parent = store.get("digest")
    if not isinstance(parent, str) or len(parent) != 64:
        raise ValueError("store must be finalized with a 64-char digest before versioning")
    updated = dict(store)
    updated["version"] = int(store.get("version") or 0) + 1
    updated["parent_digest"] = parent
    if notes:
        updated["version_notes"] = notes
    updated.pop("digest", None)
    return finalize_wrp_artifact(updated)


def append_exemplar(
    store: dict[str, Any],
    *,
    trajectory_id: str,
    success: bool,
    error_signal: float,
    features: dict[str, float] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Return a new store with exemplar appended (immutable update)."""
    if store.get("frozen") is True:
        raise ValueError("experience store is frozen; cannot append")
    exemplars = list(store.get("exemplars") or [])
    exemplars.append(
        {
            "trajectory_id": trajectory_id,
            "success": bool(success),
            "error_signal": float(error_signal),
            "features": dict(features or {}),
            "notes": notes,
        }
    )
    updated = dict(store)
    updated["exemplars"] = exemplars
    updated.pop("digest", None)
    return finalize_wrp_artifact(updated)


def freeze_store(store: dict[str, Any]) -> dict[str, Any]:
    updated = dict(store)
    updated["frozen"] = True
    updated.pop("digest", None)
    return finalize_wrp_artifact(updated)


def error_rate(store: dict[str, Any]) -> float:
    exemplars = store.get("exemplars") or []
    if not exemplars:
        return 0.0
    failures = sum(1 for e in exemplars if not e.get("success"))
    return failures / len(exemplars)


def validate_experience_store(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=EXPERIENCE_STORE_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("updates_live_routing") is not False:
        errors.append("updates_live_routing must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if not isinstance(record.get("exemplars"), list):
        errors.append("exemplars must be a list")
    version = record.get("version")
    if version is not None and (
        not isinstance(version, int) or isinstance(version, bool) or version < 0
    ):
        errors.append("version must be a non-negative int when present")
    parent = record.get("parent_digest")
    if parent is not None and (not isinstance(parent, str) or len(parent) != 64):
        errors.append("parent_digest must be a 64-char hex digest when present")
    return errors
