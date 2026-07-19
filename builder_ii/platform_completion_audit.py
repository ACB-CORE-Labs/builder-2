from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from builder_ii.assurance import (
    ASSURANCE_STATES,
    BLOCKED_BY_EVIDENCE,
    BOUNDED_EXECUTION_VERIFIED,
    DEMO_ONLY_VERIFIED,
    LIVE_PROVIDER_VERIFIED,
    MUTATION_WITH_ROLLBACK_VERIFIED,
    PASSIVE_ARTIFACT_VERIFIED,
    READ_ONLY_RUNTIME_VERIFIED,
    AssuranceState,
)

PLATFORM_COMPLETION_MATRIX_KIND = "builder_ii.platform_completion_matrix"
PLATFORM_TRUTH_AUDIT_REPORT_KIND = "builder_ii.platform_truth_audit_report"
SCHEMA_VERSION = "1.0.0"
SOURCE_REPORT = "docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md"
NEXT_SEQUENCE = "B8 deferred; B9 complete"

STALE_TRUTH_PHRASES: tuple[str, ...] = (
    "Setup apply, receipts, rollback, migration tooling, and runtime authority are still missing",
    "rollback execution, ledger event, and replay binding are missing",
    "no setup apply, receipt, rollback, or runtime gate consumes it yet",
    "Setup receipt, changed-path receipt, rollback execution, ledger event, and replay binding are missing",
)

DEFAULT_OPERATOR_LANE_READ_PATHS: tuple[str, ...] = ("README.md",)

StateLabel = Literal[
    "NOT_STARTED",
    "DESIGN_ONLY",
    "ARTIFACT_ONLY",
    "PASSIVE_FOUNDATION",
    "IMPLEMENTED_ON_BRANCH",
    "PR_OPEN",
    "MERGED_BUT_NOT_OPERATIONAL",
    "OPERATIONALLY_VERIFIED",
]

NOT_STARTED: StateLabel = "NOT_STARTED"
DESIGN_ONLY: StateLabel = "DESIGN_ONLY"
ARTIFACT_ONLY: StateLabel = "ARTIFACT_ONLY"
PASSIVE_FOUNDATION: StateLabel = "PASSIVE_FOUNDATION"
IMPLEMENTED_ON_BRANCH: StateLabel = "IMPLEMENTED_ON_BRANCH"
PR_OPEN: StateLabel = "PR_OPEN"
MERGED_BUT_NOT_OPERATIONAL: StateLabel = "MERGED_BUT_NOT_OPERATIONAL"
OPERATIONALLY_VERIFIED: StateLabel = "OPERATIONALLY_VERIFIED"

ALLOWED_STATE_LABELS: tuple[StateLabel, ...] = (
    NOT_STARTED,
    DESIGN_ONLY,
    ARTIFACT_ONLY,
    PASSIVE_FOUNDATION,
    IMPLEMENTED_ON_BRANCH,
    PR_OPEN,
    MERGED_BUT_NOT_OPERATIONAL,
    OPERATIONALLY_VERIFIED,
)

R1_CONFIG_ONBOARDING_CAPABILITIES: tuple[str, ...] = (
    "config schema",
    "config source precedence",
    "interactive setup wizard",
    "non-interactive setup/apply/validate",
    "Goose config overlay/rollback",
    "recipe generator/wizard",
    "skill generator/installer/validator",
    "target profile wizard",
    "agent profile wizard",
    "verification profile wizard",
    "deepagents/researcher setup wizard",
    "setup receipt + rollback artifact",
)

REQUIRED_CAPABILITIES: tuple[str, ...] = (
    "generic platform identity",
    "target profiles",
    "agent profiles",
    "verification profiles",
    "context packs",
    "profile packs",
    *R1_CONFIG_ONBOARDING_CAPABILITIES,
    "model registry",
    "model routing",
    "model/provider execution",
    "tool registry",
    "low-risk tool invocation",
    "MCP invocation",
    "passive orchestration assignment",
    "workflow/event ledger",
    "replay/audit",
    "readonly founder demo",
    "orchestration founder demo wrapper",
    "HITL promotion bridge",
    "execution candidate manifests",
    "HITL-approved verification execution",
    "HITL decision envelope",
    "HITL patch proposal",
    "HITL patch application",
    "rollback execution",
    "postflight verification",
    "governed read-only runtime",
    "Goose setup",
    "Goose readonly runtime",
    "Goose command proposals",
    "deepagents policy/readiness",
    "deepagents passive work artifacts",
    "deepagents runtime/subagents",
    "governed obligation delegation",
    "notes/handoff artifacts",
    "artifact memory",
    "operator quickstart/golden path",
    "governed demo loop",
    "platform doctor/status/audit",
    "release proof/quality gates",
    "command authority as runtime gate",
    "docs truth enforcement",
)


@dataclass(frozen=True)
class CapabilityRow:
    capability: str
    state: StateLabel
    evidence_files: tuple[str, ...]
    command_surfaces: tuple[str, ...]
    tests: tuple[str, ...]
    blockers: tuple[str, ...]
    next_pr: str

    def to_jsonable(self) -> dict[str, object]:
        data = asdict(self)
        data["evidence_files"] = list(self.evidence_files)
        data["command_surfaces"] = list(self.command_surfaces)
        data["tests"] = list(self.tests)
        data["blockers"] = list(self.blockers)
        data["assurance_state"] = assurance_state_for_row(self)
        return data


class UnclassifiedCapabilityError(ValueError):
    """An OPERATIONALLY_VERIFIED row whose assurance nobody decided."""


# Every OPERATIONALLY_VERIFIED capability appears here exactly once, by an explicit decision.
#
# This used to be an if/elif chain ending in `return PASSIVE_ARTIFACT_VERIFIED`. The field that
# `docs/PLATFORM_COMPLETION_AUDIT.md` calls "authoritative for risk interpretation" therefore
# assigned its LOWEST-risk label to any row nobody had classified -- eleven of the nineteen, at the
# last count, including the one lane that spawns a subprocess. Not because anyone judged them
# passive; because nobody judged them at all, and the default guessed in the green direction. A
# field authoritative for risk must fail closed. That one failed open.
#
# `builder-platform audit-docs` cannot catch this class: it detects docs that OVERSTATE capability,
# never records that understate risk. Truth is symmetric; that audit is not. So the guard is
# structural instead: a missing key raises, a stale key is a matrix validation error, and a new
# OPERATIONALLY_VERIFIED row cannot reach the matrix without someone deciding what it does. The
# understatement is now unrepresentable rather than merely fixed once.
#
# Read `builder_ii/assurance.py` for what each state means before adding a line here. The state
# describes what the capability DOES, not how important it feels.
_OPERATIONALLY_VERIFIED_ASSURANCE: dict[str, AssuranceState] = {
    # Writes the target's source tree or git state, behind digest-prefix approval + snapshot.
    "HITL patch application": MUTATION_WITH_ROLLBACK_VERIFIED,
    "rollback execution": MUTATION_WITH_ROLLBACK_VERIFIED,
    # Reaches a live provider over the network.
    "model/provider execution": LIVE_PROVIDER_VERIFIED,
    # Starts a runtime whose own policy denies writes.
    "governed read-only runtime": READ_ONLY_RUNTIME_VERIFIED,
    "Goose readonly runtime": READ_ONLY_RUNTIME_VERIFIED,
    # Causes work to run inside a fixed, pre-approved envelope, and receipts the invocation.
    "low-risk tool invocation": BOUNDED_EXECUTION_VERIFIED,
    "governed obligation delegation": BOUNDED_EXECUTION_VERIFIED,
    # Spawns `sys.executable -m builder_ii.verification_runner_entrypoints <sub>` with fixed argv,
    # shell=False, a minimal env, and an import path the target repo cannot supply, under two-key
    # HITL approval, and binds a digest-stable receipt to the plan and the approval. Scoped exactly
    # to the platform_status and docs_audit profiles, which run builder-II's own audit code over the
    # target's data; pytest_full and builder_full execute the target's own suite behind the D7
    # execution-risk acknowledgement and are outside this claim. `bounded` describes the envelope of
    # the invocation. It says nothing about the behaviour of the code that ran inside it.
    # docs/audits/LADDER9_ASSURANCE_CLOSURE_AUDIT.md
    "HITL-approved verification execution": BOUNDED_EXECUTION_VERIFIED,
    # Same lane, same module (`deepagents_execution.py`), same envelope as the row above: the
    # verified trunk is `execution-candidate -> approve-candidate -> run-approved` over the
    # protocol_fake backend, emitting execution receipts and a tamper-evident event chain. Ladder 4
    # filed that trunk as BOUNDED_EXECUTION_VERIFIED under the delegation row while this row --
    # whose surfaces are `run-approved`, `replay-run`, `collect-results` -- was left to the old
    # default and read PASSIVE. Two rows describing one lane must not disagree about its risk, and
    # when they do the higher-risk label is the honest one. protocol_fake denies shell, source
    # writes, git, MCP, Goose, memory and model invocation; `bounded` describes that envelope, and
    # says nothing about the quality of anything an agent produces inside it.
    "deepagents runtime/subagents": BOUNDED_EXECUTION_VERIFIED,
    # Verified only against a synthetic target, inside the demo loop.
    "governed demo loop": DEMO_ONLY_VERIFIED,
    # ---- Passive: reads, builds, validates, renders. Starts nothing; spawns nothing. ----
    # Each of these was read before it was filed here; none inherited its state from the old
    # default. The reasoning that survives is recorded next to the row it justifies.
    #
    # `builder-hitl propose-patch` emits a proposal artifact; application is a different row.
    "HITL patch proposal": PASSIVE_ARTIFACT_VERIFIED,
    # `check_command_authority` is a pure decision function over the registry. It permits the
    # subprocess that `builder-verify run-approved` then spawns; it spawns nothing itself.
    "command authority as runtime gate": PASSIVE_ARTIFACT_VERIFIED,
    "context packs": PASSIVE_ARTIFACT_VERIFIED,
    # `builder init` prompts, plans, and stops. Setup mutation is `builder-setup apply` (R1.7).
    "interactive setup wizard": PASSIVE_ARTIFACT_VERIFIED,
    # Registry and routing are policy artifacts. The call that reaches a provider is
    # `model/provider execution`, above, and it is filed as LIVE_PROVIDER_VERIFIED.
    "model registry": PASSIVE_ARTIFACT_VERIFIED,
    "model routing": PASSIVE_ARTIFACT_VERIFIED,
    # Generated from the truth matrix, command authority, and memory artifacts, and the row's own
    # blockers say it "demonstrates a complete governed local workflow without runtime execution".
    "operator quickstart/golden path": PASSIVE_ARTIFACT_VERIFIED,
    # `create_verification_runner_postflight` reads `receipt["postflight_git_state"]`, compares
    # preflight and postflight fingerprints, and writes a record. The `git status` that captured
    # that state was spawned by `run-approved`, whose own row carries the execution risk;
    # `execution_postflight_records.py` disables `command_execution` and `shell_execution` in its
    # governance block. Postflight originates no process. It is passive because of what it does,
    # not because it was never looked at.
    "postflight verification": PASSIVE_ARTIFACT_VERIFIED,
    "target profiles": PASSIVE_ARTIFACT_VERIFIED,
}


def validate_assurance_classification(
    rows: tuple[CapabilityRow, ...] = (),
) -> list[str]:
    """Every OPERATIONALLY_VERIFIED row is classified, and nothing else is.

    Both directions matter. A missing key is the fail-open default returning under another name.
    A stale key is a decision about a capability that no longer holds the state it was decided for
    -- `MCP invocation` sat in the old BOUNDED set while its row was `PASSIVE_FOUNDATION`, so that
    entry had been dead for as long as anyone had been reading the chain to understand the mapping.
    """
    rows = rows or REQUIRED_CAPABILITY_ROWS
    operationally_verified = {row.capability for row in rows if row.state == OPERATIONALLY_VERIFIED}
    classified = set(_OPERATIONALLY_VERIFIED_ASSURANCE)

    errors = [
        f"operationally verified capability '{capability}' has no assurance classification: decide "
        "what it does and add it to _OPERATIONALLY_VERIFIED_ASSURANCE"
        for capability in sorted(operationally_verified - classified)
    ]
    errors.extend(
        f"assurance classification for '{capability}' is stale: the capability is not "
        "OPERATIONALLY_VERIFIED, so its state comes from the non-verified branch"
        for capability in sorted(classified - operationally_verified)
    )
    return errors


def assurance_state_for_row(row: CapabilityRow) -> AssuranceState:
    if row.state != OPERATIONALLY_VERIFIED:
        if row.state in (PASSIVE_FOUNDATION, ARTIFACT_ONLY):
            return PASSIVE_ARTIFACT_VERIFIED
        return BLOCKED_BY_EVIDENCE
    # The hardening line expressed this as an if-chain falling through to
    # PASSIVE_ARTIFACT_VERIFIED -- the exact "absence read as a safe classification" defect the
    # explicit table exists to prevent. The table's no-default raise survives; the chain's row
    # classifications were folded into the table where the rows themselves survived the merge.
    try:
        return _OPERATIONALLY_VERIFIED_ASSURANCE[row.capability]
    except KeyError:
        raise UnclassifiedCapabilityError(
            f"'{row.capability}' is OPERATIONALLY_VERIFIED with no assurance classification. "
            "There is no default: decide what the capability does (see builder_ii/assurance.py) "
            "and record it in _OPERATIONALLY_VERIFIED_ASSURANCE."
        ) from None


def _row(
    capability: str,
    state: StateLabel,
    evidence_files: tuple[str, ...],
    command_surfaces: tuple[str, ...],
    tests: tuple[str, ...],
    blockers: tuple[str, ...],
    next_pr: str,
) -> CapabilityRow:
    return CapabilityRow(
        capability=capability,
        state=state,
        evidence_files=evidence_files,
        command_surfaces=command_surfaces,
        tests=tests,
        blockers=blockers,
        next_pr=next_pr,
    )


REQUIRED_CAPABILITY_ROWS: tuple[CapabilityRow, ...] = (
    _row(
        "generic platform identity",
        PASSIVE_FOUNDATION,
        (
            "README.md",
            "docs/ROADMAP.md",
            "docs/adrs/ADR-0003-builder-ii-generic-platform-identity-and-capability-factory.md",
        ),
        (),
        ("tests/test_operator_command_surface.py", "tests/test_command_authority.py"),
        (
            "Truth-state enforcement was static before R0.",
            "Some legacy setup helpers still carry CORE-compatible environment names.",
        ),
        "R0",
    ),
    _row(
        "target profiles",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/target_profiles.py", "builder_ii/cli/targets_cli.py", "builder_ii/readonly_authority.py"),
        ("builder-targets", "builder-readonly"),
        ("tests/test_target_profiles.py", "tests/test_targets_cli.py", "tests/test_readonly_authority.py"),
        (
            "Target registration lifecycle and target-root policies are operationally verified through the read runtime.",
        ),
        "B4",
    ),
    _row(
        "agent profiles",
        PASSIVE_FOUNDATION,
        ("builder_ii/agent_profiles.py", "builder_ii/cli/agent_cli.py"),
        ("builder-agent",),
        ("tests/test_agent_profiles.py",),
        (
            "Profiles record read, plan, and proposal authority only.",
            "No runtime agent construction, approval, or receipt path exists.",
        ),
        "B5",
    ),
    _row(
        "verification profiles",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/verification_profiles.py",
            "builder_ii/cli/verification_cli.py",
            "builder_ii/verification_profile_reports.py",
        ),
        ("builder-verification",),
        ("tests/test_verification_profiles.py", "tests/test_verification_profile_reports.py"),
        (
            "Profiles propose checks and reject completed-evidence claims.",
            "HITL-approved runner and receipt binding are missing.",
        ),
        "B1",
    ),
    _row(
        "context packs",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/repo_map.py",
            "builder_ii/context_packs.py",
            "builder_ii/cli/session_cli.py",
            "builder_ii/readonly_authority.py",
        ),
        ("builder-session", "builder-context", "builder-readonly"),
        ("tests/test_repo_map.py", "tests/test_governed_prepare_package.py", "tests/test_readonly_authority.py"),
        ("Canonical context packs and read policies are operationally verified.",),
        "B4",
    ),
    _row(
        "profile packs",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/profile_pack_manifest.py",
            "builder_ii/profile_pack_render_plan.py",
            "builder_ii/profile_pack_dry_run.py",
            "builder_ii/profile_pack.py",
        ),
        ("builder-profile-pack",),
        ("tests/test_profile_pack.py", "tests/test_profile_pack_cli.py"),
        (
            "Lifecycle remains passive.",
            "Runtime materialization is intentionally not promoted by R0.",
        ),
        "defer runtime materialization",
    ),
    _row(
        "config schema",
        PASSIVE_FOUNDATION,
        ("builder_ii/config_schema.py", "builder_ii/config.py", "docs/CONFIG_ONBOARDING.md"),
        ("builder-config",),
        ("tests/test_config_schema.py", "tests/test_config_setup_cli.py", "tests/test_platform_completion_truth.py"),
        (
            "R1.1 adds a versioned passive schema with generic BUILDER_* names, legacy CORE_* aliases, target roots, artifact roots, Goose paths, deepagents mode, and disabled capability defaults.",
            "Digest-bound builder-setup apply/rollback exist for declared setup paths; ambient runtime authority and migration tooling remain unpromoted.",
        ),
        "R1",
    ),
    _row(
        "config source precedence",
        PASSIVE_FOUNDATION,
        ("builder_ii/config_sources.py", "builder_ii/cli/config_cli.py", "docs/CONFIG_ONBOARDING.md"),
        ("builder-config",),
        ("tests/test_config_sources.py", "tests/test_config_setup_cli.py", "tests/test_platform_completion_truth.py"),
        (
            "R1.1 records precedence as CLI overrides, process environment, .env, builder config file, target/profile defaults, then built-in defaults.",
            "Resolution artifacts are consumed by builder-setup apply and operator-lane composition; ambient runtime gate interception remains partial.",
        ),
        "R1",
    ),
    _row(
        "interactive setup wizard",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/cli/main.py",
            "builder_ii/init_decisions.py",
            "builder_ii/cli/setup_cli.py",
            "docs/CONFIG_ONBOARDING.md",
            "docs/audits/R1_CLOSURE_AUDIT_2_6.md",
        ),
        ("builder init", "builder onboarding", "builder-setup wizard"),
        (
            "tests/test_init_cli.py",
            "tests/test_setup_onboarding_wizard_cli.py",
            "tests/test_setup_interactive_approval.py",
            "tests/test_platform_completion_truth.py",
        ),
        (
            "Plan 2.2 builder init prompts all nine onboarding decisions (registry-validated, never free text) and plans target repo, artifact root, profiles, model/backend, Goose overlay candidates, skill install plan, and capability state before apply; the wizard itself never applies. Ladder 5 wizard v2 promoted the five formerly-defaulted decisions -- agent profile, verification profile, artifact root, runtime mode, allow-artifact-root-inside-target -- from silently resolved and echoed to prompted, with the same flag > prompt > resolved-default precedence.",
            "Goose config merge, skill copying, and recipe installation remain manual operator steps (R1.7); setup mutation remains exclusively the separately digest-approved builder-setup apply.",
        ),
        "R1 complete (2.6)",
    ),
    _row(
        "non-interactive setup/apply/validate",
        MERGED_BUT_NOT_OPERATIONAL,
        (
            "builder_ii/cli/main.py",
            "builder_ii/goose_setup.py",
            "builder_ii/setup_plan.py",
            "builder_ii/setup_overlay.py",
            "builder_ii/setup_rollback.py",
            "builder_ii/setup_apply.py",
            "builder_ii/setup_receipt.py",
            "builder_ii/cli/setup_cli.py",
        ),
        ("builder", "builder-setup"),
        (
            "tests/test_goose_setup.py",
            "tests/test_setup_plan.py",
            "tests/test_setup_overlay.py",
            "tests/test_setup_rollback.py",
            "tests/test_config_setup_cli.py",
        ),
        (
            "R1.4 disables legacy builder setup writes and redirects operators to the governed builder-setup artifact chain.",
            "R1.3A adds digest-bound governed setup apply and setup receipts for declared setup targets only; R1.3B adds digest-bound setup rollback for changed paths covered by setup snapshots.",
            "Interactive onboarding, setup wizard UX, and operational runtime promotion remain missing.",
        ),
        "R1",
    ),
    _row(
        "Goose config overlay/rollback",
        PASSIVE_FOUNDATION,
        ("builder_ii/setup_overlay.py", "builder_ii/setup_rollback.py", "builder_ii/goose_setup.py"),
        ("builder-setup", "builder", "builder-goose"),
        (
            "tests/test_setup_overlay.py",
            "tests/test_setup_rollback.py",
            "tests/test_goose_setup.py",
            "tests/scenarios/test_config_to_goose_projection_flow.py",
        ),
        (
            "Legacy merge-style Goose config application remains intentionally unimplemented.",
            "R1.2 can describe Goose config overlay keys, recipe path registration, secrets-preservation policy, and rollback snapshot requirements passively.",
            "R1.3A apply can write declared setup paths only when represented as supported create/replace/mkdir/no-op changes; R1.3B setup rollback can undo eligible setup-created paths. Merge-style Goose config overlay and generic rollback remain unimplemented.",
        ),
        "R1",
    ),
    _row(
        "HITL decision envelope",
        ARTIFACT_ONLY,
        ("builder_ii/hitl_decision_envelope.py", "docs/ARTIFACT_INDEX.md"),
        ("builder-hitl validate-decision-envelope",),
        ("tests/test_hitl_decision_envelope.py",),
        (
            "Digest-bound decision-support artifact + validator exist: criteria with acceptable_range "
            "and observed value, assumptions, constraints, alternatives, consequences of "
            "approve/reject/escalate, and accountable ownership.",
            "Decision support only -- grants_authority / artifact_is_authority / is_approval are false "
            "and the validator rejects any true; the operator still approves through the digest-bound "
            "HITL lane.",
            "Composer wiring to surface the envelope at the STRATUM decision point, and an operational "
            "loop that assembles it from real evaluation, are not yet built -- so this stays "
            "ARTIFACT_ONLY, never operationally verified.",
        ),
        "HITL envelope: STRATUM composer wiring + operational assembly",
    ),
    _row(
        "recipe generator/wizard",
        ARTIFACT_ONLY,
        ("recipes/core-platform.yaml", "builder_ii/goose_recipe_context_projection.py"),
        ("builder", "builder-goose"),
        ("tests/test_goose_recipe_context_projection.py", "tests/test_session_wiring.py"),
        (
            "Recipe assets and projections exist.",
            "Generator/wizard, preview, apply receipt, rollback path, and compatibility checks are missing.",
        ),
        "R1",
    ),
    _row(
        "skill generator/installer/validator",
        MERGED_BUT_NOT_OPERATIONAL,
        (".agents/skills/core-governed-coding/SKILL.md", "builder_ii/setup_overlay.py", "builder_ii/goose_setup.py"),
        ("builder-setup", "builder"),
        ("tests/test_setup_overlay.py", "tests/test_goose_setup.py"),
        (
            "Legacy skill copying is disabled from builder setup in R1.4.",
            "R1.2 adds passive skill install-plan entries with source/destination digests and conflict notes.",
            "Operational install/copy and target-scoped approval are missing; R1.3B setup rollback does not promote generic skill rollback.",
        ),
        "R1",
    ),
    _row(
        "target profile wizard",
        NOT_STARTED,
        ("builder_ii/target_profiles.py", "builder_ii/cli/targets_cli.py"),
        ("builder-targets",),
        ("tests/test_target_profiles.py", "tests/test_platform_completion_truth.py"),
        (
            "Guided target profile creation/editing, dry-run preview, source precedence binding, and setup receipt are missing.",
        ),
        "R1",
    ),
    _row(
        "agent profile wizard",
        NOT_STARTED,
        ("builder_ii/agent_profiles.py", "builder_ii/cli/agent_cli.py"),
        ("builder-agent",),
        ("tests/test_agent_profiles.py", "tests/test_platform_completion_truth.py"),
        ("Guided agent profile creation/editing with authority preview and disabled runtime defaults is missing.",),
        "R1",
    ),
    _row(
        "verification profile wizard",
        NOT_STARTED,
        ("builder_ii/verification_profiles.py", "builder_ii/cli/verification_cli.py"),
        ("builder-verification",),
        ("tests/test_verification_profiles.py", "tests/test_platform_completion_truth.py"),
        (
            "Guided verification profile creation/editing, command allowlist preview, target compatibility check, and no-execution proof are missing.",
        ),
        "R1",
    ),
    _row(
        "deepagents/researcher setup wizard",
        NOT_STARTED,
        (
            "builder_ii/deepagents_policy.py",
            "builder_ii/deepagents_readiness.py",
            "builder_ii/deepagents_bridge_readiness.py",
        ),
        ("builder-deepagents",),
        ("tests/test_deepagents_policy.py", "tests/test_deepagents_readiness.py"),
        (
            "Optional dependency readiness exists.",
            "Setup wizard for researcher/deepagents capability selection, denied defaults, receipts, and no-runtime proof is missing.",
        ),
        "R1",
    ),
    _row(
        "setup receipt + rollback artifact",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/setup_rollback.py",
            "builder_ii/setup_apply.py",
            "builder_ii/setup_receipt.py",
            "builder_ii/setup_rollback_execute.py",
            "builder_ii/setup_rollback_receipt.py",
            "builder_ii/receipt_records.py",
            "builder_ii/rollback_artifacts.py",
        ),
        ("builder-setup", "builder-receipt"),
        (
            "tests/test_setup_rollback.py",
            "tests/test_setup_apply.py",
            "tests/test_setup_rollback_execute.py",
            "tests/test_receipt_records.py",
            "tests/test_rollback_artifacts.py",
        ),
        (
            "Generic records exist.",
            "R1.2 adds setup rollback snapshot planning with plan/overlay digests, prior existence markers, content digests, redacted previews, and future rollback operations.",
            "R1.3A adds setup apply receipts with changed/skipped/denied paths and before/after digests; R1.3B adds setup rollback receipts for digest-bound rollback execution. Ledger event and replay binding are missing.",
        ),
        "R1",
    ),
    _row(
        "model registry",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/model_client_registry.py", "builder_ii/model_execution_gateway.py"),
        ("builder-model-policy", "builder-model call"),
        (
            "tests/test_model_client_registry.py",
            "tests/test_model_policy_cli.py",
            "tests/test_model_execution_gateway.py",
        ),
        ("None. B6 completed model client registry verification under governed execution gateway.",),
        "B7",
    ),
    _row(
        "model routing",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/model_routing_policy.py",
            "builder_ii/cli/model_policy_cli.py",
            "builder_ii/model_execution_gateway.py",
        ),
        ("builder-model-policy", "builder-model call"),
        (
            "tests/test_model_routing_policy.py",
            "tests/test_model_policy_cli.py",
            "tests/test_model_execution_gateway.py",
        ),
        ("None. B6 completed routing verification under governed execution gateway.",),
        "B7",
    ),
    _row(
        "model/provider execution",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/model_execution_gateway.py",
            "builder_ii/cli/model_cli.py",
            "builder_ii/direct_chat.py",
            "builder_ii/backends.py",
        ),
        ("builder-model call", "builder-model validate-receipt"),
        ("tests/test_model_execution_gateway.py", "tests/test_direct_chat.py", "tests/test_backends.py"),
        ("None. Governed provider execution gateway is active.",),
        "B7",
    ),
    _row(
        "tool registry",
        PASSIVE_FOUNDATION,
        ("builder_ii/tool_registry.py", "builder_ii/cli/tools_cli.py"),
        ("builder-tools",),
        ("tests/test_tool_registry.py",),
        (
            "Registry and version probes exist.",
            "Invocation envelope and effect classification are missing.",
            "Version checks remain operator-managed tooling.",
        ),
        "B7",
    ),
    _row(
        "low-risk tool invocation",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/tool_invocation_gateway.py",
            "builder_ii/mcp_policy.py",
            "docs/plan/MCP_POLICY_ARTIFACT_RFC.md",
        ),
        ("builder-tools invoke",),
        ("tests/test_tool_invocation_gateway.py", "tests/test_mcp_policy.py"),
        ("Low-risk tool invocation is implemented via in-process stubs and verified with receipt and event replay.",),
        "B7",
    ),
    _row(
        "MCP invocation",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/mcp_policy.py",
            "docs/plan/MCP_POLICY_ARTIFACT_RFC.md",
        ),
        ("builder-mcp call", "builder-mcp inventory", "builder-mcp policy"),
        ("tests/test_mcp_cli.py",),
        (
            "MCP inventory, policy, call envelopes and receipts exist.",
            "Live MCP server execution remains unpromoted; deterministic stub invocation is handled by low-risk tool gateway.",
        ),
        "B7",
    ),
    _row(
        "passive orchestration assignment",
        PASSIVE_FOUNDATION,
        ("builder_ii/orchestration_assignment.py", "builder_ii/cli/orchestration_cli.py"),
        ("builder-orchestration",),
        ("tests/test_orchestration_cli.py", "tests/test_orchestration_plan.py"),
        (
            "Assignment binds artifacts by digest and starts no agents.",
            "Runtime assignment execution must wait for B1/B5.",
        ),
        "B5",
    ),
    _row(
        "workflow/event ledger",
        PASSIVE_FOUNDATION,
        ("builder_ii/workflow_orchestrator.py", "builder_ii/workflow_records.py", "builder_ii/event_ledger.py"),
        ("builder-workflow", "builder-ledger"),
        ("tests/test_workflow_ledger.py",),
        (
            "Ledger records workflow events including verification, model call, read/content-read, and tool stub lanes when session_id is supplied.",
            "Full replay policy for all runtime event kinds and memory mutation events remains partial.",
        ),
        "B1 then B6/B7/B8",
    ),
    _row(
        "replay/audit",
        PASSIVE_FOUNDATION,
        ("builder_ii/event_ledger.py", "builder_ii/artifact_chain_verification.py"),
        ("builder-ledger", "builder-chain"),
        ("tests/test_workflow_ledger.py", "tests/test_artifact_chain_verification.py"),
        (
            "Replay validates passive event order and artifact links only.",
            "Replay policy for nondeterministic execution receipts is missing.",
        ),
        "B1",
    ),
    _row(
        "readonly founder demo",
        PASSIVE_FOUNDATION,
        ("builder_ii/readonly_founder_demo.py", "builder_ii/cli/targets_cli.py"),
        ("builder-targets",),
        ("tests/test_readonly_demo.py", "tests/test_readonly_demo_idempotence.py"),
        (
            "Demo writes passive artifacts and status.",
            "It does not run verification or inspect live content beyond artifacts.",
        ),
        "defer after R0",
    ),
    _row(
        "orchestration founder demo wrapper",
        PASSIVE_FOUNDATION,
        ("builder_ii/readonly_founder_demo.py", "docs/demos/CORE_READONLY_FOUNDER_DEMO.md"),
        ("builder-targets",),
        ("tests/test_readonly_demo.py",),
        (
            "Wrapper is a passive workflow/event demonstration.",
            "Operator golden path for real governed read/verify loops is missing.",
        ),
        "B9",
    ),
    _row(
        "HITL promotion bridge",
        PASSIVE_FOUNDATION,
        ("builder_ii/hitl_promotion_artifacts.py", "builder_ii/cli/hitl_promotion_cli.py"),
        ("builder-hitl",),
        ("tests/test_hitl_promotion_artifacts.py",),
        (
            "Approval boundary is for candidate design only.",
            "No execution authority exists.",
        ),
        "B1",
    ),
    _row(
        "execution candidate manifests",
        PASSIVE_FOUNDATION,
        ("builder_ii/execution_candidate_manifest.py", "builder_ii/cli/execution_candidate_manifest_cli.py"),
        ("builder-hitl",),
        ("tests/test_execution_candidate_manifest.py",),
        (
            "Manifest validates intent, rollback requirements, verification requirements, and command previews.",
            "Executor is missing.",
        ),
        "B1",
    ),
    _row(
        "HITL-approved verification execution",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/verification_execution_plan.py",
            "builder_ii/verification_execution_approval.py",
            "builder_ii/verification_execution_receipt.py",
            "builder_ii/verification_execution_runner.py",
            "builder_ii/verification_execution_ledger.py",
            "builder_ii/verification_runner_entrypoints.py",
            "builder_ii/cli/verification_execution_plan_cli.py",
            "builder_ii/hitl_command_execution.py",
            "builder_ii/hitl_execution_records.py",
            "builder_ii/hitl_verification_candidate.py",
            "builder_ii/cli/hitl_execution_cli.py",
        ),
        (
            "builder-hitl",
            "builder-verify plan",
            "builder-verify validate-plan",
            "builder-verify approve-plan",
            "builder-verify validate-approval",
            "builder-verify validate-receipt",
            "builder-verify run-approved",
            "builder-ledger index-receipt",
            "builder-ledger query-receipts",
            "builder-ledger validate-receipts",
            "builder-ledger reconstruct-receipts",
        ),
        (
            "tests/test_verification_execution_plan.py",
            "tests/test_verification_execution_plan_cli.py",
            "tests/test_verification_execution_approval.py",
            "tests/test_verification_execution_approval_cli.py",
            "tests/test_verification_execution_approval_authority.py",
            "tests/test_verification_execution_receipt.py",
            "tests/test_verification_execution_receipt_cli.py",
            "tests/test_verification_execution_runner.py",
            "tests/test_verification_execution_ledger.py",
            "tests/test_hitl_command_execution.py",
            "tests/test_hitl_execution_records.py",
            "tests/test_hitl_verification_candidate.py",
        ),
        (
            "B1.1 adds a digest-stable passive verification execution plan artifact only.",
            "B1.2 adds a digest-bound HITL approval artifact only and remains non-authoritative.",
            "B1.3A adds a passive verification execution receipt contract and validate-receipt surface.",
            "B1.3B adds the first bounded approved verification runner for profile=platform_status.",
            "B1.5 broadens the bounded approved runner to docs_audit using fixed in-code argv and the same shell=False/HITL envelope.",
            "B1.4A/B/C/D add passive verification ledger indexing, query, integrity, and reconstruction reporting.",
            "Receipt state may be NOT_EXECUTED, BLOCKED_BEFORE_EXECUTION, EXECUTED, or FAILED depending on runner outcome.",
            "The approved verification lane is operationally verified only for fixed platform_status and docs_audit profiles; arbitrary argv, broad shell, live read authority, patching, model/MCP/Goose/deepagents runtime, and B2 write authority remain disabled.",
            "Assurance BOUNDED_EXECUTION_VERIFIED (Ladder 9) describes the envelope of the invocation -- fixed argv, shell=False, two-key approval, an import path the target repo cannot supply, a digest-bound receipt -- and never the behaviour of the code that ran inside it (risk-register D7).",
            "Under an applied isolation policy the receipt records the approved fixed profile argv, not the container-wrapped argv that executed, so isolation_status is the runner's own assertion about itself; local isolation is containment, never attestation (docs/plan/VERIFICATION_ISOLATION_RFC.md).",
            "builder-verify plan exposes no isolation flag: isolation_policy exists in the plan schema, the runner and the receipt, but no governed CLI surface can request it.",
        ),
        "B2.0",
    ),
    _row(
        "HITL patch proposal",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/hitl_patch_proposal.py",
            "builder_ii/goose_command_proposal.py",
            "builder_ii/cli/hitl_patch_cli.py",
        ),
        ("builder-goose", "builder-hitl propose-patch"),
        ("tests/test_hitl_patch_proposal.py", "tests/test_goose_command_proposal.py"),
        ("Patch proposal artifact is operationally verified.",),
        "B4",
    ),
    _row(
        "HITL patch application",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/hitl_patch_apply.py",
            "builder_ii/hitl_patch_approval.py",
            "builder_ii/hitl_patch_ledger.py",
            "builder_ii/cli/hitl_patch_cli.py",
            "builder_ii/hitl_patch_proposal.py",
            "docs/HITL_PATCH_PROPOSAL.md",
            "docs/audits/B4_CLOSURE_AUDIT.md",
        ),
        ("builder-hitl approve-patch", "builder-hitl apply-patch"),
        (
            "tests/test_hitl_patch_proposal.py",
            "tests/test_hitl_patch_apply.py",
            "tests/test_hitl_patch_approval.py",
            "tests/test_hitl_patch_cli.py",
            "tests/test_hitl_patch_ledger.py",
            "tests/scenarios/test_hitl_patch_lane_unmocked.py",
        ),
        (
            "Operator-invoked HITL patch application is OPERATIONALLY_VERIFIED through the interactive approve-patch approval boundary, a required verification receipt, the command-authority gate, and a bound reverse-patch + ledger trail (docs/audits/B4_CLOSURE_AUDIT.md).",
            "Scoped to the operator-invoked lane: the command stays Tier 3 hitl_runtime_candidate, not enabled; autonomous or automatic apply remains forbidden and unpromoted.",
        ),
        "B4.8",
    ),
    _row(
        "rollback execution",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/rollback_artifacts.py",
            "builder_ii/hitl_rollback_approval.py",
            "builder_ii/hitl_patch_ledger.py",
            "builder_ii/cli/hitl_patch_cli.py",
            "builder_ii/hitl_patch_apply.py",
            "docs/audits/B4_CLOSURE_AUDIT.md",
        ),
        ("builder-hitl approve-rollback", "builder-hitl rollback"),
        (
            "tests/test_rollback_artifacts.py",
            "tests/test_hitl_patch_apply.py",
            "tests/test_hitl_patch_rollback.py",
            "tests/test_hitl_rollback_drift.py",
        ),
        (
            "Operator-invoked rollback execution is OPERATIONALLY_VERIFIED: a distinct approve-rollback approval, a working-tree drift preflight that refuses before touching the tree, and a recovery-block-bearing failure receipt (docs/audits/B4_CLOSURE_AUDIT.md).",
            "Scoped to the operator-invoked lane: the command stays Tier 3 hitl_runtime_candidate, not enabled; autonomous rollback remains unpromoted.",
        ),
        "B4.8",
    ),
    _row(
        "postflight verification",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/execution_postflight_records.py", "builder_ii/verification_execution_runner.py"),
        ("builder-verify run-approved",),
        ("tests/test_execution_postflight_records.py", "tests/test_verification_execution_runner.py"),
        (
            "Verification runner postflight records are generated from real approved runs and bind receipt, preflight, postflight, and mutation evidence.",
            "Postflight generation is promoted only for the bounded verification runner lane; broader execution lanes remain gated until integrated separately.",
        ),
        "B1.5",
    ),
    _row(
        "Goose setup",
        MERGED_BUT_NOT_OPERATIONAL,
        ("builder_ii/goose_setup.py", "builder_ii/cli/main.py"),
        ("builder",),
        ("tests/test_goose_setup.py",),
        (
            "R1.4 converts builder setup into a fail-closed redirect and removes legacy setup writes from the setup path.",
            "Goose runtime promotion, recipe execution, and governed runtime receipts remain missing.",
        ),
        "B4 after R0/B3",
    ),
    _row(
        "governed read-only runtime",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/readonly_authority.py", "builder_ii/cli/readonly_inspection_cli.py"),
        ("builder-readonly policy", "builder-readonly read", "builder-readonly validate"),
        ("tests/test_readonly_authority.py",),
        ("Unified governed read-only runtime is operationally verified.",),
        "B4",
    ),
    _row(
        "Goose readonly runtime",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/goose_session.py",
            "builder_ii/goose_readonly.py",
            "builder_ii/goose_inspection.py",
            "builder_ii/cli/goose_cli.py",
            "builder_ii/goose_runtime_harness.py",
        ),
        ("builder-goose", "builder-goose start-readonly", "builder-goose close-readonly"),
        ("tests/test_goose_readonly.py", "tests/test_goose_inspection.py", "tests/test_goose_runtime_harness.py"),
        ("Goose readonly runtime is operationally verified with receipts and no-mutation postflight.",),
        "B5",
    ),
    _row(
        "Goose command proposals",
        PASSIVE_FOUNDATION,
        ("builder_ii/goose_command_proposal.py",),
        ("builder-goose",),
        ("tests/test_goose_command_proposal.py",),
        (
            "Proposal records require approval and executed=false.",
            "Execution envelope and receipt are missing.",
        ),
        "B1/B4",
    ),
    _row(
        "deepagents policy/readiness",
        PASSIVE_FOUNDATION,
        ("builder_ii/deepagents_policy.py", "builder_ii/deepagents_readiness.py", "builder_ii/deepagents_bridge.py"),
        ("builder-deepagents",),
        ("tests/test_deepagents_policy.py", "tests/test_deepagents_readiness.py", "tests/test_deepagents_bridge.py"),
        (
            "Policy/readiness may inspect import metadata.",
            "Runtime harness is operational.",
        ),
        "B6",
    ),
    _row(
        "deepagents passive work artifacts",
        PASSIVE_FOUNDATION,
        ("builder_ii/deepagents_work_artifacts.py", "builder_ii/cli/deepagents_cli.py"),
        ("builder-deepagents",),
        ("tests/test_deepagents_work_artifacts.py",),
        (
            "Work artifacts deny model/tool/shell/Goose/deepagents/MCP/network/writes.",
            "Runtime harness is operational.",
        ),
        "B6",
    ),
    _row(
        "deepagents runtime/subagents",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/cli/deepagents_cli.py",
            "docs/DEEPAGENTS_POLICY.md",
            "builder_ii/deepagents_runtime.py",
            "builder_ii/deepagents_execution.py",
        ),
        (
            "builder-deepagents",
            "builder-deepagents execution-candidate",
            "builder-deepagents approve-candidate",
            "builder-deepagents run-approved",
            "builder-deepagents replay-run",
            "builder-deepagents collect-results",
        ),
        (
            "tests/test_deepagents_policy.py",
            "tests/test_deepagents_work_artifacts.py",
            "tests/test_deepagents_runtime.py",
            "tests/test_deepagents_execution.py",
        ),
        (
            "The verified runtime trunk is execution-candidate -> approve-candidate (flag-driven, digest-bound seal) -> run-approved over the protocol_fake backend, with execution receipts, a tamper-evident event chain, replay, and proposal-only results.",
            "builder-deepagents run-plan is a legacy structural projection, not the trunk: it runs no backend and verifies nothing (its summaries say so); run-plan outputs are not execution evidence.",
            "The native optional_deepagents backend remains unpromoted behind the backend readiness gate and the two-key acknowledgement.",
        ),
        "B6",
    ),
    _row(
        "governed obligation delegation",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/orchestration_obligation.py",
            "builder_ii/orchestration_lane_policy.py",
            "builder_ii/deepagents_execution.py",
            "builder_ii/verification_promotion_gate.py",
            "docs/ORCHESTRATION_OBLIGATIONS.md",
            "docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md",
        ),
        (
            "builder-orchestration lane-policy",
            "builder-orchestration validate-lane-policy",
            "builder-orchestration mint-obligation",
            "builder-orchestration validate-obligation",
            "builder-orchestration status",
            "builder-orchestration why",
            "builder-deepagents run-approved",
        ),
        (
            "tests/test_orchestration_obligation.py",
            "tests/test_orchestration_lane_policy.py",
            "tests/test_orchestration_delegation_run.py",
            "tests/scenarios/test_full_obligation_delegation_lane.py",
            "tests/scenarios/test_promotion_gate_delegation_tree.py",
            "tests/test_ladder4_closure_evidence.py",
        ),
        (
            "Verified over the protocol_fake backend as CI truth: one flag-driven digest-bound seal opens the obligation envelope; every mint is enforced fail-closed against it (named refusals carrying fixing edits); discharges classify CONTRACT_SATISFIED / DISCHARGED_UNVERIFIED / CONTRACT_VIOLATED / BLOCKED; the event chain is digest-stamped, tamper-evident, and replayable (Ladder 4 PR-8; docs/audits/LADDER4_ORCHESTRATION_CLOSURE_AUDIT.md).",
            "The native optional_deepagents backend is NOT covered by this row: it remains a separate readiness-gated, two-key-acknowledged claim with no promoted execution, and this row never implies agent-output quality.",
            "No autonomous dispatch, model execution, tool/shell/Goose/MCP invocation, source writes, or hidden memory; mutation obligations discharge only through the already-promoted HITL patch lane, verification obligations only through the approved verification lane.",
        ),
        "Ladder 4 complete (PR-8)",
    ),
    _row(
        "notes/handoff artifacts",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/cli/notes_cli.py",
            "builder_ii/handoff_artifacts.py",
            "builder_ii/handoff_notes.py",
            "builder_ii/handoff_bundle_records.py",
        ),
        ("builder-notes", "builder-handoff"),
        ("tests/test_handoff_notes.py", "tests/test_handoff_bundle_records.py"),
        (
            "Handoffs summarize and reference evidence.",
            "They do not mutate a memory store or prove execution.",
        ),
        "defer operational memory",
    ),
    _row(
        "artifact memory",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/artifact_memory.py",
            "builder_ii/cli/memory_cli.py",
            "docs/ARTIFACT_MEMORY.md",
            "docs/plan/ARTIFACT_MEMORY_RFC.md",
        ),
        (
            "builder-memory",
            "builder-memory atom",
            "builder-memory index",
            "builder-memory reconstruct",
            "builder-memory search",
        ),
        (
            "tests/test_artifact_memory.py",
            "tests/test_memory_cli.py",
            "tests/test_platform_completion_truth.py",
        ),
        (
            "Artifact memory is explicit, content-addressed, and reviewable only.",
            "No hidden memory, vector store, autonomous writes, or runtime authority are promoted.",
            "Remains PASSIVE_FOUNDATION by design; docs and UX do not imply operational memory mutation.",
        ),
        "defer operational memory",
    ),
    _row(
        "operator quickstart/golden path",
        OPERATIONALLY_VERIFIED,
        ("docs/OPERATOR_QUICKSTART.md", "builder_ii/operator_golden_path.py", "builder_ii/operator_lane.py"),
        (
            "builder-platform operator-status",
            "builder-platform next",
            "builder-platform golden-path",
            "builder-platform operator-lane",
        ),
        (
            "tests/test_operator_golden_path.py",
            "tests/test_operator_status.py",
            "tests/test_operator_next.py",
            "tests/test_operator_lane.py",
        ),
        (
            "Golden path UX generated from truth matrix, command authority, and B8 memory artifacts.",
            "Demonstrates a complete governed local workflow without runtime execution.",
            "Does not promote runtime execution or operational memory authority.",
        ),
        "B9 complete",
    ),
    _row(
        "governed demo loop",
        OPERATIONALLY_VERIFIED,
        (
            "builder_ii/demo_loop.py",
            "builder_ii/cli/platform_status_cli.py",
            "docs/CORE_DEMO_WALKTHROUGH.md",
            "docs/audits/B4_9_DEMO_GENERALIZATION_AUDIT.md",
        ),
        ("builder-platform demo-loop", "builder-platform validate-demo-loop", "builder-platform wow"),
        ("tests/test_demo_loop.py", "tests/test_platform_completion_truth.py", "tests/test_command_authority.py"),
        (
            "Runs against a temporary detached worktree of an operator-designated target repo, never the source checkout; AssetOverflow/core remains a supported profile carrying its identity check and sensitive-module policy.",
            "Mutation is limited to one approved temporary documentation marker patch and is paired with rollback plus final clean postflight.",
            "No commit, push, model execution, Goose activation, MCP call, hidden memory, or source checkout mutation is promoted.",
        ),
        "B4.9 complete",
    ),
    _row(
        "platform doctor/status/audit",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/platform_completion_audit.py",
            "builder_ii/cli/platform_status_cli.py",
            "builder_ii/r1_closure_report.py",
            "docs/PLATFORM_COMPLETION_AUDIT.md",
        ),
        ("builder-platform",),
        (
            "tests/test_platform_completion_truth.py",
            "tests/test_platform_completion_audit.py",
            "tests/test_r1_closure_report.py",
            "tests/test_platform_r1_closure_cli.py",
        ),
        (
            "R0 adds source-derived truth status.",
            "R1.6 adds canonical R1 closure report and golden path proof commands.",
            "Legacy builder doctor/status remain operator-managed environment helpers.",
            "Operational execution still waits for R1 then B1.",
        ),
        "R1 then B1",
    ),
    _row(
        "release proof/quality gates",
        PASSIVE_FOUNDATION,
        (
            "scripts/verify_v0_release.py",
            "docs/RELEASE_PROOF.md",
            "builder_ii/quality_gates.py",
            "builder_ii/cli/quality_cli.py",
        ),
        ("builder-quality",),
        ("tests/test_v0_release_proof_harness.py", "tests/test_quality_gates.py"),
        (
            "Proof harness proves passive artifact chain and no target mutation.",
            "Quality gates are plans, not runners.",
            "Operational runtime proof waits for B1.",
        ),
        "B1",
    ),
    _row(
        "command authority as runtime gate",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/command_authority.py", "docs/COMMAND_AUTHORITY.md"),
        ("builder-verify run-approved",),
        (
            "tests/test_command_authority.py",
            "tests/test_verification_execution_runner.py",
            "tests/test_platform_completion_truth.py",
        ),
        (
            "Central fail-closed command authority decisions are implemented and machine-checkable.",
            "The bounded verification runner consults the gate before crossing subprocess/artifact-write authority.",
            "Full legacy CLI wrapper interception remains out of scope; each authority-bearing lane must explicitly call the gate before promotion.",
        ),
        "B1.5",
    ),
    _row(
        "docs truth enforcement",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/platform_completion_audit.py",
            "builder_ii/cli/platform_status_cli.py",
            "docs/PLATFORM_COMPLETION_AUDIT.md",
        ),
        ("builder-platform",),
        ("tests/test_docs_truth_enforcement.py", "tests/test_platform_completion_truth.py"),
        (
            "R0 adds docs truth scanning against the matrix.",
            "No runtime authority is promoted by docs enforcement.",
        ),
        "R1 then B1",
    ),
)


@dataclass(frozen=True)
class DocTruthViolation:
    path: str
    line_number: int
    reason: str
    line: str

    def to_jsonable(self) -> dict[str, object]:
        return asdict(self)


def capability_rows() -> tuple[CapabilityRow, ...]:
    return REQUIRED_CAPABILITY_ROWS


def state_counts(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> dict[str, int]:
    counts = {state: 0 for state in ALLOWED_STATE_LABELS}
    for row in rows:
        counts[row.state] += 1
    return counts


def render_matrix_jsonable(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> dict[str, object]:
    return {
        "kind": PLATFORM_COMPLETION_MATRIX_KIND,
        "schema_version": SCHEMA_VERSION,
        "source_report": SOURCE_REPORT,
        "allowed_state_labels": list(ALLOWED_STATE_LABELS),
        "allowed_assurance_states": list(ASSURANCE_STATES),
        "next_sequence": NEXT_SEQUENCE,
        "summary": {
            "passive_foundation_complete": True,
            "operationally_incomplete": True,
            "operationally_verified_count": state_counts(rows)[OPERATIONALLY_VERIFIED],
            "state_counts": state_counts(rows),
        },
        "capabilities": [row.to_jsonable() for row in rows],
    }


def dumps_matrix(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> str:
    return json.dumps(render_matrix_jsonable(rows), indent=2, sort_keys=True) + "\n"


def render_capability_table_markdown(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> str:
    lines = ["| Capability | State | Next PR |", "|---|---|---|"]
    for row in rows:
        lines.append(f"| {row.capability} | `{row.state}` | {row.next_pr} |")
    return "\n".join(lines) + "\n"


def render_truth_report_capability_row(row: CapabilityRow) -> str:
    evidence = ", ".join(row.evidence_files[:4])
    if len(row.evidence_files) > 4:
        evidence += ", ..."
    commands = ", ".join(row.command_surfaces) if row.command_surfaces else "none dedicated"
    tests = ", ".join(row.tests[:3])
    if len(row.tests) > 3:
        tests += ", ..."
    blockers = " ".join(row.blockers)
    return (
        f"| {row.capability} | {row.state} | `{evidence}`; commands: {commands} | {blockers} | {row.next_pr} |"
    )


def matrix_blocker_violations(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> list[str]:
    errors: list[str] = []
    for row in rows:
        for phrase in STALE_TRUTH_PHRASES:
            for blocker in row.blockers:
                if phrase in blocker:
                    errors.append(f"{row.capability}: stale blocker phrase: {phrase}")
    return errors


def render_human_summary(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> str:
    counts = state_counts(rows)
    operational = sorted(row.capability for row in rows if row.state == OPERATIONALLY_VERIFIED)
    incomplete_count = len([row for row in rows if row.state != OPERATIONALLY_VERIFIED])
    lines = [
        "builder-II platform truth state",
        "",
        f"builder-II is passive-foundation-complete and operationally incomplete: {counts[OPERATIONALLY_VERIFIED]} capabilities are operationally verified and {incomplete_count} remain incomplete.",
        "Operational authority is capability-scoped by the matrix; commit/push automation, hidden memory, and source CORE checkout mutation remain unpromoted.",
        "The governed demo loop is promoted only for a temporary detached worktree of an operator-designated target repo (AssetOverflow/core remains a supported profile) with explicit approval, rollback, and final postflight.",
        f"Next sequence: {NEXT_SEQUENCE}. R1 Config + Onboarding Kernel must precede B1 verification execution.",
        "",
        "Capability states:",
    ]
    for state in ALLOWED_STATE_LABELS:
        lines.append(f"- {state}: {counts[state]}")
    lines.extend(
        [
            "",
            "R1 config/onboarding rows promoted through R1.4:",
            "- config schema: PASSIVE_FOUNDATION",
            "- config source precedence: PASSIVE_FOUNDATION",
            "- setup plan/overlay/rollback-snapshot/apply/rollback command surface: governed apply and setup rollback are digest-bound and non-runtime, and legacy builder setup now fails closed",
            "- Goose config overlay/rollback planning: PASSIVE_FOUNDATION",
            "- setup receipt + rollback receipt artifacts: PASSIVE_FOUNDATION",
            "",
            "Operationally verified highlights: " + ", ".join(operational) + ".",
        ]
    )
    return "\n".join(lines) + "\n"


def validate_matrix_shape(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    for row in rows:
        if row.capability in seen:
            errors.append(f"duplicate capability row: {row.capability}")
        seen.add(row.capability)
        if row.state not in ALLOWED_STATE_LABELS:
            errors.append(f"{row.capability}: unsupported state {row.state}")
        if not row.evidence_files:
            errors.append(f"{row.capability}: missing evidence_files")
        if not row.tests:
            errors.append(f"{row.capability}: missing tests")
        if not row.blockers:
            errors.append(f"{row.capability}: missing blockers")
        if not row.next_pr.strip():
            errors.append(f"{row.capability}: missing next_pr")

    missing = sorted(set(REQUIRED_CAPABILITIES) - seen)
    extra = sorted(seen - set(REQUIRED_CAPABILITIES))
    for capability in missing:
        errors.append(f"missing required capability row: {capability}")
    for capability in extra:
        errors.append(f"unexpected capability row: {capability}")
    return errors


def validate_referenced_files(root: Path, rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> list[str]:
    errors: list[str] = []
    for row in rows:
        for rel_path in (*row.evidence_files, *row.tests):
            if not (root / rel_path).exists():
                errors.append(f"{row.capability}: referenced file does not exist: {rel_path}")
    return errors


# R1 rows the operator has explicitly flipped to OPERATIONALLY_VERIFIED (plan tier C: evidence
# first, operator applies the flip). Any future R1 flip must be added here in the same reviewed
# diff as its closure audit — the default for every other R1 row stays fail-closed below.
R1_OPERATOR_FLIPPED_CAPABILITIES: tuple[str, ...] = (
    # 2.6 R1 closure flip: docs/audits/R1_CLOSURE_AUDIT_2_6.md (builder init unified orchestrator
    # + interactive digest-prefix apply approval, plan item 2.2).
    "interactive setup wizard",
)


def validate_r1_config_onboarding_mapping(
    rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS,
) -> list[str]:
    by_capability = {row.capability: row for row in rows}
    errors: list[str] = []
    for capability in R1_CONFIG_ONBOARDING_CAPABILITIES:
        row = by_capability.get(capability)
        if row is None:
            errors.append(f"missing R1 config/onboarding capability row: {capability}")
            continue
        if capability in R1_OPERATOR_FLIPPED_CAPABILITIES:
            if row.state != OPERATIONALLY_VERIFIED:
                errors.append(f"{capability}: operator-flipped R1 row must be OPERATIONALLY_VERIFIED")
            continue
        if row.next_pr != "R1":
            errors.append(f"{capability}: expected next_pr R1, got {row.next_pr}")
        if row.state == OPERATIONALLY_VERIFIED:
            errors.append(f"{capability}: R1 config/onboarding row must remain non-operational in R0")
    return errors


def validate_command_surfaces(
    authority_names: set[str],
    rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS,
) -> list[str]:
    errors: list[str] = []
    for row in rows:
        for command in row.command_surfaces:
            if command not in authority_names:
                errors.append(f"{row.capability}: command surface missing authority registry entry: {command}")
    return errors


def validate_completion_matrix(root: Path | None = None) -> list[str]:
    errors = validate_matrix_shape()
    # An unclassified OPERATIONALLY_VERIFIED row makes `assurance_state_for_row` raise. Report it as
    # a matrix error too, so `builder-platform matrix` and the platform_status verification profile
    # name the missing decision instead of dying in a traceback.
    errors.extend(validate_assurance_classification())
    if root is not None:
        errors.extend(validate_referenced_files(root))
    return errors


_FALSE_COMPLETION_EXACT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfully completed and verified\b", re.IGNORECASE), "ambiguous completed-and-verified claim"),
    (re.compile(r"\bfoundation is complete\b", re.IGNORECASE), "ambiguous foundation completion claim"),
    (
        re.compile(r"\bartifact-first foundation is complete\b", re.IGNORECASE),
        "ambiguous artifact foundation completion claim",
    ),
    (
        re.compile(r"\bfull governed artifact platform is built, tested, and proven\b", re.IGNORECASE),
        "ambiguous full-platform claim",
    ),
    (
        re.compile(r"\bModel routing policy artifact \(RFC exists, artifact not yet built\)", re.IGNORECASE),
        "stale model routing RFC claim",
    ),
)

_CLAIM_PATTERN = re.compile(
    r"\b(complete|completed|finished|ready|sealed|enabled|operational|verified)\b",
    re.IGNORECASE,
)

_SAFE_CONTEXT_PATTERN = re.compile(
    r"("
    r"passive|passive-foundation|artifact-only|artifact only|design-only|design only|"
    r"not |no |non-operational|incomplete|candidate|disabled|denied|missing|future|"
    r"requires|before|until|must not|does not|without|not yet|"
    r"state label|state labels|STATE|NOT_STARTED|DESIGN_ONLY|ARTIFACT_ONLY|"
    r"PASSIVE_FOUNDATION|IMPLEMENTED_ON_BRANCH|PR_OPEN|MERGED_BUT_NOT_OPERATIONAL|"
    r"OPERATIONALLY_VERIFIED|truth report|false-completion|claim pattern"
    r")",
    re.IGNORECASE,
)

_DOC_AUDIT_EXCLUDED = {
    SOURCE_REPORT,
}


def _docs_to_scan(root: Path) -> list[Path]:
    files = [root / "README.md"]
    docs_root = root / "docs"
    if docs_root.exists():
        files.extend(sorted(docs_root.rglob("*.md")))
    return [
        path
        for path in files
        if path.exists() and path.is_file() and path.relative_to(root).as_posix() not in _DOC_AUDIT_EXCLUDED
    ]


def _non_operational_capability_names(rows: tuple[CapabilityRow, ...]) -> tuple[str, ...]:
    return tuple(row.capability for row in rows if row.state != OPERATIONALLY_VERIFIED)


def scan_docs_for_false_completion(
    root: Path,
    rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS,
) -> list[DocTruthViolation]:
    violations: list[DocTruthViolation] = []
    non_operational = _non_operational_capability_names(rows)

    for path in _docs_to_scan(root):
        rel_path = path.relative_to(root).as_posix()
        for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            line = raw_line.strip()
            if not line:
                continue
            lowered = line.lower()

            for pattern, reason in _FALSE_COMPLETION_EXACT_PATTERNS:
                if pattern.search(line):
                    violations.append(DocTruthViolation(rel_path, line_number, reason, line))

            if not _CLAIM_PATTERN.search(line):
                continue
            if _SAFE_CONTEXT_PATTERN.search(line):
                continue
            for capability in non_operational:
                if capability.lower() in lowered:
                    violations.append(
                        DocTruthViolation(
                            rel_path,
                            line_number,
                            f"non-operational capability '{capability}' is described with operational-completion language",
                            line,
                        )
                    )
                    break
    return violations


def render_docs_audit_jsonable(root: Path) -> dict[str, object]:
    violations = scan_docs_for_false_completion(root)
    scanned = [path.relative_to(root).as_posix() for path in _docs_to_scan(root)]
    return {
        "kind": PLATFORM_TRUTH_AUDIT_REPORT_KIND,
        "schema_version": SCHEMA_VERSION,
        "source_matrix_kind": PLATFORM_COMPLETION_MATRIX_KIND,
        "scanned_files": scanned,
        "valid": not violations,
        "violations": [violation.to_jsonable() for violation in violations],
    }


def dumps_docs_audit(root: Path) -> str:
    return json.dumps(render_docs_audit_jsonable(root), indent=2, sort_keys=True) + "\n"
