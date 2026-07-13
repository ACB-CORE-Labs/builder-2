"""S2 — HITL live orchestration lane (bounded graph run under approval).

``run_approved`` executes a digest-bound plan only when:
1. Approval artifact is present, approved, and plan_digest matches
2. MSDA preflight is forced on for every declared tool step (lane-local)
3. Graph nodes are limited to noop/record/msda_probe (no raw shell)

This is HITL runtime candidate power — not global enabled multi-agent autonomy.
Does not call model/tool gateways unless future node types are added under separate gates.
"""

from __future__ import annotations

from typing import Any, Mapping

from builder_ii.wrp.artifacts import (
    LIVE_RUN_APPROVAL_KIND,
    LIVE_RUN_PLAN_KIND,
    LIVE_RUN_RECEIPT_KIND,
    base_envelope,
)
from builder_ii.wrp.graph_runtime import execute_from_plan
from builder_ii.wrp.msda_preflight import MsdaPreflightDenied, assert_msda_preflight
from builder_ii.wrp.patterns import sequential_chain
from builder_ii.wrp.receipt_ingest import ingest_receipts
from builder_ii.wrp.subtask_graph import create_subtask_graph


class LiveLaneError(ValueError):
    """Fail-closed live lane refusal."""


def build_live_run_plan(
    *,
    task: str,
    nodes: list[str] | None = None,
    node_specs: dict[str, dict[str, Any]] | None = None,
    fleet_binding: dict[str, Any] | None = None,
    wrp_binding: dict[str, Any] | None = None,
    msda_tools: list[dict[str, str]] | None = None,
    max_iterations: int = 1,
    pattern: str = "sequential",
) -> dict[str, Any]:
    """Create a digest-bound live run plan (still requires approval to execute)."""
    node_list = nodes or ["classify", "allocate", "msda_probe", "handoff"]
    graph = sequential_chain(node_list)
    plan_graph = create_subtask_graph(graph, task=task)
    specs = node_specs or {
        nid: {"node_type": "record" if nid != "msda_probe" else "noop", "cost_estimate": 0.0, "payload": {"step": nid}}
        for nid in node_list
    }
    # msda_probe is preflight-only; runtime node stays noop.
    tools = msda_tools or [
        {"tool": "repo_map", "data_domain": "local_workspace", "risk": "local_offline"},
    ]
    return base_envelope(
        kind=LIVE_RUN_PLAN_KIND,
        artifact_state="PLANNED_ONLY",
        capability_state="wrp_hitl_live_lane",
        extra={
            "task": task,
            "pattern": pattern,
            "subtask_graph": plan_graph,
            "node_specs": specs,
            "fleet_binding": fleet_binding or {},
            "wrp_binding": wrp_binding or {},
            "msda_preflight_forced": True,
            "msda_tools": tools,
            "max_iterations": max_iterations,
            "allowed_node_types": ["noop", "record"],
            "model_gateway_invoked": False,
            "tool_gateway_invoked": False,
            "grants_authority": False,
            "executes_shell": False,
        },
    )


def build_live_run_approval(
    *,
    plan: dict[str, Any],
    approved_by: str,
    approved: bool = True,
    notes: str = "",
) -> dict[str, Any]:
    plan_digest = plan.get("digest")
    if not isinstance(plan_digest, str) or len(plan_digest) != 64:
        raise LiveLaneError("plan must be finalized with a 64-char digest before approval")
    return base_envelope(
        kind=LIVE_RUN_APPROVAL_KIND,
        artifact_state="HITL_APPROVAL_ONLY",
        capability_state="wrp_hitl_live_lane",
        extra={
            "approved": bool(approved),
            "approved_by": str(approved_by).strip(),
            "plan_kind": plan.get("kind"),
            "plan_digest": plan_digest,
            "notes": notes,
            "grants_unbounded_execution": False,
            "authorizes_live_lane_only": True,
        },
    )


def _require_approval(plan: dict[str, Any], approval: dict[str, Any]) -> None:
    if approval.get("kind") != LIVE_RUN_APPROVAL_KIND:
        raise LiveLaneError(f"approval.kind must be {LIVE_RUN_APPROVAL_KIND}")
    if approval.get("approved") is not True:
        raise LiveLaneError("approval.approved must be true")
    if not str(approval.get("approved_by") or "").strip():
        raise LiveLaneError("approval.approved_by is required")
    if approval.get("plan_digest") != plan.get("digest"):
        raise LiveLaneError("approval.plan_digest must match plan.digest (digest-bound HITL)")
    if plan.get("kind") != LIVE_RUN_PLAN_KIND:
        raise LiveLaneError(f"plan.kind must be {LIVE_RUN_PLAN_KIND}")


def _run_msda_probes(plan: dict[str, Any], policy: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Force MSDA preflight for every tool declared on the plan (lane-local force)."""
    tools = plan.get("msda_tools") or []
    decisions: list[dict[str, Any]] = []
    if not tools:
        raise LiveLaneError("live plan must declare msda_tools for S2 preflight")
    for item in tools:
        if not isinstance(item, Mapping):
            raise LiveLaneError("msda_tools entries must be objects")
        tool = str(item.get("tool") or "")
        domain = str(item.get("data_domain") or "local_workspace")
        risk = str(item.get("risk") or "local_offline")
        try:
            decision = assert_msda_preflight(
                tool=tool,
                data_domain=domain,
                risk=risk,
                policy=policy,
                enabled=True,  # forced for S2 lane regardless of env default
            )
        except MsdaPreflightDenied as exc:
            raise LiveLaneError(str(exc)) from exc
        if decision is not None:
            decisions.append(decision)
    return decisions


def run_approved(
    *,
    plan: dict[str, Any],
    approval: dict[str, Any],
    msda_policy: dict[str, Any] | None = None,
    experience_store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute bounded live lane under approval + forced MSDA preflight."""
    _require_approval(plan, approval)
    if plan.get("msda_preflight_forced") is not True:
        raise LiveLaneError("plan.msda_preflight_forced must be true for S2")
    if plan.get("executes_shell") is not False:
        raise LiveLaneError("plan.executes_shell must be false")
    if plan.get("model_gateway_invoked") is not False or plan.get("tool_gateway_invoked") is not False:
        # S2 v1: graph-only; gateway node types not yet enabled.
        raise LiveLaneError("S2 v1 refuses plans that claim model/tool gateway invocation")

    msda_decisions = _run_msda_probes(plan, msda_policy)

    graph_art = plan.get("subtask_graph")
    if not isinstance(graph_art, dict):
        raise LiveLaneError("plan.subtask_graph is required")
    raw_specs = plan.get("node_specs")
    node_specs: dict[str, dict[str, Any]] = raw_specs if isinstance(raw_specs, dict) else {}
    # Refuse unknown node types beyond runtime allowlist
    for nid, spec in node_specs.items():
        if not isinstance(spec, dict):
            continue
        ntype = str(spec.get("node_type", "noop"))
        if ntype not in {"noop", "record"}:
            raise LiveLaneError(f"node {nid!r} type {ntype!r} not allowed in S2 v1 (noop|record only)")

    max_iter = int(plan.get("max_iterations") or 1)
    run_result = execute_from_plan(
        graph_art,
        node_specs=node_specs,
        max_iterations=max_iter,
    )
    if run_result.get("status") != "success":
        raise LiveLaneError(f"graph runtime failed: {run_result.get('events')}")

    receipts = [
        {
            "kind": "wrp_live_step",
            "success": True,
            "digest": plan.get("digest"),
            "trajectory_id": f"live-{plan.get('digest', '')[:12]}",
            "notes": f"nodes={len(run_result.get('execution_order') or [])}",
        }
    ]
    exp_out = None
    if experience_store is not None:
        exp_out = ingest_receipts(experience_store, receipts)

    return base_envelope(
        kind=LIVE_RUN_RECEIPT_KIND,
        artifact_state="HITL_LIVE_RECEIPT",
        capability_state="wrp_hitl_live_lane",
        extra={
            "status": "success",
            "plan_digest": plan.get("digest"),
            "approval_digest": approval.get("digest"),
            "approved_by": approval.get("approved_by"),
            "task": plan.get("task"),
            "fleet_binding": plan.get("fleet_binding") or {},
            "wrp_binding": plan.get("wrp_binding") or {},
            "msda_decision_digests": [d.get("digest") for d in msda_decisions if isinstance(d, dict)],
            "graph_run": {
                "status": run_result.get("status"),
                "execution_order": run_result.get("execution_order"),
                "events": run_result.get("events"),
                "total_cost_estimate": run_result.get("total_cost_estimate"),
                "digest": run_result.get("digest"),
            },
            "experience_store_digest": (exp_out or {}).get("digest"),
            "model_gateway_invoked": False,
            "tool_gateway_invoked": False,
            "executes_shell": False,
            "grants_authority": False,
            "s2_version": "v1_graph_msda_hitl",
        },
    )


def validate_live_run_plan(record: Any) -> list[str]:
    from builder_ii.wrp.artifacts import validate_wrp_artifact_envelope

    errors = validate_wrp_artifact_envelope(record, expected_kind=LIVE_RUN_PLAN_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("msda_preflight_forced") is not True:
        errors.append("msda_preflight_forced must be true")
    if record.get("executes_shell") is not False:
        errors.append("executes_shell must be false")
    if record.get("model_gateway_invoked") is not False:
        errors.append("model_gateway_invoked must be false in S2 v1")
    if record.get("tool_gateway_invoked") is not False:
        errors.append("tool_gateway_invoked must be false in S2 v1")
    if not record.get("task"):
        errors.append("task is required")
    if not isinstance(record.get("subtask_graph"), dict):
        errors.append("subtask_graph is required")
    tools = record.get("msda_tools")
    if not isinstance(tools, list) or not tools:
        errors.append("msda_tools must be a non-empty list (forced preflight targets)")
    fleet = record.get("fleet_binding")
    if fleet is not None:
        if not isinstance(fleet, dict):
            errors.append("fleet_binding must be an object when present")
        elif not fleet.get("selected_alias"):
            errors.append("fleet_binding.selected_alias is required when fleet_binding is present")
        elif fleet.get("grants_authority") is not False and "grants_authority" in fleet:
            errors.append("fleet_binding.grants_authority must be false when set")
    wrp = record.get("wrp_binding")
    if wrp is not None:
        if not isinstance(wrp, dict):
            errors.append("wrp_binding must be an object when present")
        elif not wrp.get("classification_digest"):
            errors.append("wrp_binding.classification_digest is required when wrp_binding is present")
    return errors


def validate_live_run_approval(record: Any) -> list[str]:
    from builder_ii.wrp.artifacts import validate_wrp_artifact_envelope

    errors = validate_wrp_artifact_envelope(record, expected_kind=LIVE_RUN_APPROVAL_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("approved") is not True:
        errors.append("approved must be true for a positive approval artifact")
    if not str(record.get("approved_by") or "").strip():
        errors.append("approved_by is required")
    digest = record.get("plan_digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("plan_digest must be a 64-char hex digest")
    return errors


def validate_live_run_receipt(record: Any) -> list[str]:
    from builder_ii.wrp.artifacts import validate_wrp_artifact_envelope

    errors = validate_wrp_artifact_envelope(record, expected_kind=LIVE_RUN_RECEIPT_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("status") != "success":
        errors.append("status must be success for completed receipt")
    if record.get("executes_shell") is not False:
        errors.append("executes_shell must be false")
    if record.get("model_gateway_invoked") is not False:
        errors.append("model_gateway_invoked must be false in S2 v1")
    if record.get("tool_gateway_invoked") is not False:
        errors.append("tool_gateway_invoked must be false in S2 v1")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    return errors
