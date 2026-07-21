"""Authority tier, promotion state, and approval mode constants."""
from __future__ import annotations

# Standard authority tiers
TIER_0 = "Tier 0 — read-only inspection"
TIER_1 = "Tier 1 — artifact-only planning/validation"
TIER_2 = "Tier 2 — operator-managed setup/runtime helper"
TIER_3 = "Tier 3 — HITL-gated execution candidate"
TIER_4 = "Tier 4 — forbidden/unpromoted automation"

VALID_TIERS = {TIER_0, TIER_1, TIER_2, TIER_3, TIER_4}

# Valid promotion states
STATE_SPEC_ONLY = "spec_only"
STATE_SMOKE_ONLY = "smoke_only"
STATE_ARTIFACT_ONLY = "artifact_only"
STATE_VALIDATION_ONLY = "validation_only"
STATE_READ_ONLY_RUNTIME_CANDIDATE = "read_only_runtime_candidate"
STATE_OPERATOR_MANAGED = "operator_managed"
STATE_HITL_RUNTIME_CANDIDATE = "hitl_runtime_candidate"
STATE_FORBIDDEN_UNPROMOTED = "forbidden_unpromoted"
STATE_ENABLED = "enabled"

VALID_PROMOTION_STATES = {
    STATE_SPEC_ONLY,
    STATE_SMOKE_ONLY,
    STATE_ARTIFACT_ONLY,
    STATE_VALIDATION_ONLY,
    STATE_READ_ONLY_RUNTIME_CANDIDATE,
    STATE_OPERATOR_MANAGED,
    STATE_HITL_RUNTIME_CANDIDATE,
    STATE_FORBIDDEN_UNPROMOTED,
    STATE_ENABLED,
}


# Valid approval modes
MODE_NONE = "none"
MODE_EXPLICIT_OPERATOR_INVOCATION = "explicit_operator_invocation"
MODE_HITL_ARTIFACT_REQUIRED = "hitl_artifact_required"
MODE_FORBIDDEN_UNPROMOTED = "forbidden_unpromoted"

VALID_APPROVAL_MODES = {
    MODE_NONE,
    MODE_EXPLICIT_OPERATOR_INVOCATION,
    MODE_HITL_ARTIFACT_REQUIRED,
    MODE_FORBIDDEN_UNPROMOTED,
}

READONLY_TUI_COMMANDS: tuple[str, ...] = (
    "builder hitl status",
    "builder hitl chain",
    "builder hitl pending",
    "builder hitl approval",
    "builder hitl evidence",
    "builder hitl execution",
    "builder hitl promote",
    "builder hitl replay",
    "builder profile status",
    "builder profile lifecycle",
    "builder profile validate",
    "builder profile render-plan",
    "builder profile dry-run",
    "builder profile resolve",
    "builder profile history",
    "builder model routing show",
    "builder model routing simulate",
    "builder model routing candidates",
    "builder model routing policy",
    "builder model routing execution-policy",
    "builder model routing validate",
    "builder model registry show",
    "builder model registry diff",
    "builder promote status",
    "builder promote readiness",
    "builder promote artifact",
    "builder promote decision",
    "builder promote compatibility",
    "builder promote history",
    "builder promote gates",
    "builder postflight status",
    "builder postflight record",
    "builder postflight verify",
    "builder postflight governance",
    "builder postflight actions",
    "builder postflight refs",
    "builder postflight validate",
    "builder goose status",
    "builder goose manifest",
    "builder goose links",
    "builder goose actions",
    "builder goose governance",
    "builder goose validate",
    "builder goose approval",
    "builder code-vault status",
    "builder code-vault frame",
    "builder code-vault determinism",
    "builder code-vault recall",
    "builder code-vault lint",
    "builder code-vault context",
    "builder code-vault governance",
    "builder code-vault validate",
)

