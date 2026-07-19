"""W1.1 — model budget deny/debit (immutable versions)."""

from __future__ import annotations

import pytest

from builder_ii.model_budget import (
    BudgetExceededError,
    assert_budget_allows_call,
    create_model_budget,
    debit_budget,
    project_call_cost,
    remaining,
    validate_model_budget,
)
from builder_ii.price_book import create_default_price_book


def test_create_and_validate_budget() -> None:
    b = create_model_budget(session_id="s1", max_usd=0.5)
    assert validate_model_budget(b) == []
    assert b["budget_state"] == "ACTIVE"
    assert b["budget_version"] == 1
    assert len(b["digest"]) == 64


def test_budget_deny_on_overspend() -> None:
    book = create_default_price_book()
    b = create_model_budget(
        session_id="s1",
        max_input_tokens=2,
        max_output_tokens=10,
        max_total_tokens=10,
        max_usd=100.0,
    )
    projected = project_call_cost(
        prompt="one two three four",
        max_output_tokens=5,
        model_id="gpt-4o-stub",
        price_book=book,
    )
    assert projected["input_tokens"] >= 4
    with pytest.raises(BudgetExceededError):
        assert_budget_allows_call(b, projected)


def test_debit_returns_new_version() -> None:
    b = create_model_budget(session_id="s1", max_total_tokens=1000, max_usd=10.0)
    cost = {
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "estimated_usd_total": 0.01,
    }
    b2 = debit_budget(b, cost)
    assert b2["budget_version"] == 2
    assert b2["spent_total_tokens"] == 15
    assert b2["spent_usd"] == 0.01
    # Original unchanged (immutable)
    assert b["spent_total_tokens"] == 0
    assert b["budget_version"] == 1
    rem = remaining(b2)
    assert rem["total_tokens"] == 985


def test_debit_exhausts_budget() -> None:
    b = create_model_budget(
        session_id="s1",
        max_input_tokens=10,
        max_output_tokens=10,
        max_total_tokens=10,
        max_usd=0.001,
    )
    cost = {
        "input_tokens": 10,
        "output_tokens": 0,
        "total_tokens": 10,
        "estimated_usd_total": 0.001,
    }
    b2 = debit_budget(b, cost)
    assert b2["budget_state"] == "EXHAUSTED"
    with pytest.raises(BudgetExceededError):
        assert_budget_allows_call(b2, {"input_tokens": 1, "output_tokens": 0, "total_tokens": 1, "estimated_usd_total": 0.0})
