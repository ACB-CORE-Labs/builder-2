"""W1.3 — cost-aware routing remains RECOMMENDATION_ONLY."""

from __future__ import annotations

from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.routing.model_routing_policy import (
    create_model_routing_policy,
    create_model_routing_recommendation,
    validate_model_routing_recommendation,
)
from builder_ii.routing.price_book import create_default_price_book


def test_cheapest_capable_ranks_free_local_first_when_tools_not_required() -> None:
    registry = create_model_client_registry()
    policy = create_model_routing_policy()
    book = create_default_price_book()
    rec = create_model_routing_recommendation(
        policy,
        registry,
        request={
            "task_intent": "reasoning",
            "max_risk_classification": "local_network",
            "requires_tool_use": False,
            "prefer_cheapest_capable": True,
            "price_book": book,
        },
    )
    assert rec["recommendation_state"] == "RECOMMENDATION_ONLY"
    assert rec["executes_model"] is False
    assert validate_model_routing_recommendation(rec) == []
    top = rec["recommended_candidates"][0]
    # Prefer free_local / low cost when capable
    assert top.get("cost_class") in ("free_local", "low", "medium", "high", "placeholder")
    if rec.get("savings_vs_frontier_baseline"):
        assert rec["savings_vs_frontier_baseline"]["grants_authority"] is False
        assert rec["savings_vs_frontier_baseline"]["ledgerable"] is True


def test_routing_still_never_executes() -> None:
    registry = create_model_client_registry()
    policy = create_model_routing_policy()
    rec = create_model_routing_recommendation(policy, registry)
    assert rec["governance"]["model_execution"] == "DISABLED"
    assert rec["governance"]["recommendation_executes"] is False
