from __future__ import annotations

import re
from dataclasses import dataclass

SESSION_MODES = ("orchestrator", "quick", "deep", "coding")

# Keywords suggesting fast tier (explain, search, doc) vs deep (write, fix, test, review).
_FAST_PATTERNS = re.compile(
    r"\b(explain|what is|where is|find|search|list|describe|summarize|doc|read)\b",
    re.IGNORECASE,
)
_DEEP_PATTERNS = re.compile(
    r"\b(write|implement|fix|test|refactor|review|verify|debug|add|create|patch)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class SessionPlan:
    mode: str
    model_tier: str
    recipe_name: str
    planner_same_as_execution: bool


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


def classify_task(text: str) -> str:
    """Return model tier: fast or primary."""
    if _DEEP_PATTERNS.search(text):
        return "primary"
    if _FAST_PATTERNS.search(text):
        return "fast"
    return "primary"


def plan_session(mode: str = "orchestrator", task_hint: str = "") -> SessionPlan:
    if mode not in SESSION_MODES:
        raise ValueError(f"mode must be one of {SESSION_MODES}, got {mode!r}")
    tier = tier_for_mode(mode)
    if mode == "orchestrator" and task_hint:
        tier = classify_task(task_hint)
    return SessionPlan(
        mode=mode,
        model_tier=tier,
        recipe_name=recipe_for_mode(mode),
        planner_same_as_execution=True,  # M1 16GB: one model loaded at a time
    )