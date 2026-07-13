"""S2 — HITL live orchestration lane (bounded graph run under approval).

``run_approved`` executes a digest-bound plan only when:
1. Approval artifact is present, approved, and plan_digest matches
2. MSDA preflight is forced on for every declared tool step (lane-local)
3. Node allowlist matches the plan's S2 lane version:
   - **v1** (default): noop|record only; no gateway invoke flags
   - **v2**: noop|record|model_gateway|tool_gateway under forced MSDA;
     default gateway mode is ``record`` (no network / no cloud provider)

This is HITL runtime candidate power — not global enabled multi-agent autonomy.
No shell. Cloud provider model execution is not the default gateway path.
"""

from __future__ import annotations

from typing import Any, Mapping

from builder_ii.wrp.artifacts import (
    LIVE_RUN_APPROVAL_KIND,
    LIVE_RUN_PLAN_KIND,
    LIVE_RUN_RECEIPT_KIND,
    base_envelope,
)
from builder_ii.wrp.gateway_nodes import (
    GATEWAY_MODES,
    GATEWAY_NODE_TYPES,
    S2_V1_LANE_VERSION,
    S2_V2_LANE_VERSION,
    run_gateway_node,
)
from builder_ii.wrp.graph_runtime import execute_from_plan
from builder_ii.wrp.msda_preflight import MsdaPreflightDenied, assert_msda_preflight
from builder_ii.wrp.patterns import sequential_chain
from builder_ii.wrp.receipt_ingest import ingest_receipts
from builder_ii.wrp.subtask_graph import create_subtask_graph

V1_NODE_TYPES: frozenset[str] = frozenset({"noop", "record"})
V2_NODE_TYPES: frozenset[str] = V1_NODE_TYPES | GATEWAY_NODE_TYPES


class LiveLaneError(ValueError):
    """Fail-closed live lane refusal."""


def _normalize_lane_version(s2_version: str | None) -> str:
    raw = str(s2_version or "v1").strip().lower()
    if raw in {"v1", S2_V1_LANE_VERSION, "v1_graph_msda_hitl"}:
        return S2_V1_LANE_VERSION
    if raw in {"v2", S2_V2_LANE_VERSION, "v2_gateway_hitl"}:
        return S2_V2_LANE_VERSION
    raise LiveLaneError(
        f"unknown s2_version {s2_version!r}; use v1 or v2 "
        f"({S2_V1_LANE_VERSION} | {S2_V2_LANE_VERSION})"
    )


def _default_node_specs(node_list: list[str], *, lane_version: str) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for nid in node_list:
        if nid == "msda_probe":
            specs[nid] = {"node_type": "noop", "cost_estimate": 0.0, "payload": {"step": nid}}
        elif lane_version == S2_V2_LANE_VERSION and nid in {"model_call", "model_gateway"}:
            specs[nid] = {
                "node_type": "model_gateway",
                "cost_estimate": 0.0,
                "payload": {
                    "step": nid,
                    "tool": "model_call",
                    "data_domain": "local_workspace",
                    "risk": "local_network",
                    "model_id": "record-only-local",
                },
            }
        elif lane_version == S2_V2_LANE_VERSION and nid in {"tool_call", "tool_gateway"}:
            specs[nid] = {
                "node_type": "tool_gateway",
                "cost_estimate": 0.0,
                "payload": {
                    "step": nid,
                    "tool_id": "builtin.echo",
                    "tool": "builtin.echo",
                    "data_domain": "local_workspace",
                    "risk": "local_offline",
                    "text": f"live:{nid}",
                },
            }
        else:
            specs[nid] = {
                "node_type": "record",
                "cost_estimate": 0.0,
                "payload": {"step": nid},
            }
    return specs


def _flags_from_specs(specs: Mapping[str, Mapping[str, Any]]) -> tuple[bool, bool]:
    model = False
    tool = False
    for spec in specs.values():
        if not isinstance(spec, Mapping):
            continue
        ntype = str(spec.get("node_type", "noop"))
        if ntype == "model_gateway":
            model = True
        elif ntype == "tool_gateway":
            tool = True
    return model, tool


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
    s2_version: str = "v1",
    gateway_mode: str = "record",
) -> dict[str, Any]:
    """Create a digest-bound live run plan (still requires approval to execute)."""
    lane = _normalize_lane_version(s2_version)
    if lane == S2_V2_LANE_VERSION:
        node_list = nodes or ["classify", "model_gateway", "tool_gateway", "msda_probe", "handoff"]
    else:
        node_list = nodes or ["classify", "allocate", "msda_probe", "handoff"]
    graph = sequential_chain(node_list)
    plan_graph = create_subtask_graph(graph, task=task)
    specs = node_specs or _default_node_specs(node_list, lane_version=lane)
    model_flag, tool_flag = _flags_from_specs(specs)
    if lane == S2_V1_LANE_VERSION and (model_flag or tool_flag):
        raise LiveLaneError("S2 v1 plan cannot include gateway node types; use s2_version=v2")
    mode = str(gateway_mode or "record")
    if mode not in GATEWAY_MODES:
        raise LiveLaneError(f"gateway_mode must be one of {sorted(GATEWAY_MODES)}")
    if lane == S2_V1_LANE_VERSION:
        mode = "record"  # unused on v1
        allowed = sorted(V1_NODE_TYPES)
        model_flag = False
        tool_flag = False
    else:
        allowed = sorted(V2_NODE_TYPES)

    tools = msda_tools or [
        {"tool": "repo_map", "data_domain": "local_workspace", "risk": "local_offline"},
    ]
    # v2: ensure gateway tools appear in msda_tools for plan-level probe
    if lane == S2_V2_LANE_VERSION:
        declared = {(t.get("tool") if isinstance(t, Mapping) else None) for t in tools}
        if model_flag and "model_call" not in declared:
            tools = [*tools, {"tool": "model_call", "data_domain": "local_workspace", "risk": "local_network"}]
        if tool_flag and "builtin.echo" not in declared:
            tools = [*tools, {"tool": "builtin.echo", "data_domain": "local_workspace", "risk": "local_offline"}]

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
            "allowed_node_types": allowed,
            "s2_version": lane,
            "gateway_mode": mode if lane == S2_V2_LANE_VERSION else None,
            "model_gateway_invoked": model_flag,
            "tool_gateway_invoked": tool_flag,
            "grants_authority": False,
            "executes_shell": False,
            "cloud_provider_invoke": False,
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
            "s2_version": plan.get("s2_version") or S2_V1_LANE_VERSION,
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
    if plan.get("cloud_provider_invoke") is True:
        raise LiveLaneError("cloud_provider_invoke is not permitted on the live lane")

    lane = _normalize_lane_version(str(plan.get("s2_version") or S2_V1_LANE_VERSION))
    model_flag = bool(plan.get("model_gateway_invoked"))
    tool_flag = bool(plan.get("tool_gateway_invoked"))

    if lane == S2_V1_LANE_VERSION:
        if model_flag or tool_flag:
            raise LiveLaneError("S2 v1 refuses plans that claim model/tool gateway invocation")
        allowed = V1_NODE_TYPES
        gateway_handler = None
        gateway_mode = "record"
    else:
        allowed = V2_NODE_TYPES
        gateway_mode = str(plan.get("gateway_mode") or "record")
        if gateway_mode not in GATEWAY_MODES:
            raise LiveLaneError(f"plan.gateway_mode must be one of {sorted(GATEWAY_MODES)}")
        plan_digest = str(plan.get("digest") or "")
        approved_by = str(approval.get("approved_by") or "")

        def gateway_handler(
            node_id: str, spec: dict[str, Any], handoff_state: dict[str, Any]
        ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]:
            return run_gateway_node(
                node_id=node_id,
                node_type=str(spec.get("node_type") or ""),
                spec=spec,
                handoff_state=handoff_state,
                plan_digest=plan_digest,
                approved_by=approved_by,
                gateway_mode=gateway_mode,
                msda_policy=msda_policy,
            )

    msda_decisions = _run_msda_probes(plan, msda_policy)

    graph_art = plan.get("subtask_graph")
    if not isinstance(graph_art, dict):
        raise LiveLaneError("plan.subtask_graph is required")
    raw_specs = plan.get("node_specs")
    node_specs: dict[str, dict[str, Any]] = raw_specs if isinstance(raw_specs, dict) else {}
    saw_model = False
    saw_tool = False
    for nid, spec in node_specs.items():
        if not isinstance(spec, dict):
            continue
        ntype = str(spec.get("node_type", "noop"))
        if ntype not in allowed:
            raise LiveLaneError(
                f"node {nid!r} type {ntype!r} not allowed in {lane} "
                f"(allowed: {sorted(allowed)})"
            )
        if ntype == "model_gateway":
            saw_model = True
        if ntype == "tool_gateway":
            saw_tool = True

    # Flags must match actual specs (fail closed on claim inflation).
    if bool(model_flag) != saw_model:
        raise LiveLaneError("plan.model_gateway_invoked must match presence of model_gateway nodes")
    if bool(tool_flag) != saw_tool:
        raise LiveLaneError("plan.tool_gateway_invoked must match presence of tool_gateway nodes")

    max_iter = int(plan.get("max_iterations") or 1)
    run_result = execute_from_plan(
        graph_art,
        node_specs=node_specs,
        max_iterations=max_iter,
        gateway_handler=gateway_handler,
    )
    if run_result.get("status") != "success":
        raise LiveLaneError(f"graph runtime failed: {run_result.get('events')}")

    receipts = [
        {
            "kind": "wrp_live_step",
            "success": True,
            "digest": plan.get("digest"),
            "trajectory_id": f"live-{plan.get('digest', '')[:12]}",
            "notes": f"nodes={len(run_result.get('execution_order') or [])};lane={lane}",
        }
    ]
    # Surface gateway digests as optional success signals for experience.
    traj = run_result.get("trajectory")
    if not isinstance(traj, dict):
        traj = {}
    for nid, payload in traj.items():
        if isinstance(payload, dict) and payload.get("digest"):
            receipts.append(
                {
                    "kind": "wrp_live_step",
                    "success": True,
                    "trajectory_id": f"gw-{nid}",
                    "digest": payload.get("digest"),
                    "notes": f"gateway node={nid} type={payload.get('kind')}",
                }
            )

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
                "trajectory": traj,
                "total_cost_estimate": run_result.get("total_cost_estimate"),
                "digest": run_result.get("digest"),
            },
            "experience_store_digest": (exp_out or {}).get("digest"),
            "model_gateway_invoked": saw_model,
            "tool_gateway_invoked": saw_tool,
            "gateway_mode": gateway_mode if lane == S2_V2_LANE_VERSION else None,
            "cloud_provider_invoke": False,
            "executes_shell": False,
            "grants_authority": False,
            "s2_version": lane,
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
    if record.get("cloud_provider_invoke") is True:
        errors.append("cloud_provider_invoke must be false")
    if not record.get("task"):
        errors.append("task is required")
    if not isinstance(record.get("subtask_graph"), dict):
        errors.append("subtask_graph is required")
    tools = record.get("msda_tools")
    if not isinstance(tools, list) or not tools:
        errors.append("msda_tools must be a non-empty list (forced preflight targets)")

    lane_raw = record.get("s2_version") or S2_V1_LANE_VERSION
    try:
        lane = _normalize_lane_version(str(lane_raw))
    except LiveLaneError as exc:
        errors.append(str(exc))
        return errors

    model_flag = record.get("model_gateway_invoked")
    tool_flag = record.get("tool_gateway_invoked")
    if lane == S2_V1_LANE_VERSION:
        if model_flag is not False:
            errors.append("model_gateway_invoked must be false in S2 v1")
        if tool_flag is not False:
            errors.append("tool_gateway_invoked must be false in S2 v1")
    else:
        if not isinstance(model_flag, bool):
            errors.append("model_gateway_invoked must be a bool in S2 v2")
        if not isinstance(tool_flag, bool):
            errors.append("tool_gateway_invoked must be a bool in S2 v2")
        mode = record.get("gateway_mode")
        if mode not in GATEWAY_MODES:
            errors.append(f"gateway_mode must be one of {sorted(GATEWAY_MODES)} in S2 v2")

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
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("cloud_provider_invoke") is True:
        errors.append("cloud_provider_invoke must be false")
    lane = record.get("s2_version") or S2_V1_LANE_VERSION
    if lane == S2_V1_LANE_VERSION:
        if record.get("model_gateway_invoked") is not False:
            errors.append("model_gateway_invoked must be false in S2 v1")
        if record.get("tool_gateway_invoked") is not False:
            errors.append("tool_gateway_invoked must be false in S2 v1")
    elif lane == S2_V2_LANE_VERSION:
        if not isinstance(record.get("model_gateway_invoked"), bool):
            errors.append("model_gateway_invoked must be a bool in S2 v2")
        if not isinstance(record.get("tool_gateway_invoked"), bool):
            errors.append("tool_gateway_invoked must be a bool in S2 v2")
    else:
        errors.append(f"unknown s2_version on receipt: {lane!r}")
    return errors
