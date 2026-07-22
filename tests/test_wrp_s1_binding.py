"""S1: WRP recommendations operationally bound (still RECOMMENDATION_ONLY)."""

from __future__ import annotations

import os

import pytest

from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.routing.model_router import choose_model_alias
from builder_ii.routing.model_routing_policy import (
    create_model_routing_policy,
    create_model_routing_recommendation,
    validate_model_routing_recommendation,
)


def test_policy_require_wrp_binding_default_false() -> None:
    policy = create_model_routing_policy()
    assert policy.get("require_wrp_binding") is False


def test_recommendation_without_require_has_no_required_binding() -> None:
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    rec = create_model_routing_recommendation(
        policy=policy,
        registry=registry,
        request={"task_intent": "coding", "task_text": "implement a CLI command", "max_risk_classification": "local_network", "requires_tool_use": True},
    )
    assert rec.get("require_wrp_binding") is False
    # Advisory binding may still be present when task_text is provided
    if "wrp_binding" in rec:
        assert rec["wrp_binding"].get("required") is False
    assert validate_model_routing_recommendation(rec) == []


def test_recommendation_require_wrp_binding_includes_digest_and_prefers_alias() -> None:
    policy = create_model_routing_policy(require_wrp_binding=True)
    registry = create_model_client_registry()
    rec = create_model_routing_recommendation(
        policy=policy,
        registry=registry,
        request={
            "task_intent": "coding",
            "task_text": "implement a new CLI command for sessions",
            "max_risk_classification": "local_network",
            "requires_tool_use": True,
        },
    )
    assert rec["require_wrp_binding"] is True
    binding = rec["wrp_binding"]
    assert binding["required"] is True
    assert len(binding["classification_digest"]) == 64
    assert binding["recommended_model_alias"]
    assert binding["source_kind"] == "builder_ii.wrp.workload_classification"
    assert validate_model_routing_recommendation(rec) == []
    top = rec["recommended_candidates"][0]
    # Prefer WRP alias when it is among candidates
    assert top["model_alias"] == binding["recommended_model_alias"] or "wrp_alias_excluded_reason" in binding


def test_validator_fails_when_require_true_but_binding_missing() -> None:
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    rec = create_model_routing_recommendation(
        policy=policy,
        registry=registry,
        request={"task_intent": "coding", "max_risk_classification": "local_network", "requires_tool_use": True},
    )
    rec["require_wrp_binding"] = True
    rec.pop("wrp_binding", None)
    errors = validate_model_routing_recommendation(rec)
    assert any("wrp_binding" in e for e in errors)


def test_require_wrp_binding_fail_closed_on_empty_task() -> None:
    policy = create_model_routing_policy(require_wrp_binding=True)
    registry = create_model_client_registry()
    with pytest.raises(ValueError, match="require_wrp_binding"):
        create_model_routing_recommendation(
            policy=policy,
            registry=registry,
            request={"task_intent": "", "task_text": "", "max_risk_classification": "local_network"},
        )


def test_model_router_bind_env_selects_wrp_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUILDER_II_WRP_BIND", "1")
    tier, alias, confidence, rationale = choose_model_alias("implement a new CLI command for sessions")
    assert alias in {"qwen-coder", "phi-reasoning"}
    assert "WRP BIND active" in rationale
    assert confidence in {"high", "medium", "low"}
    # Without bind, advisory only
    monkeypatch.delenv("BUILDER_II_WRP_BIND", raising=False)
    # clear any leftover
    os.environ.pop("BUILDER_II_WRP_BIND", None)
    _t2, _a2, _c2, rationale2 = choose_model_alias("implement a new CLI command for sessions")
    assert "WRP BIND active" not in rationale2
