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
    "builder inspect hitl status",
    "builder inspect hitl chain",
    "builder inspect hitl pending",
    "builder inspect hitl approval",
    "builder inspect hitl evidence",
    "builder inspect hitl execution",
    "builder inspect hitl promote",
    "builder inspect hitl replay",
    "builder inspect profile status",
    "builder inspect profile lifecycle",
    "builder inspect profile validate",
    "builder inspect profile render-plan",
    "builder inspect profile dry-run",
    "builder inspect profile resolve",
    "builder inspect profile history",
    "builder inspect model routing show",
    "builder inspect model routing simulate",
    "builder inspect model routing candidates",
    "builder inspect model routing policy",
    "builder inspect model routing execution-policy",
    "builder inspect model routing validate",
    "builder inspect model registry show",
    "builder inspect model registry diff",
    "builder inspect promote status",
    "builder inspect promote readiness",
    "builder inspect promote artifact",
    "builder inspect promote decision",
    "builder inspect promote compatibility",
    "builder inspect promote history",
    "builder inspect promote gates",
    "builder inspect postflight status",
    "builder inspect postflight record",
    "builder inspect postflight verify",
    "builder inspect postflight governance",
    "builder inspect postflight actions",
    "builder inspect postflight refs",
    "builder inspect postflight validate",
    "builder inspect goose status",
    "builder inspect goose manifest",
    "builder inspect goose links",
    "builder inspect goose actions",
    "builder inspect goose governance",
    "builder inspect goose validate",
    "builder inspect goose approval",
    "builder inspect code-vault status",
    "builder inspect code-vault frame",
    "builder inspect code-vault determinism",
    "builder inspect code-vault recall",
    "builder inspect code-vault lint",
    "builder inspect code-vault context",
    "builder inspect code-vault governance",
    "builder inspect code-vault validate",
)

