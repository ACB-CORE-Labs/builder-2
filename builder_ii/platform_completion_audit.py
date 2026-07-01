from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal


PLATFORM_COMPLETION_MATRIX_KIND = "builder_ii.platform_completion_matrix"
PLATFORM_TRUTH_AUDIT_REPORT_KIND = "builder_ii.platform_truth_audit_report"
SCHEMA_VERSION = "1.0.0"
SOURCE_REPORT = "docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md"
NEXT_SEQUENCE = "B5 -> B6"

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
    "MCP/tool invocation",
    "passive orchestration assignment",
    "workflow/event ledger",
    "replay/audit",
    "readonly founder demo",
    "orchestration founder demo wrapper",
    "HITL promotion bridge",
    "execution candidate manifests",
    "HITL-approved verification execution",
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
    "notes/handoff artifacts",
    "artifact memory",
    "operator quickstart/golden path",
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
        return data


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
        ("builder_ii/target_profiles.py", "builder_ii/targets_cli.py", "builder_ii/readonly_authority.py"),
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
        ("builder_ii/agent_profiles.py", "builder_ii/agent_cli.py"),
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
            "builder_ii/verification_cli.py",
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
        ("builder_ii/repo_map.py", "builder_ii/context_packs.py", "builder_ii/session_cli.py", "builder_ii/readonly_authority.py"),
        ("builder-session", "builder-context", "builder-readonly"),
        ("tests/test_repo_map.py", "tests/test_governed_prepare_package.py", "tests/test_readonly_authority.py"),
        (
            "Canonical context packs and read policies are operationally verified.",
        ),
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
            "Setup apply, receipts, rollback, migration tooling, and runtime authority are still missing.",
        ),
        "R1",
    ),
    _row(
        "config source precedence",
        PASSIVE_FOUNDATION,
        ("builder_ii/config_sources.py", "builder_ii/config_cli.py", "docs/CONFIG_ONBOARDING.md"),
        ("builder-config",),
        ("tests/test_config_sources.py", "tests/test_config_setup_cli.py", "tests/test_platform_completion_truth.py"),
        (
            "R1.1 records precedence as CLI overrides, process environment, .env, builder config file, target/profile defaults, then built-in defaults.",
            "Resolution is artifact-only; no setup apply, receipt, rollback, or runtime gate consumes it yet.",
        ),
        "R1",
    ),
    _row(
        "interactive setup wizard",
        NOT_STARTED,
        ("README.md", SOURCE_REPORT),
        (),
        ("tests/test_platform_completion_truth.py",),
        (
            "No wizard plans target repo, artifact root, profiles, model/backend, Goose writes, recipes, skills, and capability state before apply.",
        ),
        "R1",
    ),
    _row(
        "non-interactive setup/apply/validate",
        MERGED_BUT_NOT_OPERATIONAL,
        (
            "builder_ii/cli.py",
            "builder_ii/goose_setup.py",
            "builder_ii/setup_plan.py",
            "builder_ii/setup_overlay.py",
            "builder_ii/setup_rollback.py",
            "builder_ii/setup_apply.py",
            "builder_ii/setup_receipt.py",
            "builder_ii/setup_cli.py",
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
        ("builder_ii/target_profiles.py", "builder_ii/targets_cli.py"),
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
        ("builder_ii/agent_profiles.py", "builder_ii/agent_cli.py"),
        ("builder-agent",),
        ("tests/test_agent_profiles.py", "tests/test_platform_completion_truth.py"),
        (
            "Guided agent profile creation/editing with authority preview and disabled runtime defaults is missing.",
        ),
        "R1",
    ),
    _row(
        "verification profile wizard",
        NOT_STARTED,
        ("builder_ii/verification_profiles.py", "builder_ii/verification_cli.py"),
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
        ("tests/test_setup_rollback.py", "tests/test_setup_apply.py", "tests/test_setup_rollback_execute.py", "tests/test_receipt_records.py", "tests/test_rollback_artifacts.py"),
        (
            "Generic records exist.",
            "R1.2 adds setup rollback snapshot planning with plan/overlay digests, prior existence markers, content digests, redacted previews, and future rollback operations.",
            "R1.3A adds setup apply receipts with changed/skipped/denied paths and before/after digests; R1.3B adds setup rollback receipts for digest-bound rollback execution. Ledger event and replay binding are missing.",
        ),
        "R1",
    ),
    _row(
        "model registry",
        PASSIVE_FOUNDATION,
        ("builder_ii/model_client_registry.py",),
        ("builder-model-policy",),
        ("tests/test_model_client_registry.py", "tests/test_model_policy_cli.py"),
        (
            "Registry is recorded-only and disabled for provider calls.",
            "Execution gateway is missing.",
        ),
        "B6",
    ),
    _row(
        "model routing",
        PASSIVE_FOUNDATION,
        ("builder_ii/model_routing_policy.py", "builder_ii/model_policy_cli.py"),
        ("builder-model-policy",),
        ("tests/test_model_routing_policy.py", "tests/test_model_policy_cli.py"),
        (
            "Recommendation is advisory only.",
            "Provider calls, cost budgets, prompt digests, receipts, and replay declaration are missing.",
        ),
        "B6",
    ),
    _row(
        "model/provider execution",
        MERGED_BUT_NOT_OPERATIONAL,
        ("builder_ii/direct_chat.py", "builder_ii/backends.py"),
        ("builder ask", "builder start"),
        ("tests/test_direct_chat.py", "tests/test_backends.py"),
        (
            "Legacy live local model paths exist.",
            "Governed provider envelope, prompt/context digest, budget, receipt, ledger, and replay statement are missing.",
        ),
        "B6",
    ),
    _row(
        "tool registry",
        PASSIVE_FOUNDATION,
        ("builder_ii/tool_registry.py", "builder_ii/tools_cli.py"),
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
        "MCP/tool invocation",
        DESIGN_ONLY,
        (
            "docs/plan/MCP_POLICY_ARTIFACT_RFC.md",
            "docs/plan/MCP_TOOL_INVENTORY_RFC.md",
            "docs/plan/GOOSE_DEEPAGENTS_MCP_SEAM.md",
        ),
        (),
        ("tests/test_platform_completion_truth.py",),
        (
            "MCP inventory implementation, policy validator, tool call envelope, approval, receipt, rollback classification, and audit are missing.",
        ),
        "B7",
    ),
    _row(
        "passive orchestration assignment",
        PASSIVE_FOUNDATION,
        ("builder_ii/orchestration_assignment.py", "builder_ii/orchestration_cli.py"),
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
            "Ledger records passive workflow events only.",
            "Runtime event kinds for reads, execution, model/tool calls, rollback, and memory mutation are missing.",
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
        ("builder_ii/readonly_founder_demo.py", "builder_ii/targets_cli.py"),
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
        ("builder_ii/hitl_promotion_artifacts.py", "builder_ii/hitl_promotion_cli.py"),
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
        ("builder_ii/execution_candidate_manifest.py", "builder_ii/execution_candidate_manifest_cli.py"),
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
        PASSIVE_FOUNDATION,
        (
            "builder_ii/verification_execution_plan.py",
            "builder_ii/verification_execution_approval.py",
            "builder_ii/verification_execution_receipt.py",
            "builder_ii/verification_execution_runner.py",
            "builder_ii/verification_execution_ledger.py",
            "builder_ii/verification_runner_entrypoints.py",
            "builder_ii/verification_execution_plan_cli.py",
            "builder_ii/hitl_command_execution.py",
            "builder_ii/hitl_execution_records.py",
            "builder_ii/hitl_verification_candidate.py",
            "builder_ii/hitl_execution_cli.py",
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
            "B1.4A/B/C/D add passive verification ledger indexing, query, integrity, and reconstruction reporting.",
            "Receipt state may be NOT_EXECUTED, BLOCKED_BEFORE_EXECUTION, EXECUTED, or FAILED depending on runner outcome.",
            "B1 is closed as passive foundation only; broader execution profiles, live read authority, patching, model/MCP/Goose/deepagents runtime, and B2 write authority remain disabled.",
        ),
        "B2.0",
    ),
    _row(
        "HITL patch proposal",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/hitl_patch_proposal.py", "builder_ii/goose_command_proposal.py", "builder_ii/hitl_patch_cli.py"),
        ("builder-goose", "builder-hitl propose-patch"),
        ("tests/test_hitl_patch_proposal.py", "tests/test_goose_command_proposal.py"),
        (
            "Patch proposal artifact is operationally verified.",
        ),
        "B4",
    ),
    _row(
        "HITL patch application",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/hitl_patch_apply.py", "builder_ii/hitl_patch_cli.py", "builder_ii/hitl_patch_proposal.py", "docs/HITL_PATCH_PROPOSAL.md"),
        ("builder-hitl apply-patch",),
        ("tests/test_hitl_patch_proposal.py", "tests/test_hitl_patch_apply.py"),
        (
            "Patch application is operationally verified.",
            "Enforces clean git state, approval match, verification receipt, and rollback generation before apply.",
        ),
        "B4",
    ),
    _row(
        "rollback execution",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/rollback_artifacts.py", "builder_ii/hitl_patch_cli.py", "builder_ii/hitl_patch_apply.py"),
        ("builder-hitl rollback",),
        ("tests/test_rollback_artifacts.py", "tests/test_hitl_patch_apply.py"),
        (
            "Rollback execution is operationally verified.",
        ),
        "B4",
    ),
    _row(
        "postflight verification",
        ARTIFACT_ONLY,
        ("builder_ii/execution_postflight_records.py",),
        ("builder-hitl",),
        ("tests/test_execution_postflight_records.py",),
        (
            "Postflight records can exist as artifacts.",
            "Generated postflight from real execution is missing.",
        ),
        "B1",
    ),
    _row(
        "Goose setup",
        MERGED_BUT_NOT_OPERATIONAL,
        ("builder_ii/goose_setup.py", "builder_ii/cli.py"),
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
        ("builder_ii/readonly_authority.py", "builder_ii/readonly_inspection_cli.py"),
        ("builder-readonly policy", "builder-readonly read", "builder-readonly validate"),
        ("tests/test_readonly_authority.py",),
        (
            "Unified governed read-only runtime is operationally verified.",
        ),
        "B4",
    ),
    _row(
        "Goose readonly runtime",
        OPERATIONALLY_VERIFIED,
        ("builder_ii/goose_session.py", "builder_ii/goose_readonly.py", "builder_ii/goose_inspection.py", "builder_ii/goose_cli.py", "builder_ii/goose_runtime_harness.py"),
        ("builder-goose", "builder-goose start-readonly", "builder-goose close-readonly"),
        ("tests/test_goose_readonly.py", "tests/test_goose_inspection.py", "tests/test_goose_runtime_harness.py"),
        (
            "Goose readonly runtime is operationally verified with receipts and no-mutation postflight.",
        ),
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
        ("builder_ii/deepagents_work_artifacts.py", "builder_ii/deepagents_cli.py"),
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
        ("builder_ii/deepagents_cli.py", "docs/DEEPAGENTS_POLICY.md", "builder_ii/deepagents_runtime.py"),
        ("builder-deepagents", "builder-deepagents run-plan", "builder-deepagents collect-results"),
        ("tests/test_deepagents_policy.py", "tests/test_deepagents_work_artifacts.py", "tests/test_deepagents_runtime.py"),
        (
            "deepagents runtime is operationally verified with subagent execution receipts and proposal-only results.",
        ),
        "B6",
    ),
    _row(
        "notes/handoff artifacts",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/notes_cli.py",
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
        "B8",
    ),
    _row(
        "artifact memory",
        DESIGN_ONLY,
        ("docs/plan/ARTIFACT_MEMORY_RFC.md",),
        (),
        ("tests/test_platform_completion_truth.py",),
        (
            "Memory atom schema, memory index, reconstruction artifact, staleness policy, searchable handoffs, and mutation approval are missing.",
        ),
        "B8",
    ),
    _row(
        "operator quickstart/golden path",
        PASSIVE_FOUNDATION,
        ("docs/OPERATOR_QUICKSTART.md", "builder_ii/workflow_orchestrator.py"),
        ("builder-session", "builder-workflow"),
        ("tests/test_prepare_package_quickstart.py", "tests/test_workflow_ledger.py"),
        (
            "Quickstart is a passive package lane.",
            "A coherent path through real read, plan, approve, verify, patch, rollback, and handoff is missing.",
        ),
        "B9",
    ),
    _row(
        "platform doctor/status/audit",
        PASSIVE_FOUNDATION,
        (
            "builder_ii/platform_completion_audit.py",
            "builder_ii/platform_status_cli.py",
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
        ("scripts/verify_v0_release.py", "docs/RELEASE_PROOF.md", "builder_ii/quality_gates.py", "builder_ii/quality_cli.py"),
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
        MERGED_BUT_NOT_OPERATIONAL,
        ("builder_ii/command_authority.py", "docs/COMMAND_AUTHORITY.md"),
        (),
        ("tests/test_command_authority.py", "tests/test_platform_completion_truth.py"),
        (
            "Registry metadata is explicit and tested.",
            "No dynamic interceptor prevents legacy commands or future commands from crossing authority.",
        ),
        "B1/B6/B7",
    ),
    _row(
        "docs truth enforcement",
        PASSIVE_FOUNDATION,
        ("builder_ii/platform_completion_audit.py", "builder_ii/platform_status_cli.py", "docs/PLATFORM_COMPLETION_AUDIT.md"),
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


def render_human_summary(rows: tuple[CapabilityRow, ...] = REQUIRED_CAPABILITY_ROWS) -> str:
    counts = state_counts(rows)
    lines = [
        "builder-II platform truth state",
        "",
        "builder-II is passive-foundation-complete for governed artifacts, but operationally incomplete.",
        "No runtime execution, patch application, model/provider call, MCP/tool invocation, Goose runtime promotion, deepagents runtime, autonomous write, or commit/push authority is promoted by R1.4.",
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
            "Generic/B2 rollback execution, interactive setup wizard, runtime execution, and B1 verification execution remain non-operational; R1.4 reconciles only the legacy setup command surface.",
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
    if root is not None:
        errors.extend(validate_referenced_files(root))
    return errors


_FALSE_COMPLETION_EXACT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bfully completed and verified\b", re.IGNORECASE), "ambiguous completed-and-verified claim"),
    (re.compile(r"\bfoundation is complete\b", re.IGNORECASE), "ambiguous foundation completion claim"),
    (re.compile(r"\bartifact-first foundation is complete\b", re.IGNORECASE), "ambiguous artifact foundation completion claim"),
    (re.compile(r"\bfull governed artifact platform is built, tested, and proven\b", re.IGNORECASE), "ambiguous full-platform claim"),
    (re.compile(r"\bModel routing policy artifact \(RFC exists, artifact not yet built\)", re.IGNORECASE), "stale model routing RFC claim"),
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
