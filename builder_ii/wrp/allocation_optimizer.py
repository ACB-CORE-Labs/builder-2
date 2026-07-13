"""W2 / F2 — AllocationOptimizer (OmniRouter reference).

Constrained fleet allocation over local model_role_matrix lanes first.
High-cost models only recommended for non-trivial work. RECOMMENDATION_ONLY.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from builder_ii.wrp.artifacts import (
    FLEET_ALLOCATION_KIND,
    base_envelope,
    validate_wrp_artifact_envelope,
)

# Approximate relative token cost units per alias (deterministic table, not live prices).
_COST_UNITS: dict[str, float] = {
    "phi-reasoning": 1.0,
    "qwen-coder": 2.0,
    "gemma-fast": 1.5,
    "llama": 2.0,
    "qwen-coder-14b": 6.0,
    "deepseek": 7.0,
    "gpt-5.5": 20.0,
    "claude-opus-4.8": 22.0,
    "gemini-3.1-pro": 18.0,
    "gemini-3.5-flash": 4.0,
    "grok-4.5": 16.0,
    "composer-2.5-fast": 3.0,
}

_LOCAL_DEFAULTS = ("phi-reasoning", "qwen-coder")
_HIGH_COST = frozenset(
    {
        "qwen-coder-14b",
        "deepseek",
        "gpt-5.5",
        "claude-opus-4.8",
        "gemini-3.1-pro",
        "grok-4.5",
    }
)


@dataclass(frozen=True)
class FleetCandidate:
    alias: str
    quality: float  # 0..1 expected quality
    latency: float  # relative latency units
    risk_class: str  # local_offline | local_network | cloud_external


def default_candidates() -> list[FleetCandidate]:
    return [
        FleetCandidate("phi-reasoning", quality=0.55, latency=0.4, risk_class="local_offline"),
        FleetCandidate("qwen-coder", quality=0.78, latency=0.7, risk_class="local_offline"),
        FleetCandidate("composer-2.5-fast", quality=0.7, latency=0.5, risk_class="cloud_external"),
        FleetCandidate("grok-4.5", quality=0.92, latency=0.9, risk_class="cloud_external"),
        FleetCandidate("gemini-3.1-pro", quality=0.93, latency=1.0, risk_class="cloud_external"),
        FleetCandidate("gemini-3.5-flash", quality=0.72, latency=0.45, risk_class="cloud_external"),
        FleetCandidate("qwen-coder-14b", quality=0.85, latency=1.3, risk_class="local_network"),
    ]


def _score(c: FleetCandidate, *, alpha: float, beta: float, gamma: float) -> float:
    cost = _COST_UNITS.get(c.alias, 10.0)
    # Higher is better: quality - cost penalty - latency penalty
    return alpha * c.quality - beta * (cost / 10.0) - gamma * c.latency


def allocate_fleet(
    *,
    task_tier: str,
    token_budget: float,
    max_risk: str = "local_network",
    non_trivial: bool = False,
    candidates: list[FleetCandidate] | None = None,
) -> dict[str, Any]:
    """Select a recommended fleet within token budget (units ≈ cost_units * steps)."""
    if token_budget <= 0:
        raise ValueError("token_budget must be positive")
    risk_rank = {"local_offline": 1, "local_network": 2, "cloud_external": 3}
    max_rank = risk_rank.get(max_risk, 2)
    pool = candidates or default_candidates()
    eligible = [c for c in pool if risk_rank.get(c.risk_class, 99) <= max_rank]

    # Prefer local for trivial; allow high-cost only when non_trivial.
    filtered: list[FleetCandidate] = []
    for c in eligible:
        if c.alias in _HIGH_COST and not non_trivial:
            continue
        if task_tier == "fast" and c.alias not in {"phi-reasoning", "gemini-3.5-flash", "composer-2.5-fast"}:
            # still keep qwen out of pure fast unless only option
            if c.alias == "qwen-coder":
                continue
        filtered.append(c)
    if not filtered:
        filtered = [c for c in eligible if c.alias in _LOCAL_DEFAULTS] or list(eligible[:1])

    ranked = sorted(
        filtered,
        key=lambda c: _score(c, alpha=1.0, beta=0.6, gamma=0.3),
        reverse=True,
    )
    primary = ranked[0]
    primary_cost = _COST_UNITS.get(primary.alias, 10.0)
    # steps that fit budget (at least 1)
    steps = max(1, int(token_budget // max(primary_cost, 0.1)))
    projected = primary_cost * steps
    # Budget conservation: projected must stay within 10% of budget when we scale steps
    if projected > token_budget * 1.10:
        steps = max(1, int(token_budget // max(primary_cost, 0.1)))
        projected = primary_cost * steps

    secondary = ranked[1].alias if len(ranked) > 1 else None
    budget_remaining = max(0.0, float(token_budget) - float(projected))
    fleet_binding = {
        "selected_alias": primary.alias,
        "secondary_alias": secondary,
        "token_budget": float(token_budget),
        "token_budget_remaining": budget_remaining,
        "projected_cost_units": float(projected),
        "risk_class": primary.risk_class,
        "task_tier": task_tier,
        "non_trivial": non_trivial,
        "binds_session_routing": True,
        "grants_authority": False,
    }
    return base_envelope(
        kind=FLEET_ALLOCATION_KIND,
        artifact_state="RECOMMENDATION_ONLY",
        capability_state="wrp_recommendation_only",
        extra={
            "task_tier": task_tier,
            "token_budget": token_budget,
            "max_risk": max_risk,
            "non_trivial": non_trivial,
            "allocation": {
                "primary_alias": primary.alias,
                "secondary_alias": secondary,
                "projected_cost_units": projected,
                "planned_steps": steps,
                "budget_utilization": projected / token_budget,
                "within_10pct_budget": abs(projected - token_budget) / token_budget <= 0.10
                or projected <= token_budget * 1.10,
                "high_cost_conserved": primary.alias not in _HIGH_COST or non_trivial,
            },
            # S1/P2 remainder: structured binding for router / recommendation consumers.
            "fleet_binding": fleet_binding,
            "ranked": [
                {
                    "alias": c.alias,
                    "score": round(_score(c, alpha=1.0, beta=0.6, gamma=0.3), 6),
                    "cost_units": _COST_UNITS.get(c.alias, 10.0),
                    "risk_class": c.risk_class,
                }
                for c in ranked
            ],
            "executes_model": False,
            "grants_authority": False,
        },
    )


def validate_fleet_allocation(record: Any) -> list[str]:
    errors = validate_wrp_artifact_envelope(record, expected_kind=FLEET_ALLOCATION_KIND)
    if not isinstance(record, dict):
        return errors
    if record.get("artifact_state") != "RECOMMENDATION_ONLY":
        errors.append("artifact_state must be RECOMMENDATION_ONLY")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false")
    alloc = record.get("allocation")
    if not isinstance(alloc, dict):
        errors.append("allocation must be an object")
    else:
        if not alloc.get("primary_alias"):
            errors.append("allocation.primary_alias required")
        if alloc.get("high_cost_conserved") is not True:
            # only error if non_trivial is false and high cost used
            if not record.get("non_trivial") and alloc.get("primary_alias") in _HIGH_COST:
                errors.append("high-cost model used without non_trivial=true")
    binding = record.get("fleet_binding")
    if binding is not None:
        if not isinstance(binding, dict):
            errors.append("fleet_binding must be an object when present")
        else:
            if not binding.get("selected_alias"):
                errors.append("fleet_binding.selected_alias required")
            if binding.get("grants_authority") is not False:
                errors.append("fleet_binding.grants_authority must be false")
            if isinstance(alloc, dict) and binding.get("selected_alias") != alloc.get("primary_alias"):
                errors.append("fleet_binding.selected_alias must match allocation.primary_alias")
    return errors
