"""Phase 2 – Intent-Based Cognitive Routing.

On an M1 with 16GB of unified memory, only one quantized model can be
loaded at a time. This module acts as a fast-pass semantic filter:

- Fast tier  → gemma-4-e4b (4.8 GB) or qwen2.5-coder-7b (4.5 GB)
  Triggered by exploratory/read-only intent.

- Primary tier → gemma-4-12b (6.5 GB), deepseek-coder-v2-lite, llama-3.1-8b
  Triggered by structural/generative/verification intent.

planner_same_as_execution is always True to prevent memory thrashing.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

SESSION_MODES = ("orchestrator", "quick", "deep", "coding")

# ---------------------------------------------------------------------------
# Tier classification patterns
# ---------------------------------------------------------------------------

# Exploratory / read-only keywords → fast tier
_FAST_PATTERNS = re.compile(
    r"\b("
    r"explain|what|where|find|search|list|describe|summarize"
    r"|doc|read|show|print|trace|outline|lookup|check|inspect"
    r"|display|query|report|scan|count|status"
    r")\b",
    re.IGNORECASE,
)

# Structural / generative / destructive keywords → primary tier
_DEEP_PATTERNS = re.compile(
    r"\b("
    r"implement|fix|verify|write|refactor|review|debug|add|create"
    r"|patch|build|generate|migrate|optimize|port|rewrite|test"
    r"|benchmark|profile|delete|remove|replace|rename|restructure"
    r"|analyze|audit|enforce|validate|simulate"
    r")\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SessionPlan:
    """Routing decision for a single Goose session."""
    mode: str
    model_tier: str           # 'fast' | 'primary'
    recipe_name: str
    planner_same_as_execution: bool  # Always True on M1 16GB
    confidence: str           # 'high' | 'low' (regex matched vs default)
    rationale: str            # Human-readable explanation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def recipe_for_mode(mode: str) -> str:
    if mode == "coding":
        return "core-coding.yaml"
    return "core-platform.yaml"


def tier_for_mode(mode: str) -> str:
    if mode == "quick":
        return "fast"
    if mode in ("deep", "orchestrator"):
        return "primary"
    return "primary"


def classify_task(text: str) -> tuple[str, str, str]:
    """Return (tier, confidence, rationale) for a free-text task hint.

    Priority: deep patterns win over fast patterns when both match,
    because structural work is always safer to run at full capacity.
    """
    deep_match = _DEEP_PATTERNS.search(text)
    fast_match = _FAST_PATTERNS.search(text)

    if deep_match:
        return (
            "primary",
            "high",
            f"Structural keyword '{deep_match.group()}' detected → primary tier",
        )
    if fast_match:
        return (
            "fast",
            "high",
            f"Exploratory keyword '{fast_match.group()}' detected → fast tier",
        )
    return (
        "primary",
        "low",
        "No strong signal detected; defaulting to primary tier (safe)",
    )


# ---------------------------------------------------------------------------
# Session planning
# ---------------------------------------------------------------------------

def plan_session(mode: str = "orchestrator", task_hint: str = "") -> SessionPlan:
    """Return a routing plan for the given mode and optional task hint.

    In orchestrator mode, task_hint drives semantic interception.
    In all other modes, the mode itself determines the tier.
    planner_same_as_execution is always True: one model at a time on M1.
    """
    if mode not in SESSION_MODES:
        raise ValueError(f"mode must be one of {SESSION_MODES}, got {mode!r}")

    if mode == "orchestrator" and task_hint:
        tier, confidence, rationale = classify_task(task_hint)
    else:
        tier = tier_for_mode(mode)
        confidence = "high"
        rationale = f"Mode '{mode}' explicitly maps to {tier!r} tier"

    return SessionPlan(
        mode=mode,
        model_tier=tier,
        recipe_name=recipe_for_mode(mode),
        planner_same_as_execution=True,
        confidence=confidence,
        rationale=rationale,
    )


def explain_plan(plan: SessionPlan) -> str:
    """Return a human-readable routing explanation for CLI display."""
    lines = [
        f"Session mode  : {plan.mode}",
        f"Model tier    : {plan.model_tier}  (confidence: {plan.confidence})",
        f"Recipe        : {plan.recipe_name}",
        f"Planner=Exec  : {plan.planner_same_as_execution}  (M1 16GB — one model at a time)",
        f"Rationale     : {plan.rationale}",
    ]
    return "\n".join(lines)
