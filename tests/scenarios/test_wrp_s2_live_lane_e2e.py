"""S2 scenario: classify → allocate → live plan → HITL approval → run_approved receipt."""

from __future__ import annotations

import pytest

from builder_ii.wrp.allocation_optimizer import allocate_fleet
from builder_ii.wrp.artifacts import (
    LIVE_RUN_APPROVAL_KIND,
    LIVE_RUN_PLAN_KIND,
    LIVE_RUN_RECEIPT_KIND,
)
from builder_ii.wrp.experience_store import create_experience_store
from builder_ii.wrp.live_lane import (
    LiveLaneError,
    build_live_run_approval,
    build_live_run_plan,
    run_approved,
    validate_live_run_approval,
    validate_live_run_plan,
    validate_live_run_receipt,
)
from builder_ii.wrp.workload_classifier import classify_workload


def test_s2_live_lane_end_to_end_with_bindings() -> None:
    task = "implement MSDA-gated live lane validators and scenario tests"
    clf = classify_workload(text=task)
    assert clf["grants_authority"] is False

    fleet = allocate_fleet(task_tier=clf["classification"]["tier"], token_budget=40.0)
    assert fleet["grants_authority"] is False

    plan = build_live_run_plan(
        task=task,
        nodes=["classify", "allocate", "msda_probe", "handoff"],
        fleet_binding=fleet.get("fleet_binding") or {},
        wrp_binding={
            "tier": clf["classification"]["tier"],
            "recommended_model_alias": clf["recommended_model_alias"],
            "classification_digest": clf["digest"],
            "allocation_digest": fleet["digest"],
        },
        msda_tools=[{"tool": "repo_map", "data_domain": "local_workspace", "risk": "local_offline"}],
    )
    assert plan["kind"] == LIVE_RUN_PLAN_KIND
    assert plan["msda_preflight_forced"] is True
    assert plan["model_gateway_invoked"] is False
    assert plan["tool_gateway_invoked"] is False
    assert plan["executes_shell"] is False
    assert validate_live_run_plan(plan) == []

    approval = build_live_run_approval(plan=plan, approved_by="HITL-operator", notes="scenario s2")
    assert approval["kind"] == LIVE_RUN_APPROVAL_KIND
    assert approval["authorizes_live_lane_only"] is True
    assert approval["grants_unbounded_execution"] is False
    assert validate_live_run_approval(approval) == []

    store = create_experience_store(store_id="s2-scenario")
    receipt = run_approved(plan=plan, approval=approval, experience_store=store)

    assert receipt["kind"] == LIVE_RUN_RECEIPT_KIND
    assert receipt["status"] == "success"
    assert receipt["plan_digest"] == plan["digest"]
    assert receipt["approved_by"] == "HITL-operator"
    assert receipt["model_gateway_invoked"] is False
    assert receipt["tool_gateway_invoked"] is False
    assert receipt["grants_authority"] is False
    assert receipt["executes_shell"] is False
    assert receipt["graph_run"]["status"] == "success"
    assert len(receipt["graph_run"]["execution_order"]) >= 1
    assert receipt.get("experience_store_digest")
    assert validate_live_run_receipt(receipt) == []


def test_s2_scenario_fail_closed_on_false_approval() -> None:
    plan = build_live_run_plan(task="scenario deny path")
    approval = build_live_run_approval(plan=plan, approved_by="HITL-operator", approved=False)
    with pytest.raises(LiveLaneError, match="approved"):
        run_approved(plan=plan, approval=approval)


def test_s2_scenario_fail_closed_on_msda_shell() -> None:
    plan = build_live_run_plan(
        task="scenario msda shell deny",
        msda_tools=[{"tool": "shell", "data_domain": "local_workspace", "risk": "local_offline"}],
    )
    approval = build_live_run_approval(plan=plan, approved_by="HITL-operator")
    with pytest.raises(LiveLaneError, match="MSDA|denied|shell"):
        run_approved(plan=plan, approval=approval)
