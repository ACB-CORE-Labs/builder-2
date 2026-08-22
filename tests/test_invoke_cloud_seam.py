"""W2.2 invoke_cloud gateway mode."""

from __future__ import annotations

from pathlib import Path

from builder_ii.wrp.gateway_nodes import GATEWAY_MODES, run_gateway_node


def test_invoke_cloud_in_modes() -> None:
    assert "invoke_cloud" in GATEWAY_MODES


def test_invoke_cloud_requires_approval_path(tmp_path: Path, cloud_route_sources_factory) -> None:
    route_sources = cloud_route_sources_factory("c1")
    event, _s, _t, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "cost_estimate": 0.0,
            "payload": {
                "model_id": "gpt-4o-stub",
                "prompt": "cloud hello",
                "route_sources": route_sources,
                "hard_spend_cap_usd": 1.0,
                "enable_stub_if_disabled": True,
                "artifact_dir": str(tmp_path / "a"),
            },
        },
        handoff_state={},
        plan_digest="c" * 64,
        approved_by="operator",
        gateway_mode="invoke_cloud",
    )
    assert err is not None
    assert "approval_path" in err


def test_invoke_cloud_stub_with_approval(tmp_path: Path, cloud_route_sources_factory) -> None:
    approval = tmp_path / "approval.json"
    approval.write_text('{"valid": true, "kind": "builder_ii.model_call_approval", "expires_at": 20000000000, "model_id": "gpt-4o-stub", "prompt_digest": "bac22c39560b7f4c50876c7733a9182d9d8704675c52082b187e7e9b03aee6a0"}\n', encoding="utf-8")
    route_sources = cloud_route_sources_factory("c2")
    event, state, traj, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "cost_estimate": 0.0,
            "payload": {
                "model_id": "gpt-4o-stub",
                "prompt": "cloud hello under gates",
                "route_sources": route_sources,
                "hard_spend_cap_usd": 2.0,
                "approval_path": str(approval),
                "enable_stub_if_disabled": True,
                "artifact_dir": str(tmp_path / "artifacts"),
                "session_id": "c2",
                "max_tokens": 64,
            },
        },
        handoff_state={},
        plan_digest="d" * 64,
        approved_by="operator",
        gateway_mode="invoke_cloud",
    )
    assert err is None, err
    assert event["status"] == "ok"
    body = traj["m1"]
    assert body["mode"] == "invoke_cloud"
    assert body["cloud_provider_invoke"] is True
    assert body["executes_model_provider"] is True
    assert body["ledger_bound"] is True
    assert "cloud_egress" in body
    assert isinstance(state.get("last_debited_budget"), dict)
