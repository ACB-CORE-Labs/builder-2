"""P4 — R* apply path: real receipts → corrections → HITL-bound φ-policy versioning.

Dual-correction cannot self-grant authority. Applying suggested φ deltas requires:
1. digest-bound ``rstar_apply_plan`` listing correction digests + base φ policy
2. digest-bound ``rstar_apply_approval`` matching plan.digest
3. ``apply_approved`` which emits a **new** versioned ``phi_policy`` + receipt

Does **not**:
- mutate ``DEFAULT_PHI`` in code
- update live routing defaults silently
- grant model/shell/gateway execution
- apply without HITL approval
"""

from __future__ import annotations

from typing import Any, Mapping

from builder_ii.wrp.artifacts import (
    ADJOINT_CORRECTION_KIND,
    PHI_POLICY_KIND,
    RSTAR_APPLY_APPROVAL_KIND,
    RSTAR_APPLY_PLAN_KIND,
    RSTAR_APPLY_RECEIPT_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)
from builder_ii.wrp.experience_store import (
    create_experience_store,
    error_rate,
    freeze_store,
    version_store,
)
from builder_ii.wrp.receipt_ingest import receipt_to_exemplar_fields
from builder_ii.wrp.spaces import DEFAULT_PHI, WORKLOAD_AXES

# Hard bounds so HITL-applied φ cannot explode the metric.
PHI_MIN = 0.1
PHI_MAX = 5.0
MAX_DELTA_PER_AXIS = 0.25
MAX_CORRECTIONS_PER_PLAN = 64


class RStarApplyError(ValueError):
    """Fail-closed R* apply refusal."""


def _clamp_phi(value: float) -> float:
    return max(PHI_MIN, min(PHI_MAX, float(value)))


def _normalize_phi(raw: Mapping[str, Any] | None) -> dict[str, float]:
    base = dict(DEFAULT_PHI)
    if raw is None:
        return {axis: float(base[axis]) for axis in WORKLOAD_AXES}
    out: dict[str, float] = {}
    for axis in WORKLOAD_AXES:
        if axis in raw:
            out[axis] = _clamp_phi(float(raw[axis]))
        else:
            out[axis] = float(base[axis])
    # Reject unknown axes (fail closed on silent extra authority axes).
    for key in raw:
        if key not in WORKLOAD_AXES:
            raise RStarApplyError(f"unknown phi axis {key!r}; allowed={list(WORKLOAD_AXES)}")
    return out


def create_phi_policy(
    *,
    policy_id: str = "default",
    phi: Mapping[str, float] | None = None,
    version: int = 0,
    parent_policy_digest: str | None = None,
    source_correction_digests: list[str] | None = None,
    applied_by: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Create a versioned φ-policy artifact (recorded only; not live routing authority)."""
    if version < 0:
        raise RStarApplyError("version must be >= 0")
    if parent_policy_digest is not None:
        if not isinstance(parent_policy_digest, str) or len(parent_policy_digest) != 64:
            raise RStarApplyError("parent_policy_digest must be a 64-char hex digest when set")
    coeffs = _normalize_phi(phi)
    return base_envelope(
        kind=PHI_POLICY_KIND,
        artifact_state="RECORDED_ONLY",
        capability_state="wrp_recorded_only",
        extra={
            "policy_id": policy_id,
            "version": int(version),
            "phi": coeffs,
            "parent_policy_digest": parent_policy_digest,
            "source_correction_digests": list(source_correction_digests or []),
            "applied_by": applied_by,
            "notes": notes,
            "updates_live_routing_defaults": False,
            "grants_authority": False,
            "requires_explicit_bind": True,
        },
    )


def phi_from_policy(policy: Mapping[str, Any]) -> dict[str, float]:
    """Extract clamped φ map from a phi_policy artifact."""
    if policy.get("kind") != PHI_POLICY_KIND:
        raise RStarApplyError(f"policy.kind must be {PHI_POLICY_KIND}")
    raw = policy.get("phi")
    if not isinstance(raw, Mapping):
        raise RStarApplyError("policy.phi must be an object")
    return _normalize_phi(raw)


def corrections_from_receipts(
    store: dict[str, Any],
    receipts: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Map receipts → experience exemplars + R* correction artifacts (immutable).

    Uses ``adjoint_correct`` once per receipt (append + correction). Failures produce
    positive error_signal and feature-driven suggested φ deltas. Does **not** apply φ.
    Returns (versioned_store, corrections).
    """
    from builder_ii.wrp.adjoint_operator import adjoint_correct

    if not isinstance(receipts, list):
        raise RStarApplyError("receipts must be a list")
    # Validate all receipts first (fail closed before any append).
    fields_list = [receipt_to_exemplar_fields(r, index=i) for i, r in enumerate(receipts)]

    working = store
    corrections: list[dict[str, Any]] = []
    for fields in fields_list:
        feature_deltas = dict(fields["features"])
        axis_deltas = {
            axis: float(feature_deltas[axis])
            for axis in WORKLOAD_AXES
            if axis in feature_deltas
        }
        if not fields["success"] and not axis_deltas:
            # Failures without axes still nudge difficulty (conservative default).
            axis_deltas = {"difficulty": 0.5}
        working, correction = adjoint_correct(
            store=working,
            trajectory_id=fields["trajectory_id"],
            success=fields["success"],
            error_signal=fields["error_signal"],
            feature_deltas=axis_deltas or None,
        )
        corrections.append(correction)
    versioned = version_store(working, notes="post-receipt R* corrections")
    return versioned, corrections


def _aggregate_phi_deltas(corrections: list[dict[str, Any]]) -> dict[str, float]:
    if not corrections:
        raise RStarApplyError("corrections list must be non-empty")
    if len(corrections) > MAX_CORRECTIONS_PER_PLAN:
        raise RStarApplyError(f"at most {MAX_CORRECTIONS_PER_PLAN} corrections per plan")
    sums: dict[str, float] = {axis: 0.0 for axis in WORKLOAD_AXES}
    counts: dict[str, int] = {axis: 0 for axis in WORKLOAD_AXES}
    digests: list[str] = []
    for index, corr in enumerate(corrections):
        if not isinstance(corr, dict):
            raise RStarApplyError(f"corrections[{index}] must be a dict")
        if corr.get("kind") != ADJOINT_CORRECTION_KIND:
            raise RStarApplyError(
                f"corrections[{index}].kind must be {ADJOINT_CORRECTION_KIND}"
            )
        if corr.get("requires_hitl_promotion_to_apply") is not True:
            raise RStarApplyError(
                f"corrections[{index}] must require HITL promotion to apply"
            )
        if corr.get("updates_live_routing") is not False:
            raise RStarApplyError(
                f"corrections[{index}].updates_live_routing must be false"
            )
        digest = corr.get("digest")
        if not isinstance(digest, str) or len(digest) != 64:
            raise RStarApplyError(f"corrections[{index}] must be finalized with digest")
        digests.append(digest)
        deltas = corr.get("suggested_phi_deltas") or {}
        if not isinstance(deltas, Mapping):
            raise RStarApplyError(f"corrections[{index}].suggested_phi_deltas must be object")
        for axis, value in deltas.items():
            if axis not in WORKLOAD_AXES:
                raise RStarApplyError(
                    f"corrections[{index}] suggests unknown axis {axis!r}"
                )
            try:
                num = float(value)
            except (TypeError, ValueError) as exc:
                raise RStarApplyError(
                    f"corrections[{index}].suggested_phi_deltas[{axis}] must be numeric"
                ) from exc
            # Only failure-driven positive nudges count toward aggregate apply.
            if corr.get("success") is False:
                sums[axis] += abs(num) * 0.05  # scale raw feature signal to φ delta space
                counts[axis] += 1
    aggregated: dict[str, float] = {}
    for axis in WORKLOAD_AXES:
        if counts[axis] == 0:
            continue
        mean = sums[axis] / counts[axis]
        # Cap per-axis absolute delta for this plan.
        capped = max(-MAX_DELTA_PER_AXIS, min(MAX_DELTA_PER_AXIS, mean))
        if abs(capped) > 1e-12:
            aggregated[axis] = round(capped, 6)
    if not aggregated:
        raise RStarApplyError(
            "no apply-worthy φ deltas (need at least one failed correction with axes)"
        )
    return aggregated


def build_rstar_apply_plan(
    *,
    base_policy: dict[str, Any],
    corrections: list[dict[str, Any]],
    experience_store: dict[str, Any] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """Build digest-bound plan to apply aggregated R* deltas onto base φ policy."""
    if base_policy.get("kind") != PHI_POLICY_KIND:
        raise RStarApplyError(f"base_policy.kind must be {PHI_POLICY_KIND}")
    base_digest = base_policy.get("digest")
    if not isinstance(base_digest, str) or len(base_digest) != 64:
        raise RStarApplyError("base_policy must be finalized with a 64-char digest")
    base_phi = phi_from_policy(base_policy)
    aggregated = _aggregate_phi_deltas(corrections)
    proposed = {
        axis: _clamp_phi(base_phi[axis] + aggregated.get(axis, 0.0)) for axis in WORKLOAD_AXES
    }
    correction_digests = [c["digest"] for c in corrections]
    store_digest = None
    if experience_store is not None:
        store_digest = experience_store.get("digest")
        if not isinstance(store_digest, str) or len(store_digest) != 64:
            raise RStarApplyError("experience_store must be finalized with digest when provided")
    next_version = int(base_policy.get("version") or 0) + 1
    return base_envelope(
        kind=RSTAR_APPLY_PLAN_KIND,
        artifact_state="PLANNED_ONLY",
        capability_state="wrp_hitl_phi_apply",
        extra={
            "base_policy_digest": base_digest,
            "base_policy_version": int(base_policy.get("version") or 0),
            "proposed_version": next_version,
            "base_phi": base_phi,
            "aggregated_deltas": aggregated,
            "proposed_phi": proposed,
            "correction_digests": correction_digests,
            "experience_store_digest": store_digest,
            "max_delta_per_axis": MAX_DELTA_PER_AXIS,
            "phi_bounds": {"min": PHI_MIN, "max": PHI_MAX},
            "updates_live_routing_defaults": False,
            "requires_hitl_approval": True,
            "grants_authority": False,
            "notes": notes,
        },
    )


def build_rstar_apply_approval(
    *,
    plan: dict[str, Any],
    approved_by: str,
    approved: bool = True,
    notes: str = "",
) -> dict[str, Any]:
    plan_digest = plan.get("digest")
    if not isinstance(plan_digest, str) or len(plan_digest) != 64:
        raise RStarApplyError("plan must be finalized with a 64-char digest before approval")
    if plan.get("kind") != RSTAR_APPLY_PLAN_KIND:
        raise RStarApplyError(f"plan.kind must be {RSTAR_APPLY_PLAN_KIND}")
    return base_envelope(
        kind=RSTAR_APPLY_APPROVAL_KIND,
        artifact_state="HITL_APPROVAL_ONLY",
        capability_state="wrp_hitl_phi_apply",
        extra={
            "approved": bool(approved),
            "approved_by": str(approved_by).strip(),
            "plan_kind": plan.get("kind"),
            "plan_digest": plan_digest,
            "notes": notes,
            "grants_unbounded_execution": False,
            "authorizes_phi_apply_only": True,
        },
    )


def _require_approval(plan: dict[str, Any], approval: dict[str, Any]) -> None:
    if approval.get("kind") != RSTAR_APPLY_APPROVAL_KIND:
        raise RStarApplyError(f"approval.kind must be {RSTAR_APPLY_APPROVAL_KIND}")
    if approval.get("approved") is not True:
        raise RStarApplyError("approval.approved must be true")
    if not str(approval.get("approved_by") or "").strip():
        raise RStarApplyError("approval.approved_by is required")
    if approval.get("plan_digest") != plan.get("digest"):
        raise RStarApplyError("approval.plan_digest must match plan.digest (digest-bound HITL)")
    if plan.get("kind") != RSTAR_APPLY_PLAN_KIND:
        raise RStarApplyError(f"plan.kind must be {RSTAR_APPLY_PLAN_KIND}")
    if plan.get("requires_hitl_approval") is not True:
        raise RStarApplyError("plan.requires_hitl_approval must be true")
    if plan.get("updates_live_routing_defaults") is not False:
        raise RStarApplyError("plan.updates_live_routing_defaults must be false")
    if plan.get("grants_authority") is not False:
        raise RStarApplyError("plan.grants_authority must be false")


def apply_approved(
    *,
    plan: dict[str, Any],
    approval: dict[str, Any],
    policy_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply HITL-approved R* plan → new versioned phi_policy + receipt.

    Returns (new_phi_policy, apply_receipt). Never mutates DEFAULT_PHI.
    """
    _require_approval(plan, approval)
    proposed = plan.get("proposed_phi")
    if not isinstance(proposed, Mapping):
        raise RStarApplyError("plan.proposed_phi is required")
    proposed_phi = _normalize_phi(proposed)
    # Re-check deltas vs base do not exceed caps (tamper resistance).
    base_phi = plan.get("base_phi")
    if not isinstance(base_phi, Mapping):
        raise RStarApplyError("plan.base_phi is required")
    base_norm = _normalize_phi(base_phi)
    for axis in WORKLOAD_AXES:
        delta = proposed_phi[axis] - base_norm[axis]
        if abs(delta) > MAX_DELTA_PER_AXIS + 1e-9:
            raise RStarApplyError(
                f"proposed delta for {axis} exceeds MAX_DELTA_PER_AXIS={MAX_DELTA_PER_AXIS}"
            )
    digests = plan.get("correction_digests")
    if not isinstance(digests, list) or not digests:
        raise RStarApplyError("plan.correction_digests must be a non-empty list")
    for d in digests:
        if not isinstance(d, str) or len(d) != 64:
            raise RStarApplyError("each correction_digest must be a 64-char hex digest")

    pid = policy_id or "default"
    new_policy = create_phi_policy(
        policy_id=pid,
        phi=proposed_phi,
        version=int(plan.get("proposed_version") or 0),
        parent_policy_digest=str(plan.get("base_policy_digest")),
        source_correction_digests=[str(d) for d in digests],
        applied_by=str(approval.get("approved_by")),
        notes=f"applied via HITL plan {plan.get('digest', '')[:16]}",
    )
    receipt = base_envelope(
        kind=RSTAR_APPLY_RECEIPT_KIND,
        artifact_state="HITL_PHI_APPLY_RECEIPT",
        capability_state="wrp_hitl_phi_apply",
        extra={
            "status": "success",
            "plan_digest": plan.get("digest"),
            "approval_digest": approval.get("digest"),
            "approved_by": approval.get("approved_by"),
            "base_policy_digest": plan.get("base_policy_digest"),
            "new_policy_digest": new_policy.get("digest"),
            "new_policy_version": new_policy.get("version"),
            "applied_phi": proposed_phi,
            "aggregated_deltas": plan.get("aggregated_deltas") or {},
            "correction_digests": list(digests),
            "experience_store_digest": plan.get("experience_store_digest"),
            "updates_live_routing_defaults": False,
            "grants_authority": False,
            "requires_explicit_bind": True,
            "p4_version": "v1_hitl_phi_policy",
        },
    )
    return new_policy, receipt


def simulate_receipt_epochs(
    *,
    receipt_epochs: list[list[dict[str, Any]]],
    store_id: str = "receipt_epochs",
) -> dict[str, Any]:
    """Real-receipt epoch harness: ingest per epoch, track error_rate reduction.

    Unlike synthetic ``simulate_epochs``, each epoch is a concrete receipt batch.
    Does not apply φ (apply is a separate HITL path). Measures store error_rate only.
    """
    if not isinstance(receipt_epochs, list) or not receipt_epochs:
        raise RStarApplyError("receipt_epochs must be a non-empty list of receipt lists")
    store = create_experience_store(store_id=store_id)
    rates: list[float] = []
    all_corrections: list[dict[str, Any]] = []
    for epoch_index, receipts in enumerate(receipt_epochs):
        if not isinstance(receipts, list) or not receipts:
            raise RStarApplyError(f"receipt_epochs[{epoch_index}] must be a non-empty list")
        store, corrections = corrections_from_receipts(store, receipts)
        all_corrections.extend(corrections)
        rates.append(error_rate(store))
    store = freeze_store(store)
    if not rates or rates[0] <= 0:
        reduction = 0.0
    else:
        reduction = (rates[0] - rates[-1]) / rates[0]
    return {
        "epoch_error_rates": rates,
        "relative_reduction": reduction,
        "meets_w4_threshold": reduction >= 0.30,
        "store": store,
        "correction_count": len(all_corrections),
        "correction_digests": [c.get("digest") for c in all_corrections if isinstance(c, dict)],
        "source": "real_receipts",
    }


# ---------------------------------------------------------------------------
# Validators
# ---------------------------------------------------------------------------


def validate_phi_policy(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=PHI_POLICY_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("updates_live_routing_defaults") is not False:
        errors.append("updates_live_routing_defaults must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("requires_explicit_bind") is not True:
        errors.append("requires_explicit_bind must be true")
    version = record.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version < 0:
        errors.append("version must be a non-negative int")
    phi = record.get("phi")
    if not isinstance(phi, dict):
        errors.append("phi must be an object")
    else:
        for axis in WORKLOAD_AXES:
            if axis not in phi:
                errors.append(f"phi missing axis {axis}")
            else:
                try:
                    val = float(phi[axis])
                    if val < PHI_MIN or val > PHI_MAX:
                        errors.append(f"phi[{axis}] out of bounds [{PHI_MIN}, {PHI_MAX}]")
                except (TypeError, ValueError):
                    errors.append(f"phi[{axis}] must be numeric")
        for key in phi:
            if key not in WORKLOAD_AXES:
                errors.append(f"unknown phi axis {key}")
    return errors


def validate_rstar_apply_plan(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=RSTAR_APPLY_PLAN_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("requires_hitl_approval") is not True:
        errors.append("requires_hitl_approval must be true")
    if record.get("updates_live_routing_defaults") is not False:
        errors.append("updates_live_routing_defaults must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    digest = record.get("base_policy_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("base_policy_digest must be a 64-char hex digest")
    digests = record.get("correction_digests")
    if not isinstance(digests, list) or not digests:
        errors.append("correction_digests must be a non-empty list")
    if not isinstance(record.get("proposed_phi"), dict):
        errors.append("proposed_phi must be an object")
    if not isinstance(record.get("aggregated_deltas"), dict):
        errors.append("aggregated_deltas must be an object")
    return errors


def validate_rstar_apply_approval(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=RSTAR_APPLY_APPROVAL_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("approved") is not True:
        errors.append("approved must be true for a positive approval artifact")
    if not str(record.get("approved_by") or "").strip():
        errors.append("approved_by is required")
    digest = record.get("plan_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("plan_digest must be a 64-char hex digest")
    if record.get("authorizes_phi_apply_only") is not True:
        errors.append("authorizes_phi_apply_only must be true")
    if record.get("grants_unbounded_execution") is not False:
        errors.append("grants_unbounded_execution must be false")
    return errors


def validate_rstar_apply_receipt(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=RSTAR_APPLY_RECEIPT_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("status") != "success":
        errors.append("status must be success for completed receipt")
    if record.get("updates_live_routing_defaults") is not False:
        errors.append("updates_live_routing_defaults must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("requires_explicit_bind") is not True:
        errors.append("requires_explicit_bind must be true")
    for key in ("plan_digest", "approval_digest", "new_policy_digest", "base_policy_digest"):
        val = record.get(key)
        if not isinstance(val, str) or len(val) != 64:
            errors.append(f"{key} must be a 64-char hex digest")
    return errors
