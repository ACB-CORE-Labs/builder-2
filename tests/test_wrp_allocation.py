from __future__ import annotations

from builder_ii.wrp.allocation_optimizer import allocate_fleet, validate_fleet_allocation


def test_allocation_valid_and_passive() -> None:
    art = allocate_fleet(task_tier="primary", token_budget=20.0, max_risk="local_network")
    assert validate_fleet_allocation(art) == []
    assert art["executes_model"] is False
    assert art["allocation"]["within_10pct_budget"] is True


def test_high_cost_conserved_for_trivial() -> None:
    art = allocate_fleet(task_tier="fast", token_budget=10.0, non_trivial=False, max_risk="cloud_external")
    assert art["allocation"]["primary_alias"] not in {
        "grok-4.5",
        "gemini-3.1-pro",
        "gpt-5.5",
        "claude-opus-4.8",
        "qwen-coder-14b",
        "deepseek",
    }


def test_non_trivial_may_select_high_cost() -> None:
    art = allocate_fleet(
        task_tier="primary",
        token_budget=100.0,
        non_trivial=True,
        max_risk="cloud_external",
    )
    assert validate_fleet_allocation(art) == []
    assert art["allocation"]["high_cost_conserved"] is True


def test_budget_stress_within_10_percent() -> None:
    for budget in (5.0, 10.0, 20.0, 50.0, 100.0):
        art = allocate_fleet(task_tier="primary", token_budget=budget, non_trivial=False)
        util = art["allocation"]["budget_utilization"]
        assert util <= 1.10 + 1e-9, f"budget={budget} util={util}"
