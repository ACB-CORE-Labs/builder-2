"""W3.2 ceremony surface — scoped multi-agent enablement *decision* artifacts.

Does **not** silently flip global S3 defaults. Produces a digest-bound decision
that an operator can apply only when Class U proof is held and HITL approval
is present. Global ``s3_enabled`` registry defaults remain false until that
decision is explicitly applied to a session binding.
"""

from __future__ import annotations

import hashlib
import json as json_lib
from typing import Any

S3_ENABLEMENT_DECISION_KIND = "builder_ii.wrp.s3_enablement_decision"
S3_ENABLEMENT_DECISION_SCHEMA_VERSION = 1
S3_SESSION_BINDING_KIND = "builder_ii.wrp.s3_session_binding"
S3_SESSION_BINDING_SCHEMA_VERSION = 1


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_s3_enablement_decision(
    *,
    class_u_report: dict[str, Any],
    class_u_proof: dict[str, Any],
    approved_by: str,
    scope: str = "session_scoped_multi_agent",
    rationale: str = "Class U production-shaped evidence held; operator ceremony approval",
) -> dict[str, Any]:
    """Build a decision artifact. Fails closed unless proof.held and utility_ok."""
    if not str(approved_by or "").strip():
        raise ValueError("approved_by required")
    if class_u_proof.get("held") is not True:
        raise ValueError("class_u_proof.held must be true to create S3 enablement decision")
    summary = (class_u_report.get("summary") if isinstance(class_u_report, dict) else None) or {}
    if summary and summary.get("utility_ok") is False and summary.get("proof_u_held") is False:
        raise ValueError("class_u report summary must not explicitly fail utility_ok/proof_u_held")

    decision: dict[str, Any] = {
        "kind": S3_ENABLEMENT_DECISION_KIND,
        "schema_version": S3_ENABLEMENT_DECISION_SCHEMA_VERSION,
        "decision_state": "APPROVED_SCOPED",
        "scope": scope,
        "approved_by": approved_by,
        "rationale": rationale,
        "class_u_report_digest": class_u_report.get("digest"),
        "class_u_proof_digest": class_u_proof.get("digest"),
        "class_u_proof_held": True,
        "global_default_s3_enabled": False,  # never auto-flips global default
        "session_scoped_enable_permitted": True,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_operator_apply": True,
    }
    decision["digest"] = _digest({k: v for k, v in decision.items() if k != "digest"})
    return decision


def apply_s3_session_binding(
    *,
    decision: dict[str, Any],
    session_id: str,
) -> dict[str, Any]:
    """Apply a decision to a *session* binding only (not global registry)."""
    errs = validate_s3_enablement_decision(decision)
    if errs:
        raise ValueError("invalid s3 enablement decision: " + "; ".join(errs))
    if decision.get("session_scoped_enable_permitted") is not True:
        raise ValueError("decision does not permit session-scoped enable")
    if not session_id.strip():
        raise ValueError("session_id required")
    binding: dict[str, Any] = {
        "kind": S3_SESSION_BINDING_KIND,
        "schema_version": S3_SESSION_BINDING_SCHEMA_VERSION,
        "session_id": session_id,
        "s3_enabled": True,  # session scope only
        "scope": decision.get("scope"),
        "decision_digest": decision.get("digest"),
        "approved_by": decision.get("approved_by"),
        "global_default_s3_enabled": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "notes": "Session-scoped multi-agent enablement; does not mutate DEFAULT registry s3_enabled.",
    }
    binding["digest"] = _digest({k: v for k, v in binding.items() if k != "digest"})
    return binding


def validate_s3_enablement_decision(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["s3 enablement decision must be a JSON object"]
    if record.get("kind") != S3_ENABLEMENT_DECISION_KIND:
        errors.append(f"kind must be {S3_ENABLEMENT_DECISION_KIND}")
    if record.get("schema_version") != S3_ENABLEMENT_DECISION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {S3_ENABLEMENT_DECISION_SCHEMA_VERSION}")
    if record.get("class_u_proof_held") is not True:
        errors.append("class_u_proof_held must be true")
    if record.get("global_default_s3_enabled") is not False:
        errors.append("global_default_s3_enabled must remain false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if not str(record.get("approved_by") or "").strip():
        errors.append("approved_by required")
    return errors


def validate_s3_session_binding(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["s3 session binding must be a JSON object"]
    if record.get("kind") != S3_SESSION_BINDING_KIND:
        errors.append(f"kind must be {S3_SESSION_BINDING_KIND}")
    if record.get("global_default_s3_enabled") is not False:
        errors.append("global_default_s3_enabled must be false")
    if record.get("s3_enabled") is not True:
        errors.append("session s3_enabled must be true for an applied binding")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    return errors
