"""V.4 — CORE target profile only (isolated; not platform identity).

All CORE-specific invariants, verification routing defaults, safe path catalogs,
and semgrep rule catalogs live here. Nothing in this module grants Workbench
coupling, runtime authority, or mutates generic/builder target profiles.

Promotion posture: spec_only / validation_only (target profile data + doctor).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from builder_ii.core.config import Settings

CORE_TARGET_NAME = "core"

# Explicit CORE engineering invariants (catalog for target-profile consumers).
# These are profile data, not enforcement engines.
CORE_INVARIANTS: tuple[dict[str, Any], ...] = (
    {
        "id": "versor_condition",
        "statement": "versor_condition(F) < 1e-6 for field-algebra changes",
        "enforcement": "target_profile_catalog",
        "grants_runtime": False,
    },
    {
        "id": "exact_cga_recall",
        "statement": "Exact CGA recall only — no ANN/HNSW/cosine vector indexes as truth",
        "enforcement": "target_profile_catalog",
        "grants_runtime": False,
    },
    {
        "id": "temperature_zero",
        "statement": "Model temperature 0 for deterministic agent lanes when used",
        "enforcement": "target_profile_catalog",
        "grants_runtime": False,
    },
    {
        "id": "speculative_until_cli_gates",
        "statement": "CORE capability claims remain SPECULATIVE until CLI gates pass",
        "enforcement": "target_profile_catalog",
        "grants_runtime": False,
    },
    {
        "id": "no_workbench_identity",
        "statement": "builder-II must not claim CORE Workbench/UI identity",
        "enforcement": "target_profile_catalog",
        "grants_runtime": False,
    },
)

# Verification routing defaults for CORE as a *target* (not platform defaults).
CORE_VERIFICATION_ROUTING_DEFAULTS: dict[str, Any] = {
    "default_verification_profile": "core_smoke",
    "preferred_commands": (
        "builder verify <changed-path>",
        "uv run pytest -q (focused suites under CORE repo)",
        "preserve CORE invariants before broad runs",
    ),
    "hitl_profiles_allowed": (
        "platform_status",
        "docs_audit",
    ),
    "target_code_profiles_require_risk_ack": True,
    "routes_generic_platform": False,
    "notes": (
        "CORE verification defaults apply only when target=core. "
        "They do not rewrite generic/builder verification policy."
    ),
}

# Safe / sensitive path *categories* (catalog). Not a runtime sandbox.
CORE_SAFE_FILE_PATH_CATEGORIES: dict[str, tuple[str, ...]] = {
    "preferred_context": (
        "README.md",
        "AGENTS.md",
        "GROK.md",
        "CLAUDE.md",
        "docs/",
        "tests/",
    ),
    "algebra_sensitive": (
        "**/algebra/**",
        "**/field/**",
        "**/vault/**",
        "**/cognition/**",
        "**/geometry/**",
    ),
    "deny_as_default_write_targets": (
        ".env",
        "**/*secret*",
        "**/credentials*",
        "**/.git/**",
    ),
    "artifact_only_ok": (
        ".builder/artifacts/**",
        "planning/evidence/**",
    ),
}

# CORE-specific semgrep rule *catalog* (ids + intent). Doctor does not run semgrep.
CORE_SEMGREP_RULES_CATALOG: tuple[dict[str, str], ...] = (
    {
        "id": "core.no-hardcoded-secrets",
        "intent": "Flag hardcoded API keys/tokens in CORE target sources",
        "severity": "error",
    },
    {
        "id": "core.no-ann-index-as-truth",
        "intent": "Flag ANN/HNSW/cosine index construction presented as CORE recall truth",
        "severity": "error",
    },
    {
        "id": "core.no-temperature-gt-zero",
        "intent": "Flag non-zero temperature in CORE agent/model config paths",
        "severity": "warning",
    },
    {
        "id": "core.no-workbench-coupling",
        "intent": "Flag imports or claims that bind builder-II to CORE Workbench/UI",
        "severity": "error",
    },
)


def core_profile_block() -> dict[str, Any]:
    """Immutable CORE-only extension block for target profile artifacts."""
    return {
        "target": CORE_TARGET_NAME,
        "isolation": "CORE_TARGET_ONLY",
        "workbench_coupling": "NONE",
        "grants_runtime_authority": False,
        "platform_identity": False,
        "invariants": [dict(item) for item in CORE_INVARIANTS],
        "verification_routing_defaults": {
            **CORE_VERIFICATION_ROUTING_DEFAULTS,
            "preferred_commands": list(CORE_VERIFICATION_ROUTING_DEFAULTS["preferred_commands"]),
            "hitl_profiles_allowed": list(CORE_VERIFICATION_ROUTING_DEFAULTS["hitl_profiles_allowed"]),
        },
        "safe_file_path_categories": {
            key: list(paths) for key, paths in CORE_SAFE_FILE_PATH_CATEGORIES.items()
        },
        "semgrep_rules_catalog": [dict(rule) for rule in CORE_SEMGREP_RULES_CATALOG],
        "semgrep_executed_by_profile": False,
        "promotion_state": "validation_only",
        "notes": (
            "V.4 CORE profile block: catalog + doctor only. "
            "Not Workbench; not S3; not generic platform policy."
        ),
    }


def validate_core_profile_block(block: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(block, dict):
        return ["core_profile must be an object"]
    if block.get("target") != CORE_TARGET_NAME:
        errors.append(f"core_profile.target must be {CORE_TARGET_NAME!r}")
    if block.get("isolation") != "CORE_TARGET_ONLY":
        errors.append("core_profile.isolation must be CORE_TARGET_ONLY")
    if block.get("workbench_coupling") != "NONE":
        errors.append("core_profile.workbench_coupling must be NONE")
    if block.get("grants_runtime_authority") is not False:
        errors.append("core_profile.grants_runtime_authority must be false")
    if block.get("platform_identity") is not False:
        errors.append("core_profile.platform_identity must be false")
    if block.get("semgrep_executed_by_profile") is not False:
        errors.append("core_profile.semgrep_executed_by_profile must be false")
    invariants = block.get("invariants")
    if not isinstance(invariants, list) or not invariants:
        errors.append("core_profile.invariants must be a non-empty list")
    else:
        ids = {item.get("id") for item in invariants if isinstance(item, dict)}
        for required in ("versor_condition", "exact_cga_recall", "no_workbench_identity"):
            if required not in ids:
                errors.append(f"core_profile.invariants missing {required}")
    routing = block.get("verification_routing_defaults")
    if not isinstance(routing, dict):
        errors.append("core_profile.verification_routing_defaults must be an object")
    elif routing.get("routes_generic_platform") is not False:
        errors.append("verification_routing_defaults.routes_generic_platform must be false")
    categories = block.get("safe_file_path_categories")
    if not isinstance(categories, dict) or "preferred_context" not in categories:
        errors.append("core_profile.safe_file_path_categories.preferred_context required")
    rules = block.get("semgrep_rules_catalog")
    if not isinstance(rules, list) or not rules:
        errors.append("core_profile.semgrep_rules_catalog must be a non-empty list")
    return errors


def doctor_core_profile(settings: Settings) -> dict[str, Any]:
    """Read-only doctor for CORE target isolation (validation_only).

    Does not run semgrep, does not mutate the CORE repo, does not start Workbench.
    """
    checks: list[dict[str, Any]] = []
    core_root = Path(settings.target_repo).expanduser().resolve(strict=False)
    block = core_profile_block()
    block_errors = validate_core_profile_block(block)
    checks.append(
        {
            "name": "core_profile_block_valid",
            "ok": not block_errors,
            "errors": block_errors,
        }
    )
    checks.append(
        {
            "name": "target_repo_path_configured",
            "ok": bool(str(core_root)),
            "path": str(core_root),
            "exists": core_root.exists(),
            "errors": [] if core_root else ["target_repo empty"],
        }
    )
    checks.append(
        {
            "name": "workbench_coupling_none",
            "ok": block.get("workbench_coupling") == "NONE",
            "errors": [] if block.get("workbench_coupling") == "NONE" else ["workbench coupling set"],
        }
    )
    checks.append(
        {
            "name": "not_platform_identity",
            "ok": block.get("platform_identity") is False,
            "errors": [] if block.get("platform_identity") is False else ["claims platform identity"],
        }
    )
    checks.append(
        {
            "name": "semgrep_catalog_only",
            "ok": block.get("semgrep_executed_by_profile") is False
            and isinstance(block.get("semgrep_rules_catalog"), list)
            and len(block.get("semgrep_rules_catalog") or []) >= 1,
            "rule_count": len(block.get("semgrep_rules_catalog") or []),
            "errors": [],
        }
    )
    checks.append(
        {
            "name": "invariants_catalog_present",
            "ok": len(block.get("invariants") or []) >= 3,
            "count": len(block.get("invariants") or []),
            "errors": [],
        }
    )
    ok = all(c.get("ok") for c in checks)
    return {
        "kind": "builder_ii.target_profile_doctor_report",
        "schema_version": 1,
        "target": CORE_TARGET_NAME,
        "ok": ok,
        "checks": checks,
        "core_profile": block,
        "grants_runtime_authority": False,
        "workbench_coupling": "NONE",
        "semgrep_executed": False,
        "promotion_state": "validation_only",
        "notes": (
            "V.4 CORE target doctor: isolation + catalog checks only. "
            "Does not execute semgrep or CORE runtime."
        ),
    }
