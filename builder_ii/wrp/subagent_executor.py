"""W3.1 partial — governed subagent *step* via the WRP invoke_local seam.

This does **not** flip AgentFactory ``spawn_executed=true`` (lifecycle records
remain honesty-pinned). It runs one model step under the same fail-closed
constraints as ``gateway_mode=invoke_local``.

Full multi-step recursive HITL + earned spawn_executed is DEFERRED pending
schema versioning + HUMAN ceremony (see LAST_MILE_MASTER_CHECKLIST).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from builder_ii.wrp.gateway_nodes import run_gateway_node


def run_governed_subagent_step(
    *,
    role: str,
    task: str,
    model_id: str,
    prompt: str,
    plan_digest: str,
    approved_by: str,
    budget: Mapping[str, Any],
    registry: dict[str, Any] | None = None,
    artifact_dir: Path | str | None = None,
    session_id: str | None = None,
    max_tokens: int = 128,
) -> dict[str, Any]:
    """Execute one subagent model step through the seam. Returns gateway trajectory body."""
    payload: dict[str, Any] = {
        "tool": "model_call",
        "data_domain": "local_workspace",
        "risk": "local_network",
        "model_id": model_id,
        "prompt": prompt,
        "budget": dict(budget),
        "role": role,
        "task": task,
        "max_tokens": max_tokens,
        "enable_stub_if_disabled": True,
        "session_id": session_id or f"subagent-{plan_digest[:12]}",
        "spawn_executed": False,  # honesty pin: step runner ≠ AgentFactory process spawn
    }
    if registry is not None:
        payload["registry"] = registry
    if artifact_dir is not None:
        payload["artifact_dir"] = str(artifact_dir)

    event, state, traj, err = run_gateway_node(
        node_id=f"subagent_{role}",
        node_type="model_gateway",
        spec={"node_type": "model_gateway", "cost_estimate": 0.0, "payload": payload},
        handoff_state={},
        plan_digest=plan_digest,
        approved_by=approved_by,
        gateway_mode="invoke_local",
    )
    if err is not None:
        raise RuntimeError(err)
    body = traj.get(f"subagent_{role}") or {}
    return {
        "kind": "builder_ii.wrp.subagent_step_receipt",
        "role": role,
        "task": task,
        "event": event,
        "state": state,
        "gateway_result": body,
        "spawn_executed": False,
        "uses_seam": True,
        "gateway_mode": "invoke_local",
        "grants_authority": False,
    }
