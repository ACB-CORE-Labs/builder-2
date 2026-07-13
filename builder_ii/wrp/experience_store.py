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
            "grants_authority": False,
            "updates_live_routing": False,
        },
    )


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
    return errors
