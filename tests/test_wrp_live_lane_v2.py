"""S2 v2 live lane — gateway nodes under HITL."""

from __future__ import annotations

import pytest

from builder_ii.wrp.allocation_optimizer import allocate_fleet
from builder_ii.wrp.gateway_nodes import S2_V2_LANE_VERSION
from builder_ii.wrp.live_lane import (
    LiveLaneError,
    build_live_run_approval,
    build_live_run_plan,
    run_approved,
    validate_live_run_plan,
    validate_live_run_receipt,
)
from builder_ii.wrp.workload_classifier import classify_workload


def _v2_plan(**kwargs):
    task = kwargs.pop("task", "implement a CLI command with gateway steps")
    clf = classify_workload(text=task)
    fleet = allocate_fleet(task_tier="primary", token_budget=80.0)
    return build_live_run_plan(
        task=task,
        s2_version="v2",
        fleet_binding=fleet["fleet_binding"],
        wrp_binding={
            "tier": clf["classification"]["tier"],
            "recommended_model_alias": clf["recommended_model_alias"],
            "classification_digest": clf["digest"],
        },
        **kwargs,
    )


def test_v2_happy_path_record_gateways() -> None:
    plan = _v2_plan()
    assert plan["s2_version"] == S2_V2_LANE_VERSION
    assert plan["model_gateway_invoked"] is True
    assert plan["tool_gateway_invoked"] is True
    assert plan["cloud_provider_invoke"] is False
    assert validate_live_run_plan(plan) == []

    approval = build_live_run_approval(plan=plan, approved_by="HUMAN")
    receipt = run_approved(plan=plan, approval=approval)
    assert receipt["s2_version"] == S2_V2_LANE_VERSION
    assert receipt["model_gateway_invoked"] is True
    assert receipt["tool_gateway_invoked"] is True
    assert receipt["gateway_mode"] == "record"
    assert receipt["cloud_provider_invoke"] is False
    assert receipt["executes_shell"] is False
    assert validate_live_run_receipt(receipt) == []
    traj = receipt["graph_run"]["trajectory"]
    assert any("gateway" in str(v.get("kind", "")) for v in traj.values() if isinstance(v, dict))


def test_v2_stub_tool_mode() -> None:
    plan = _v2_plan(gateway_mode="stub_tool")
    # stub_tool invalid for model_gateway — default plan includes model_gateway
    approval = build_live_run_approval(plan=plan, approved_by="HUMAN")
    with pytest.raises(LiveLaneError, match="stub_tool|failed"):
        run_approved(plan=plan, approval=approval)


def test_v2_stub_tool_tool_only() -> None:
    plan = _v2_plan(
        gateway_mode="stub_tool",
        nodes=["tool_gateway", "msda_probe", "handoff"],
        node_specs={
            "tool_gateway": {
                "node_type": "tool_gateway",
                "cost_estimate": 0.0,
                "payload": {
                    "tool_id": "builtin.echo",
                    "tool": "builtin.echo",
                    "text": "lane-v2",
                },
            },
            "msda_probe": {"node_type": "noop", "cost_estimate": 0.0, "payload": {}},
            "handoff": {"node_type": "record", "cost_estimate": 0.0, "payload": {"done": True}},
        },
    )
    assert plan["model_gateway_invoked"] is False
    assert plan["tool_gateway_invoked"] is True
    approval = build_live_run_approval(plan=plan, approved_by="HUMAN")
    receipt = run_approved(plan=plan, approval=approval)
    assert receipt["tool_gateway_invoked"] is True
    assert receipt["model_gateway_invoked"] is False
    tool_payload = receipt["graph_run"]["trajectory"]["tool_gateway"]
    assert tool_payload["stdout"] == "lane-v2"


def test_v1_still_refuses_gateway_flags() -> None:
    plan = build_live_run_plan(task="simple v1")
    assert plan["s2_version"].startswith("v1")
    # Tamper flags after build
    bad = dict(plan)
    bad["model_gateway_invoked"] = True
    bad.pop("digest", None)
    from builder_ii.wrp.artifacts import finalize_wrp_artifact

    bad = finalize_wrp_artifact(bad)
    approval = build_live_run_approval(plan=bad, approved_by="HUMAN")
    with pytest.raises(LiveLaneError, match="v1|gateway"):
        run_approved(plan=bad, approval=approval)


def test_v2_msda_deny_blocks() -> None:
    plan = _v2_plan(
        msda_tools=[{"tool": "shell", "data_domain": "local_workspace", "risk": "local_offline"}]
    )
    # plan builder may append gateway tools; force shell-only
    bad = dict(plan)
    bad["msda_tools"] = [{"tool": "shell", "data_domain": "local_workspace", "risk": "local_offline"}]
    bad.pop("digest", None)
    from builder_ii.wrp.artifacts import finalize_wrp_artifact

    bad = finalize_wrp_artifact(bad)
    approval = build_live_run_approval(plan=bad, approved_by="HUMAN")
    with pytest.raises(LiveLaneError, match="MSDA|denied|shell"):
        run_approved(plan=bad, approval=approval)
