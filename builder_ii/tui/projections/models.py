"""Model registry / routing / local config projection."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModelRow:
    name: str
    alias: str
    provider: str
    endpoint_kind: str
    context_window: int
    cost_class: str
    enabled: bool
    model_family: str


@dataclass(frozen=True)
class RoutingRuleView:
    rule_id: str
    task_intent: str
    preferred: tuple[str, ...]
    fallback: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class LocalModelConfigView:
    backend: str
    alias: str
    tier: str
    base_url: str
    temperature: str
    note: str


@dataclass(frozen=True)
class ModelMatrixView:
    rows: tuple[ModelRow, ...]
    backends: tuple[str, ...]
    rules: tuple[RoutingRuleView, ...]
    registry_state: str
    local: LocalModelConfigView
    compose_policy_render: str
    compose_models: str
    error: str | None = None


def _local_config() -> LocalModelConfigView:
    backend = os.environ.get("BUILDER_MODEL_BACKEND") or "—"
    alias = os.environ.get("BUILDER_MODEL_ALIAS") or "—"
    tier = os.environ.get("BUILDER_MODEL_TIER") or "—"
    base = os.environ.get("BUILDER_MODEL_BASE_URL") or "—"
    temp = os.environ.get("BUILDER_MODEL_TEMPERATURE") or "—"
    # Never surface API keys — only ref-ish env presence
    has_key_ref = any(
        os.environ.get(k) for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "XAI_API_KEY", "GROQ_API_KEY")
    )
    note = "cloud key env present (value hidden)" if has_key_ref else "no cloud API key env detected"
    return LocalModelConfigView(
        backend=str(backend),
        alias=str(alias),
        tier=str(tier),
        base_url=str(base),
        temperature=str(temp),
        note=note,
    )


def project_model_matrix() -> ModelMatrixView:
    rows: list[ModelRow] = []
    backends: list[str] = []
    rules: list[RoutingRuleView] = []
    registry_state = "—"
    error: str | None = None
    local = _local_config()

    try:
        from builder_ii.routing.model_client_registry import create_model_client_registry

        registry = create_model_client_registry()
        registry_state = str(registry.get("registry_state", "—"))
        clients = registry.get("clients") or []
        seen_backends: list[str] = []
        for client in clients:
            if not isinstance(client, dict):
                continue
            endpoint = str(client.get("endpoint_kind") or "unknown")
            if endpoint not in seen_backends:
                seen_backends.append(endpoint)
            rows.append(
                ModelRow(
                    name=str(client.get("model_name") or "—"),
                    alias=str(client.get("model_alias") or "—"),
                    provider=str(client.get("provider_name") or "—"),
                    endpoint_kind=endpoint,
                    context_window=int(client.get("context_window") or 0),
                    cost_class=str(client.get("cost_class") or "—"),
                    enabled=bool(client.get("enabled")),
                    model_family=str(client.get("model_family") or "—"),
                )
            )
        backends = seen_backends
    except Exception as exc:
        error = f"model registry: {exc}"

    try:
        from builder_ii.routing.model_routing_policy import create_model_routing_policy

        policy = create_model_routing_policy()
        for rule in policy.get("rules") or []:
            if not isinstance(rule, dict):
                continue
            preferred = (
                rule.get("preferred_model_lanes")
                or rule.get("preferred_clients")
                or rule.get("preferred_model_aliases")
                or []
            )
            fallback = (
                rule.get("fallback_model_lanes")
                or rule.get("fallback_clients")
                or rule.get("fallback_model_aliases")
                or []
            )
            if not isinstance(preferred, list):
                preferred = []
            if not isinstance(fallback, list):
                fallback = []
            rules.append(
                RoutingRuleView(
                    rule_id=str(rule.get("rule_id") or "—"),
                    task_intent=str(rule.get("task_intent") or "—"),
                    preferred=tuple(str(p) for p in preferred),
                    fallback=tuple(str(f) for f in fallback),
                    rationale=str(rule.get("rationale") or ""),
                )
            )
    except Exception as exc:
        if error:
            error = f"{error}; routing policy: {exc}"
        else:
            error = f"routing policy: {exc}"

    return ModelMatrixView(
        rows=tuple(rows),
        backends=tuple(backends),
        rules=tuple(rules),
        registry_state=registry_state,
        local=local,
        compose_policy_render=(
            "uv run builder-model-policy render --task-intent coding "
            "-o .builder/artifacts/model-routing-recommendation.json"
        ),
        compose_models="uv run builder models",
        error=error,
    )
