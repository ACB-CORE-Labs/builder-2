"""S2 v2 — HITL model/tool gateway nodes for the live lane.

Default mode is ``record``: forced MSDA preflight + digest-bound synthetic
gateway receipt fragments. No network, no shell, no cloud model call.

Optional mode ``stub_tool`` invokes the B7 in-process stub allowlist
(``builtin.echo`` / ``builtin.utc_static``) only — still no shell.

Real cloud/provider model execution is intentionally out of the default path
(mechanical sympathy + separate model-gateway authority). Dual-correction
cannot self-grant broader provider enablement.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from builder_ii.wrp.msda_preflight import MsdaPreflightDenied, assert_msda_preflight

GATEWAY_NODE_TYPES: frozenset[str] = frozenset({"model_gateway", "tool_gateway"})
GATEWAY_MODES: frozenset[str] = frozenset({"record", "stub_tool"})
S2_V2_LANE_VERSION = "v2_gateway_hitl"
S2_V1_LANE_VERSION = "v1_graph_msda_hitl"

# Stub tools only when mode=stub_tool (matches B7 allowlist).
_STUB_TOOL_ALLOWLIST: frozenset[str] = frozenset({"builtin.echo", "builtin.utc_static"})


class GatewayNodeError(ValueError):
    """Fail-closed gateway node refusal."""


def _sha(payload: Mapping[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _msda_for_node(
    *,
    node_type: str,
    spec: Mapping[str, Any],
    msda_policy: dict[str, Any] | None,
) -> dict[str, Any]:
    payload = spec.get("payload") if isinstance(spec.get("payload"), Mapping) else {}
    if node_type == "model_gateway":
        tool = str(payload.get("tool") or "model_call")
        domain = str(payload.get("data_domain") or "local_workspace")
        risk = str(payload.get("risk") or "local_network")
    else:
        tool = str(payload.get("tool") or payload.get("tool_id") or "builtin.echo")
        domain = str(payload.get("data_domain") or "local_workspace")
        risk = str(payload.get("risk") or "local_offline")
    try:
        decision = assert_msda_preflight(
            tool=tool,
            data_domain=domain,
            risk=risk,
            policy=msda_policy,
            enabled=True,  # forced for every gateway node
        )
    except MsdaPreflightDenied as exc:
        raise GatewayNodeError(str(exc)) from exc
    if decision is None:
        raise GatewayNodeError("MSDA preflight must run for gateway nodes")
    return decision


def _record_model_gateway(
    *,
    node_id: str,
    spec: Mapping[str, Any],
    plan_digest: str,
    approved_by: str,
    msda_decision: Mapping[str, Any],
) -> dict[str, Any]:
    payload = spec.get("payload") if isinstance(spec.get("payload"), Mapping) else {}
    model_id = str(payload.get("model_id") or "record-only-local")
    prompt_snippet = str(payload.get("prompt_snippet") or payload.get("task") or "")[:120]
    body = {
        "kind": "builder_ii.wrp.gateway_model_record",
        "mode": "record",
        "node_id": node_id,
        "model_id": model_id,
        "prompt_snippet": prompt_snippet,
        "plan_digest": plan_digest,
        "approved_by": approved_by,
        "msda_decision_digest": msda_decision.get("digest"),
        "performs_network": False,
        "executes_model_provider": False,
        "executes_shell": False,
        "grants_authority": False,
    }
    return {**body, "digest": _sha(body)}


def _record_tool_gateway(
    *,
    node_id: str,
    spec: Mapping[str, Any],
    plan_digest: str,
    approved_by: str,
    msda_decision: Mapping[str, Any],
) -> dict[str, Any]:
    payload = spec.get("payload") if isinstance(spec.get("payload"), Mapping) else {}
    tool_id = str(payload.get("tool_id") or payload.get("tool") or "builtin.echo")
    body = {
        "kind": "builder_ii.wrp.gateway_tool_record",
        "mode": "record",
        "node_id": node_id,
        "tool_id": tool_id,
        "plan_digest": plan_digest,
        "approved_by": approved_by,
        "msda_decision_digest": msda_decision.get("digest"),
        "performs_network": False,
        "executes_tool_stub": False,
        "executes_shell": False,
        "grants_authority": False,
    }
    return {**body, "digest": _sha(body)}


def _stub_tool_gateway(
    *,
    node_id: str,
    spec: Mapping[str, Any],
    plan_digest: str,
    approved_by: str,
    msda_decision: Mapping[str, Any],
) -> dict[str, Any]:
    """In-process B7-aligned stub tools only — no shell, no network, no MCP servers."""
    payload = spec.get("payload") if isinstance(spec.get("payload"), Mapping) else {}
    tool_id = str(payload.get("tool_id") or "builtin.echo")
    if tool_id not in _STUB_TOOL_ALLOWLIST:
        raise GatewayNodeError(
            f"stub_tool mode allows only {sorted(_STUB_TOOL_ALLOWLIST)}; got {tool_id!r}"
        )
    arguments = payload.get("arguments") if isinstance(payload.get("arguments"), Mapping) else {}
    if tool_id == "builtin.echo":
        text = arguments.get("text", payload.get("text", f"gateway:{node_id}"))
        stdout = str(text)
    else:  # builtin.utc_static
        stdout = "2026-07-01T10:00:00Z"

    body = {
        "kind": "builder_ii.wrp.gateway_tool_stub",
        "mode": "stub_tool",
        "node_id": node_id,
        "tool_id": tool_id,
        "stdout": stdout[:512],
        "plan_digest": plan_digest,
        "approved_by": approved_by,
        "msda_decision_digest": msda_decision.get("digest"),
        "performs_network": False,
        "executes_tool_stub": True,
        "executes_shell": False,
        "grants_authority": False,
        "aligns_b7_allowlist": True,
    }
    return {**body, "digest": _sha(body)}


def run_gateway_node(
    *,
    node_id: str,
    node_type: str,
    spec: Mapping[str, Any],
    handoff_state: Mapping[str, Any],
    plan_digest: str,
    approved_by: str,
    gateway_mode: str = "record",
    msda_policy: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], str | None]:
    """Execute one gateway node. Returns (event, new_state, trajectory_delta, error).

    Signature matches graph_runtime gateway_handler contract.
    """
    if node_type not in GATEWAY_NODE_TYPES:
        return (
            {
                "node_id": node_id,
                "status": "failed",
                "cost_estimate": float(spec.get("cost_estimate", 0.0)),
                "error": f"not a gateway node type: {node_type!r}",
            },
            dict(handoff_state),
            {},
            f"not a gateway node type: {node_type!r}",
        )
    mode = str(gateway_mode or "record")
    if mode not in GATEWAY_MODES:
        msg = f"unknown gateway_mode {mode!r} (supported: {sorted(GATEWAY_MODES)})"
        return (
            {
                "node_id": node_id,
                "status": "failed",
                "cost_estimate": float(spec.get("cost_estimate", 0.0)),
                "error": msg,
            },
            dict(handoff_state),
            {},
            msg,
        )
    if mode == "stub_tool" and node_type == "model_gateway":
        msg = "stub_tool mode is not valid for model_gateway (use record; no provider invoke in S2 v2 default)"
        return (
            {
                "node_id": node_id,
                "status": "failed",
                "cost_estimate": float(spec.get("cost_estimate", 0.0)),
                "error": msg,
            },
            dict(handoff_state),
            {},
            msg,
        )

    cost = float(spec.get("cost_estimate", 0.0))
    try:
        msda_decision = _msda_for_node(node_type=node_type, spec=spec, msda_policy=msda_policy)
        if node_type == "model_gateway":
            result = _record_model_gateway(
                node_id=node_id,
                spec=spec,
                plan_digest=plan_digest,
                approved_by=approved_by,
                msda_decision=msda_decision,
            )
        elif mode == "stub_tool":
            result = _stub_tool_gateway(
                node_id=node_id,
                spec=spec,
                plan_digest=plan_digest,
                approved_by=approved_by,
                msda_decision=msda_decision,
            )
        else:
            result = _record_tool_gateway(
                node_id=node_id,
                spec=spec,
                plan_digest=plan_digest,
                approved_by=approved_by,
                msda_decision=msda_decision,
            )
    except GatewayNodeError as exc:
        return (
            {
                "node_id": node_id,
                "status": "failed",
                "cost_estimate": cost,
                "error": str(exc),
                "node_type": node_type,
            },
            dict(handoff_state),
            {},
            str(exc),
        )

    new_state = {
        **dict(handoff_state),
        f"{node_id}_gateway_digest": result["digest"],
        "last_gateway_node": node_id,
        "last_gateway_type": node_type,
    }
    event = {
        "node_id": node_id,
        "status": "ok",
        "cost_estimate": cost,
        "error": None,
        "node_type": node_type,
        "gateway_mode": result.get("mode"),
        "gateway_digest": result["digest"],
    }
    return event, new_state, {node_id: result}, None
