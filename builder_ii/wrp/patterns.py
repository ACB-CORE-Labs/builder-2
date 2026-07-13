"""Formal orchestration patterns over TrajectoryGraph."""

from __future__ import annotations

from builder_ii.wrp.spaces import TrajectoryEdge, TrajectoryGraph


def sequential_chain(node_ids: list[str]) -> TrajectoryGraph:
    edges = [
        TrajectoryEdge(source=node_ids[i], target=node_ids[i + 1], expected_cost=1.0)
        for i in range(len(node_ids) - 1)
    ]
    return TrajectoryGraph(nodes=list(node_ids), edges=edges, pattern="sequential")


def parallel_fanout(root: str, workers: list[str], sink: str) -> TrajectoryGraph:
    nodes = [root, *workers, sink]
    edges = [TrajectoryEdge(source=root, target=w, expected_cost=1.0) for w in workers]
    edges.extend(TrajectoryEdge(source=w, target=sink, expected_cost=1.0) for w in workers)
    return TrajectoryGraph(nodes=nodes, edges=edges, pattern="parallel_fanout")


def hierarchical(manager: str, workers: list[str]) -> TrajectoryGraph:
    nodes = [manager, *workers]
    edges = [TrajectoryEdge(source=manager, target=w, expected_cost=1.0) for w in workers]
    return TrajectoryGraph(nodes=nodes, edges=edges, pattern="hierarchical")


def handoff_route(sequence: list[str]) -> TrajectoryGraph:
    g = sequential_chain(sequence)
    g.pattern = "handoff"
    return g


def cyclic_revisitation(nodes: list[str]) -> TrajectoryGraph:
    """Controlled revisitation loop skeleton (Evaluator → AgentFactory correction)."""
    if len(nodes) < 2:
        raise ValueError("cyclic pattern needs at least 2 nodes")
    edges = [
        TrajectoryEdge(source=nodes[i], target=nodes[i + 1], expected_cost=1.0)
        for i in range(len(nodes) - 1)
    ]
    edges.append(TrajectoryEdge(source=nodes[-1], target=nodes[0], expected_cost=1.0, expected_reward=-0.1))
    return TrajectoryGraph(nodes=list(nodes), edges=edges, pattern="cyclic")
