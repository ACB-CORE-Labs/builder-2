"""Pure-Python WRP graph runtime — pattern executors and fail-closed gates."""

from __future__ import annotations

from builder_ii.core.config_schema import digest_jsonable
from builder_ii.wrp.graph_runtime import (
    SUPPORTED_NODE_TYPES,
    execute_from_plan,
    execute_graph,
)
from builder_ii.wrp.patterns import (
    cyclic_revisitation,
    handoff_route,
    hierarchical,
    parallel_fanout,
    sequential_chain,
)
from builder_ii.wrp.spaces import TrajectoryEdge, TrajectoryGraph
from builder_ii.wrp.subtask_graph import create_subtask_graph

# ---------------------------------------------------------------------------
# Pattern success paths
# ---------------------------------------------------------------------------


def test_sequential_noop_chain() -> None:
    graph = sequential_chain(["a", "b", "c"])
    result = execute_graph(graph)
    assert result["status"] == "success"
    assert result["pattern"] == "sequential"
    assert result["execution_order"] == ["a", "b", "c"]
    assert len(result["events"]) == 3
    for event, node_id in zip(result["events"], ["a", "b", "c"], strict=True):
        assert event["node_id"] == node_id
        assert event["status"] == "ok"
        assert "cost_estimate" in event
        assert event.get("error") in (None, "")
    assert result["grants_authority"] is False
    assert result["executes_model"] is False
    assert result["executes_tools"] is False


def test_fan_out_fan_in_execution_order() -> None:
    graph = parallel_fanout(root="root", workers=["w1", "w2"], sink="sink")
    result = execute_graph(graph)
    assert result["status"] == "success"
    # patterns.py uses parallel_fanout; runtime normalizes to fan_out_fan_in
    assert result["pattern"] == "fan_out_fan_in"
    assert result.get("source_pattern") == "parallel_fanout"
    order = result["execution_order"]
    assert order[0] == "root"
    assert order[-1] == "sink"
    assert set(order[1:-1]) == {"w1", "w2"}
    assert len(result["events"]) == 4


def test_hierarchical_manager_then_workers() -> None:
    graph = hierarchical(manager="mgr", workers=["u1", "u2", "u3"])
    result = execute_graph(graph)
    assert result["status"] == "success"
    assert result["pattern"] == "hierarchical"
    assert result["execution_order"][0] == "mgr"
    assert set(result["execution_order"][1:]) == {"u1", "u2", "u3"}


def test_handoff_route_with_required_keys_present() -> None:
    graph = handoff_route(["maker", "governor"])
    state = {
        "task": "ship",
        "target": "builder-ii",
        "authority": "none",
        "risks": "low",
        "evidence_status": "pending",
    }
    result = execute_graph(
        graph,
        handoff_state=state,
        required_keys=list(state.keys()),
    )
    assert result["status"] == "success"
    assert result["pattern"] == "handoff"
    assert result["execution_order"] == ["maker", "governor"]


def test_cyclic_respects_max_iterations_hard_cap() -> None:
    graph = cyclic_revisitation(["eval", "agent"])
    result = execute_graph(graph, max_iterations=3)
    assert result["status"] == "success"
    assert result["pattern"] == "cyclic"
    # Two nodes × three iterations
    assert result["execution_order"] == ["eval", "agent"] * 3
    assert len(result["events"]) == 6
    assert result["iterations_completed"] == 3


# ---------------------------------------------------------------------------
# Node types: noop + record
# ---------------------------------------------------------------------------


def test_record_node_writes_payload_into_trajectory() -> None:
    graph = sequential_chain(["prep", "work"])
    specs = {
        "prep": {"node_type": "noop", "cost_estimate": 0.1},
        "work": {
            "node_type": "record",
            "cost_estimate": 1.5,
            "payload": {"artifact": "patch.diff", "lines": 12},
        },
    }
    result = execute_graph(graph, node_specs=specs)
    assert result["status"] == "success"
    assert result["trajectory"]["work"] == {"artifact": "patch.diff", "lines": 12}
    assert "prep" not in result["trajectory"]
    work_event = result["events"][1]
    assert work_event["cost_estimate"] == 1.5
    assert abs(result["total_cost_estimate"] - 1.6) < 1e-9


def test_unknown_node_type_fails_closed() -> None:
    graph = sequential_chain(["a"])
    result = execute_graph(
        graph,
        node_specs={"a": {"node_type": "llm_call"}},
    )
    assert result["status"] == "failed"
    assert result["execution_order"] == [] or result["events"][0]["status"] == "failed"
    assert any(
        "unknown node type" in (e.get("error") or "").lower()
        or "unknown node type" in (result.get("error") or "").lower()
        for e in (result.get("events") or [{}])
    )
    assert "llm_call" in (result.get("error") or "") or any(
        "llm_call" in (e.get("error") or "") for e in result.get("events", [])
    )


def test_supported_node_types_are_noop_and_record_only() -> None:
    assert SUPPORTED_NODE_TYPES == frozenset({"noop", "record"})


# ---------------------------------------------------------------------------
# Fail-closed gates
# ---------------------------------------------------------------------------


def test_cyclic_without_max_iterations_fails_closed() -> None:
    graph = cyclic_revisitation(["a", "b"])
    result = execute_graph(graph)
    assert result["status"] == "failed"
    assert "max_iterations" in (result.get("error") or "").lower()
    assert result["execution_order"] == []
    assert result["events"] == []


def test_cyclic_with_zero_max_iterations_fails_closed() -> None:
    graph = cyclic_revisitation(["a", "b"])
    result = execute_graph(graph, max_iterations=0)
    assert result["status"] == "failed"
    assert "max_iterations" in (result.get("error") or "").lower()


def test_non_cyclic_graph_with_cycle_fails_closed() -> None:
    graph = TrajectoryGraph(
        nodes=["a", "b"],
        edges=[TrajectoryEdge("a", "b"), TrajectoryEdge("b", "a")],
        pattern="sequential",
    )
    result = execute_graph(graph)
    assert result["status"] == "failed"
    err = (result.get("error") or "").lower()
    assert "cycle" in err


def test_handoff_missing_required_keys_fails_closed() -> None:
    graph = handoff_route(["maker", "governor"])
    result = execute_graph(
        graph,
        handoff_state={"task": "only-task"},
        required_keys=["task", "target", "authority"],
    )
    assert result["status"] == "failed"
    err = (result.get("error") or "").lower()
    assert "handoff" in err or "missing" in err
    assert "target" in err or any("target" in (e.get("error") or "") for e in result.get("events", []))


def test_per_node_required_keys_checked_before_step() -> None:
    graph = sequential_chain(["a", "b"])
    specs = {
        "a": {"node_type": "record", "payload": {"task": "done"}},
        "b": {"node_type": "noop", "required_keys": ["task", "authority"]},
    }
    # authority never appears → fail at b
    result = execute_graph(graph, node_specs=specs, handoff_state={})
    assert result["status"] == "failed"
    assert result["execution_order"] == ["a"] or (
        result["execution_order"] == ["a", "b"] and result["events"][-1]["status"] == "failed"
    )
    assert "authority" in (result.get("error") or "") or any(
        "authority" in (e.get("error") or "") for e in result.get("events", [])
    )


def test_unknown_pattern_fails_closed() -> None:
    graph = TrajectoryGraph(nodes=["a"], edges=[], pattern="quantum_entangle")
    result = execute_graph(graph)
    assert result["status"] == "failed"
    assert "pattern" in (result.get("error") or "").lower()


# ---------------------------------------------------------------------------
# Integration with subtask_graph plan + digest-friendly result
# ---------------------------------------------------------------------------


def test_execute_from_subtask_graph_plan() -> None:
    plan = create_subtask_graph(sequential_chain(["x", "y"]), task="runtime demo")
    result = execute_from_plan(plan)
    assert result["status"] == "success"
    assert result["execution_order"] == ["x", "y"]
    assert result.get("plan_task") == "runtime demo" or result.get("task") == "runtime demo"


def test_result_is_digest_friendly() -> None:
    graph = sequential_chain(["n1"])
    result = execute_graph(graph)
    assert isinstance(result.get("digest"), str)
    assert len(result["digest"]) == 64
    # digest matches canonical payload
    assert result["digest"] == digest_jsonable(result)


def test_result_includes_events_with_required_fields() -> None:
    graph = sequential_chain(["only"])
    result = execute_graph(
        graph,
        node_specs={"only": {"node_type": "record", "payload": {"k": 1}, "cost_estimate": 2.0}},
    )
    event = result["events"][0]
    assert set(event.keys()) >= {"node_id", "status", "cost_estimate"}
    assert event["node_id"] == "only"
    assert event["status"] == "ok"
    assert event["cost_estimate"] == 2.0


def test_fan_out_alias_parallel_fanout_accepted() -> None:
    """patterns.py emits pattern='parallel_fanout'; runtime normalizes to fan_out_fan_in."""
    graph = parallel_fanout("r", ["w"], "s")
    assert graph.pattern == "parallel_fanout"
    result = execute_graph(graph)
    assert result["status"] == "success"
    assert result["pattern"] == "fan_out_fan_in"


def test_empty_graph_succeeds() -> None:
    graph = TrajectoryGraph(nodes=[], edges=[], pattern="sequential")
    result = execute_graph(graph)
    assert result["status"] == "success"
    assert result["execution_order"] == []
    assert result["events"] == []


def test_record_payload_can_satisfy_downstream_handoff_keys() -> None:
    graph = handoff_route(["src", "dst"])
    specs = {
        "src": {
            "node_type": "record",
            "payload": {"task": "t", "target": "x", "authority": "none"},
        },
        "dst": {"node_type": "noop"},
    }
    result = execute_graph(
        graph,
        node_specs=specs,
        handoff_state={},
        required_keys=["task", "target", "authority"],
        # keys checked after each step / before downstream — src fills them
        require_keys_before_first_node=False,
    )
    assert result["status"] == "success"
    assert result["trajectory"]["src"]["task"] == "t"
