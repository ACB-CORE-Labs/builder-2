"""WRP artifact kinds, finalization, and shared envelope validation."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable
from builder_ii.governance_standard import build_standard_governance, validate_standard_governance

# Artifact kinds (digest-bound, recommendation/plan/validation only)
WORKLOAD_CLASSIFICATION_KIND = "builder_ii.wrp.workload_classification"
COLLABORATION_TOPOLOGY_KIND = "builder_ii.wrp.collaboration_topology"
FLEET_ALLOCATION_KIND = "builder_ii.wrp.fleet_allocation"
MSDA_POLICY_KIND = "builder_ii.wrp.msda_policy"
MSDA_GATE_DECISION_KIND = "builder_ii.wrp.msda_gate_decision"
EXPERIENCE_STORE_KIND = "builder_ii.wrp.experience_store"
AGENT_FACTORY_PLAN_KIND = "builder_ii.wrp.agent_factory_plan"
SUBTASK_GRAPH_KIND = "builder_ii.wrp.subtask_graph"
TRAJECTORY_EVALUATION_KIND = "builder_ii.wrp.trajectory_evaluation"
FORWARD_ROUTE_KIND = "builder_ii.wrp.forward_route"
ADJOINT_CORRECTION_KIND = "builder_ii.wrp.adjoint_correction"
PROOF_RECORD_KIND = "builder_ii.wrp.proof_record"
REPLAY_REPORT_KIND = "builder_ii.wrp.replay_report"
MAKER_CANDIDATE_MANIFEST_KIND = "builder_ii.wrp.maker_candidate_manifest"
GOVERNOR_CERTIFICATION_KIND = "builder_ii.wrp.governor_certification"

WRP_SCHEMA_VERSION = 1

WRP_ARTIFACT_KINDS: frozenset[str] = frozenset(
    {
        WORKLOAD_CLASSIFICATION_KIND,
        COLLABORATION_TOPOLOGY_KIND,
        FLEET_ALLOCATION_KIND,
        MSDA_POLICY_KIND,
        MSDA_GATE_DECISION_KIND,
        EXPERIENCE_STORE_KIND,
        AGENT_FACTORY_PLAN_KIND,
        SUBTASK_GRAPH_KIND,
        TRAJECTORY_EVALUATION_KIND,
        FORWARD_ROUTE_KIND,
        ADJOINT_CORRECTION_KIND,
        PROOF_RECORD_KIND,
        REPLAY_REPORT_KIND,
        MAKER_CANDIDATE_MANIFEST_KIND,
        GOVERNOR_CERTIFICATION_KIND,
    }
)

_FORBIDDEN_ACTIVE_STATES = frozenset(
    {
        "EXECUTED",
        "AUTHORIZED",
        "PROMOTED",
        "ENABLED",
        "RUNTIME_ACTIVE",
        "AUTHORITY_GRANTED",
    }
)

# Capability states allowed on WRP artifacts (honest, non-inflating).
ALLOWED_CAPABILITY_STATES = frozenset(
    {
        "wrp_recommendation_only",
        "wrp_plan_only",
        "wrp_validation_only",
        "wrp_artifact_only",
        "wrp_recorded_only",
        "wrp_exchange_only",
    }
)


def dumps_wrp(data: dict[str, Any]) -> str:
    return json_lib.dumps(data, indent=2, sort_keys=True) + "\n"


def write_wrp(data: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_wrp(data), encoding="utf-8")


def finalize_wrp_artifact(data: dict[str, Any]) -> dict[str, Any]:
    """Attach digest without mutating authority fields."""
    payload = dict(data)
    payload.pop("digest", None)
    return attach_digest(payload)


def base_envelope(
    *,
    kind: str,
    artifact_state: str,
    capability_state: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if kind not in WRP_ARTIFACT_KINDS:
        raise ValueError(f"unknown WRP kind: {kind}")
    if capability_state not in ALLOWED_CAPABILITY_STATES:
        raise ValueError(f"capability_state not allowed for WRP: {capability_state}")
    body: dict[str, Any] = {
        "kind": kind,
        "schema_version": WRP_SCHEMA_VERSION,
        "artifact_state": artifact_state,
        "governance": build_standard_governance(capability_state),
        "reference_frameworks": {
            "star": "classification reference only",
            "masrouter": "collaboration topology reference only",
            "omnirouter": "fleet allocation reference only",
            "msda": "declarative access gating reference only",
            "maap": "experience / adjoint reference only",
            "moira": "agent factory lifecycle reference only",
            "langgraph": "subtask graph pattern reference only — no LangGraph dependency",
            "modernbert": "optional embedding backend unpromoted",
            "vllm_wrp": "research / non-default target profile reference only",
        },
        "non_authority": {
            "grants_execution": False,
            "grants_promotion": False,
            "model_output_is_approval": False,
            "artifact_is_authority": False,
        },
    }
    if extra:
        body.update(extra)
    return finalize_wrp_artifact(body)


def validate_wrp_artifact_envelope(record: Any, *, expected_kind: str | None = None) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["WRP artifact must be a JSON object"]
    kind = record.get("kind")
    if kind not in WRP_ARTIFACT_KINDS:
        errors.append(f"kind must be one of WRP kinds, got {kind!r}")
    if expected_kind is not None and kind != expected_kind:
        errors.append(f"kind must be {expected_kind}")
    if record.get("schema_version") != WRP_SCHEMA_VERSION:
        errors.append(f"schema_version must be {WRP_SCHEMA_VERSION}")
    state = record.get("artifact_state")
    if not isinstance(state, str) or not state:
        errors.append("artifact_state must be a non-empty string")
    elif state.upper() in _FORBIDDEN_ACTIVE_STATES:
        errors.append(f"artifact_state must not claim active authority: {state}")

    gov = record.get("governance")
    cap = None
    if isinstance(gov, dict):
        cap = gov.get("capability_state")
    if cap not in ALLOWED_CAPABILITY_STATES:
        errors.append(f"governance.capability_state must be one of {sorted(ALLOWED_CAPABILITY_STATES)}")
    else:
        errors.extend(validate_standard_governance(gov, str(cap)))

    non_auth = record.get("non_authority")
    if not isinstance(non_auth, dict):
        errors.append("non_authority must be an object")
    else:
        for key in ("grants_execution", "grants_promotion", "model_output_is_approval", "artifact_is_authority"):
            if non_auth.get(key) is not False:
                errors.append(f"non_authority.{key} must be false")

    digest = record.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("digest must be a 64-char hex sha256")
    else:
        expected = digest_jsonable(record)
        if digest != expected:
            errors.append("digest mismatch")
    return errors
