"""W1 / F1 — CollaborationPlanner (MasRouter reference).

Maps Maker/Governor roles onto topology nodes with mode gating and handoff contracts.
No runtime agent spawn — plan/topology artifacts only.
"""

from __future__ import annotations

from typing import Any

from builder_ii.wrp.artifacts import (
    COLLABORATION_TOPOLOGY_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)
from builder_ii.wrp.spaces import AgentPoint

# Canonical dual-platform nodes (Master-Plan Maker/Governor)
DEFAULT_NODES: tuple[AgentPoint, ...] = (
    AgentPoint(
        role="maker_structural",
        reasoning_coverage=0.9,
        tool_coverage=0.85,
        model_family="grok-4.5",
        platform="maker",
    ),
    AgentPoint(
        role="maker_unit",
        reasoning_coverage=0.55,
        tool_coverage=0.9,
        model_family="composer-2.5-fast",
        platform="maker",
    ),
    AgentPoint(
        role="governor_architecture",
        reasoning_coverage=0.95,
        tool_coverage=0.4,
        model_family="gemini-3.1-pro",
        platform="governor",
    ),
    AgentPoint(
        role="governor_telemetry",
        reasoning_coverage=0.5,
        tool_coverage=0.55,
        model_family="gemini-3.5-flash",
        platform="governor",
    ),
)

REQUIRED_HANDOFF_KEYS: tuple[str, ...] = (
    "task",
    "target",
    "authority",
    "risks",
    "evidence_status",
    "workload_digest",
    "denied_actions",
)

_MODE_GATES: dict[str, dict[str, Any]] = {
    "standard": {
        "min_priority": 0,
        "max_clearance": "operator",
        "allowed_platforms": ["maker", "governor"],
    },
    "high_security": {
        "min_priority": 2,
        "max_clearance": "lead_engineer",
        "allowed_platforms": ["governor", "maker"],
        "require_governor_before_push": True,
    },
    "maker_only_draft": {
        "min_priority": 0,
        "max_clearance": "operator",
        "allowed_platforms": ["maker"],
        "require_governor_before_push": True,
    },
}


def plan_collaboration(
    *,
    task: str,
    priority: int = 1,
    clearance: str = "operator",
    mode: str = "standard",
    security_sensitive: bool = False,
) -> dict[str, Any]:
    if not task or not task.strip():
        raise ValueError("task must be non-empty")
    if mode not in _MODE_GATES:
        raise ValueError(f"unknown collaboration mode: {mode}")
    if security_sensitive:
        mode = "high_security"
    gate = _MODE_GATES[mode]
    min_priority = int(gate["min_priority"])
    if priority < min_priority:
        # Auto-raise priority to satisfy mode gate (fail-closed elevation, not privilege widening).
        priority = min_priority

    nodes = [n for n in DEFAULT_NODES if n.platform in gate["allowed_platforms"]]
    # Mode gating: information flow edges
    edges: list[dict[str, Any]] = []
    maker_roles = [n.role for n in nodes if n.platform == "maker"]
    governor_roles = [n.role for n in nodes if n.platform == "governor"]
    if maker_roles and governor_roles:
        edges.append(
            {
                "source": maker_roles[0],
                "target": governor_roles[0],
                "flow": "candidate_changeset",
                "requires_keys": list(REQUIRED_HANDOFF_KEYS),
            }
        )
        if len(maker_roles) > 1:
            edges.append(
                {
                    "source": maker_roles[0],
                    "target": maker_roles[1],
                    "flow": "unit_delegation",
                    "requires_keys": list(REQUIRED_HANDOFF_KEYS),
                }
            )
        if len(governor_roles) > 1:
            edges.append(
                {
                    "source": governor_roles[0],
                    "target": governor_roles[1],
                    "flow": "telemetry_digest",
                    "requires_keys": ["evidence_status", "task"],
                }
            )

    handoff_contract = {
        "required_keys": list(REQUIRED_HANDOFF_KEYS),
        "zero_loss_rule": "every required key present on every maker→governor edge",
        "continuity_requirement": (
            "each node must preserve task, target, authority, risks, and evidence_status"
        ),
    }

    return base_envelope(
        kind=COLLABORATION_TOPOLOGY_KIND,
        artifact_state="PLANNED_ONLY",
        capability_state="wrp_plan_only",
        extra={
            "task": task.strip(),
            "mode": mode,
            "priority": priority,
            "clearance": clearance,
            "mode_gate": gate,
            "nodes": [n.to_jsonable() for n in nodes],
            "edges": edges,
            "handoff_contract": handoff_contract,
            "runtime_binding": "UNBOUND",
            "grants_authority": False,
        },
    )


def validate_handoff_state(state: dict[str, Any]) -> list[str]:
    """Ensure zero loss of required handoff keys."""
    errors: list[str] = []
    for key in REQUIRED_HANDOFF_KEYS:
        if key not in state or state[key] in (None, ""):
            errors.append(f"missing handoff key: {key}")
    return errors


def complete_handoff_state(
    *,
    task: str,
    target: str = "builder-ii",
    authority: str = "none",
    risks: str = "local_offline",
    evidence_status: str = "pending",
    workload_digest: str = "0" * 64,
    denied_actions: str = "shell,cloud_invoke",
) -> dict[str, Any]:
    """Build a full zero-loss handoff state for local graph continuity tests."""
    return {
        "task": task,
        "target": target,
        "authority": authority,
        "risks": risks,
        "evidence_status": evidence_status,
        "workload_digest": workload_digest,
        "denied_actions": denied_actions,
    }


def measure_handoff_overhead(
    *,
    iterations: int = 20,
    threshold_ms: float = 50.0,
) -> dict[str, Any]:
    """Measure pure local handoff path wall time (topology + graph continuity).

    Master-Plan W1 acceptance: handoff overhead &lt;50ms with zero state loss.
    Local pure-Python only — not a network Maker↔Governor SLA claim.
    Does not grant authority or spawn agents.
    """
    import statistics
    import time

    from builder_ii.wrp.graph_runtime import execute_graph
    from builder_ii.wrp.patterns import handoff_route

    if iterations < 1:
        raise ValueError("iterations must be >= 1")

    topology = plan_collaboration(task="handoff-measure", mode="standard", priority=1)
    state = complete_handoff_state(task="handoff-measure")
    keys = list(REQUIRED_HANDOFF_KEYS)
    graph = handoff_route(["maker", "governor"])

    walls: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter()
        topo_err = validate_collaboration_topology(topology)
        hand_err = validate_handoff_state(state)
        if topo_err or hand_err:
            return {
                "ok": False,
                "meets_threshold": False,
                "threshold_ms": threshold_ms,
                "iterations": iterations,
                "errors": [*topo_err, *hand_err],
                "grants_authority": False,
                "scope": "local_pure_python",
            }
        result = execute_graph(
            graph,
            handoff_state=state,
            required_keys=keys,
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        walls.append(elapsed_ms)
        if result.get("status") != "success":
            return {
                "ok": False,
                "meets_threshold": False,
                "threshold_ms": threshold_ms,
                "iterations": iterations,
                "errors": [str(result.get("error") or "graph handoff failed")],
                "median_ms": round(statistics.median(walls), 4),
                "grants_authority": False,
                "scope": "local_pure_python",
            }

    median = statistics.median(walls)
    p95 = sorted(walls)[max(0, int(0.95 * (len(walls) - 1)))]
    return {
        "ok": True,
        "meets_threshold": median < threshold_ms,
        "threshold_ms": threshold_ms,
        "iterations": iterations,
        "median_ms": round(float(median), 4),
        "p95_ms": round(float(p95), 4),
        "max_ms": round(float(max(walls)), 4),
        "zero_loss": True,
        "required_keys": keys,
        "topology_digest": topology.get("digest"),
        "grants_authority": False,
        "scope": "local_pure_python",
        "notes": (
            "Measures pure topology validate + handoff_route execute with REQUIRED_HANDOFF_KEYS. "
            "Not a cloud/network dual-platform handoff SLO."
        ),
    }


def validate_collaboration_topology(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=COLLABORATION_TOPOLOGY_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("artifact_state") != "PLANNED_ONLY":
        errors.append("artifact_state must be PLANNED_ONLY")
    if record.get("runtime_binding") != "UNBOUND":
        errors.append("runtime_binding must be UNBOUND")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    nodes = record.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("nodes must be a non-empty list")
    handoff = record.get("handoff_contract")
    if not isinstance(handoff, dict):
        errors.append("handoff_contract must be an object")
    else:
        keys = handoff.get("required_keys")
        if not isinstance(keys, list) or set(REQUIRED_HANDOFF_KEYS) - set(keys):
            errors.append("handoff_contract.required_keys incomplete")
    return errors
