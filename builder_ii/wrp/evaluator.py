"""Trajectory Evaluator + proof classes R / D / U (STAR evaluation reference)."""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.artifacts import (
    PROOF_RECORD_KIND,
    TRAJECTORY_EVALUATION_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)


def evaluate_trajectory(
    *,
    trajectory_id: str,
    success: bool,
    safety_ok: bool,
    sequence_ok: bool,
    cost_units: float,
    budget_units: float,
) -> dict[str, Any]:
    quality = 1.0 if success and safety_ok and sequence_ok else 0.0
    if success and safety_ok and not sequence_ok:
        quality = 0.5
    over_budget = cost_units > budget_units * 1.10 if budget_units > 0 else False
    return base_envelope(
        kind=TRAJECTORY_EVALUATION_KIND,
        artifact_state="VALIDATION_ONLY",
        capability_state="wrp_validation_only",
        extra={
            "trajectory_id": trajectory_id,
            "metrics": {
                "success": success,
                "safety_ok": safety_ok,
                "sequence_ok": sequence_ok,
                "quality": quality,
                "cost_units": cost_units,
                "budget_units": budget_units,
                "over_budget": over_budget,
            },
            "grants_authority": False,
        },
    )


def create_proof_record(
    *,
    proof_class: str,
    claim: str,
    held: bool,
    evidence_refs: list[str] | None = None,
) -> dict[str, Any]:
    if proof_class not in {"R", "D", "U"}:
        raise ValueError("proof_class must be R, D, or U")
    return base_envelope(
        kind=PROOF_RECORD_KIND,
        artifact_state="VALIDATION_ONLY",
        capability_state="wrp_validation_only",
        extra={
            "proof_class": proof_class,
            "class_name": {
                "R": "Representation Integrity",
                "D": "Detection Validity",
                "U": "Engineering Utility",
            }[proof_class],
            "claim": claim,
            "held": held,
            "evidence_refs": list(evidence_refs or []),
            "grants_authority": False,
        },
    )


def validate_trajectory_evaluation(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=TRAJECTORY_EVALUATION_KIND)
    if not isinstance(record, dict):
        return errors
    metrics = record.get("metrics")
    if not isinstance(metrics, dict):
        errors.append("metrics must be an object")
    return errors


def validate_proof_record(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=PROOF_RECORD_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("proof_class") not in {"R", "D", "U"}:
        errors.append("proof_class must be R, D, or U")
    return errors
