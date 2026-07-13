"""S2 HITL live lane — plan / approval / run_approved fail-closed tests."""

from __future__ import annotations

import pytest

from builder_ii.wrp.allocation_optimizer import allocate_fleet
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


def _plan_with_bindings(**kwargs):
    clf = classify_workload(text=kwargs.get("task", "implement a CLI command"))
    fleet = allocate_fleet(task_tier="primary", token_budget=80.0)
    return build_live_run_plan(
        task=kwargs.get("task", "implement a CLI command"),
        fleet_binding=fleet["fleet_binding"],
        wrp_binding={
            "tier": clf["classification"]["tier"],
            "recommended_model_alias": clf["recommended_model_alias"],
            "classification_digest": clf["digest"],
        },
        **{k: v for k, v in kwargs.items() if k != "task"},
    )


def test_happy_path_plan_approve_run() -> None:
    plan = _plan_with_bindings()
    assert validate_live_run_plan(plan) == []
    approval = build_live_run_approval(plan=plan, approved_by="HUMAN")
    assert validate_live_run_approval(approval) == []
    store = create_experience_store(store_id="s2-test")
    receipt = run_approved(plan=plan, approval=approval, experience_store=store)
    assert receipt["status"] == "success"
    assert receipt["model_gateway_invoked"] is False
    assert receipt["tool_gateway_invoked"] is False
    assert receipt["grants_authority"] is False
    assert receipt["executes_shell"] is False
    assert validate_live_run_receipt(receipt) == []
    assert receipt.get("experience_store_digest")


def test_rejects_unapproved() -> None:
    plan = _plan_with_bindings()
    approval = build_live_run_approval(plan=plan, approved_by="HUMAN", approved=False)
    with pytest.raises(LiveLaneError, match="approved"):
        run_approved(plan=plan, approval=approval)


def test_rejects_digest_mismatch() -> None:
    plan = _plan_with_bindings()
    other = _plan_with_bindings(task="different task text for digest")
    approval = build_live_run_approval(plan=other, approved_by="HUMAN")
    with pytest.raises(LiveLaneError, match="plan_digest"):
        run_approved(plan=plan, approval=approval)


def test_msda_deny_blocks_run() -> None:
    plan = _plan_with_bindings(
        msda_tools=[{"tool": "shell", "data_domain": "local_workspace", "risk": "local_offline"}]
    )
    approval = build_live_run_approval(plan=plan, approved_by="HUMAN")
    with pytest.raises(LiveLaneError, match="MSDA|denied|shell"):
        run_approved(plan=plan, approval=approval)


def test_unknown_node_type_refused() -> None:
    plan = _plan_with_bindings(
        nodes=["a", "b"],
        node_specs={
            "a": {"node_type": "noop", "cost_estimate": 0.0},
            "b": {"node_type": "shell", "cost_estimate": 1.0},
        },
    )
    approval = build_live_run_approval(plan=plan, approved_by="HUMAN")
    with pytest.raises(LiveLaneError, match="not allowed|shell"):
        run_approved(plan=plan, approval=approval)
