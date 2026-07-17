"""Passive Goose setup metadata for governed R1 planning.

R1.4 reconciles legacy setup surfaces by keeping Goose setup representation in
passive configuration/overlay form and redirecting operators to the governed
`builder-setup` artifact chain. This module intentionally avoids direct
filesystem mutation, skill copying, recipe validation, Goose startup, or
subprocess execution.
"""

from __future__ import annotations

from pathlib import Path

from builder_ii.config import Settings, load_settings

SETUP_REDIRECT_KIND = "builder_ii.legacy_setup_redirect_report"


def goose_config_dir() -> Path:
    return Path.home() / ".config" / "goose"


def skills_source(settings: Settings) -> Path:
    return settings.project_root / ".agents" / "skills"



def build_goose_config(settings: Settings) -> dict:
    """Build the passive Goose config overlay candidate structure."""
    recipes = settings.project_root / "recipes"
    return {
        "GOOSE_TEMPERATURE": settings.temperature,
        "GOOSE_MODE": "auto",
        "GOOSE_MAX_TURNS": 1000,
        "GOOSE_AUTO_COMPACT_THRESHOLD": 0.8,
        "GOOSE_CLI_SHOW_COST": False,
        "GOOSE_RECIPE_PATH": str(recipes),
        "slash_commands": [
            {"command": "explore", "recipe_path": str(recipes / "subrecipes" / "explore.yaml")},
            {"command": "implement", "recipe_path": str(recipes / "subrecipes" / "implement.yaml")},
            {"command": "review", "recipe_path": str(recipes / "subrecipes" / "review.yaml")},
            {"command": "verify", "recipe_path": str(recipes / "subrecipes" / "verify.yaml")},
            {"command": "plan", "recipe_path": str(recipes / "subrecipes" / "plan.yaml")},
            {"command": "platform", "recipe_path": str(recipes / "core-platform.yaml")},
            {"command": "coding", "recipe_path": str(recipes / "core-coding.yaml")},
        ],
        "extensions": {
            "developer": {
                "bundled": True,
                "enabled": True,
                "name": "developer",
                "timeout": 600,
                "type": "builtin",
                "description": "Filesystem and shell tools for edit-test-fix loops",
            },
            "skills": {
                "bundled": True,
                "enabled": True,
                "name": "skills",
                "timeout": 300,
                "type": "platform",
                "description": "builder-II governed coding skills",
            },
            "summon": {
                "bundled": True,
                "enabled": True,
                "name": "summon",
                "timeout": 300,
                "type": "platform",
                "description": "Sub-agent spawning for plan/implement/verify pipeline",
            },
        },
    }


def governed_setup_command_sequence() -> tuple[str, ...]:
    return (
        "builder-setup plan --output /tmp/builder-ii-setup-plan.json",
        "builder-setup validate-plan /tmp/builder-ii-setup-plan.json",
        "builder-setup overlay-plan /tmp/builder-ii-setup-plan.json --output /tmp/builder-ii-setup-overlay.json",
        "builder-setup validate-overlay-plan /tmp/builder-ii-setup-overlay.json",
        "builder-setup rollback-snapshot /tmp/builder-ii-setup-overlay.json --output /tmp/builder-ii-setup-rollback-snapshot.json",
        "builder-setup validate-rollback-snapshot /tmp/builder-ii-setup-rollback-snapshot.json",
        "builder-setup apply /tmp/builder-ii-setup-overlay.json --rollback-snapshot /tmp/builder-ii-setup-rollback-snapshot.json --approve-digest <overlay_plan_digest> --output /tmp/builder-ii-setup-receipt.json",
        "builder-setup validate-receipt /tmp/builder-ii-setup-receipt.json",
        "builder-setup rollback /tmp/builder-ii-setup-receipt.json --rollback-snapshot /tmp/builder-ii-setup-rollback-snapshot.json --approve-digest <setup_receipt_digest> --output /tmp/builder-ii-setup-rollback-receipt.json",
        "builder-setup validate-rollback-receipt /tmp/builder-ii-setup-rollback-receipt.json",
    )


def legacy_setup_surface_rows(settings: Settings) -> tuple[dict[str, str], ...]:
    return (
        {
            "surface": "builder setup",
            "current_behavior": "Legacy one-shot helper previously wrote Goose config, .goosehints, session context, skill installs, and ran Goose recipe validation.",
            "reconciled_behavior": "Disabled compatibility wrapper. Prints governed R1 command sequence and fails closed without writes.",
            "reconciliation_mode": "disabled_redirect",
            "authority_tier": "Tier 1 compatibility redirect",
            "write_runtime_boundary": "No setup writes, no Goose runtime start, no subprocess/shell, no model/provider, no MCP/tool, and no patch authority.",
        },
        {
            "surface": "builder_ii/goose_setup.py",
            "current_behavior": "Represents Goose config, slash-command, and skill-source metadata for setup planning.",
            "reconciled_behavior": "Passive overlay/config candidate helper only. No direct config writes, skill copying, or recipe validation remain in this module.",
            "reconciliation_mode": "passive_only",
            "authority_tier": "Tier 1 passive metadata",
            "write_runtime_boundary": "No writes or runtime activation; artifacts remain non-authoritative.",
        },
        {
            "surface": "builder start",
            "current_behavior": "Legacy runtime helper can launch backend and Goose when explicitly invoked by the operator.",
            "reconciled_behavior": "No longer auto-runs legacy setup writes before runtime launch.",
            "reconciliation_mode": "runtime_decoupled",
            "authority_tier": "Tier 2 operator-managed runtime helper",
            "write_runtime_boundary": "Runtime start remains operator-managed; setup reconciliation must go through builder-setup artifacts and digest-bound apply/rollback when writes are needed.",
        },
        {
            "surface": "builder_ii/goose_launcher.py",
            "current_behavior": "Launches Goose runtime and writes only transient session-context metadata needed by an active operator-launched session.",
            "reconciled_behavior": "Runtime-only helper. No Goose setup delegation, config writes, skill installs, or recipe validation.",
            "reconciliation_mode": "runtime_only",
            "authority_tier": "Tier 2 operator-managed runtime helper",
            "write_runtime_boundary": "No setup writes; no bypass around governed builder-setup apply/rollback.",
        },
        {
            "surface": "docs setup instructions",
            "current_behavior": "Historical docs referenced direct builder setup behavior.",
            "reconciled_behavior": "Docs must redirect operators to builder-setup plan/overlay/rollback-snapshot/apply/rollback and state that Goose runtime is still unpromoted.",
            "reconciliation_mode": "documented_redirect",
            "authority_tier": "Documentation boundary",
            "write_runtime_boundary": "No unmanaged writes or runtime authority implied by docs.",
        },
    )


def legacy_setup_redirect_payload(settings: Settings | None = None) -> dict[str, object]:
    active_settings = settings or load_settings()
    return {
        "kind": SETUP_REDIRECT_KIND,
        "schema_version": "1.0.0",
        "project_root": str(active_settings.project_root),
        "target_repo": str(active_settings.target_repo),
        "goose_config_path": str(goose_config_dir() / "config.yaml"),
        "skills_source": str(skills_source(active_settings)),
        "governed_setup_commands": list(governed_setup_command_sequence()),
        "legacy_setup_surfaces": list(legacy_setup_surface_rows(active_settings)),
        "non_goals": [
            "no live Goose runtime promotion",
            "no subprocess or shell execution in the reconciled setup path",
            "no unmanaged Goose config writes",
            "no unmanaged .goosehints writes",
            "no unmanaged skill copying",
            "no recipe installation writes",
            "no model/provider calls",
            "no MCP/tool invocation",
            "no deepagents runtime",
            "no patch authority",
            "no autonomous writes",
        ],
    }


def render_legacy_setup_redirect_text(settings: Settings | None = None) -> str:
    payload = legacy_setup_redirect_payload(settings)
    commands = "\n".join(f"  {command}" for command in payload["governed_setup_commands"])
    return (
        "Legacy `builder setup` is disabled in R1.4.\n"
        "Use the governed R1 setup chain instead:\n"
        f"{commands}\n\n"
        "Reconciled boundary:\n"
        "- no Goose config writes\n"
        "- no `.goosehints` writes\n"
        "- no skill copying\n"
        "- no recipe validation subprocesses\n"
        "- no Goose start\n"
        "- no model/provider, MCP/tool, deepagents, patch, or autonomous write authority\n"
    )
