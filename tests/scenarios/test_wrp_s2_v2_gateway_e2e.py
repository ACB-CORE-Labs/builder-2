"""S2 v2 e2e: plan-live v2 → approve → run-approved with gateway nodes."""

from __future__ import annotations

from builder_ii.wrp.allocation_optimizer import allocate_fleet
from builder_ii.wrp.experience_store import create_experience_store
from builder_ii.wrp.gateway_nodes import S2_V2_LANE_VERSION
from builder_ii.wrp.live_lane import build_live_run_approval, build_live_run_plan, run_approved
from builder_ii.wrp.workload_classifier import classify_workload


def test_s2_v2_full_lane_with_experience_ingest() -> None:
    task = "route a model and tool gateway step under HITL"
    clf = classify_workload(text=task)
    fleet = allocate_fleet(task_tier="primary", token_budget=100.0)
    plan = build_live_run_plan(
        task=task,
        s2_version="v2",
        gateway_mode="record",
        fleet_binding=fleet["fleet_binding"],
        wrp_binding={
            "tier": clf["classification"]["tier"],
            "recommended_model_alias": clf["recommended_model_alias"],
            "classification_digest": clf["digest"],
        },
    )
    approval = build_live_run_approval(plan=plan, approved_by="e2e-human")
    store = create_experience_store(store_id="s2v2-e2e")
    receipt = run_approved(plan=plan, approval=approval, experience_store=store)

    assert receipt["s2_version"] == S2_V2_LANE_VERSION
    assert receipt["model_gateway_invoked"] is True
    assert receipt["tool_gateway_invoked"] is True
    assert receipt["cloud_provider_invoke"] is False
    assert receipt["experience_store_digest"]
    order = receipt["graph_run"]["execution_order"]
    assert "model_gateway" in order
    assert "tool_gateway" in order
