"""W1.2 keystone — WRP model_gateway invoke_local under HITL + budget + ledger."""

from __future__ import annotations

from pathlib import Path

from builder_ii.model_budget import create_model_budget
from builder_ii.model_client_registry import create_model_client_registry
from builder_ii.wrp.gateway_nodes import run_gateway_node
from builder_ii.wrp.live_lane import (
    build_live_run_approval,
    build_live_run_plan,
    run_approved,
    validate_live_run_receipt,
)


def test_default_record_mode_does_not_invoke() -> None:
    event, _state, traj, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "cost_estimate": 0.0,
            "payload": {"tool": "model_call", "model_id": "record-only-local", "prompt_snippet": "hi"},
        },
        handoff_state={},
        plan_digest="a" * 64,
        approved_by="human",
        gateway_mode="record",
    )
    assert err is None
    assert traj["m1"]["executes_model_provider"] is False
    assert traj["m1"]["mode"] == "record"


def test_invoke_local_stub_produces_real_receipt(tmp_path: Path) -> None:
    registry = create_model_client_registry()
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    budget = create_model_budget(session_id="seam-1", max_usd=5.0, max_total_tokens=50_000)
    event, _state, traj, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "cost_estimate": 0.0,
            "payload": {
                "tool": "model_call",
                "model_id": "gpt-4o-stub",
                "prompt": "Say hello from the seam",
                "budget": budget,
                "registry": registry,
                "artifact_dir": str(tmp_path / "artifacts"),
                "enable_stub_if_disabled": True,
                "session_id": "seam-1",
                "max_tokens": 64,
            },
        },
        handoff_state={},
        plan_digest="b" * 64,
        approved_by="operator",
        gateway_mode="invoke_local",
    )
    assert err is None, err
    assert event["status"] == "ok"
    result = traj["m1"]
    assert result["mode"] == "invoke_local"
    assert result["executes_model_provider"] is True
    assert result["cloud_provider_invoke"] is False
    assert result["receipt_digest"]
    assert result["envelope_digest"]
    assert result["cost_report"]["token_accounting"] == "measured"
    assert result["ledger_bound"] is True
    events_dir = Path(result["events_dir"])
    assert events_dir.is_dir()
    assert list(events_dir.glob("*.json")), "ledger events required"


def test_invoke_local_refuses_record_only_model_id() -> None:
    _event, _state, _traj, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "payload": {
                "model_id": "record-only-local",
                "prompt": "x",
                "auto_budget": True,
            },
        },
        handoff_state={},
        plan_digest="c" * 64,
        approved_by="human",
        gateway_mode="invoke_local",
    )
    assert err is not None
    assert "real registry model_id" in err


def test_invoke_local_requires_budget() -> None:
    registry = create_model_client_registry()
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    _event, _state, _traj, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "payload": {
                "model_id": "gpt-4o-stub",
                "prompt": "hi",
                "registry": registry,
                "enable_stub_if_disabled": True,
            },
        },
        handoff_state={},
        plan_digest="d" * 64,
        approved_by="human",
        gateway_mode="invoke_local",
    )
    assert err is not None
    assert "budget" in err.lower()


def test_live_lane_invoke_local_plan_to_receipt(tmp_path: Path) -> None:
    registry = create_model_client_registry()
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    budget = create_model_budget(session_id="live-seam", max_usd=5.0)
    plan = build_live_run_plan(
        task="seam live lane invoke_local",
        s2_version="v2",
        gateway_mode="invoke_local",
        nodes=["model_gateway"],
        node_specs={
            "model_gateway": {
                "node_type": "model_gateway",
                "cost_estimate": 0.0,
                "payload": {
                    "tool": "model_call",
                    "data_domain": "local_workspace",
                    "risk": "local_network",
                    "model_id": "gpt-4o-stub",
                    "prompt": "Live lane seam prompt",
                    "budget": budget,
                    "registry": registry,
                    "artifact_dir": str(tmp_path / "live_artifacts"),
                    "enable_stub_if_disabled": True,
                    "session_id": "live-seam",
                    "max_tokens": 32,
                },
            }
        },
    )
    assert plan["gateway_mode"] == "invoke_local"
    assert plan["cloud_provider_invoke"] is False
    assert plan.get("model_provider_invoke") is True
    approval = build_live_run_approval(plan=plan, approved_by="operator")
    receipt = run_approved(plan=plan, approval=approval)
    assert validate_live_run_receipt(receipt) == []
    assert receipt["status"] == "success"
    assert receipt["gateway_mode"] == "invoke_local"
    assert receipt["model_provider_invoke"] is True
    traj = receipt["graph_run"]["trajectory"]
    assert traj["model_gateway"]["executes_model_provider"] is True
    assert traj["model_gateway"]["receipt_digest"]
