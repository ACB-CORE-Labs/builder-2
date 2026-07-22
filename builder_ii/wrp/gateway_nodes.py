"""S2 v2 — HITL model/tool gateway nodes for the live lane.

Default mode is ``record``: forced MSDA preflight + digest-bound synthetic
gateway receipt fragments. No network, no shell, no cloud model call.

Optional modes (implemented; activation gated — not "unimplemented"):
- ``stub_tool`` — B7 in-process stub allowlist only
- ``invoke_local`` — ModelExecutionGateway local/stub seam
- ``invoke_cloud`` — harder-gated cloud seam (approval + spend cap + egress)

Honesty: default ``record`` does **not** mean cloud/local invoke code is
absent. See ``docs/HONESTY_PINS_VS_IMPLEMENTATION.md``.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from builder_ii.wrp.msda_preflight import MsdaPreflightDenied, assert_msda_preflight

GATEWAY_NODE_TYPES: frozenset[str] = frozenset({"model_gateway", "tool_gateway"})
# W2.2: invoke_cloud is a first-class mode with harder gates (approval path + budget +
# allow_cloud_models + egress record). Default remains record.
GATEWAY_MODES: frozenset[str] = frozenset({"record", "stub_tool", "invoke_local", "invoke_cloud"})
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
    payload = spec.get("payload")
    if not isinstance(payload, dict):
        payload = {}
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
    payload = spec.get("payload")
    if not isinstance(payload, dict):
        payload = {}
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


def _invoke_local_model_gateway(
    *,
    node_id: str,
    spec: Mapping[str, Any],
    plan_digest: str,
    approved_by: str,
    msda_decision: Mapping[str, Any],
    artifact_dir: Any = None,
    handoff_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke ModelExecutionGateway for local/stub providers only (the seam).

    Requires payload fields: model_id, prompt (or prompt_snippet), and for
    fail-closed governance: budget (dict), optional execution_policy/registry.
    Cloud risk_classification models are refused.
    """
    from pathlib import Path

    from builder_ii.core.config import load_settings
    from builder_ii.routing.model_budget import BudgetExceededError, create_model_budget
    from builder_ii.routing.model_client_registry import create_model_client_registry
    from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
    from builder_ii.routing.model_routing_policy import create_model_execution_policy
    from builder_ii.routing.price_book import create_default_price_book

    payload = spec.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    model_id = str(payload.get("model_id") or "").strip()
    if not model_id or model_id.startswith("record:") or model_id == "record-only-local":
        raise GatewayNodeError(
            "invoke_local requires a real registry model_id (not record-only-local)"
        )
    prompt = str(payload.get("prompt") or payload.get("prompt_snippet") or payload.get("task") or "")
    if not prompt.strip():
        raise GatewayNodeError("invoke_local requires payload.prompt (or prompt_snippet/task)")

    registry_raw = payload.get("registry")
    registry: dict[str, Any] = (
        dict(registry_raw) if isinstance(registry_raw, dict) else create_model_client_registry()
    )
    client_record: dict[str, Any] | None = None
    for client in registry.get("clients", []):
        if isinstance(client, dict) and client.get("model_id") == model_id:
            client_record = client
            break
    if client_record is None:
        raise GatewayNodeError(f"model_id {model_id!r} not found in registry")
    if not client_record.get("enabled"):
        # Auto-enable stub providers for governed tests / offline seam demos only when requested.
        if client_record.get("provider_id") in ("openai_stub_provider", "anthropic_stub_provider") and payload.get(
            "enable_stub_if_disabled"
        ):
            client_record = {**client_record, "enabled": True}
            clients = [
                client_record if isinstance(c, dict) and c.get("model_id") == model_id else c
                for c in registry.get("clients", [])
            ]
            registry = {**registry, "clients": clients}
        else:
            raise GatewayNodeError(f"model_id {model_id!r} is disabled in registry")

    risk = client_record.get("risk_classification")
    if risk == "cloud_external" and client_record.get("provider_id") not in (
        "openai_stub_provider",
        "anthropic_stub_provider",
    ):
        raise GatewayNodeError(
            "invoke_local refuses cloud_external providers (use gateway_mode=invoke_cloud; H6)"
        )

    # Budget required for seam — prefer payload, else chain from prior node debit.
    budget_raw = payload.get("budget")
    handoff = dict(handoff_state or {})
    budget: dict[str, Any]
    if budget_raw is None:
        chained = handoff.get("last_debited_budget")
        if isinstance(chained, dict):
            budget = dict(chained)
        elif payload.get("auto_budget") is True:
            budget = create_model_budget(
                session_id=str(payload.get("session_id") or f"wrp-{plan_digest[:12]}"),
                task_id=str(payload.get("task_id") or node_id),
                max_input_tokens=int(payload.get("max_input_tokens") or 50_000),
                max_output_tokens=int(payload.get("max_tokens") or 256),
                max_total_tokens=int(payload.get("max_total_tokens") or 50_000),
                max_usd=float(payload.get("max_usd") or 1.0),
            )
        else:
            raise GatewayNodeError(
                "invoke_local requires payload.budget, handoff last_debited_budget, or auto_budget=true"
            )
    elif isinstance(budget_raw, dict):
        budget = dict(budget_raw)
    else:
        raise GatewayNodeError("payload.budget must be an object")

    rec = {
        "kind": "builder_ii.model_routing_recommendation",
        "recommended_candidates": [{"model_id": model_id}],
    }
    policy_raw = payload.get("execution_policy")
    execution_policy: dict[str, Any]
    if isinstance(policy_raw, dict):
        execution_policy = dict(policy_raw)
    else:
        execution_policy = create_model_execution_policy(rec, max_tokens=int(payload.get("max_tokens") or 256))
    allowed = list(execution_policy.get("allowed_models") or [])
    if model_id not in allowed:
        execution_policy = {
            **execution_policy,
            "allowed_models": list(dict.fromkeys([*allowed, model_id])),
        }

    settings = load_settings()
    # Stub cloud models need allow_cloud_models for risk gate even though they are stubs.
    if client_record.get("provider_id") in ("openai_stub_provider", "anthropic_stub_provider"):
        if not getattr(settings, "allow_cloud_models", False):
            settings = type(settings)(**{**settings.__dict__, "allow_cloud_models": True})

    pb_raw = payload.get("price_book")
    price_book: dict[str, Any] = dict(pb_raw) if isinstance(pb_raw, dict) else create_default_price_book()
    gateway = ModelExecutionGateway(settings, registry, execution_policy, price_book=price_book)

    base = Path(artifact_dir) if artifact_dir is not None else Path(".builder/artifacts/wrp_invoke_local")
    base = base / plan_digest[:16] / node_id
    base.mkdir(parents=True, exist_ok=True)
    envelope_path = base / "envelope.json"
    receipt_path = base / "receipt.json"
    events_dir = base / "events"
    session_id = str(payload.get("session_id") or f"wrp-{plan_digest[:12]}")

    budget_path = base / "budget.json"
    approval_raw = payload.get("approval_path") or payload.get("cloud_call_approval_path")
    approval_path = Path(str(approval_raw)) if approval_raw else None
    try:
        envelope, receipt, debited_budget = gateway.run_model_call(
            model_id=model_id,
            prompt=prompt,
            system_prompt=str(payload.get("system_prompt") or "Answer helpfully.") or None,
            max_tokens=int(payload.get("max_tokens") or 256),
            temperature=payload.get("temperature"),
            envelope_path=envelope_path,
            receipt_path=receipt_path,
            approval_path=approval_path,
            ledger_bound=True,
            budget=budget,
            budget_path=budget_path,
            events_dir=events_dir,
            session_id=session_id,
        )
    except BudgetExceededError as exc:
        raise GatewayNodeError(f"budget denied: {exc}") from exc
    except Exception as exc:
        raise GatewayNodeError(f"invoke_local failed: {exc}") from exc

    body = {
        "kind": "builder_ii.wrp.gateway_model_invoke",
        "mode": "invoke_local",
        "node_id": node_id,
        "model_id": model_id,
        "plan_digest": plan_digest,
        "approved_by": approved_by,
        "msda_decision_digest": msda_decision.get("digest"),
        "envelope_digest": envelope.get("digest"),
        "receipt_digest": receipt.get("digest"),
        "cost_report": receipt.get("cost_report"),
        "budget_ref": receipt.get("budget_ref"),
        # Post-debit budget for multi-step chaining (next node must use this object).
        "debited_budget": debited_budget,
        "debited_budget_path": str(budget_path) if debited_budget is not None else None,
        "ledger_bound": True,
        "events_dir": str(events_dir),
        "performs_network": bool(envelope.get("performs_network_calls")),
        "executes_model_provider": True,
        "executes_shell": False,
        "cloud_provider_invoke": False,
        "grants_authority": False,
        "artifact_is_authority": False,
    }
    return {**body, "digest": _sha(body)}


def _invoke_cloud_model_gateway(
    *,
    node_id: str,
    spec: Mapping[str, Any],
    plan_digest: str,
    approved_by: str,
    msda_decision: Mapping[str, Any],
    artifact_dir: Any = None,
    handoff_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """W2.2 — harder-gated cloud seam: approval file + budget + allow_cloud + egress.

    Cloud stubs may run offline; real openai_compatible_cloud needs API key env.
    """
    from pathlib import Path

    from builder_ii.core.config import load_settings
    from builder_ii.routing.model_budget import BudgetExceededError, create_model_budget
    from builder_ii.routing.model_client_registry import create_model_client_registry
    from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
    from builder_ii.routing.model_routing_policy import create_model_execution_policy
    from builder_ii.routing.price_book import create_default_price_book

    payload = spec.get("payload")
    if not isinstance(payload, dict):
        payload = {}

    if not str(approved_by or "").strip():
        raise GatewayNodeError("invoke_cloud requires approved_by (HITL)")

    approval_raw = payload.get("approval_path") or payload.get("cloud_call_approval_path")
    if not approval_raw:
        raise GatewayNodeError(
            "invoke_cloud requires payload.approval_path (per-call cloud approval artifact)"
        )
    approval_path = Path(str(approval_raw))
    if not approval_path.is_file():
        raise GatewayNodeError(f"invoke_cloud approval_path not found: {approval_path}")

    model_id = str(payload.get("model_id") or "").strip()
    if not model_id:
        raise GatewayNodeError("invoke_cloud requires payload.model_id")
    prompt = str(payload.get("prompt") or payload.get("prompt_snippet") or payload.get("task") or "")
    if not prompt.strip():
        raise GatewayNodeError("invoke_cloud requires payload.prompt")

    hard_cap = payload.get("hard_spend_cap_usd")
    if hard_cap is None:
        hard_cap = payload.get("max_usd")
    if hard_cap is None:
        raise GatewayNodeError("invoke_cloud requires payload.hard_spend_cap_usd (or max_usd)")

    registry_raw = payload.get("registry")
    registry: dict[str, Any] = (
        dict(registry_raw) if isinstance(registry_raw, dict) else create_model_client_registry()
    )
    client_record: dict[str, Any] | None = None
    for client in registry.get("clients", []):
        if isinstance(client, dict) and client.get("model_id") == model_id:
            client_record = client
            break
    if client_record is None:
        raise GatewayNodeError(f"model_id {model_id!r} not found in registry")
    if not client_record.get("enabled"):
        if client_record.get("provider_id") in ("openai_stub_provider", "anthropic_stub_provider") and payload.get(
            "enable_stub_if_disabled"
        ):
            client_record = {**client_record, "enabled": True}
            clients = [
                client_record if isinstance(c, dict) and c.get("model_id") == model_id else c
                for c in registry.get("clients", [])
            ]
            registry = {**registry, "clients": clients}
        else:
            raise GatewayNodeError(f"model_id {model_id!r} is disabled in registry")

    if client_record.get("risk_classification") != "cloud_external":
        raise GatewayNodeError("invoke_cloud requires risk_classification=cloud_external")

    handoff = dict(handoff_state or {})
    budget_raw = payload.get("budget")
    if budget_raw is None:
        chained = handoff.get("last_debited_budget")
        if isinstance(chained, dict):
            budget = dict(chained)
        else:
            budget = create_model_budget(
                session_id=str(payload.get("session_id") or f"wrp-cloud-{plan_digest[:12]}"),
                task_id=str(payload.get("task_id") or node_id),
                max_input_tokens=int(payload.get("max_input_tokens") or 50_000),
                max_output_tokens=int(payload.get("max_tokens") or 256),
                max_total_tokens=int(payload.get("max_total_tokens") or 50_000),
                max_usd=float(hard_cap),
            )
    elif isinstance(budget_raw, dict):
        budget = dict(budget_raw)
    else:
        raise GatewayNodeError("payload.budget must be an object")

    # Hard spend cap: budget max_usd must be ≤ hard cap.
    if float(budget.get("max_usd") or 0.0) > float(hard_cap) + 1e-12:
        raise GatewayNodeError(
            f"invoke_cloud budget.max_usd {budget.get('max_usd')} exceeds hard_spend_cap_usd {hard_cap}"
        )

    rec = {
        "kind": "builder_ii.model_routing_recommendation",
        "recommended_candidates": [{"model_id": model_id}],
    }
    policy_raw = payload.get("execution_policy")
    if isinstance(policy_raw, dict):
        execution_policy = dict(policy_raw)
    else:
        execution_policy = create_model_execution_policy(rec, max_tokens=int(payload.get("max_tokens") or 256))
    allowed = list(execution_policy.get("allowed_models") or [])
    if model_id not in allowed:
        execution_policy = {
            **execution_policy,
            "allowed_models": list(dict.fromkeys([*allowed, model_id])),
        }

    settings = load_settings()
    if not getattr(settings, "allow_cloud_models", False):
        # Stubs may proceed when enable_stub_if_disabled + local ceremony for offline CI.
        if client_record.get("provider_id") in ("openai_stub_provider", "anthropic_stub_provider") and payload.get(
            "enable_stub_if_disabled"
        ):
            settings = type(settings)(**{**settings.__dict__, "allow_cloud_models": True})
        else:
            raise GatewayNodeError(
                "invoke_cloud denied: BUILDER_ALLOW_CLOUD_MODELS/settings.allow_cloud_models is false"
            )

    pb_raw = payload.get("price_book")
    price_book: dict[str, Any] = dict(pb_raw) if isinstance(pb_raw, dict) else create_default_price_book()
    gateway = ModelExecutionGateway(settings, registry, execution_policy, price_book=price_book)

    base = Path(artifact_dir) if artifact_dir is not None else Path(".builder/artifacts/wrp_invoke_cloud")
    base = base / plan_digest[:16] / node_id
    base.mkdir(parents=True, exist_ok=True)
    envelope_path = base / "envelope.json"
    receipt_path = base / "receipt.json"
    events_dir = base / "events"
    budget_path = base / "budget.json"
    session_id = str(payload.get("session_id") or f"wrp-cloud-{plan_digest[:12]}")

    try:
        envelope, receipt, debited_budget = gateway.run_model_call(
            model_id=model_id,
            prompt=prompt,
            system_prompt=str(payload.get("system_prompt") or "Answer helpfully.") or None,
            max_tokens=int(payload.get("max_tokens") or 256),
            temperature=payload.get("temperature"),
            envelope_path=envelope_path,
            receipt_path=receipt_path,
            approval_path=approval_path,
            ledger_bound=True,
            budget=budget,
            budget_path=budget_path,
            events_dir=events_dir,
            session_id=session_id,
        )
    except BudgetExceededError as exc:
        raise GatewayNodeError(f"budget denied: {exc}") from exc
    except Exception as exc:
        raise GatewayNodeError(f"invoke_cloud failed: {exc}") from exc

    egress = receipt.get("cloud_egress") if isinstance(receipt.get("cloud_egress"), dict) else {
        "kind": "builder_ii.cloud_egress_record",
        "provider_id": client_record.get("provider_id"),
        "model_id": model_id,
        "performs_network": bool(envelope.get("performs_network_calls")),
        "grants_authority": False,
    }

    body = {
        "kind": "builder_ii.wrp.gateway_model_invoke",
        "mode": "invoke_cloud",
        "node_id": node_id,
        "model_id": model_id,
        "plan_digest": plan_digest,
        "approved_by": approved_by,
        "msda_decision_digest": msda_decision.get("digest"),
        "envelope_digest": envelope.get("digest"),
        "receipt_digest": receipt.get("digest"),
        "cost_report": receipt.get("cost_report"),
        "budget_ref": receipt.get("budget_ref"),
        "debited_budget": debited_budget,
        "debited_budget_path": str(budget_path) if debited_budget is not None else None,
        "ledger_bound": True,
        "events_dir": str(events_dir),
        "hard_spend_cap_usd": float(hard_cap),
        "approval_path": str(approval_path),
        "cloud_egress": egress,
        "performs_network": bool(envelope.get("performs_network_calls")),
        "executes_model_provider": True,
        "executes_shell": False,
        "cloud_provider_invoke": True,
        "grants_authority": False,
        "artifact_is_authority": False,
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
    payload = spec.get("payload")
    if not isinstance(payload, dict):
        payload = {}
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
    payload = spec.get("payload")
    if not isinstance(payload, dict):
        payload = {}
    tool_id = str(payload.get("tool_id") or "builtin.echo")
    if tool_id not in _STUB_TOOL_ALLOWLIST:
        raise GatewayNodeError(
            f"stub_tool mode allows only {sorted(_STUB_TOOL_ALLOWLIST)}; got {tool_id!r}"
        )
    arguments = payload.get("arguments")
    if not isinstance(arguments, dict):
        arguments = {}
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
        msg = "stub_tool mode is not valid for model_gateway (use record, invoke_local, or invoke_cloud)"
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
    if mode in {"invoke_local", "invoke_cloud"} and node_type != "model_gateway":
        msg = f"{mode} mode is only valid for model_gateway"
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
            if mode == "invoke_local":
                result = _invoke_local_model_gateway(
                    node_id=node_id,
                    spec=spec,
                    plan_digest=plan_digest,
                    approved_by=approved_by,
                    msda_decision=msda_decision,
                    artifact_dir=(spec.get("payload") or {}).get("artifact_dir")
                    if isinstance(spec.get("payload"), dict)
                    else None,
                    handoff_state=handoff_state,
                )
            elif mode == "invoke_cloud":
                result = _invoke_cloud_model_gateway(
                    node_id=node_id,
                    spec=spec,
                    plan_digest=plan_digest,
                    approved_by=approved_by,
                    msda_decision=msda_decision,
                    artifact_dir=(spec.get("payload") or {}).get("artifact_dir")
                    if isinstance(spec.get("payload"), dict)
                    else None,
                    handoff_state=handoff_state,
                )
            else:
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
    # Chain post-debit budget for multi-step WRP runs (next model_gateway may read it).
    if isinstance(result.get("debited_budget"), dict):
        new_state["last_debited_budget"] = result["debited_budget"]
        new_state[f"{node_id}_debited_budget"] = result["debited_budget"]
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
