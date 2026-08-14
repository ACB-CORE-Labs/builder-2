"""P2 remainder wires: fleet_binding, MSDA preflight, classifier↔embedder."""

from __future__ import annotations

import pytest

from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.routing.model_routing_policy import (
    create_model_routing_policy,
    create_model_routing_recommendation,
    validate_model_routing_recommendation,
)
from builder_ii.wrp.allocation_optimizer import allocate_fleet, validate_fleet_allocation
from builder_ii.wrp.governance_router import create_default_msda_policy
from builder_ii.wrp.msda_preflight import (
    MsdaPreflightDenied,
    assert_msda_preflight,
    msda_preflight_enabled,
    run_msda_preflight,
)
from builder_ii.wrp.workload_classifier import classify_workload


def test_allocate_fleet_emits_fleet_binding() -> None:
    rec = allocate_fleet(task_tier="primary", token_budget=100.0, non_trivial=False)
    assert validate_fleet_allocation(rec) == []
    binding = rec["fleet_binding"]
    assert binding["selected_alias"] == rec["allocation"]["primary_alias"]
    assert binding["grants_authority"] is False
    assert "token_budget_remaining" in binding
    assert binding["risk_class"]


def test_recommendation_consumes_fleet_binding_alias() -> None:
    fleet = allocate_fleet(task_tier="fast", token_budget=50.0)
    binding = fleet["fleet_binding"]
    policy = create_model_routing_policy()
    registry = create_model_client_registry()
    rec = create_model_routing_recommendation(
        policy=policy,
        registry=registry,
        request={
            "task_intent": "coding",
            "max_risk_classification": "local_network",
            "requires_tool_use": True,
            "fleet_binding": binding,
        },
    )
    assert validate_model_routing_recommendation(rec) == []
    assert rec["fleet_binding"]["selected_alias"] == binding["selected_alias"]
    # Prefer fleet alias when present in candidates
    top = rec["recommended_candidates"][0]
    assert top["model_alias"] == binding["selected_alias"] or any(
        c["model_alias"] == binding["selected_alias"] for c in rec["recommended_candidates"]
    )


def test_msda_preflight_skipped_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUILDER_II_WRP_MSDA_PREFLIGHT", raising=False)
    assert msda_preflight_enabled() is False
    assert assert_msda_preflight(tool="shell", data_domain="local_workspace") is None


def test_msda_preflight_denies_shell_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUILDER_II_WRP_MSDA_PREFLIGHT", "1")
    with pytest.raises(MsdaPreflightDenied):
        assert_msda_preflight(tool="shell", data_domain="local_workspace")


def test_msda_preflight_allows_local_readonly_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BUILDER_II_WRP_MSDA_PREFLIGHT", "1")
    decision = assert_msda_preflight(tool="repo_map", data_domain="local_workspace", risk="local_offline")
    assert decision is not None
    assert decision["decision"]["effect"] == "allow"


def test_msda_preflight_explicit_policy_allow_model_call() -> None:
    policy = create_default_msda_policy()
    # inject allow model_call for preflight tests without changing default package policy
    rules = list(policy.get("rules") or [])
    rules.insert(
        0,
        {
            "rule_id": "allow_model_call",
            "effect": "allow",
            "tools": ["model_call"],
            "data_domains": ["local_workspace"],
            "max_risk": "local_network",
        },
    )
    policy = {**policy, "rules": rules}
    decision = run_msda_preflight(
        tool="model_call",
        data_domain="local_workspace",
        risk="local_network",
        policy=policy,
    )
    assert decision["decision"]["effect"] == "allow"
    assert_msda_preflight(
        tool="model_call",
        data_domain="local_workspace",
        risk="local_network",
        policy=policy,
        enabled=True,
    )


def test_classifier_embedding_path_deterministic() -> None:
    a = classify_workload(text="implement a new CLI command for sessions", use_embedding=True)
    b = classify_workload(text="implement a new CLI command for sessions", use_embedding=True)
    assert a["classification"]["method"] == "embedding_knn"
    assert a["classification"]["embedder"]
    assert a["digest"] == b["digest"]
    assert a["recommended_model_alias"]
    assert a["executes_model"] is False


def test_classifier_default_still_metric_not_embed() -> None:
    rec = classify_workload(text="implement a new CLI command for sessions", use_embedding=False)
    assert rec["classification"]["method"] == "workload_metric"
    assert rec["classification"].get("embedder") is None
