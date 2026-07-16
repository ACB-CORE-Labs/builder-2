"""Intrinsic mathematical spaces for the WRP control plane.

Workload Space W, Agent Manifold A, Tool/Policy Space T, Trajectory Space Gamma.
Coordinates are explicit floats in [0, 1] unless documented otherwise. No embeddings
or ModernBERT required for v1 — mechanical sympathy for M1 16GB.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

# Sensitivity coefficients φ_i for d_W (fixed, deterministic; not learned at runtime).
DEFAULT_PHI: dict[str, float] = {
    "domain": 1.0,
    "difficulty": 1.2,
    "safety": 1.5,
    "context": 0.8,
    "interaction": 0.9,
}

WORKLOAD_AXES: tuple[str, ...] = ("domain", "difficulty", "safety", "context", "interaction")


def _clamp01(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return float(value)


@dataclass(frozen=True)
class WorkloadPoint:
    """Point w ∈ W: (domain, difficulty, safety, context, interaction)."""

    domain: float
    difficulty: float
    safety: float
    context: float
    interaction: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "domain", _clamp01(self.domain))
        object.__setattr__(self, "difficulty", _clamp01(self.difficulty))
        object.__setattr__(self, "safety", _clamp01(self.safety))
        object.__setattr__(self, "context", _clamp01(self.context))
        object.__setattr__(self, "interaction", _clamp01(self.interaction))

    def as_vector(self) -> dict[str, float]:
        return {
            "domain": self.domain,
            "difficulty": self.difficulty,
            "safety": self.safety,
            "context": self.context,
            "interaction": self.interaction,
        }

    def to_jsonable(self) -> dict[str, Any]:
        return {"space": "W", "coordinates": self.as_vector()}

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> WorkloadPoint:
        coords = data.get("coordinates", data)
        if not isinstance(coords, Mapping):
            raise ValueError("workload coordinates must be a mapping")
        return cls(
            domain=float(coords.get("domain", 0.0)),
            difficulty=float(coords.get("difficulty", 0.0)),
            safety=float(coords.get("safety", 0.0)),
            context=float(coords.get("context", 0.0)),
            interaction=float(coords.get("interaction", 0.0)),
        )


def workload_distance(
    w1: WorkloadPoint,
    w2: WorkloadPoint,
    phi: Mapping[str, float] | None = None,
) -> float:
    """Weighted Euclidean distance d_W(w1, w2)."""
    coeffs = dict(DEFAULT_PHI if phi is None else phi)
    total = 0.0
    for axis in WORKLOAD_AXES:
        delta = getattr(w1, axis) - getattr(w2, axis)
        weight = float(coeffs.get(axis, 1.0))
        total += weight * (delta * delta)
    return math.sqrt(total)


@dataclass(frozen=True)
class AgentPoint:
    """Point a ∈ A: (role, reasoning_coverage, tool_coverage, model_family)."""

    role: str
    reasoning_coverage: float
    tool_coverage: float
    model_family: str
    platform: str = "maker"  # maker | governor | either

    def __post_init__(self) -> None:
        object.__setattr__(self, "reasoning_coverage", _clamp01(self.reasoning_coverage))
        object.__setattr__(self, "tool_coverage", _clamp01(self.tool_coverage))
        if not self.role:
            raise ValueError("agent role must be non-empty")
        if not self.model_family:
            raise ValueError("model_family must be non-empty")

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "space": "A",
            "role": self.role,
            "reasoning_coverage": self.reasoning_coverage,
            "tool_coverage": self.tool_coverage,
            "model_family": self.model_family,
            "platform": self.platform,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> AgentPoint:
        return cls(
            role=str(data["role"]),
            reasoning_coverage=float(data.get("reasoning_coverage", 0.5)),
            tool_coverage=float(data.get("tool_coverage", 0.5)),
            model_family=str(data.get("model_family", "unknown")),
            platform=str(data.get("platform", "maker")),
        )


@dataclass(frozen=True)
class ToolPolicyPoint:
    """Point in tool/policy space T — allowed tools under declarative gates."""

    policy_id: str
    allowed_tools: tuple[str, ...] = ()
    denied_tools: tuple[str, ...] = ()
    data_domains: tuple[str, ...] = ()
    require_msda_gate: bool = True

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "space": "T",
            "policy_id": self.policy_id,
            "allowed_tools": list(self.allowed_tools),
            "denied_tools": list(self.denied_tools),
            "data_domains": list(self.data_domains),
            "require_msda_gate": self.require_msda_gate,
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> ToolPolicyPoint:
        return cls(
            policy_id=str(data["policy_id"]),
            allowed_tools=tuple(data.get("allowed_tools") or ()),
            denied_tools=tuple(data.get("denied_tools") or ()),
            data_domains=tuple(data.get("data_domains") or ()),
            require_msda_gate=bool(data.get("require_msda_gate", True)),
        )


@dataclass(frozen=True)
class TrajectoryEdge:
    source: str
    target: str
    expected_reward: float = 0.0
    expected_cost: float = 0.0

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TrajectoryGraph:
    """DAG (or controlled cyclic revisitation plan) Γ for a subtask graph."""

    nodes: list[str] = field(default_factory=list)
    edges: list[TrajectoryEdge] = field(default_factory=list)
    pattern: str = "sequential"  # sequential | parallel_fanout | hierarchical | handoff | cyclic

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "space": "Gamma",
            "pattern": self.pattern,
            "nodes": list(self.nodes),
            "edges": [e.to_jsonable() for e in self.edges],
        }

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> TrajectoryGraph:
        edges_raw = data.get("edges") or []
        edges: list[TrajectoryEdge] = []
        for item in edges_raw:
            if not isinstance(item, Mapping):
                continue
            edges.append(
                TrajectoryEdge(
                    source=str(item["source"]),
                    target=str(item["target"]),
                    expected_reward=float(item.get("expected_reward", 0.0)),
                    expected_cost=float(item.get("expected_cost", 0.0)),
                )
            )
        return cls(
            nodes=[str(n) for n in (data.get("nodes") or [])],
            edges=edges,
            pattern=str(data.get("pattern", "sequential")),
        )

    def topological_order(self) -> list[str]:
        """Kahn topological sort; raises ValueError on cycle unless pattern is cyclic."""
        indegree: dict[str, int] = {n: 0 for n in self.nodes}
        adj: dict[str, list[str]] = {n: [] for n in self.nodes}
        for edge in self.edges:
            if edge.source not in indegree or edge.target not in indegree:
                raise ValueError(f"edge references unknown node: {edge.source}->{edge.target}")
            adj[edge.source].append(edge.target)
            indegree[edge.target] += 1
        queue = [n for n, d in indegree.items() if d == 0]
        order: list[str] = []
        while queue:
            node = queue.pop(0)
            order.append(node)
            for nxt in adj[node]:
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    queue.append(nxt)
        if len(order) != len(self.nodes):
            if self.pattern == "cyclic":
                # Controlled revisitation: return nodes in declaration order as replay skeleton.
                return list(self.nodes)
            raise ValueError("trajectory graph contains a cycle (use pattern=cyclic for revisitation)")
        return order
