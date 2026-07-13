"""S2 v2 gateway node unit tests — MSDA forced; no cloud/shell."""

from __future__ import annotations

from builder_ii.wrp.gateway_nodes import run_gateway_node
from builder_ii.wrp.graph_runtime import execute_graph
from builder_ii.wrp.patterns import sequential_chain


def test_model_gateway_record_mode_msda_and_digest() -> None:
    event, state, traj, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "cost_estimate": 0.1,
            "payload": {"tool": "model_call", "model_id": "local-record", "prompt_snippet": "hi"},
        },
        handoff_state={},
        plan_digest="a" * 64,
        approved_by="human",
        gateway_mode="record",
    )
    assert err is None
    assert event["status"] == "ok"
    assert event["gateway_digest"]
    assert traj["m1"]["performs_network"] is False
    assert traj["m1"]["executes_model_provider"] is False
    assert state["last_gateway_type"] == "model_gateway"


def test_tool_gateway_stub_echo() -> None:
    event, _state, traj, err = run_gateway_node(
        node_id="t1",
        node_type="tool_gateway",
        spec={
            "node_type": "tool_gateway",
            "cost_estimate": 0.0,
            "payload": {
                "tool_id": "builtin.echo",
                "tool": "builtin.echo",
                "arguments": {"text": "ping"},
            },
        },
        handoff_state={},
        plan_digest="b" * 64,
        approved_by="human",
        gateway_mode="stub_tool",
    )
    assert err is None
    assert event["status"] == "ok"
    assert traj["t1"]["stdout"] == "ping"
    assert traj["t1"]["executes_tool_stub"] is True
    assert traj["t1"]["executes_shell"] is False


def test_stub_tool_rejects_non_allowlist() -> None:
    _event, _state, _traj, err = run_gateway_node(
        node_id="t1",
        node_type="tool_gateway",
        spec={
            "node_type": "tool_gateway",
            "payload": {"tool_id": "shell", "tool": "shell"},
        },
        handoff_state={},
        plan_digest="c" * 64,
        approved_by="human",
        gateway_mode="stub_tool",
    )
    assert err is not None
    assert "allow" in err.lower() or "shell" in err.lower()


def test_model_gateway_rejects_stub_tool_mode() -> None:
    _event, _state, _traj, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={"node_type": "model_gateway", "payload": {"tool": "model_call"}},
        handoff_state={},
        plan_digest="d" * 64,
        approved_by="human",
        gateway_mode="stub_tool",
    )
    assert err is not None
    assert "stub_tool" in err


def test_graph_runtime_refuses_gateway_without_handler() -> None:
    graph = sequential_chain(["gw"])
    result = execute_graph(
        graph,
        node_specs={"gw": {"node_type": "model_gateway", "cost_estimate": 0.0, "payload": {}}},
    )
    assert result["status"] == "failed"
    assert "gateway_handler" in (result.get("error") or "")


def test_graph_runtime_with_handler_runs_gateway() -> None:
    graph = sequential_chain(["pre", "gw"])

    def handler(node_id, spec, state):
        return run_gateway_node(
            node_id=node_id,
            node_type=str(spec["node_type"]),
            spec=spec,
            handoff_state=state,
            plan_digest="e" * 64,
            approved_by="ops",
            gateway_mode="record",
        )

    result = execute_graph(
        graph,
        node_specs={
            "pre": {"node_type": "record", "cost_estimate": 0.0, "payload": {"x": 1}},
            "gw": {
                "node_type": "tool_gateway",
                "cost_estimate": 0.0,
                "payload": {"tool_id": "builtin.echo", "tool": "builtin.echo", "text": "z"},
            },
        },
        gateway_handler=handler,
    )
    assert result["status"] == "success"
    assert result["execution_order"] == ["pre", "gw"]
    assert "gw" in result["trajectory"]
