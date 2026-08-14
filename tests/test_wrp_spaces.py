from __future__ import annotations

import pytest

from builder_ii.wrp.spaces import (
    AgentPoint,
    TrajectoryEdge,
    TrajectoryGraph,
    WorkloadPoint,
    workload_distance,
)


def test_workload_point_clamps() -> None:
    w = WorkloadPoint(domain=-1, difficulty=2, safety=0.5, context=0.1, interaction=0.2)
    assert w.domain == 0.0
    assert w.difficulty == 1.0


def test_workload_distance_zero_for_same() -> None:
    w = WorkloadPoint(0.3, 0.4, 0.5, 0.6, 0.7)
    assert workload_distance(w, w) == 0.0


def test_workload_distance_positive() -> None:
    a = WorkloadPoint(0.0, 0.0, 0.0, 0.0, 0.0)
    b = WorkloadPoint(1.0, 0.0, 0.0, 0.0, 0.0)
    assert workload_distance(a, b) > 0


def test_agent_point_requires_role() -> None:
    with pytest.raises(ValueError):
        AgentPoint(role="", reasoning_coverage=0.5, tool_coverage=0.5, model_family="x")


def test_trajectory_topological_order() -> None:
    g = TrajectoryGraph(
        nodes=["a", "b", "c"],
        edges=[
            TrajectoryEdge("a", "b"),
            TrajectoryEdge("b", "c"),
        ],
    )
    assert g.topological_order() == ["a", "b", "c"]


def test_trajectory_cycle_raises_unless_cyclic() -> None:
    g = TrajectoryGraph(
        nodes=["a", "b"],
        edges=[TrajectoryEdge("a", "b"), TrajectoryEdge("b", "a")],
        pattern="sequential",
    )
    with pytest.raises(ValueError, match="cycle"):
        g.topological_order()
    g.pattern = "cyclic"
    assert g.topological_order() == ["a", "b"]
