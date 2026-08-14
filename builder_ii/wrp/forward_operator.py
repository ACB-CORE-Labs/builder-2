"""Forward routing operator R: W → (A, T, Γ)."""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.allocation_optimizer import allocate_fleet
from builder_ii.wrp.artifacts import FORWARD_ROUTE_KIND, base_envelope, validate_wrp_artifact_envelope
from builder_ii.wrp.collaboration_planner import plan_collaboration
from builder_ii.wrp.governance_router import create_default_msda_policy
from builder_ii.wrp.patterns import sequential_chain
from builder_ii.wrp.spaces import WorkloadPoint
from builder_ii.wrp.subtask_graph import create_subtask_graph
from builder_ii.wrp.workload_classifier import classify_workload


def forward_route(
    *,
    text: str,
    task: str | None = None,
    token_budget: float = 20.0,
    max_risk: str = "local_network",
) -> dict[str, Any]:
    """Compose classification → collaboration → allocation → subtask graph recommendation."""
    classification = classify_workload(text=text)
    tier = classification["classification"]["tier"]
    safety = float(classification["workload"]["coordinates"]["safety"])
    collab = plan_collaboration(
        task=task or text,
        priority=2 if tier == "primary_constrained" or safety >= 0.85 else 1,
        security_sensitive=safety >= 0.85,
    )
    non_trivial = tier in {"primary", "primary_constrained"}
    allocation = allocate_fleet(
        task_tier="fast" if tier == "fast" else "primary",
        token_budget=token_budget,
        max_risk=max_risk,
        non_trivial=non_trivial and tier == "primary_constrained",
    )
    # Graph: maker_structural → maker_unit → governor_architecture
    node_ids = [n["role"] for n in collab["nodes"]]
    if len(node_ids) < 2:
        node_ids = ["maker_structural", "governor_architecture"]
    graph_art = create_subtask_graph(sequential_chain(node_ids), task=task or text)
    policy = create_default_msda_policy()

    return base_envelope(
        kind=FORWARD_ROUTE_KIND,
        artifact_state="RECOMMENDATION_ONLY",
        capability_state="wrp_recommendation_only",
        extra={
            "operator": "R",
            "workload": classification["workload"],
            "classification_digest": classification["digest"],
            "collaboration_digest": collab["digest"],
            "allocation_digest": allocation["digest"],
            "subtask_graph_digest": graph_art["digest"],
            "msda_policy_digest": policy["digest"],
            "recommended_tier": tier,
            "recommended_alias": allocation["allocation"]["primary_alias"],
            "components": {
                "classification": classification,
                "collaboration": collab,
                "allocation": allocation,
                "subtask_graph": graph_art,
                "msda_policy": policy,
            },
            "deterministic_given_frozen_experience": True,
            "executes_model": False,
            "grants_authority": False,
        },
    )


def validate_forward_route(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=FORWARD_ROUTE_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("operator") != "R":
        errors.append("operator must be R")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    return errors


def workload_from_forward(record: dict[str, Any]) -> WorkloadPoint:
    return WorkloadPoint.from_mapping(record["workload"])
