"""Intent-based cognitive routing for local CORE agent sessions.

The router is deliberately conservative for M1 16GB hardware. It does not try
to load a second planner model. It selects one concrete model alias for the
whole Goose session and records the routing rationale so the user can see why
that model was chosen.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from builder_ii.core.config import normalize_model_alias

SESSION_MODES = ("orchestrator", "quick", "deep", "coding")

# Exploratory / read-only keywords -> fast tier. Phi is preferred because its
# tiny footprint leaves maximum unified-memory headroom for KV cache.
_FAST_PATTERNS = re.compile(
    r"\b("
    r"explain|what|where|find|search|list|describe|summarize"
    r"|doc|read|show|print|trace|outline|lookup|check|inspect"
    r"|display|query|report|scan|count|status"
    r")\b",
    re.IGNORECASE,
)

# Structural/generative work -> primary tier. Qwen2.5-Coder 7B is the default
# implementation model because it is code-specialized without overfilling RAM.
_DEEP_PATTERNS = re.compile(
    r"\b("
    r"implement|fix|write|refactor|debug|add|create|patch|build"
    r"|generate|migrate|optimize|port|rewrite|test|delete|remove"
    r"|replace|rename|restructure"
    r")\b",
    re.IGNORECASE,
)

# Formal review, invariant reasoning, and audit work benefits from the stricter
# small reasoning model even when it is not purely read-only.
_LOGIC_PATTERNS = re.compile(
    r"\b("
    r"audit|review|verify|validate|prove|proof|invariant|versor"
    r"|cga|clifford|algebra|determine|refusal|refuse|safety"
    r"|governance|contract|adr|simulate|benchmark|profile"
    r")\b",
    re.IGNORECASE,
)

# Heavy context hints are not automatically routed to a heavy model. The M1
# policy is to keep heavy candidates explicit opt-in via `builder switch-model`.
_HEAVY_HINTS = re.compile(
    r"\b(whole repo|entire repo|deep refactor|large refactor|multi-file sweep|"
    r"cross-module|call graph|global migration|architecture-wide)\b",
    re.IGNORECASE,
)


def _snippet(text: str, limit: int = 80) -> str:
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def tier_for_alias(alias: str) -> str:
    if alias in {"phi-reasoning", "gemma-fast"}:
        return "fast"
    return "primary"


@dataclass(frozen=True)
class SessionPlan:
    """Routing decision for a single Goose session."""

    mode: str
    model_tier: str  # 'fast' | 'primary'
    model_alias: str
    recipe_name: str
    planner_same_as_execution: bool  # Always True on M1 16GB
    confidence: str  # 'high' | 'medium' | 'low'
    rationale: str
    target_name: str = "builder"
    agent_profile: str = "patch_planner"


def recipe_for_mode(mode: str) -> str:
    if mode == "coding":
        return "core-coding.yaml"
    return "core-platform.yaml"


def tier_for_mode(mode: str) -> str:
    if mode == "quick":
        return "fast"
    return "primary"


def alias_for_mode(mode: str) -> str:
    if mode == "quick":
        return "phi-reasoning"
    return "qwen-coder"


def classify_task(text: str) -> tuple[str, str, str]:
    """Return (tier, confidence, rationale) for backward-compatible callers.

    Deep patterns win over fast patterns unless the task is explicitly a formal
    audit/review/verification job, in which case Phi's small reasoning profile
    is preferred. Use choose_model_alias() when the concrete model matters.
    """
    tier, _alias, confidence, rationale = choose_model_alias(text)
    return tier, confidence, rationale


def choose_model_alias(text: str) -> tuple[str, str, str, str]:
    """Return (tier, model_alias, confidence, rationale) for a free-text task."""
    logic_match = _LOGIC_PATTERNS.search(text)
    deep_match = _DEEP_PATTERNS.search(text)
    fast_match = _FAST_PATTERNS.search(text)
    heavy_match = _HEAVY_HINTS.search(text)
    task_snippet = _snippet(text)

    if logic_match and not deep_match:
        tier, alias, confidence, rationale = (
            "fast",
            "phi-reasoning",
            "high",
            f"Formal/constraint keyword '{logic_match.group()}' detected in task '{task_snippet}' -> phi-reasoning",
        )
    elif deep_match:
        extra = ""
        if heavy_match:
            extra = "; heavy-context hint detected, but M1 policy keeps heavy models explicit opt-in"
        tier, alias, confidence, rationale = (
            "primary",
            "qwen-coder",
            "high",
            f"Implementation keyword '{deep_match.group()}' detected in task '{task_snippet}' -> qwen-coder{extra}",
        )
    elif logic_match:
        tier, alias, confidence, rationale = (
            "fast",
            "phi-reasoning",
            "high",
            f"Formal/constraint keyword '{logic_match.group()}' detected in task '{task_snippet}' -> phi-reasoning",
        )
    elif fast_match:
        tier, alias, confidence, rationale = (
            "fast",
            "phi-reasoning",
            "high",
            f"Exploratory keyword '{fast_match.group()}' detected in task '{task_snippet}' -> phi-reasoning",
        )
    else:
        tier, alias, confidence, rationale = (
            "primary",
            "qwen-coder",
            "low",
            "No strong signal detected; defaulting to qwen-coder implementation lane",
        )

    wrp_bind = os.getenv("BUILDER_II_WRP_BIND", "").strip().lower() in {"1", "true", "yes", "on"}
    try:
        from builder_ii.wrp.workload_classifier import classify_workload
        wrp_res = classify_workload(text=text)
        wrp_clf = wrp_res["classification"]
        wrp_alias = wrp_res["recommended_model_alias"]
        wrp_tier = wrp_clf["tier"]
        wrp_conf = wrp_clf["confidence"]
        rationale += (
            f" [WRP Recommendation: tier={wrp_tier}, alias={wrp_alias}, "
            f"rationale={wrp_clf['rationale']}]"
        )
        # S1 bind: when BUILDER_II_WRP_BIND is set, WRP wins if confidence is high/medium.
        if wrp_bind and wrp_conf in {"high", "medium"}:
            tier = wrp_tier if wrp_tier in {"fast", "primary", "primary_constrained"} else tier
            # Map primary_constrained → primary lane alias (still qwen-coder under M1 defaults).
            if wrp_tier == "primary_constrained":
                tier = "primary"
            alias = wrp_alias
            confidence = wrp_conf
            rationale += f" [WRP BIND active: selected alias={alias} tier={tier}]"
    except (ImportError, KeyError):
        if wrp_bind:
            raise
    except Exception as exc:
        if wrp_bind:
            raise
        import sys
        sys.stderr.write(f"Warning: WRP workload classification failed: {exc}\n")

    return tier, alias, confidence, rationale


def plan_session(mode: str = "orchestrator", task_hint: str = "") -> SessionPlan:
    """Return a concrete routing plan for the given mode and optional task hint."""
    if mode not in SESSION_MODES:
        raise ValueError(f"mode must be one of {SESSION_MODES}, got {mode!r}")

    env_alias = os.getenv("CORE_AGENT_MODEL_ALIAS")
    if env_alias:
        alias = normalize_model_alias(env_alias, tier_fallback=tier_for_mode(mode))
        tier = tier_for_alias(alias)
        confidence = "high"
        rationale = f"CORE_AGENT_MODEL_ALIAS explicitly selects {alias!r}; task router is bypassed"
    elif task_hint:
        tier, alias, confidence, rationale = choose_model_alias(task_hint)
    else:
        tier = tier_for_mode(mode)
        alias = alias_for_mode(mode)
        confidence = "high"
        rationale = f"Mode '{mode}' explicitly maps to {alias!r} ({tier} tier)"

    return SessionPlan(
        mode=mode,
        model_tier=tier,
        model_alias=alias,
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
        f"Model alias   : {plan.model_alias}",
        f"Recipe        : {plan.recipe_name}",
        f"Planner=Exec  : {plan.planner_same_as_execution}  (M1 16GB - one model at a time)",
        f"Rationale     : {plan.rationale}",
    ]
    return "\n".join(lines)
