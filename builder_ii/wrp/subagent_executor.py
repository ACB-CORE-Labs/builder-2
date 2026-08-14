"""W3.1 — governed subagent executor via the WRP execution seam.

Supports:
- single step (``run_governed_subagent_step``)
- multi-step bounded loop (``run_governed_subagent_loop``)

Each step goes through ``gateway_mode=invoke_local`` (or ``invoke_cloud`` when
explicitly requested and ceremony payload is present).

``spawn_executed`` is **true only** when the loop runs under local (or fully
gated cloud) seam calls with budget + HITL approval fields + kill-switch arming.
AgentFactory lifecycle *records* remain a separate honesty surface
(``spawn_agent`` still defaults spawn_executed=false).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from builder_ii.wrp.gateway_nodes import run_gateway_node

SUBAGENT_STEP_KIND = "builder_ii.wrp.subagent_step_receipt"
SUBAGENT_LOOP_KIND = "builder_ii.wrp.subagent_loop_receipt"
SUBAGENT_EVIDENCE_KIND = "builder_ii.wrp.subagent_evidence_bundle"


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
    gateway_mode: str = "invoke_local",
    cloud_approval_path: str | None = None,
    handoff_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute one subagent model step through the seam."""
    payload: dict[str, Any] = {
        "tool": "model_call",
        "data_domain": "local_workspace",
        "risk": "local_network" if gateway_mode == "invoke_local" else "cloud_external",
        "model_id": model_id,
        "prompt": prompt,
        "budget": dict(budget),
        "role": role,
        "task": task,
        "max_tokens": max_tokens,
        "enable_stub_if_disabled": True,
        "session_id": session_id or f"subagent-{plan_digest[:12]}",
    }
    if registry is not None:
        payload["registry"] = registry
    if artifact_dir is not None:
        payload["artifact_dir"] = str(artifact_dir)
    if cloud_approval_path is not None:
        payload["approval_path"] = cloud_approval_path
        payload["cloud_call_approval_path"] = cloud_approval_path

    event, state, traj, err = run_gateway_node(
        node_id=f"subagent_{role}",
        node_type="model_gateway",
        spec={"node_type": "model_gateway", "cost_estimate": 0.0, "payload": payload},
        handoff_state=dict(handoff_state or {}),
        plan_digest=plan_digest,
        approved_by=approved_by,
        gateway_mode=gateway_mode,
    )
    if err is not None:
        raise RuntimeError(err)
    body = traj.get(f"subagent_{role}") or {}
    return {
        "kind": SUBAGENT_STEP_KIND,
        "role": role,
        "task": task,
        "event": event,
        "state": state,
        "gateway_result": body,
        "uses_seam": True,
        "gateway_mode": gateway_mode,
        "grants_authority": False,
        # Single step alone does not claim AgentFactory process spawn.
        "spawn_executed": False,
        "step_executed": True,
    }


def _kill_switch_tripped(kill_switch_path: Path | None) -> bool:
    if kill_switch_path is None:
        return False
    if not kill_switch_path.exists():
        return False
    text = kill_switch_path.read_text(encoding="utf-8").strip().lower()
    return text in {"1", "true", "kill", "stop", "halt"}


def _inherit_budget(parent: Mapping[str, Any], *, child_max_usd: float | None) -> dict[str, Any]:
    """Child may only spend ≤ parent remaining USD and remaining tokens."""
    from builder_ii.routing.model_budget import create_model_budget

    parent_max_usd = float(parent.get("max_usd") or 0.0)
    spent_usd = float(parent.get("spent_usd") or 0.0)
    remaining_usd = max(0.0, parent_max_usd - spent_usd)
    if child_max_usd is not None:
        remaining_usd = min(remaining_usd, float(child_max_usd))

    parent_max_tok = int(parent.get("max_total_tokens") or 0)
    spent_tok = int(parent.get("spent_total_tokens") or 0)
    remaining_tok = max(0, parent_max_tok - spent_tok)

    return create_model_budget(
        session_id=str(parent.get("session_id") or "subagent-session"),
        task_id=str(parent.get("task_id") or "subagent-task"),
        max_input_tokens=int(parent.get("max_input_tokens") or remaining_tok),
        max_output_tokens=int(parent.get("max_output_tokens") or min(256, remaining_tok)),
        max_total_tokens=remaining_tok,
        max_usd=remaining_usd,
    )


def run_governed_subagent_loop(
    *,
    role: str,
    task: str,
    model_id: str,
    steps: list[str],
    plan_digest: str,
    approved_by: str,
    parent_budget: Mapping[str, Any],
    registry: dict[str, Any] | None = None,
    artifact_dir: Path | str | None = None,
    session_id: str | None = None,
    max_tokens: int = 128,
    max_steps: int | None = None,
    kill_switch_path: Path | str | None = None,
    child_max_usd: float | None = None,
    gateway_mode: str = "invoke_local",
    cloud_approval_path: str | None = None,
) -> dict[str, Any]:
    """Bounded multi-step subagent loop through the seam.

    Sets ``spawn_executed=True`` only when at least one step executed successfully
    under budget + approved_by + armed kill-switch path (may be absent file).
    """
    if not steps:
        raise ValueError("steps must be non-empty")
    limit = max_steps if max_steps is not None else len(steps)
    if limit < 1:
        raise ValueError("max_steps must be >= 1")
    if not approved_by or not str(approved_by).strip():
        raise ValueError("approved_by is required (HITL boundary)")
    if not plan_digest or len(plan_digest) != 64:
        raise ValueError("plan_digest must be a 64-char hex digest")

    ks_path = Path(kill_switch_path) if kill_switch_path is not None else None
    # Arm kill-switch: parent must supply a path (file may not exist until tripped).
    kill_switch_armed = ks_path is not None

    budget = _inherit_budget(parent_budget, child_max_usd=child_max_usd)
    handoff: dict[str, Any] = {"last_debited_budget": budget}
    step_receipts: list[dict[str, Any]] = []
    stopped_reason = "completed"
    executed_count = 0

    for idx, prompt in enumerate(steps[:limit]):
        if _kill_switch_tripped(ks_path):
            stopped_reason = "kill_switch"
            break
        try:
            step = run_governed_subagent_step(
                role=role,
                task=f"{task} [step {idx + 1}/{limit}]",
                model_id=model_id,
                prompt=prompt,
                plan_digest=plan_digest,
                approved_by=approved_by,
                budget=handoff.get("last_debited_budget") or budget,
                registry=registry,
                artifact_dir=artifact_dir,
                session_id=session_id or f"subagent-loop-{plan_digest[:12]}",
                max_tokens=max_tokens,
                gateway_mode=gateway_mode,
                cloud_approval_path=cloud_approval_path,
                handoff_state=handoff,
            )
        except Exception as exc:  # noqa: BLE001 — surface as loop failure receipt
            stopped_reason = f"step_error:{exc}"
            step_receipts.append(
                {
                    "kind": SUBAGENT_STEP_KIND,
                    "role": role,
                    "step_index": idx,
                    "error": str(exc),
                    "step_executed": False,
                }
            )
            break

        step_receipts.append({**step, "step_index": idx})
        executed_count += 1
        # Chain budget from gateway handoff state
        st = step.get("state") if isinstance(step.get("state"), dict) else {}
        if isinstance(st.get("last_debited_budget"), dict):
            handoff["last_debited_budget"] = st["last_debited_budget"]
        gw = step.get("gateway_result") if isinstance(step.get("gateway_result"), dict) else {}
        if isinstance(gw.get("debited_budget"), dict):
            handoff["last_debited_budget"] = gw["debited_budget"]

    spawn_ok = (
        executed_count >= 1
        and kill_switch_armed
        and bool(str(approved_by).strip())
        and stopped_reason in {"completed", "kill_switch"}
        and gateway_mode in {"invoke_local", "invoke_cloud"}
    )

    evidence = {
        "kind": SUBAGENT_EVIDENCE_KIND,
        "role": role,
        "task": task,
        "plan_digest": plan_digest,
        "approved_by": approved_by,
        "step_count": executed_count,
        "step_digests": [
            (s.get("gateway_result") or {}).get("digest")
            for s in step_receipts
            if isinstance(s.get("gateway_result"), dict)
        ],
        "kill_switch_armed": kill_switch_armed,
        "kill_switch_path": str(ks_path) if ks_path is not None else None,
        "final_budget": handoff.get("last_debited_budget"),
        "grants_authority": False,
    }

    return {
        "kind": SUBAGENT_LOOP_KIND,
        "role": role,
        "task": task,
        "model_id": model_id,
        "plan_digest": plan_digest,
        "approved_by": approved_by,
        "gateway_mode": gateway_mode,
        "steps_requested": min(len(steps), limit),
        "steps_executed": executed_count,
        "stopped_reason": stopped_reason,
        "step_receipts": step_receipts,
        "evidence": evidence,
        "uses_seam": True,
        "kill_switch_armed": kill_switch_armed,
        # Earned only under local/gated cloud + budget + HITL + kill-switch arming.
        "spawn_executed": spawn_ok,
        "spawn_permitted": spawn_ok,
        "process_spawn": False,  # still no OS process fork — governed loop only
        "runtime_binding": "SEAM_BOUND" if spawn_ok else "UNBOUND",
        "grants_authority": False,
        "s3_enabled": False,
    }
