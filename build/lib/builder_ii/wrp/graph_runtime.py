"""Pure-Python subtask graph runtime (LangGraph reference only — no dependency).

Executes TrajectoryGraph / subtask_graph plans for orchestration patterns:
sequential, fan_out_fan_in, hierarchical, handoff, cyclic (max_iterations hard cap).

Node types (P2.6 + S2 v2):
- noop   — no side effects
- record — records payload into the run trajectory
- model_gateway / tool_gateway — only when a ``gateway_handler`` is supplied
  (live_lane S2 v2); pure runtime without handler still fail-closes these types.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Mapping, Sequence

from builder_ii.config_schema import attach_digest
from builder_ii.wrp.spaces import TrajectoryGraph

# Pure runtime always knows noop/record. Gateway types need a live-lane handler.
SUPPORTED_NODE_TYPES: frozenset[str] = frozenset({"noop", "record"})
GATEWAY_NODE_TYPES: frozenset[str] = frozenset({"model_gateway", "tool_gateway"})
ALL_NODE_TYPES: frozenset[str] = SUPPORTED_NODE_TYPES | GATEWAY_NODE_TYPES

# gateway_handler(node_id, spec, handoff_state) -> (event, new_state, trajectory_delta, error|None)
GatewayHandler = Callable[
    [str, dict[str, Any], dict[str, Any]],
    tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None],
]

# Canonical pattern names accepted by the runtime.
SUPPORTED_PATTERNS: frozenset[str] = frozenset(
    {
        "sequential",
        "fan_out_fan_in",
        "hierarchical",
        "handoff",
        "cyclic",
    }
)

# Map patterns.py / spaces.py names onto canonical runtime names.
_PATTERN_ALIASES: dict[str, str] = {
    "parallel_fanout": "fan_out_fan_in",
    "fanout": "fan_out_fan_in",
    "fan_out": "fan_out_fan_in",
    "fan-out-fan-in": "fan_out_fan_in",
}


def normalize_pattern(pattern: str) -> str:
    """Return canonical pattern name (may still be unsupported)."""
    raw = str(pattern or "").strip()
    if not raw:
        return "sequential"
    return _PATTERN_ALIASES.get(raw, raw)


def _as_graph(graph: TrajectoryGraph | Mapping[str, Any]) -> TrajectoryGraph:
    if isinstance(graph, TrajectoryGraph):
        return graph
    if isinstance(graph, Mapping):
        return TrajectoryGraph.from_mapping(graph)
    raise TypeError("graph must be a TrajectoryGraph or mapping")


def _spec_for(node_id: str, node_specs: Mapping[str, Mapping[str, Any]] | None) -> dict[str, Any]:
    if not node_specs:
        return {"node_type": "noop", "cost_estimate": 0.0}
    raw = node_specs.get(node_id)
    if not isinstance(raw, Mapping):
        return {"node_type": "noop", "cost_estimate": 0.0}
    return {
        "node_type": str(raw.get("node_type", "noop")),
        "cost_estimate": float(raw.get("cost_estimate", 0.0)),
        "payload": raw.get("payload"),
        "required_keys": list(raw.get("required_keys") or ()),
    }


def _missing_keys(state: Mapping[str, Any], required: Sequence[str]) -> list[str]:
    missing: list[str] = []
    for key in required:
        if key not in state or state[key] in (None, ""):
            missing.append(str(key))
    return missing


def _event(
    *,
    node_id: str,
    status: str,
    cost_estimate: float,
    error: str | None = None,
    iteration: int | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "node_id": node_id,
        "status": status,
        "cost_estimate": float(cost_estimate),
        "error": error,
    }
    if iteration is not None:
        event["iteration"] = iteration
    return event


def _failed_result(
    *,
    pattern: str,
    error: str,
    execution_order: list[str] | None = None,
    events: list[dict[str, Any]] | None = None,
    trajectory: dict[str, Any] | None = None,
    total_cost_estimate: float = 0.0,
    iterations_completed: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "runtime": "builder_ii.wrp.graph_runtime",
        "status": "failed",
        "pattern": pattern,
        "execution_order": list(execution_order or []),
        "events": list(events or []),
        "trajectory": dict(trajectory or {}),
        "total_cost_estimate": float(total_cost_estimate),
        "error": error,
        "iterations_completed": iterations_completed,
        "grants_authority": False,
        "executes_model": False,
        "executes_tools": False,
    }
    if extra:
        body = {**body, **dict(extra)}
    return attach_digest(body)


def _success_result(
    *,
    pattern: str,
    execution_order: list[str],
    events: list[dict[str, Any]],
    trajectory: dict[str, Any],
    total_cost_estimate: float,
    iterations_completed: int | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "runtime": "builder_ii.wrp.graph_runtime",
        "status": "success",
        "pattern": pattern,
        "execution_order": list(execution_order),
        "events": list(events),
        "trajectory": dict(trajectory),
        "total_cost_estimate": float(total_cost_estimate),
        "error": None,
        "iterations_completed": iterations_completed,
        "grants_authority": False,
        "executes_model": False,
        "executes_tools": False,
    }
    if extra:
        body = {**body, **dict(extra)}
    return attach_digest(body)


def _schedule_nodes(graph: TrajectoryGraph, pattern: str) -> list[str] | str:
    """Return ordered node ids for one pass, or an error string on failure."""
    if pattern == "cyclic":
        # Declaration order is the controlled revisitation skeleton (spaces.topological_order).
        return list(graph.nodes)
    try:
        return graph.topological_order()
    except ValueError as exc:
        return str(exc)


def _run_node(
    *,
    node_id: str,
    spec: dict[str, Any],
    handoff_state: dict[str, Any],
    trajectory: dict[str, Any],
    iteration: int | None = None,
    gateway_handler: GatewayHandler | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]:
    """Execute one node. Returns (event, new_state, new_trajectory, error_or_none)."""
    node_type = spec["node_type"]
    cost = float(spec["cost_estimate"])

    # Per-node required_keys gate (handoff continuity at node boundary).
    required = list(spec.get("required_keys") or ())
    if required:
        missing = _missing_keys(handoff_state, required)
        if missing:
            msg = f"missing handoff keys before node {node_id}: {', '.join(missing)}"
            return (
                _event(node_id=node_id, status="failed", cost_estimate=cost, error=msg, iteration=iteration),
                handoff_state,
                trajectory,
                msg,
            )

    if node_type in GATEWAY_NODE_TYPES:
        if gateway_handler is None:
            msg = (
                f"gateway node type {node_type!r} requires a gateway_handler "
                "(S2 v2 live lane only; pure runtime refuses)"
            )
            return (
                _event(node_id=node_id, status="failed", cost_estimate=cost, error=msg, iteration=iteration),
                handoff_state,
                trajectory,
                msg,
            )
        event, new_state, traj_delta, err = gateway_handler(node_id, spec, handoff_state)
        if iteration is not None and isinstance(event, dict) and "iteration" not in event:
            event = {**event, "iteration": iteration}
        new_trajectory = {**trajectory, **dict(traj_delta or {})}
        return event, new_state, new_trajectory, err

    if node_type not in SUPPORTED_NODE_TYPES:
        msg = f"unknown node type: {node_type!r} (supported: {sorted(ALL_NODE_TYPES)})"
        return (
            _event(node_id=node_id, status="failed", cost_estimate=cost, error=msg, iteration=iteration),
            handoff_state,
            trajectory,
            msg,
        )

    new_state = dict(handoff_state)
    new_trajectory = dict(trajectory)

    if node_type == "record":
        payload = spec.get("payload")
        recorded: Any
        if isinstance(payload, Mapping):
            recorded = dict(payload)
            # Merge mapping payloads into handoff state for downstream required_keys.
            new_state = {**new_state, **recorded}
        else:
            recorded = payload
        new_trajectory = {**new_trajectory, node_id: recorded}

    # noop: no trajectory write, no state change
    return (
        _event(node_id=node_id, status="ok", cost_estimate=cost, error=None, iteration=iteration),
        new_state,
        new_trajectory,
        None,
    )


def execute_graph(
    graph: TrajectoryGraph | Mapping[str, Any],
    *,
    node_specs: Mapping[str, Mapping[str, Any]] | None = None,
    handoff_state: Mapping[str, Any] | None = None,
    required_keys: Sequence[str] | None = None,
    max_iterations: int | None = None,
    require_keys_before_first_node: bool = True,
    gateway_handler: GatewayHandler | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a TrajectoryGraph under the pure-Python runtime.

    Parameters
    ----------
    graph:
        TrajectoryGraph instance or Gamma mapping (nodes/edges/pattern).
    node_specs:
        Optional per-node config: node_type, cost_estimate, payload, required_keys.
        Missing specs default to noop with cost 0.
    handoff_state:
        Mutable logical state carried across nodes (immutably updated).
    required_keys:
        Global required keys for handoff continuity. Checked against handoff_state
        when set (non-empty).
    max_iterations:
        Hard cap for cyclic pattern. Required when pattern is cyclic.
    require_keys_before_first_node:
        When True (default), global required_keys are checked before any node runs.
        When False, keys may be filled by an early ``record`` node before a later check.
    gateway_handler:
        Optional handler for model_gateway/tool_gateway nodes (S2 v2 live lane).
        Pure runtime without handler fail-closes gateway node types.
    extra:
        Optional fields merged into the result dict before digest attach.

    Returns
    -------
    Digest-friendly result dict with status success|failed, execution_order, events[].
    """
    try:
        g = _as_graph(graph)
    except (TypeError, ValueError, KeyError) as exc:
        return _failed_result(pattern="unknown", error=f"invalid graph: {exc}", extra=extra)

    raw_pattern = str(g.pattern or "sequential")
    pattern = normalize_pattern(raw_pattern)

    if pattern not in SUPPORTED_PATTERNS:
        return _failed_result(
            pattern=raw_pattern,
            error=f"unknown pattern: {raw_pattern!r} (supported: {sorted(SUPPORTED_PATTERNS)})",
            extra=extra,
        )

    if pattern == "cyclic":
        if max_iterations is None or int(max_iterations) < 1:
            return _failed_result(
                pattern=pattern,
                error="cyclic pattern requires max_iterations >= 1 (hard cap; fail closed)",
                extra=extra,
            )
        iterations = int(max_iterations)
    else:
        iterations = 1

    schedule = _schedule_nodes(g, pattern)
    if isinstance(schedule, str):
        # topological_order failure (cycle on non-cyclic pattern, unknown edge nodes, …)
        schedule_err = schedule
        if "cycle" in schedule_err.lower() and pattern != "cyclic":
            schedule_err = (
                f"trajectory graph contains a cycle (use pattern=cyclic with max_iterations): {schedule_err}"
            )
        return _failed_result(pattern=pattern, error=schedule_err, extra=extra)

    ordered_nodes: list[str] = schedule
    state: dict[str, Any] = dict(handoff_state or {})
    global_keys = [str(k) for k in (required_keys or ())]
    trajectory: dict[str, Any] = {}
    events: list[dict[str, Any]] = []
    execution_order: list[str] = []
    total_cost = 0.0

    if global_keys and require_keys_before_first_node:
        missing = _missing_keys(state, global_keys)
        if missing:
            return _failed_result(
                pattern=pattern,
                error=f"missing handoff keys: {', '.join(missing)}",
                extra=extra,
            )

    for iteration_idx in range(iterations):
        iter_label = iteration_idx + 1 if pattern == "cyclic" else None
        for node_id in ordered_nodes:
            spec = _spec_for(node_id, node_specs)

            # Global required_keys re-check before each node when not forced only at start
            # (and always after the first node so record can fill gaps when flag is False).
            if global_keys and (require_keys_before_first_node or execution_order):
                missing = _missing_keys(state, global_keys)
                if missing:
                    msg = f"missing handoff keys: {', '.join(missing)}"
                    fail_event = _event(
                        node_id=node_id,
                        status="failed",
                        cost_estimate=float(spec["cost_estimate"]),
                        error=msg,
                        iteration=iter_label,
                    )
                    return _failed_result(
                        pattern=pattern,
                        error=msg,
                        execution_order=execution_order,
                        events=[*events, fail_event],
                        trajectory=trajectory,
                        total_cost_estimate=total_cost,
                        iterations_completed=iteration_idx if pattern == "cyclic" else None,
                        extra=extra,
                    )

            event, state, trajectory, node_err = _run_node(
                node_id=node_id,
                spec=spec,
                handoff_state=state,
                trajectory=trajectory,
                iteration=iter_label,
                gateway_handler=gateway_handler,
            )
            events = [*events, event]
            total_cost += float(event["cost_estimate"])
            if node_err is not None:
                return _failed_result(
                    pattern=pattern,
                    error=node_err,
                    execution_order=execution_order,
                    events=events,
                    trajectory=trajectory,
                    total_cost_estimate=total_cost,
                    iterations_completed=iteration_idx if pattern == "cyclic" else None,
                    extra=extra,
                )
            execution_order = [*execution_order, node_id]

        # After first pass with require_keys_before_first_node=False, enforce keys once filled.
        if global_keys and not require_keys_before_first_node and pattern != "cyclic":
            missing = _missing_keys(state, global_keys)
            if missing:
                return _failed_result(
                    pattern=pattern,
                    error=f"missing handoff keys: {', '.join(missing)}",
                    execution_order=execution_order,
                    events=events,
                    trajectory=trajectory,
                    total_cost_estimate=total_cost,
                    extra=extra,
                )

    result_extra: dict[str, Any] = dict(extra or {})
    if raw_pattern != pattern:
        result_extra["source_pattern"] = raw_pattern

    return _success_result(
        pattern=pattern,
        execution_order=execution_order,
        events=events,
        trajectory=trajectory,
        total_cost_estimate=total_cost,
        iterations_completed=iterations if pattern == "cyclic" else None,
        extra=result_extra or None,
    )


def execute_from_plan(
    plan: Mapping[str, Any],
    *,
    node_specs: Mapping[str, Mapping[str, Any]] | None = None,
    handoff_state: Mapping[str, Any] | None = None,
    required_keys: Sequence[str] | None = None,
    max_iterations: int | None = None,
    require_keys_before_first_node: bool = True,
    gateway_handler: GatewayHandler | None = None,
) -> dict[str, Any]:
    """Execute the graph embedded in a ``builder_ii.wrp.subtask_graph`` plan artifact."""
    if not isinstance(plan, Mapping):
        return _failed_result(pattern="unknown", error="plan must be a mapping")
    graph_data = plan.get("graph")
    if not isinstance(graph_data, Mapping):
        return _failed_result(pattern="unknown", error="plan.graph must be an object")
    task = plan.get("task")
    extra: dict[str, Any] = {}
    if task is not None:
        extra["task"] = task
        extra["plan_task"] = task
    planned_order = plan.get("execution_order")
    if isinstance(planned_order, list):
        extra["planned_execution_order"] = list(planned_order)
    return execute_graph(
        graph_data,
        node_specs=node_specs,
        handoff_state=handoff_state,
        required_keys=required_keys,
        max_iterations=max_iterations,
        require_keys_before_first_node=require_keys_before_first_node,
        gateway_handler=gateway_handler,
        extra=extra or None,
    )
