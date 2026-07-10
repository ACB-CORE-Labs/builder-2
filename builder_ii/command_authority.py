import functools
from dataclasses import dataclass, fields, replace
from typing import Any, cast

from builder_ii.assurance import (
    BLOCKED_BY_EVIDENCE,
    BOUNDED_EXECUTION_VERIFIED,
    DEMO_ONLY_VERIFIED,
    LIVE_PROVIDER_VERIFIED,
    LOCAL_STATE_MUTATION_VERIFIED,
    MUTATION_WITH_ROLLBACK_VERIFIED,
    PASSIVE_ARTIFACT_VERIFIED,
    READ_ONLY_RUNTIME_VERIFIED,
    SAFETY_CRITICAL_PROHIBITED,
    AssuranceState,
    render_assurance_definitions_markdown,
)

# Standard authority tiers
TIER_0 = "Tier 0 — read-only inspection"
TIER_1 = "Tier 1 — artifact-only planning/validation"
TIER_2 = "Tier 2 — operator-managed setup/runtime helper"
TIER_3 = "Tier 3 — HITL-gated execution candidate"
TIER_4 = "Tier 4 — forbidden/unpromoted automation"

VALID_TIERS = {TIER_0, TIER_1, TIER_2, TIER_3, TIER_4}

# Valid promotion states
STATE_SPEC_ONLY = "spec_only"
STATE_ARTIFACT_ONLY = "artifact_only"
STATE_VALIDATION_ONLY = "validation_only"
STATE_READ_ONLY_RUNTIME_CANDIDATE = "read_only_runtime_candidate"
STATE_OPERATOR_MANAGED = "operator_managed"
STATE_HITL_RUNTIME_CANDIDATE = "hitl_runtime_candidate"
STATE_FORBIDDEN_UNPROMOTED = "forbidden_unpromoted"
STATE_ENABLED = "enabled"

VALID_PROMOTION_STATES = {
    STATE_SPEC_ONLY,
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


@dataclass(frozen=True)
class CommandAuthorityRecord:
    name: str  # Script name or subcommand path, e.g. "builder" or "builder-session prepare-package"
    entrypoint: str  # Python entrypoint mapping
    tier: str  # Authority tier
    promotion_state: str  # Capability promotion state
    runtime_boundary: str  # Description of execution boundaries
    write_boundary: str  # Description of what may be modified or created
    approval_mode: str  # Method of approval required
    approval_boundary: str  # Human boundary for approval
    output_behavior: str  # Behavior of stdout/stderr and file writing
    failure_mode: str  # How errors are propagated and state recovered
    notes: str  # Details on limitations and deprecated/legacy logic
    allows_runtime_start: bool = False
    allows_process_control: bool = False
    allows_model_execution: bool = False
    allows_shell_execution: bool = False
    allows_source_writes: bool = False
    allows_memory_mutation: bool = False
    allows_git_mutation: bool = False
    allows_artifact_writes: bool = False
    allows_state_writes: bool = False
    allows_readonly_subprocess: bool = False
    allows_external_tool_invocation: bool = False

    # Set by `_generate_extra_records` for the commands nobody declared, and by
    # `convention_kernel.find_matching_record` for a subcommand a delegating group stands in for.
    # Either way the authority is a copy of a neighbour's, taken because the neighbour's name is a
    # prefix of theirs. That is a naming coincidence, not evidence, so an inherited record may never
    # certify a requested effect.
    #
    # `inherited_from` names the record the authority was copied *from*, so it is never this record:
    # a record that inherits from itself would report a copy as a declaration, which is the one
    # thing this pair of fields exists to prevent. `validate_registry_invariants` enforces it.
    authority_is_inherited: bool = False
    inherited_from: str = ""

    @property
    def is_command_group(self) -> bool:
        """Structural fact: some other command's name extends this one on a word boundary.

        Derived from the registry rather than transcribed beside it. The transcribed version listed
        twenty names, one of which (`builder-tui`) matched no record at all -- the CLI group is named
        `builder tui`, with a space -- while thirty-two records that demonstrably have subcommands
        went unmarked. A hand-kept list of "which records are groups" is a second place for the truth
        to live, and it had already drifted.
        """
        return self.name in structural_command_groups()

    @property
    def authority_delegates_to_subcommands(self) -> bool:
        """Resolution policy: may an *unregistered* subcommand of this record resolve to it?

        This is a different question from `is_command_group`, and conflating the two is how a
        structural fact would silently widen a permission. `builder-runtime` is structurally a group
        and declares `runtime_start`, `state_writes`, `readonly_subprocess` and
        `external_tool_invocation`; letting `builder-runtime <anything>` resolve to it would hand
        that authority to a subcommand nobody wrote. Delegation stays a curated decision.
        """
        return self.name in AUTHORITY_DELEGATING_GROUPS


# Which command groups may absorb an *unregistered* subcommand in `find_matching_record`. Curated,
# because widening it grants that group's declared authority to a command nobody wrote. Every name
# here must be a real record and must be structurally a group -- both are pinned. The transcribed
# predicate this replaces also carried `builder-tui`, which has never named a record.
AUTHORITY_DELEGATING_GROUPS: frozenset[str] = frozenset(
    {
        "builder",
        "builder-context",
        "builder-goose",
        "builder-deepagents",
        "builder-hitl",
        "builder-orchestration",
        "builder-session",
        "builder-profile-pack",
        "builder-workflow",
        "builder-ledger",
        "builder-targets",
        "builder-platform",
        "builder-memory",
        "builder-config",
        "builder-setup",
        "builder-model",
        "builder-mcp",
        "builder-tools",
        "builder-code-vault",
    }
)


def command_name_words(name: str) -> tuple[str, ...]:
    """A command name is a sequence of words. `builder-goose validate` is two, not one string.

    Every question about parentage here is a question about *word* prefixes. Asking it about string
    prefixes instead made `builder-goose validate-command-proposal` a child of `builder-goose
    validate` rather than of the `builder-goose` group.
    """
    return tuple(name.split())


def is_token_prefix(parent: str, child: str) -> bool:
    """True when `parent` names a strict word-prefix of `child`."""
    pw, cw = command_name_words(parent), command_name_words(child)
    return len(pw) < len(cw) and cw[: len(pw)] == pw


@functools.cache
def structural_command_groups() -> frozenset[str]:
    """Every record that some other command's name extends on a word boundary.

    Called lazily: the registry must be fully assembled first, because `builder tui` is a group only
    by virtue of `builder tui gates`, which is itself synthesized.
    """
    names = tuple(record.name for record in COMMAND_AUTHORITY_REGISTRY)
    return frozenset(parent for parent in names if any(is_token_prefix(parent, child) for child in names))


def inheritance_errors(record: CommandAuthorityRecord) -> list[str]:
    """An inherited record is a copy, so it names a source, and the source is never itself.

    Two producers mint inherited records -- `_generate_extra_records` here, and
    `convention_kernel.find_matching_record` for a delegating group's unregistered subcommand. Only
    the first lands in the registry, so `validate_registry_invariants` alone cannot see the second.
    Both are checked against this, because a record that inherits from itself reports a copy as a
    declaration, and `check_command_authority` refuses effects on exactly that distinction.
    """
    errors: list[str] = []
    if record.authority_is_inherited:
        if not record.inherited_from:
            errors.append(f"Record '{record.name}' is marked inherited but names no source record")
        elif record.inherited_from == record.name:
            errors.append(f"Record '{record.name}' inherits from itself; a copy is not a declaration")
    elif record.inherited_from:
        errors.append(f"Record '{record.name}' names inheritance source '{record.inherited_from}' but is not inherited")
    return errors


# Every `allows_*` field the record carries, in declaration order. Derived from the dataclass rather
# than transcribed beside it: a hand-written list is a second place for the truth to live, and
# `render_registry_markdown_table` already demonstrated what happens when one drifts -- it named five
# of eleven flags for as long as the flags existed, and nothing failed, because nothing compared them.
CAPABILITY_FLAGS: tuple[str, ...] = tuple(
    field.name for field in fields(CommandAuthorityRecord) if field.name.startswith("allows_")
)


def _readonly_tui_record(name: str) -> CommandAuthorityRecord:
    return CommandAuthorityRecord(
        name=name,
        entrypoint="builder_ii.tui_inspection_cli",
        tier=TIER_0,
        promotion_state=STATE_SPEC_ONLY,
        runtime_boundary="Reads existing governed artifact files and renders terminal inspection output only; no runtime, model, shell, Goose, deepagents, MCP, or tool execution.",
        write_boundary="No changes to workspace, artifact store, runtime state, target repository, git, or memory.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints read-only inspection status, validation diagnostics, and real next-command hints to stdout.",
        failure_mode="Exits non-zero on invalid JSON, schema errors, governance violations, failed present gates, command authority drift, or explicit lookup misses.",
        notes="First-class governed TUI inspector surface. It observes and explains only; artifact creation and execution remain on separate governed CLIs.",
    )


READONLY_TUI_COMMAND_GROUPS: tuple[str, ...] = (
    "builder tui",
    "builder hitl",
    "builder profile",
    "builder model",
    "builder promote",
    "builder postflight",
    "builder goose",
    "builder code-vault",
)

READONLY_TUI_AUTHORITY_RECORDS: tuple[CommandAuthorityRecord, ...] = tuple(
    _readonly_tui_record(name) for name in (*READONLY_TUI_COMMAND_GROUPS, *READONLY_TUI_COMMANDS)
)


class CommandAuthorityError(PermissionError):
    """Raised when a command attempts an unregistered or under-classified effect."""


@dataclass(frozen=True)
class CommandAuthorityDecision:
    command_name: str
    allowed: bool
    tier: str
    promotion_state: str
    approval_mode: str
    assurance_state: AssuranceState
    requested_effects: tuple[str, ...]
    reasons: tuple[str, ...]
    capability_ref: str = ""

    @property
    def command(self) -> str:
        return self.command_name

    @property
    def reason(self) -> str:
        return "; ".join(self.reasons) if self.reasons else ""

    @property
    def allowed_effects(self) -> tuple[str, ...]:
        record = get_command_record(self.command_name)
        if record is None:
            return ()
        return tuple(
            effect for effect, flags in _EFFECT_FLAGS.items() if any(bool(getattr(record, flag)) for flag in flags)
        )

    @property
    def denied_effects(self) -> tuple[str, ...]:
        allowed = self.allowed_effects
        return tuple(eff for eff in self.requested_effects if eff not in allowed)

    def to_evidence(self) -> dict[str, object]:
        return {
            "kind": "builder_ii.command_authority_decision",
            "command": self.command,
            "allowed": self.allowed,
            "reason": self.reason,
            "tier": self.tier,
            "promotion_state": self.promotion_state,
            "approval_mode": self.approval_mode,
            "allowed_effects": list(self.allowed_effects),
            "denied_effects": list(self.denied_effects),
            "capability_ref": self.capability_ref,
            "fail_closed": not self.allowed,
        }


_EFFECT_FLAGS: dict[str, tuple[str, ...]] = {
    "runtime_start": ("allows_runtime_start",),
    "process_control": ("allows_process_control",),
    "model_execution": ("allows_model_execution",),
    "shell_execution": ("allows_shell_execution",),
    "source_write": ("allows_source_writes",),
    "source_writes": ("allows_source_writes",),
    "patch_application": ("allows_source_writes",),
    "git_mutation": ("allows_git_mutation",),
    "memory_mutation": ("allows_memory_mutation",),
    "artifact_write": ("allows_artifact_writes",),
    "artifact_writes": ("allows_artifact_writes",),
    "state_write": ("allows_state_writes",),
    "state_writes": ("allows_state_writes",),
    "readonly_subprocess": ("allows_readonly_subprocess",),
    "external_tool": ("allows_external_tool_invocation",),
    "external_tool_invocation": ("allows_external_tool_invocation",),
}


@dataclass(frozen=True)
class AssuranceDerivation:
    """An assurance state together with the single fact that produced it."""

    state: AssuranceState
    because: str


# Order matters: the first branch that matches decides. `_BOUNDED_FLAGS` is the tail of the chain, so
# a record setting several of them is attributed to the first one declared here.
_BOUNDED_FLAGS: tuple[str, ...] = (
    "allows_process_control",
    "allows_shell_execution",
    "allows_external_tool_invocation",
    "allows_readonly_subprocess",
)

# Writes to builder-II's own local state, outside the artifact store. Below `_BOUNDED_FLAGS` in the
# chain -- `builder-runtime stop` deletes the same marker `clear-marker` does, and also kills a
# process, which is the larger claim. Above the passive fall-through, which is the whole point:
# `PASSIVE_ARTIFACT_VERIFIED` promises the command "writes nothing outside the artifact store".
#
# `allows_memory_mutation` is deliberately absent. It also mutates a store outside the artifact
# store, so it reads like a member -- but this state's definition ends "starts no runtime, spawns no
# process, and calls no provider", a *positive* safety claim, and `allows_memory_mutation` is the one
# capability builder-II refuses to promote on any evidence. Granting the refused capability the
# safest available label is the defect this whole chain exists to prevent, one level up. It derives
# SAFETY_CRITICAL_PROHIBITED instead.
_LOCAL_STATE_FLAGS: tuple[str, ...] = ("allows_state_writes",)


def explain_assurance_for_record(record: CommandAuthorityRecord) -> AssuranceDerivation:
    """Map legacy authority metadata into the sharper high-assurance state lattice, and say why.

    The state alone is not reviewable. Three records -- `builder-readonly`, `builder-goose
    start-readonly`, `builder-goose close-readonly` -- derive READ_ONLY_RUNTIME_VERIFIED with *no*
    capability flag set, from their promotion state. A reader given only the eleven flags and the
    state cannot reconcile them, and would reasonably conclude the state was wrong. It is not; the
    derivation simply was not written down. Now it is, and `render_command_authority_doc` prints it.
    """
    # First, above tier and promotion state, because a refused capability is refused whatever else
    # the record says about itself. A Tier 4 record claiming it would otherwise read
    # BLOCKED_BY_EVIDENCE -- "blocked pending evidence" -- and no evidence unblocks this one.
    if record.allows_memory_mutation:
        return AssuranceDerivation(SAFETY_CRITICAL_PROHIBITED, "`allows_memory_mutation` is set")
    if record.tier == TIER_4:
        return AssuranceDerivation(BLOCKED_BY_EVIDENCE, "tier is `Tier 4`")
    if record.promotion_state == STATE_FORBIDDEN_UNPROMOTED:
        return AssuranceDerivation(BLOCKED_BY_EVIDENCE, f"promotion state is `{STATE_FORBIDDEN_UNPROMOTED}`")
    if "demo" in record.name:
        return AssuranceDerivation(DEMO_ONLY_VERIFIED, "the command name says `demo`")
    if "demo" in record.notes.lower():
        return AssuranceDerivation(DEMO_ONLY_VERIFIED, "the notes say `demo`")
    if record.allows_source_writes:
        return AssuranceDerivation(MUTATION_WITH_ROLLBACK_VERIFIED, "`allows_source_writes` is set")
    if record.allows_git_mutation:
        return AssuranceDerivation(MUTATION_WITH_ROLLBACK_VERIFIED, "`allows_git_mutation` is set")
    if record.allows_model_execution:
        return AssuranceDerivation(LIVE_PROVIDER_VERIFIED, "`allows_model_execution` is set")
    if record.allows_runtime_start:
        return AssuranceDerivation(READ_ONLY_RUNTIME_VERIFIED, "`allows_runtime_start` is set")
    if record.promotion_state == STATE_READ_ONLY_RUNTIME_CANDIDATE:
        return AssuranceDerivation(READ_ONLY_RUNTIME_VERIFIED, f"promotion state is `{STATE_READ_ONLY_RUNTIME_CANDIDATE}`")
    for flag in _BOUNDED_FLAGS:
        if getattr(record, flag):
            return AssuranceDerivation(BOUNDED_EXECUTION_VERIFIED, f"`{flag}` is set")
    for flag in _LOCAL_STATE_FLAGS:
        if getattr(record, flag):
            return AssuranceDerivation(LOCAL_STATE_MUTATION_VERIFIED, f"`{flag}` is set")
    return AssuranceDerivation(PASSIVE_ARTIFACT_VERIFIED, "no flag or state raises assurance above passive")


def assurance_state_for_record(record: CommandAuthorityRecord) -> AssuranceState:
    """Map legacy authority metadata into the sharper high-assurance state lattice."""
    return explain_assurance_for_record(record).state


def _assurance_probe(**flags: bool) -> CommandAuthorityRecord:
    """A record whose only distinguishing feature is which capability flags are set.

    The flags are applied with `replace` rather than splatted into the constructor: the record now
    carries non-boolean fields, and `**flags: bool` would silently type a `str` field as `bool`. The
    keys are checked against `CAPABILITY_FLAGS` first, which is what earns the cast -- and which also
    catches a probe misspelling a flag name, where `replace` would raise but `**` would not.
    """
    unknown = tuple(sorted(set(flags) - set(CAPABILITY_FLAGS)))
    if unknown:
        raise ValueError(f"not capability flags: {unknown}")

    baseline = CommandAuthorityRecord(
        name="probe",
        entrypoint="probe",
        tier=TIER_2,
        promotion_state=STATE_ENABLED,
        runtime_boundary="probe",
        write_boundary="probe",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="probe",
        output_behavior="probe",
        failure_mode="probe",
        notes="probe",
    )
    return replace(baseline, **cast(dict[str, Any], flags))


# Which flags actually move the assurance state, discovered by perturbation rather than by reading
# the chain above and transcribing the answer. A transcription goes stale the moment the chain
# changes; this cannot. `docs/COMMAND_AUTHORITY.md` prints both sets, so a reader can see that
# `allows_memory_mutation`, `allows_artifact_writes` and `allows_state_writes` -- two of which were
# among the only five flags the doc used to render -- carry no risk signal at all.
_ASSURANCE_BASELINE: AssuranceState = assurance_state_for_record(_assurance_probe())

ASSURANCE_DERIVING_FLAGS: tuple[str, ...] = tuple(
    flag for flag in CAPABILITY_FLAGS if assurance_state_for_record(_assurance_probe(**{flag: True})) != _ASSURANCE_BASELINE
)

ASSURANCE_INERT_FLAGS: tuple[str, ...] = tuple(flag for flag in CAPABILITY_FLAGS if flag not in ASSURANCE_DERIVING_FLAGS)


def check_command_authority(
    command_name: str,
    *,
    requested_effects: tuple[str, ...] = (),
    approval_ref: str | None = None,
    safety_critical_claim: bool = False,
    hitl_bound: bool | None = None,
    capability_ref: str = "",
) -> CommandAuthorityDecision:
    record = get_command_record(command_name)
    if record is None:
        return CommandAuthorityDecision(
            command_name=command_name,
            allowed=False,
            tier=TIER_4,
            promotion_state=STATE_FORBIDDEN_UNPROMOTED,
            approval_mode=MODE_FORBIDDEN_UNPROMOTED,
            assurance_state=BLOCKED_BY_EVIDENCE,
            requested_effects=tuple(requested_effects),
            reasons=(f"command is not registered in COMMAND_AUTHORITY_REGISTRY: {command_name}",),
            capability_ref=capability_ref,
        )

    reasons: list[str] = []
    if safety_critical_claim:
        reasons.append("life-safety or safety-critical authority is prohibited by builder-II")
    if record.tier == TIER_4 or record.promotion_state == STATE_FORBIDDEN_UNPROMOTED:
        reasons.append("command is forbidden or unpromoted")

    # A record nobody declared cannot certify an effect. `_generate_extra_records` copied this
    # record's capability flags from whichever declared command is a word-prefix of its name; that
    # is a naming coincidence, and a coincidence is not evidence. Deny-only: an inherited record can
    # lose a permission it never earned, never gain one.
    if requested_effects and record.authority_is_inherited:
        reasons.append(
            f"command's authority is inherited from `{record.inherited_from}`, not declared; "
            f"an undeclared command cannot certify a requested effect"
        )

    for effect in requested_effects:
        flags = _EFFECT_FLAGS.get(effect)
        if flags is None:
            reasons.append(f"unknown requested effect: {effect}")
            continue
        if not any(bool(getattr(record, flag)) for flag in flags):
            reasons.append(f"command is not classified for requested effect: {effect}")

    if record.approval_mode == MODE_HITL_ARTIFACT_REQUIRED:
        if not approval_ref and hitl_bound is not True:
            reasons.append("command requires a HITL approval artifact reference")

    assurance = SAFETY_CRITICAL_PROHIBITED if safety_critical_claim else assurance_state_for_record(record)
    return CommandAuthorityDecision(
        command_name=command_name,
        allowed=not reasons,
        tier=record.tier,
        promotion_state=record.promotion_state,
        approval_mode=record.approval_mode,
        assurance_state=assurance,
        requested_effects=tuple(requested_effects),
        reasons=tuple(reasons),
        capability_ref=capability_ref,
    )


def enforce_command_authority(
    command_name: str,
    *,
    requested_effects: tuple[str, ...] = (),
    approval_ref: str | None = None,
    safety_critical_claim: bool = False,
    hitl_bound: bool | None = None,
    capability_ref: str = "",
) -> CommandAuthorityDecision:
    decision = check_command_authority(
        command_name,
        requested_effects=requested_effects,
        approval_ref=approval_ref,
        safety_critical_claim=safety_critical_claim,
        hitl_bound=hitl_bound,
        capability_ref=capability_ref,
    )
    if not decision.allowed:
        raise CommandAuthorityError("; ".join(decision.reasons))
    return decision


# A curated list of subcommands that must be explicitly classified
REQUIRED_SUBCOMMANDS = {
    *READONLY_TUI_COMMANDS,
    "builder-targets list",
    "builder-targets show",
    "builder-targets validate",
    "builder-targets artifact",
    "builder-targets demo",
    "builder-targets readonly-founder-demo",
    "builder-session prepare-package",
    "builder-session validate-prepare-package",
    "builder-session summarize-prepare-package",
    "builder-context pack",
    "builder-context changed",
    "builder-context artifact",
    "builder setup",
    "builder onboarding",
    "builder init",
    "builder pull",
    "builder start",
    "builder ask",
    "builder verify",
    "builder benchmark",
    "builder capabilities",
    "builder switch-model",
    "builder models",
    "builder doctor",
    "builder status",
    "builder config",
    "builder init-prompt",
    "builder stratum",
    "builder-runtime status",
    "builder-runtime clear-marker",
    "builder-runtime stop",
    "builder-runtime reset",
    "builder-goose manifest",
    "builder-goose validate",
    "builder-goose readonly-audit",
    "builder-goose validate-audit",
    "builder-goose inspect-readonly",
    "builder-goose validate-inspection",
    "builder-goose start-readonly",
    "builder-readonly policy",
    "builder-readonly read",
    "builder-readonly content-read",
    "builder-readonly validate",
    "builder-hitl run-command",
    "builder-deepagents policy",
    "builder-deepagents validate",
    "builder-deepagents readiness",
    "builder-deepagents validate-readiness",
    "builder-deepagents forge",
    "builder-deepagents delegate",
    "builder-deepagents work-plan",
    "builder-deepagents assign-subagent",
    "builder-deepagents record-result",
    "builder-deepagents review-result",
    "builder-deepagents request-human-gate",
    "builder-deepagents record-blocked-action",
    "builder-deepagents proposal-result",
    "builder-deepagents validate-work-artifact",
    "builder-deepagents run-plan",
    "builder-deepagents collect-results",
    "builder-deepagents backend-readiness",
    "builder-deepagents execution-candidate",
    "builder-deepagents approve-candidate",
    "builder-deepagents run-approved",
    "builder-deepagents replay-run",
    "builder-deepagents evidence-bundle",
    "builder-deepagents resume-approved",
    "builder-hitl propose-patch",
    "builder-hitl approve-patch",
    "builder-hitl apply-patch",
    "builder-hitl approve-rollback",
    "builder-hitl rollback",
    "builder-hitl request",
    "builder-hitl receipt",
    "builder-hitl validate",
    "builder-hitl promotion-request",
    "builder-hitl promotion-review",
    "builder-hitl promotion-decision",
    "builder-hitl approval-boundary",
    "builder-hitl rejection-record",
    "builder-hitl validate-promotion",
    "builder-hitl candidate-manifest",
    "builder-hitl validate-candidate-manifest",
    "builder-orchestration plan",
    "builder-orchestration render-assignment",
    "builder-orchestration validate",
    "builder-orchestration dry-run",
    "builder-profile-pack scaffold",
    "builder-profile-pack render",
    "builder-profile-pack validate",
    "builder-profile-pack dry-run",
    "builder-model-policy validate",
    "builder-model-policy render",
    "builder-model-policy dry-run",
    "builder-model call",
    "builder-model standalone-call",
    "builder-model validate-receipt",
    "builder workflow plan",
    "builder workflow promote",
    "builder workflow candidate",
    "builder workflow verify-chain",
    "builder workflow handoff",
    "builder workflow status",
    "builder ledger list",
    "builder ledger replay",
    "builder ledger audit",
    "builder ledger query-receipts",
    "builder ledger validate-receipts",
    "builder ledger reconstruct-receipts",
    "builder ledger export",
    "builder ledger index-receipt",
    "builder-workflow plan",
    "builder-workflow promote",
    "builder-workflow candidate",
    "builder-workflow verify-chain",
    "builder-workflow handoff",
    "builder-workflow status",
    "builder-ledger list",
    "builder-ledger replay",
    "builder-ledger audit",
    "builder-ledger query-receipts",
    "builder-ledger validate-receipts",
    "builder-ledger reconstruct-receipts",
    "builder-ledger export",
    "builder-ledger index-receipt",
    "builder-platform matrix",
    "builder-platform status",
    "builder-platform known-limitations",
    "builder-platform audit-docs",
    "builder-platform r1-closure",
    "builder-platform validate-r1-closure",
    "builder-platform operator-status",
    "builder-platform next",
    "builder-platform operator-lane",
    "builder-platform golden-path",
    "builder-platform validate-golden-path",
    "builder-platform demo-loop",
    "builder-platform validate-demo-loop",
    "builder-platform wow",
    "builder-memory atom",
    "builder-memory index",
    "builder-memory search",
    "builder-memory reconstruct",
    "builder-memory validate-atom",
    "builder-memory validate-index",
    "builder-memory validate-reconstruction",
    "builder-memory validate-search-result",
    "builder-config schema",
    "builder-config resolve",
    "builder-config validate",
    "builder-setup plan",
    "builder-setup validate-plan",
    "builder-setup overlay-plan",
    "builder-setup validate-overlay-plan",
    "builder-setup rollback-snapshot",
    "builder-setup validate-rollback-snapshot",
    "builder-setup apply",
    "builder-setup validate-receipt",
    "builder-setup rollback",
    "builder-setup validate-rollback-receipt",
    "builder-setup init",
    "builder-setup wizard",
    "builder-setup validate-onboarding-intent",
    "builder-verify plan",
    "builder-verify validate-plan",
    "builder-verify approve-plan",
    "builder-verify validate-approval",
    "builder-verify validate-receipt",
    "builder-verify evaluate-promotion",
    "builder-verify validate-promotion-evidence",
    "builder-verify run-approved",
    "builder-mcp inventory",
    "builder-mcp policy",
    "builder-mcp call",
    "builder-mcp standalone-call",
    "builder-tools list",
    "builder-tools check",
    "builder-tools missing",
    "builder-tools invoke",
    "builder-tools standalone-invoke",
}

COMMAND_AUTHORITY_REGISTRY: tuple[CommandAuthorityRecord, ...] = (
    # --- Top-Level Script Entrypoints (Delegating to subcommands) ---
    CommandAuthorityRecord(
        name="builder",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Delegates to helper subcommands; root CLI does not execute direct agent/model loops.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must explicitly run command options from active terminal.",
        output_behavior="Interactive terminal messages, text reports, or dispatch to subcommands.",
        failure_mode="Exits non-zero with diagnostic logs; leaves target system unchanged.",
        notes="Root command of builder-II developer platform. Delegates execution to subcommands.",
    ),
    *READONLY_TUI_AUTHORITY_RECORDS,
    CommandAuthorityRecord(
        name="builder stratum",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Reads passive governance artifacts to render a spatial TUI; delegates execution to core tools. Refuses to launch unless invoked with the required --experimental flag. Command tier evaluation is real: it asks check_command_authority rather than guessing from the tier. No chain digest is displayed, because verify_artifact_chain exposes none; the surface renders an explicit absence marker instead of a synthesized value. It starts exactly one runtime, and never itself: the Goose keybinding suspends the TUI and hands the operator's terminal to builder-goose start-readonly with a fixed argv and shell=False, so that command applies its own read-only policy, emits its own launch and close receipts, and runs its own no-mutation postflight. It fails closed twice before anything spawns -- enforce_command_authority must permit the governed command, and a manifest its own validator accepts must already request read_only, which STRATUM never mints. It never spawns Goose directly and never selects Goose builtins. HITL approve/reject never mutate approval state and are not pending features: a surface that renders a digest must not harvest its confirmation, so they refuse and name the governed CLI. The HITL diff viewer remains an unimplemented mockup.",
        write_boundary="No direct write authority at TUI render level. The prepare-package and subagent-dispatch keybindings collect operator input and then refuse, naming builder-session prepare-package and builder-deepagents assign-subagent; the TUI emits no artifact and reports no dispatch it did not perform. Receipts under .builder/receipts are written by the governed command it invokes, never by the render surface.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must explicitly launch TUI with --experimental. No keybinding originates authority: every action that would write, approve, or dispatch is a constitutive refusal that names the governed command, and the one runtime it starts is started by that governed command in the operator's own terminal, never by the TUI harvesting a confirmation for it. It executes nothing else and claims no execution: the command palette is a tier-permission inspector, and the CLI passthrough is a context-injecting composer that surfaces a command for the operator to run in their own terminal.",
        output_behavior="Takes over terminal with Textual TUI interface; suspends it while the governed read-only Goose command holds the terminal.",
        failure_mode="Exits non-zero if --experimental is absent, textual is missing, or the UI crashes; target unchanged. A refused or failed governed Goose launch is reported with the command's own exit code and never as success.",
        notes="STRATUM Command & Control TUI. Gated behind --experimental (plan D5 / item 3.13). Tier evaluation is wired to this registry; the chain digest is shown as absent because none is reachable; writes, subagent dispatch, and HITL approve/reject are constitutive refusals, not pending features; the Goose keybinding is a launcher of builder-goose start-readonly, not a bypass around it; the HITL diff viewer is still a mockup.",
        allows_external_tool_invocation=True,
        allows_runtime_start=True,
    ),
    CommandAuthorityRecord(
        name="builder-runtime",
        entrypoint="builder_ii.runtime_control:runtime_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Interacts with local server endpoints, background agents, and runtime indicators.",
        write_boundary="Writes session runtime lockfiles and state indicators locally.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must trigger control signals manually.",
        output_behavior="Prints server status and active process logs to stdout.",
        failure_mode="Reports failure to talk to the local background process; exits non-zero.",
        notes="Inspects and controls runtime agent sessions locally.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
        allows_runtime_start=True,
        allows_state_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-runtime status",
        entrypoint="builder_ii.runtime_control:runtime_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Inspects local server endpoints, marker files, and listener processes using read-only probes.",
        write_boundary="No changes to workspace, runtime marker, or target repository.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no autonomous runtime probing.",
        output_behavior="Prints runtime health, served model status, marker status, and listener process details.",
        failure_mode="Reports probe failures as DOWN/WARN rows without starting or stopping any process.",
        notes="Operator-managed runtime inspection. It does not grant start, stop, model, patch, or setup authority.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder-runtime clear-marker",
        entrypoint="builder_ii.runtime_control:runtime_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Does not touch live processes; only clears the local runtime marker artifact.",
        write_boundary="Deletes or rewrites the builder runtime marker under configured local state paths.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only.",
        output_behavior="Prints the cleared marker path.",
        failure_mode="Exits non-zero if marker state cannot be cleared.",
        notes="High-authority state cleanup surface; no process control is granted.",
        allows_state_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-runtime stop",
        entrypoint="builder_ii.runtime_control:runtime_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Stops local runtime listener processes selected by the configured port and marker heuristics.",
        write_boundary="Clears local runtime marker unless --keep-marker is used; does not mutate source repositories.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; foreign process termination requires literal confirmation.",
        output_behavior="Prints stopped process IDs and marker cleanup status.",
        failure_mode="Exits non-zero or reports no match; failed process termination leaves marker handling explicit.",
        notes="High-authority operator-managed process control. --force-foreign is denied unless confirmed.",
        allows_process_control=True,
        allows_state_writes=True,
        allows_readonly_subprocess=True,
    ),
    CommandAuthorityRecord(
        name="builder-runtime reset",
        entrypoint="builder_ii.runtime_control:runtime_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Composes stop plus marker cleanup for the local runtime listener.",
        write_boundary="Clears local runtime marker after attempted stop; does not mutate source repositories.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; foreign process termination requires literal confirmation.",
        output_behavior="Prints stopped process IDs and marker cleanup status.",
        failure_mode="Exits non-zero or reports no match; failed process termination leaves marker handling explicit.",
        notes="High-authority operator-managed process control. --force-foreign is denied unless confirmed.",
        allows_process_control=True,
        allows_state_writes=True,
        allows_readonly_subprocess=True,
    ),
    CommandAuthorityRecord(
        name="builder-lanes",
        entrypoint="builder_ii.lane_guides:lane_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Evaluates passive rules and checklists; no subprocess execution.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="Passive check, no approval required.",
        output_behavior="Prints verification checklists and audit messages to console.",
        failure_mode="Exits non-zero if validation fails.",
        notes="Guides operator lane readiness before committing artifacts.",
    ),
    CommandAuthorityRecord(
        name="builder-tools",
        entrypoint="builder_ii.tools_cli:tools_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Delegates governed external tool execution subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_NONE,
        approval_boundary="Delegated to subcommands.",
        output_behavior="Dispatches to tool subcommands.",
        failure_mode="Exits non-zero on failure.",
        notes="Tool execution gateway.",
    ),
    CommandAuthorityRecord(
        name="builder-tools list",
        entrypoint="builder_ii.tools_cli:tools_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Runs local PATH/version probes for known external developer tools.",
        write_boundary="No changes to workspace, target repository, or external tool state.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only.",
        output_behavior="Prints tool metadata and detected install paths.",
        failure_mode="Exits non-zero only if CLI option validation fails.",
        notes="Read-only external tool inspection. It does not invoke tool work modes.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder-tools check",
        entrypoint="builder_ii.tools_cli:tools_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Runs bounded local version probes for known external developer tools.",
        write_boundary="No changes to workspace, target repository, or external tool state.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only.",
        output_behavior="Prints detected status, path, and version for each tool.",
        failure_mode="Exits non-zero when required tools are missing.",
        notes="Read-only external tool inspection. It does not invoke tool work modes.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder-tools missing",
        entrypoint="builder_ii.tools_cli:tools_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Runs bounded local version probes to identify missing required tools.",
        write_boundary="No changes to workspace, target repository, or external tool state.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only.",
        output_behavior="Prints missing tool install guidance.",
        failure_mode="Exits non-zero when required tools are missing.",
        notes="Read-only external tool inspection. It does not install or invoke tool work modes.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder-context",
        entrypoint="builder_ii.context_cli:context_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Legacy context builder; delegates execution details to subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Legacy context generator; operator must run command explicitly.",
        output_behavior="Generates codebase context state representation via subcommands.",
        failure_mode="Exits non-zero if git or file scanning fails.",
        notes="LEGACY. Uses external repomix or git commands. Not the canonical governed path.",
    ),
    CommandAuthorityRecord(
        name="builder-git-state",
        entrypoint="builder_ii.git_state_cli:git_state_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Executes local git queries via read-only subprocess.",
        write_boundary="Writes declarative state file artifacts in workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="Passive git branch check.",
        output_behavior="Saves JSON file containing current commit info.",
        failure_mode="Exits non-zero if git command fails.",
        notes="Captures current revision state to confirm context stability.",
        allows_artifact_writes=True,
        allows_readonly_subprocess=True,
    ),
    CommandAuthorityRecord(
        name="builder-targets",
        entrypoint="builder_ii.targets_cli:targets_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Delegates target operations to helper subcommands; root CLI does not execute direct agent loops.",
        write_boundary="No direct write authority at root targets CLI level.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must explicitly run command options from active terminal.",
        output_behavior="Interactive terminal messages or dispatch to subcommands.",
        failure_mode="Exits non-zero on target resolution error.",
        notes="Root command of targets CLI.",
    ),
    CommandAuthorityRecord(
        name="builder-targets list",
        entrypoint="builder_ii.targets_cli:targets_app",
        tier=TIER_0,
        promotion_state=STATE_SPEC_ONLY,
        runtime_boundary="Retrieves target profile metadata list; no execution.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs available target names and definitions.",
        failure_mode="Exits non-zero on target resolution error.",
        notes="Lists profiles like generic, builder, and core.",
    ),
    CommandAuthorityRecord(
        name="builder-targets show",
        entrypoint="builder_ii.targets_cli:targets_app",
        tier=TIER_0,
        promotion_state=STATE_SPEC_ONLY,
        runtime_boundary="Retrieves target profile details; no execution.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs detailed target configuration.",
        failure_mode="Exits non-zero on target resolution error.",
        notes="Shows profile like generic, builder, and core.",
    ),
    CommandAuthorityRecord(
        name="builder-targets validate",
        entrypoint="builder_ii.targets_cli:targets_app",
        tier=TIER_0,
        promotion_state=STATE_SPEC_ONLY,
        runtime_boundary="Validates target profile registry or artifact.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs validation success or errors.",
        failure_mode="Exits non-zero on validation failure.",
        notes="Validates target configuration files.",
    ),
    CommandAuthorityRecord(
        name="builder-targets artifact",
        entrypoint="builder_ii.targets_cli:targets_app",
        tier=TIER_1,
        promotion_state=STATE_SPEC_ONLY,
        runtime_boundary="Resolves target details without execution.",
        write_boundary="Writes target profile JSON artifact to path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs JSON target artifact or writes to file.",
        failure_mode="Exits non-zero on generation errors.",
        notes="Generates target profile artifacts.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-targets demo",
        entrypoint="builder_ii.targets_cli:targets_app",
        tier=TIER_0,
        promotion_state=STATE_SPEC_ONLY,
        runtime_boundary="Retrieves target profile demo recipe; no execution.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs markdown demo recipe.",
        failure_mode="Exits non-zero on target resolution error.",
        notes="Prints target profile demo command recipes.",
    ),
    CommandAuthorityRecord(
        name="builder-targets readonly-founder-demo",
        entrypoint="builder_ii.targets_cli:targets_app",
        tier=TIER_1,
        promotion_state=STATE_SPEC_ONLY,
        runtime_boundary="Generates passive read-only founder demo planning artifacts; no execution.",
        write_boundary="Writes demo artifacts, events, and status JSON files in output directory.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs list of generated files.",
        failure_mode="Exits non-zero on generation errors.",
        notes="Emits only passive planning artifacts with zero execution authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-session",
        entrypoint="builder_ii.session_cli:session_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Delegates packaging and checks to subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_NONE,
        approval_boundary="Read-only checks or artifact-only packaging; no approval needed.",
        output_behavior="Dispatches to subcommand functions.",
        failure_mode="Raises ValidationError or exits non-zero on corrupt schemas.",
        notes="Canonical governed operator lane entrypoint.",
    ),
    CommandAuthorityRecord(
        name="builder-code-vault",
        entrypoint="builder_ii.cli.code_vault_cli:code_vault_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Governed read-only CodeVault frame, lint, recall, context projection, deterministic bench, and validation; no shell, model, or CORE runtime.",
        write_boundary="Writes explicit artifact JSON paths only; no target-repo mutation.",
        approval_mode=MODE_NONE,
        approval_boundary="Operator initiates scan and reviews emitted artifacts.",
        output_behavior="Emits hierarchical frame, linter report, recall report, context projection, or bench report JSON.",
        failure_mode="Exits non-zero on validation failure; delete emitted artifacts to roll back.",
        notes="Content-addressed software geometry substrate; artifact_is_authority remains false.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-agent",
        entrypoint="builder_ii.agent_cli:agent_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Resolves active agent profiles and manifests.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator triggers agent inventory check.",
        output_behavior="Lists matching agent definitions.",
        failure_mode="Exits non-zero if spec parse fails.",
        notes="Verifies agent metadata without starting active sessions.",
    ),
    CommandAuthorityRecord(
        name="builder-bridge",
        entrypoint="builder_ii.bridge_cli:bridge_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Tests readiness of external deepagents integrations.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator checks network bridge connectivity.",
        output_behavior="Outputs status report of endpoints.",
        failure_mode="Exits non-zero if network connection fails.",
        notes="Used for bridge diagnostics.",
    ),
    CommandAuthorityRecord(
        name="builder-bundle",
        entrypoint="builder_ii.bundle_cli:bundle_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Validates bundle definitions or packages build artifacts.",
        write_boundary="Creates ZIP or tar bundles in designated build folder.",
        approval_mode=MODE_NONE,
        approval_boundary="Artifact build task.",
        output_behavior="Saves packed bundles.",
        failure_mode="Fails build process and reports missing manifest files.",
        notes="Packages bundle content cleanly.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-goose",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Delegates validation and read-only audits to subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_NONE,
        approval_boundary="Validation and audit only.",
        output_behavior="Dispatches to validation subcommand functions.",
        failure_mode="Exits non-zero on verification failure.",
        notes="Interacts with Goose session metadata and configurations.",
    ),
    CommandAuthorityRecord(
        name="builder-records",
        entrypoint="builder_ii.approval_records_cli:approval_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Decodes and validates cryptographically signed or structured approval logs.",
        write_boundary="Writes verified signature files.",
        approval_mode=MODE_NONE,
        approval_boundary="None; read-only verification.",
        output_behavior="Prints verification results.",
        failure_mode="Exits non-zero on signature mismatch.",
        notes="Governance record validator.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-preflight",
        entrypoint="builder_ii.preflight_cli:preflight_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Runs local environment checks (Python version, CLI presence).",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Lists check statuses.",
        failure_mode="Exits non-zero on system incompatibility.",
        notes="Preflight sanity checker.",
    ),
    CommandAuthorityRecord(
        name="builder-receipt",
        entrypoint="builder_ii.receipt_records_cli:receipt_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Generates or reads execution receipts.",
        write_boundary="Writes receipt JSON files to output folders.",
        approval_mode=MODE_NONE,
        output_behavior="Saves JSON data.",
        failure_mode="Exits non-zero on bad receipt schema.",
        approval_boundary="None.",
        notes="Tracks execution history.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-chain",
        entrypoint="builder_ii.chain_summary_cli:chain_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Traces artifact lineage chains.",
        write_boundary="Writes chain validation artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Generates validation chain report.",
        failure_mode="Exits non-zero if lineage broken.",
        notes="Artifact linkage audit.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-handoff",
        entrypoint="builder_ii.handoff_bundle_cli:handoff_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Aggregates verified evidence and creates handoff bundle metadata.",
        write_boundary="Writes handoff markdown files.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes handoff bundle files.",
        failure_mode="Exits non-zero on missing verification docs.",
        notes="Packages handoffs.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-intake",
        entrypoint="builder_ii.intake_cli:intake_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Ingests inputs from outside workspace.",
        write_boundary="Writes configuration files in specific workspace location.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Saves ingested assets.",
        failure_mode="Exits non-zero on invalid payload.",
        notes="Imports data packages.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-index",
        entrypoint="builder_ii.artifact_index_cli:index_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Tracks and indexes generated artifact files.",
        write_boundary="Updates local artifact index JSON ledger.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Updates local index file.",
        failure_mode="Exits non-zero if path outside worktree.",
        notes="Passive registry of workspace outputs.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-promotion",
        entrypoint="builder_ii.promotion_readiness_cli:promotion_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Analyzes readiness for target promotion.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs promotion validation list.",
        failure_mode="Exits non-zero if promotion checklist is not met.",
        notes="Validates readiness gates.",
    ),
    CommandAuthorityRecord(
        name="builder-promotion-decision",
        entrypoint="builder_ii.promotion_decision_cli:promotion_decision_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a signed promotion decision artifact.",
        write_boundary="Writes promotion decision JSON artifact.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes signed promotion records.",
        failure_mode="Exits non-zero on schema validation failures.",
        notes="Governance promotion decision recorder.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-state-index",
        entrypoint="builder_ii.state_index_cli:state_index_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Constructs system state summaries.",
        write_boundary="Writes state index JSON files.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs state summary records.",
        failure_mode="Exits non-zero on file-system index failures.",
        notes="Indexes state layers.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-snapshot",
        entrypoint="builder_ii.snap_cli:snap_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Records current directory snapshot hashes.",
        write_boundary="Writes workspace snapshot hash index.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Generates checksum manifest.",
        failure_mode="Exits non-zero on scanning error.",
        notes="Workspace integrity checks.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_4,
        promotion_state=STATE_FORBIDDEN_UNPROMOTED,
        runtime_boundary="Delegates deepagent specs rendering and validation to subcommands; active run is forbidden.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_FORBIDDEN_UNPROMOTED,
        approval_boundary="Forbidden; no supported approval path.",
        output_behavior="Dispatches to subcommands.",
        failure_mode="Exits non-zero.",
        notes="Optional readiness specs and dry-runs only. Autonomous runs are blocked.",
    ),
    CommandAuthorityRecord(
        name="builder-notes",
        entrypoint="builder_ii.notes_cli:notes_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Verifies or creates handoff notes artifacts.",
        write_boundary="Writes handoff notes markdown files.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes text files.",
        failure_mode="Exits non-zero if handoff validations fail.",
        notes="Writes handoff notes.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-quality",
        entrypoint="builder_ii.quality_cli:quality_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Checks code linting or test coverage thresholds.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints compliance report.",
        failure_mode="Exits non-zero if quality threshold missed.",
        notes="Quality assurance checks.",
    ),
    CommandAuthorityRecord(
        name="builder-research",
        entrypoint="builder_ii.research_cli:research_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Builds read-only research plans.",
        write_boundary="Writes plan metadata files.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs JSON research plan.",
        failure_mode="Exits non-zero on validation failures.",
        notes="Artifact planning utility.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-performance",
        entrypoint="builder_ii.performance_cli:performance_app",
        tier=TIER_0,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Measures CLI loading time and file sizes.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs timing statistics.",
        failure_mode="Exits non-zero if execution limits exceeded.",
        notes="Performance benchmarking.",
    ),
    CommandAuthorityRecord(
        name="builder-readonly",
        entrypoint="builder_ii.readonly_inspection_cli:readonly_app",
        tier=TIER_0,
        promotion_state=STATE_READ_ONLY_RUNTIME_CANDIDATE,
        runtime_boundary="Inspects system files and configurations without execution.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs inspection reports.",
        failure_mode="Exits non-zero if targeted file does not exist.",
        notes="Ensures safe environment observation.",
    ),
    CommandAuthorityRecord(
        name="builder-readonly policy",
        entrypoint="builder_ii.readonly_inspection_cli:readonly_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Generates read policy schema.",
        write_boundary="Writes policy JSON.",
        allows_artifact_writes=True,
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs read policy.",
        failure_mode="Exits non-zero on error.",
        notes="B3 read policy.",
    ),
    CommandAuthorityRecord(
        name="builder-readonly read",
        entrypoint="builder_ii.readonly_inspection_cli:readonly_app",
        tier=TIER_1,
        promotion_state=STATE_READ_ONLY_RUNTIME_CANDIDATE,
        runtime_boundary="Reads system files according to policy.",
        write_boundary="Writes read receipt JSON.",
        allows_artifact_writes=True,
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs read receipt.",
        failure_mode="Exits non-zero on policy violation.",
        notes="B3 governed read.",
    ),
    CommandAuthorityRecord(
        name="builder-readonly content-read",
        entrypoint="builder_ii.readonly_inspection_cli:readonly_app",
        tier=TIER_1,
        promotion_state=STATE_READ_ONLY_RUNTIME_CANDIDATE,
        runtime_boundary="Bounded explicit-path content capture that refuses any file whose content matches a secret pattern (best-effort denial, never a guarantee); no recursive discovery or glob expansion.",
        write_boundary="Writes content-read receipt JSON only under explicit output directory.",
        allows_artifact_writes=True,
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs content-read receipts with content and excerpt digests; a secret-matching file yields a denied-read, never a content excerpt.",
        failure_mode="Fails closed on path escape, symlink, oversize file, binary refusal, or secret-pattern denial.",
        notes="Promoted content-read lane separate from metadata-only readonly inspection reports.",
    ),
    CommandAuthorityRecord(
        name="builder-readonly validate",
        entrypoint="builder_ii.readonly_inspection_cli:readonly_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates read receipt JSON.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs validation result.",
        failure_mode="Exits non-zero on validation failure.",
        notes="B3 read receipt validation.",
    ),
    CommandAuthorityRecord(
        name="builder-verification",
        entrypoint="builder_ii.verification_cli:verification_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates verification profile schemas.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs verification lists.",
        failure_mode="Exits non-zero if profiles are malformed.",
        notes="Audits verification setups.",
    ),
    CommandAuthorityRecord(
        name="builder-verify plan",
        entrypoint="builder_ii.verification_execution_plan_cli:verify_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Generates a passive verification execution plan artifact only; no runtime start, shell execution, subprocess execution, model execution, MCP/tool invocation, Goose, deepagents, git mutation, or B2 patch authority.",
        write_boundary="Writes only the explicit verification execution plan JSON artifact requested by --output.",
        approval_mode=MODE_NONE,
        approval_boundary="None. This is planned-only metadata and cannot authorize execution.",
        output_behavior="Prints canonical verification execution plan JSON to stdout and writes the same artifact to the explicit output path.",
        failure_mode="Exits non-zero on invalid target/profile, malformed passive step shape, disabled-authority drift, or digest mismatch.",
        notes="B1.1 passive foundation only. It never runs verification and never promotes HITL execution.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-verify validate-plan",
        entrypoint="builder_ii.verification_execution_plan_cli:verify_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a verification execution plan artifact without runtime start, shell execution, subprocess execution, model execution, MCP/tool invocation, Goose, deepagents, git mutation, or B2 patch authority.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation JSON to stdout.",
        failure_mode="Exits non-zero on malformed artifact, digest drift, enabled execution authority, raw shell strings, or forbidden authority overclaim.",
        notes="Validation-only B1.1 command. It does not execute verification or grant approval.",
    ),
    CommandAuthorityRecord(
        name="builder-platform operator-status",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Generates operator status report derived from truth matrix and command authority; no execution.",
        write_boundary="Writes status JSON artifact if output path requested.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs JSON status report.",
        failure_mode="Exits non-zero on schema validation failures.",
        notes="B9 governed operator status report.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-platform next",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Generates operator next action report derived from truth matrix and evidence gaps; no execution.",
        write_boundary="Writes next action JSON artifact if output path requested.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs JSON next action report.",
        failure_mode="Exits non-zero on schema validation failures.",
        notes="B9 governed operator next action primitive.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-platform operator-lane",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Composes config resolution, git snapshot, read/content receipts, context pack, routing recommendation, verification plan, golden path, and handoff; captures target git state via read-only `git rev-parse`/`git status` subprocesses; no model/MCP/commit authority.",
        write_boundary="Writes evidence artifacts only under explicit --output-dir.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs operator lane report JSON referencing composed artifacts.",
        failure_mode="Exits non-zero on composition or validation failure.",
        notes="Founder/operator lane orchestrating existing governed surfaces without widening authority. Spawns read-only git subprocesses like `builder-git-state`, so it declares `allows_readonly_subprocess` and derives BOUNDED_EXECUTION_VERIFIED rather than falsely reading as passive.",
        allows_artifact_writes=True,
        allows_readonly_subprocess=True,
    ),
    CommandAuthorityRecord(
        name="builder-platform golden-path",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Generates operator golden path report derived from status and next primitive; no execution.",
        write_boundary="Writes golden path JSON artifact if output path requested.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs JSON golden path report.",
        failure_mode="Exits non-zero on schema validation failures.",
        notes="B9 governed operator golden path primitive.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-platform validate-golden-path",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates operator golden path report; no execution.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs JSON validation summary.",
        failure_mode="Exits non-zero on schema validation failures.",
        notes="B9 governed operator golden path primitive.",
    ),
    CommandAuthorityRecord(
        name="builder-platform demo-loop",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Runs a guided governed demo against a temporary detached worktree of an operator-designated target repo (AssetOverflow/core remains a supported profile). It never commits, pushes, starts Goose, calls models, invokes MCP, or mutates the source checkout.",
        write_boundary="Writes demo evidence artifacts to --output-dir and may apply/rollback one approved temporary documentation marker patch inside the demo worktree only.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must explicitly pass --approve before the temporary demo worktree patch is applied.",
        output_behavior="Prints the current demo report JSON and writes a DEMO_EVIDENCE.md bundle plus JSON evidence artifacts.",
        failure_mode="Fails closed on missing target repo, failed target identity check, dirty demo worktree, invalid marker path, approval digest mismatch, patch failure, verification failure, rollback failure, or final dirty worktree.",
        notes="Generic-first recording walkthrough; CORE stays a supported target profile. Source checkout remains untouched; temporary worktree mutation is paired with rollback and final postflight.",
        allows_source_writes=True,
        allows_git_mutation=True,
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-platform validate-demo-loop",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a governed demo loop report artifact without runtime start, model execution, source writes, or git mutation.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON validation summary.",
        failure_mode="Exits non-zero on malformed report, digest drift, authority overclaim, or missing required final state.",
        notes="Validation-only check for the governed demo report.",
    ),
    CommandAuthorityRecord(
        name="builder-platform wow",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Alias for the governed demo loop used for recording. It operates on a temporary detached worktree of the target repo only.",
        write_boundary="Writes demo evidence artifacts to --output-dir and may apply/rollback one approved temporary documentation marker patch inside the demo worktree only.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must explicitly pass --approve before the temporary demo worktree patch is applied.",
        output_behavior="Prints the current demo report JSON and writes the demo evidence bundle.",
        failure_mode="Fails closed on the same boundaries as builder-platform demo-loop.",
        notes="Recording alias; no commit, push, model execution, Goose activation, MCP call, or source checkout mutation.",
        allows_source_writes=True,
        allows_git_mutation=True,
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-verify approve-plan",
        entrypoint="builder_ii.verification_execution_plan_cli:verify_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Generates a digest-bound HITL approval artifact for a passive verification execution plan only; no runtime start, direct execution, shell execution, subprocess execution, model execution, MCP/tool invocation, Goose, deepagents, git mutation, or B2 patch authority.",
        write_boundary="Writes only the explicit verification execution approval JSON artifact requested by --output.",
        approval_mode=MODE_NONE,
        approval_boundary="None. The artifact binds human approval to a plan digest only and does not authorize execution.",
        output_behavior="Prints canonical verification execution approval JSON to stdout and writes the same artifact to the explicit output path.",
        failure_mode="Exits non-zero on invalid plan input, digest mismatch, subset drift against the referenced plan, malformed approval text, or authority overclaim.",
        notes="B1.2 passive HITL binding only. It never runs verification and never grants runtime authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-verify validate-approval",
        entrypoint="builder_ii.verification_execution_plan_cli:verify_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a verification execution approval artifact against its referenced passive plan without runtime start, direct execution, shell execution, subprocess execution, model execution, MCP/tool invocation, Goose, deepagents, git mutation, or B2 patch authority.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation JSON to stdout.",
        failure_mode="Exits non-zero on malformed approval artifact, invalid referenced plan, digest drift, subset drift, enabled execution flags, or forbidden authority overclaim.",
        notes="Validation-only B1.2 command. It does not authorize execution and requires B1.3 before any approved plan can run.",
    ),
    CommandAuthorityRecord(
        name="builder-verify validate-receipt",
        entrypoint="builder_ii.verification_execution_plan_cli:verify_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a passive B1.3A verification execution receipt artifact against its referenced plan and approval without runtime start, direct execution, shell execution, subprocess execution, model execution, MCP/tool invocation, Goose, deepagents, git mutation, or B2 patch authority.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation JSON to stdout.",
        failure_mode="Exits non-zero on malformed receipt artifact, invalid referenced plan or approval, digest drift, binding mismatch, enabled execution flags, shell-enabled flags, subprocess-started flags, mutation flags, or forbidden authority overclaim.",
        notes="Validation-only B1.3A command. It validates the receipt contract only; it does not execute verification. B1.3B is required before approved verification can run.",
    ),
    CommandAuthorityRecord(
        name="builder-verify evaluate-promotion",
        entrypoint="builder_ii.verification_execution_plan_cli:verify_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="B2.0 machine-checkable promotion-gate evaluator: reads plan/approval/receipt (and optional ledger) artifacts, recomputes digest bindings and gate checks, and emits a passive promotion-evidence artifact. No subprocess, shell, model, MCP, Goose, deepagents, source writes, or matrix flips.",
        write_boundary="Writes only an optional explicit promotion-evidence JSON path when --output is provided.",
        approval_mode=MODE_NONE,
        approval_boundary="None. Evidence of gate PASS is not operator approval and does not flip capability state.",
        output_behavior="Prints canonical promotion-evidence JSON to stdout and optionally writes the same artifact to --output.",
        failure_mode="Exits non-zero on unreadable/malformed inputs or invalid emitted evidence; exits 2 when overall_state is FAIL (gates failed).",
        notes="Post-beta ladder item 2 (B2.0). Artifact proves promotion eligibility only; operator-applied matrix flips remain a separate human step.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-verify validate-promotion-evidence",
        entrypoint="builder_ii.verification_execution_plan_cli:verify_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a builder_ii.verification_promotion_evidence artifact for schema, gate shape, and non-authority invariants. No execution.",
        write_boundary="No writes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation JSON to stdout.",
        failure_mode="Exits non-zero on schema or governance violations.",
        notes="Paired validator for B2.0 promotion-evidence artifacts.",
    ),
    CommandAuthorityRecord(
        name="builder-verify run-approved",
        entrypoint="builder_ii.verification_execution_plan_cli:verify_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Runs exactly one bounded verification profile from fixed in-code argv with subprocess shell=False, after validating the plan artifact, approval artifact, and approval-to-plan binding. Supported profiles are the safe builder-II-argv profiles platform_status and docs_audit, plus the target-code-executing profiles pytest_full and builder_full, which run the target repository's own test/conftest/plugin code and therefore require an execution-risk acknowledgment on the approval before the runner will spawn them. The per-profile timeout is read from the approved plan (range-checked to [1,1800]s). This bounds invocation only, never invoked-code behavior; it is not a sandbox.",
        write_boundary="Writes only the explicit verification execution receipt artifact requested by --output, and only under the configured artifact root when output is inside the target repository. A target-code profile may leave incidental pytest cache/bytecode byproducts in the target repo; these are recorded as observed byproducts and any non-ignored change invalidates the receipt.",
        approval_mode=MODE_HITL_ARTIFACT_REQUIRED,
        approval_boundary="Requires a digest-bound verification execution approval artifact for the requested command profile and step id; a target-code profile additionally requires the approval to carry an execution-risk acknowledgment.",
        output_behavior="Prints canonical verification execution receipt JSON to stdout and writes the same receipt to the explicit output path. Captures bounded stdout/stderr excerpts and digests, not full unbounded logs.",
        failure_mode="Blocks before execution on invalid plan, invalid approval, digest mismatch, unapproved profile/step, missing execution-risk acknowledgment for a target-code profile, missing/out-of-range plan timeout, unsafe output path, unsupported profile, target/artifact-root escape, or git preflight capture failure. Marks receipt failed on timeout/nonzero exit and invalid on workspace mutation, including a HEAD-SHA change during the run or a postflight git-state that cannot be captured.",
        notes="B1.3B bounded runner candidate only; still MERGED_BUT_NOT_OPERATIONAL, and the truth matrix's operationally-verified scope remains platform_status and docs_audit. It does not allow arbitrary shell, operator-provided argv, patch authority, git mutation, model execution, MCP/tool invocation, Goose, deepagents, or B2 authority.",
        allows_artifact_writes=True,
        allows_readonly_subprocess=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Delegates execution request and receipt operations to subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_HITL_ARTIFACT_REQUIRED,
        approval_boundary="Operator must sign hitl request and verify receipts.",
        output_behavior="Dispatches to subcommands.",
        failure_mode="Exits non-zero on signature or verification failure.",
        notes="HITL-gated candidate tracking.",
    ),
    CommandAuthorityRecord(
        name="builder-orchestration",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Delegates passive plan setup, assignment rendering, validation, and dry-run subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Dispatches to subcommands.",
        failure_mode="Exits non-zero on schema validation failures.",
        notes="Artifact orchestration and assignment planner; no runtime or execution authority.",
    ),
    CommandAuthorityRecord(
        name="builder-profile-pack",
        entrypoint="builder_ii.profile_pack_cli:profile_pack_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Delegates passive profile-pack scaffold, render, dry-run, and validation subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Dispatches to profile-pack artifact lifecycle subcommands.",
        failure_mode="Exits non-zero on schema or governance validation failures.",
        notes="Passive profile-pack lifecycle; no runtime, model, Goose, deepagents, MCP, shell, or verification execution.",
    ),
    CommandAuthorityRecord(
        name="builder-model-policy",
        entrypoint="builder_ii.model_policy_cli:model_policy_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Delegates passive model client registry and routing policy subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Dispatches to model policy artifact validation, rendering, and dry-run subcommands.",
        failure_mode="Exits non-zero on schema validation failures.",
        notes="Passive model routing metadata; never invokes models or provider endpoints.",
    ),
    CommandAuthorityRecord(
        name="builder-model",
        entrypoint="builder_ii.model_cli:model_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Delegates governed model execution subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_NONE,
        approval_boundary="Delegated to subcommands.",
        output_behavior="Dispatches to model execution subcommands.",
        failure_mode="Exits non-zero on failure.",
        notes="Model/provider execution gateway.",
    ),
    CommandAuthorityRecord(
        name="builder-platform",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Delegates passive completion-truth matrix, status, and docs-audit rendering; no runtime, model, shell, Goose, deepagents, MCP, or tool execution.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Dispatches to truth rendering and validation subcommands.",
        failure_mode="Exits non-zero on invalid matrix metadata, missing authority coverage, or false-completion docs claims.",
        notes="R0 truth machine command group. It reports platform state and cannot promote authority.",
    ),
    CommandAuthorityRecord(
        name="builder-memory",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Delegates governed memory atom, index, search, reconstruction, and validation subcommands without runtime execution, model calls, shell execution, hidden retrieval, or vector-store behavior.",
        write_boundary="No direct write authority at root CLI level; subcommands may write only explicit JSON memory artifacts when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Dispatches to passive memory artifact creation and validation subcommands.",
        failure_mode="Exits non-zero on invalid source artifacts, malformed memory records, digest drift, or source-truth inflation attempts.",
        notes="B8 passive artifact-memory command group. It records searchable continuity artifacts without hidden memory, autonomous writes, or runtime authority.",
    ),
    CommandAuthorityRecord(
        name="builder-config",
        entrypoint="builder_ii.config_cli:config_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Delegates passive config schema rendering, source resolution, and validation; no runtime, model, shell, Goose, deepagents, MCP, tool, or patch execution.",
        write_boundary="No direct write authority at root CLI level; subcommands may write explicit JSON artifacts only when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Dispatches to schema, resolve, and validate subcommands.",
        failure_mode="Exits non-zero on invalid config artifacts, unsafe path policy, or unsupported source values.",
        notes="R1.1 passive config source surface. Metadata is not runtime permission.",
    ),
    CommandAuthorityRecord(
        name="builder-setup",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Delegates passive setup plan, overlay plan, rollback snapshot, and validation subcommands; no setup apply, rollback execution, Goose start, model call, shell execution, deepagents runtime, MCP/tool invocation, or patch authority.",
        write_boundary="No direct write authority at root CLI level; artifact commands write only explicit JSON output artifacts when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Dispatches to passive plan, overlay-plan, rollback-snapshot, and validation subcommands.",
        failure_mode="Exits non-zero on invalid resolution, unsafe path policy, malformed setup artifacts, or unsafe overlay paths.",
        notes="R1.4 legacy reconciliation complete at the command surface: builder-setup remains the canonical governed lane, while legacy builder setup now fails closed and redirects here.",
    ),
    CommandAuthorityRecord(
        name="builder-workflow",
        entrypoint="builder_ii.workflow_cli:workflow_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Delegates passive workflow state-machine subcommands; no runtime, model, shell, Goose, deepagents, or MCP execution.",
        write_boundary="Writes governed workflow artifacts only under explicit workflow output directories.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Dispatches to workflow plan, promotion, candidate, chain, handoff, and status subcommands.",
        failure_mode="Exits non-zero on stale stage, invalid schema, missing refs, or failed replay.",
        notes="Governed passive workflow orchestrator; records transitions and events without granting authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-ledger",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Delegates event-ledger list, replay, audit, export, and verification execution ledger query/validation/reconstruction subcommands without executing runtime work.",
        write_boundary="Writes replay and ledger export artifacts only when requested by ledger subcommands.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON audit/replay/query data or writes explicit ledger artifacts.",
        failure_mode="Exits non-zero on missing session, invalid replay, or missing artifact SHA reference.",
        notes="Event-sourced audit surface for governed workflow sessions.",
        allows_artifact_writes=True,
    ),
    # --- Selected Subcommands ---
    CommandAuthorityRecord(
        name="builder-session prepare-package",
        entrypoint="builder_ii.session_cli:session_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Prepares context packaging and checks files.",
        write_boundary="Writes prepared package files locally.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes packaged bundle files.",
        failure_mode="Exits non-zero if inputs malformed.",
        notes="Governed package preparation lane. Artifact-only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-session validate-prepare-package",
        entrypoint="builder_ii.session_cli:session_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Performs validations on the prepared package directory structure.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints verification results.",
        failure_mode="Exits non-zero on validation error.",
        notes="Governed package validator.",
    ),
    CommandAuthorityRecord(
        name="builder-session summarize-prepare-package",
        entrypoint="builder_ii.session_cli:session_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Analyzes prepared package and generates a passive summary.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints package stats and content summaries.",
        failure_mode="Exits non-zero if read fails.",
        notes="Passive summary producer.",
    ),
    CommandAuthorityRecord(
        name="builder-context pack",
        entrypoint="builder_ii.context_cli:context_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Invokes legacy external scanner or git commands.",
        write_boundary="Writes context bundle files.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no artifact approval chain.",
        output_behavior="Outputs packed context data.",
        failure_mode="Exits non-zero if repomix fails.",
        notes="Legacy repomix packing mode.",
        allows_artifact_writes=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder-context changed",
        entrypoint="builder_ii.context_cli:context_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Queries git status or git diff via subprocess.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no artifact approval chain.",
        output_behavior="Outputs diff context.",
        failure_mode="Exits non-zero if git fails.",
        notes="Legacy git diff inspection mode.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder-context artifact",
        entrypoint="builder_ii.context_cli:context_app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Processes codebase scanning, potentially using external tools like repomix.",
        write_boundary="Creates context artifact files.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no artifact approval chain.",
        output_behavior="Writes context artifact to file.",
        failure_mode="Exits non-zero if scanner errors.",
        notes="Legacy repo scan. Avoid when builder-session prepare-package can be used.",
        allows_artifact_writes=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder setup",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Fail-closed compatibility wrapper that redirects operators to governed builder-setup plan/overlay/rollback/apply commands; no setup apply is performed by this legacy surface.",
        write_boundary="No changes to workspace, target repo, Goose config, .goosehints, skills, recipes, or runtime state.",
        approval_mode=MODE_NONE,
        approval_boundary="None. The command is informational only and exits non-zero after printing the governed migration path.",
        output_behavior="Prints the governed R1 setup command sequence and disabled-legacy warning to stdout.",
        failure_mode="Fails closed without mutation or subprocess execution.",
        notes="R1.4 reconciliation disables legacy unmanaged setup writes and removes the bypass around digest-bound builder-setup apply/rollback.",
    ),
    CommandAuthorityRecord(
        name="builder onboarding",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Interactive guided onboarding flow delegating directly to governed builder-setup wizard; no Goose, model, MCP, deepagents, patch, or shell execution.",
        write_boundary="Writes passive onboarding/setup artifacts under explicit output directory only; no setup mutation or receipt generation.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints setup plan summary, digests, and deferred apply command to stdout.",
        failure_mode="Exits non-zero on schema error or digest mismatch.",
        notes="R1.5 convenience root command cleanly delegating to setup_wizard. Setup mutation remains exclusively owned by builder-setup apply.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder init",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Unified onboarding orchestrator composing the governed onboarding pipeline (setup plan, overlay plan, rollback snapshot, intent report); prompts all nine onboarding decisions and registry-validates every answer, typed or flag-provided; no Goose, model, MCP, deepagents, patch, or shell execution.",
        write_boundary="Writes passive onboarding/setup artifacts under the selected output directory only; never applies setup and never writes a receipt.",
        approval_mode=MODE_NONE,
        approval_boundary="None. Prints the follow-up builder-setup apply command without an inline digest; apply approval happens only in the separately invoked apply step.",
        output_behavior="Prints every decision with the value taken and the flag that overrides it, artifact paths, digests, and the deferred apply command to stdout.",
        failure_mode="Exits non-zero on config resolution errors, registry-invalid answers (flag-provided, or prompted after three attempts), schema error, or digest mismatch.",
        notes="Plan 2.2 unified init orchestrator over run_onboarding_pipeline. builder-setup init and builder-setup wizard remain the scripted/legacy surfaces; setup mutation remains exclusively owned by builder-setup apply.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder pull",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Runs model-cache download helpers for explicitly selected local model tiers.",
        write_boundary="Writes model cache files outside the target repository through operator-invoked helper scripts.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no autonomous download or runtime authority.",
        output_behavior="Streams helper output to the terminal and exits with the helper status.",
        failure_mode="Exits non-zero if the helper script or model pull fails.",
        notes="Network and cache mutation helper. It is not source mutation, patch authority, or model execution.",
        allows_external_tool_invocation=True,
        allows_state_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder start",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Starts background runtime processes and servers.",
        write_boundary="Creates runtime process state and session context artifacts only; does not perform legacy setup writes.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no artifact approval chain.",
        output_behavior="Launches background process and writes log info.",
        failure_mode="Exits non-zero if server cannot start.",
        notes="Used to boot local agents or backends. R1.4 removes implicit legacy setup reconciliation from this runtime path.",
        allows_runtime_start=True,
        allows_state_writes=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder ask",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Queries model provider or MLX local runtime using user input.",
        write_boundary="Writes conversation history files locally.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no artifact approval chain.",
        output_behavior="Prints model response text to terminal.",
        failure_mode="Exits non-zero on API or local runtime error.",
        notes="Direct model chat surface.",
        allows_model_execution=True,
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder verify",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Invokes local pytest/runner test suites via subprocess.",
        write_boundary="No source code changes; generates test result files.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no artifact approval chain.",
        output_behavior="Outputs test run reports.",
        failure_mode="Exits non-zero if test cases fail.",
        notes="Audits repo testing state.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder benchmark",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Runs bounded local benchmark probes and may call the configured chat-completions endpoint if reachable.",
        write_boundary="Writes a benchmark report only when an explicit output path is provided.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; no autonomous benchmark or model probing.",
        output_behavior="Prints benchmark metrics and optionally writes a report artifact.",
        failure_mode="Reports unreachable runtime as DOWN/SKIP and exits non-zero only for command errors.",
        notes="Operator-managed live probe. It is not production assurance or life-safety validation.",
        allows_model_execution=True,
        allows_artifact_writes=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder capabilities",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Checks served-model capability gates and optionally runs a live chat smoke when --chat is passed.",
        write_boundary="No changes to workspace, target repository, or runtime state.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only; --chat is a live model probe.",
        output_behavior="Prints capability gate results.",
        failure_mode="Exits non-zero if any gate fails.",
        notes="Operator-managed live capability probe. It is not model promotion or certification.",
        allows_model_execution=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder switch-model",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Normalizes model aliases and prints environment lines only.",
        write_boundary="No changes to workspace, environment files, runtime state, or target repository.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints suggested environment variable lines.",
        failure_mode="Exits non-zero if the requested backend is invalid.",
        notes="Passive helper. Operators must apply environment changes themselves.",
    ),
    CommandAuthorityRecord(
        name="builder models",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Inspects local model cache directories with bounded read-only filesystem and size probes.",
        write_boundary="No changes to workspace, cache contents, or target repository.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only.",
        output_behavior="Prints configured model roster and cache status.",
        failure_mode="Reports missing or incomplete cache state without mutation.",
        notes="Read-only model cache inspection. It does not download, execute, or promote models.",
        allows_readonly_subprocess=True,
    ),
    CommandAuthorityRecord(
        name="builder doctor",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Runs local readiness probes across repo path, Goose availability, backend health, recipes, compliance, and model cache state.",
        write_boundary="No changes to workspace, runtime state, or target repository.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only.",
        output_behavior="Prints a readiness table and failure details.",
        failure_mode="Exits non-zero if required readiness checks fail.",
        notes="Operator-managed diagnostic. It does not start runtimes, call model completions, or mutate setup.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder status",
        entrypoint="builder_ii.cli:app",
        tier=TIER_2,
        promotion_state=STATE_OPERATOR_MANAGED,
        runtime_boundary="Reads backend health, Goose status, recipe validation, compliance, and local model cache status.",
        write_boundary="No changes to workspace, runtime state, or target repository.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit operator invocation only.",
        output_behavior="Prints status lines for runtime, compliance, recipes, and model cache.",
        failure_mode="Reports DOWN/WARN states without mutating local state.",
        notes="Operator-managed read-only status probe.",
        allows_readonly_subprocess=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder config",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Renders passive configuration and legacy setup redirect metadata.",
        write_boundary="No changes to workspace, runtime state, or target repository.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON configuration metadata.",
        failure_mode="Exits non-zero if configuration loading fails.",
        notes="Passive config introspection only.",
    ),
    CommandAuthorityRecord(
        name="builder init-prompt",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Renders the governed initialization prompt text.",
        write_boundary="No changes to workspace, runtime state, or target repository.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints the prompt and estimated token count.",
        failure_mode="Exits non-zero only on unexpected output errors.",
        notes="Passive prompt inspection only.",
    ),
    CommandAuthorityRecord(
        name="builder-goose manifest",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Inspects Goose configuration manifest templates.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Validates manifest layout.",
        failure_mode="Exits non-zero on schema mismatch.",
        notes="Goose spec validation.",
    ),
    CommandAuthorityRecord(
        name="builder-goose validate",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Performs validations on active Goose session configs.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs verification checklist status.",
        failure_mode="Exits non-zero on mismatch.",
        notes="Configuration verification.",
    ),
    CommandAuthorityRecord(
        name="builder-goose readonly-audit",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Ensures a target Goose session uses read-only tools only.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Validates tool capabilities and permissions.",
        failure_mode="Exits non-zero if write tools are allowed.",
        notes="Safety auditor for Goose profiles.",
    ),
    CommandAuthorityRecord(
        name="builder-goose validate-audit",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates the output of a Goose audit run.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints verification results.",
        failure_mode="Exits non-zero on validation error.",
        notes="Audit integrity check.",
    ),
    CommandAuthorityRecord(
        name="builder-goose inspect-readonly",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Performs read-only inspection validation on explicitly requested paths.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Validates inspection path configuration.",
        failure_mode="Exits non-zero if write paths are targeted.",
        notes="Audit tool for read-only containment.",
    ),
    CommandAuthorityRecord(
        name="builder-goose validate-inspection",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates inspection config details.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints verification results.",
        failure_mode="Exits non-zero on validation error.",
        notes="Validation check.",
    ),
    CommandAuthorityRecord(
        name="builder-goose start-readonly",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_3,
        promotion_state=STATE_READ_ONLY_RUNTIME_CANDIDATE,
        runtime_boundary="Starts a Goose session bounded by read-only policies.",
        write_boundary="No writes permitted. Strict environment isolation.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Requires implicit or explicit HITL approval for launch.",
        output_behavior="Outputs launch receipt and runs session.",
        failure_mode="Exits non-zero on failure or read-only violation.",
        notes="Goose readonly runtime promotion.",
    ),
    CommandAuthorityRecord(
        name="builder-goose close-readonly",
        entrypoint="builder_ii.goose_cli:goose_app",
        tier=TIER_3,
        promotion_state=STATE_READ_ONLY_RUNTIME_CANDIDATE,
        runtime_boundary="Closes a governed Goose session and verifies no mutation occurred.",
        write_boundary="No writes permitted. Target filesystem is inspected for drift.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Delegated to CLI lifecycle.",
        output_behavior="Outputs close receipt and no-mutation postflight receipt.",
        failure_mode="Exits non-zero on drift or failure.",
        notes="Goose readonly runtime closure.",
    ),
    CommandAuthorityRecord(
        name="builder-deepagents policy",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders governed deepagents policy metadata statically.",
        write_boundary="Writes policy JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Policy artifact rendering only; no deepagents construction.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents validate",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates deepagents spec metadata.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Validation checklist.",
        failure_mode="Exits non-zero on schema error.",
        notes="Dry-run audit.",
    ),
    CommandAuthorityRecord(
        name="builder-deepagents readiness",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders optional deepagents dependency-readiness metadata.",
        write_boundary="Writes readiness JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on readiness schema error.",
        notes="Readiness artifact only; does not construct agents or run delegation.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents validate-readiness",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates deepagents dependency-readiness metadata.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Validation checklist.",
        failure_mode="Exits non-zero on schema error.",
        notes="Readiness validation only.",
    ),
    CommandAuthorityRecord(
        name="builder-deepagents forge",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates or previews governed deepagent profile artifacts only; no native deepagents construction, model execution, shell execution, MCP/tool invocation, Goose activation, source writes outside bounded Forge artifacts, git mutation, or runtime promotion.",
        write_boundary="Dry-run writes nothing. Real emission writes only profiles/deepagents/{slug}.yaml and an optional profiles/deepagents/forge_{slug}.handoff.json handoff artifact.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must explicitly invoke Forge; emitted artifacts are not runtime approval or promotion authority.",
        output_behavior="Prints deterministic preview/emit status, exact paths, warnings, blockers, and optional hook results.",
        failure_mode="Exits non-zero on invalid spec, governance blockers, unsafe slug/path, command-authority denial, or profile write failure; optional hook failures are reported without pretending success.",
        notes="Forge is a governed artifact factory for profiles and handoff intent only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents delegate",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_4,
        promotion_state=STATE_FORBIDDEN_UNPROMOTED,
        runtime_boundary="Attempts to execute autonomous models. Forbidden.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_FORBIDDEN_UNPROMOTED,
        approval_boundary="Forbidden; no supported approval path.",
        output_behavior="Error message.",
        failure_mode="Exits non-zero.",
        notes="Autonomous deepagent model execution is not promoted.",
    ),
    CommandAuthorityRecord(
        name="builder-deepagents work-plan",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive deepagents work plan statically.",
        write_boundary="Writes work plan JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Work plan rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents assign-subagent",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive subagent assignment statically.",
        write_boundary="Writes subagent assignment JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Subagent assignment rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents record-result",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive subagent result statically.",
        write_boundary="Writes subagent result JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Subagent result rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents review-result",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive subagent review statically.",
        write_boundary="Writes subagent review JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Subagent review rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents request-human-gate",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive human gate request statically.",
        write_boundary="Writes human gate request JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Human gate request rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents record-blocked-action",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive blocked action record statically.",
        write_boundary="Writes blocked action record JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Blocked action record rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents proposal-result",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive proposal result statically.",
        write_boundary="Writes proposal result JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Proposal result rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents validate-work-artifact",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates passive deepagents work artifact metadata.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Validation checklist.",
        failure_mode="Exits non-zero on schema error.",
        notes="Validation audit only.",
    ),
    CommandAuthorityRecord(
        name="builder-deepagents backend-readiness",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Inspects the optional_deepagents protocol adapter exports and records a promotion-readiness gate without constructing an agent.",
        write_boundary="Writes backend readiness gate JSON only to explicit artifact output paths.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must explicitly assert AGENTS.md capability gates before the gate can pass.",
        output_behavior="Writes JSON readiness gate with PASS/FAIL status and next valid command.",
        failure_mode="Produces a FAIL readiness artifact on missing dependency, schema drift, failed denial probe, or missing capability gate assertion.",
        notes="Readiness proof only; no native deepagents construction, model invocation, tool execution, shell, MCP, source writes, memory mutation, Goose, or CORE Workbench coupling.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents execution-candidate",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a bounded deepagents protocol execution candidate without running a backend; optional_deepagents requires a passing backend-readiness gate.",
        write_boundary="Writes candidate JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None; later run-approved requires digest-bound HITL approval.",
        output_behavior="Writes JSON candidate and prints the next command.",
        failure_mode="Exits non-zero on invalid work plan, backend mode, output root, or budget.",
        notes="Candidate artifact only; no model, tool, shell, Goose, MCP, or deepagents construction.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents approve-candidate",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Binds human approval to the exact candidate digest via required --approval-actor/--approval-reason flags (non-interactive; no typed-prefix prompt); the digest-bound approval artifact seals the whole envelope (lane policy, root budget, allowed obligation kinds, refused lanes) when the candidate declares one.",
        write_boundary="Writes approval JSON only to explicit artifact output paths.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Human actor and reason are required inputs; --native-backend-acknowledged is the second key required to seal an optional_deepagents obligation-bearing candidate.",
        output_behavior="Writes JSON approval and prints the next command.",
        failure_mode="Exits non-zero on candidate drift, invalid approval shape, or a missing native-backend acknowledgement for an optional_deepagents envelope.",
        notes="Approval is not authority by itself; only run-approved can cross the bounded protocol lane. Sealed envelope fields live inside the approval digest basis.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents run-approved",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Runs the approved protocol backend lane only after candidate and approval digests bind. With --obligation, each subagent runs its OWN mint-checked obligation task and each discharge is classified (CONTRACT_SATISFIED / DISCHARGED_UNVERIFIED / CONTRACT_VIOLATED / BLOCKED).",
        write_boundary="Writes run envelope, hash-chained events (including obligation_minted / obligation_mint_refused / obligation_consumed), replay report, ledger, receipt, and optional checkpoint under the approved output root.",
        approval_mode=MODE_HITL_ARTIFACT_REQUIRED,
        approval_boundary="Requires a valid builder_ii.deepagents_execution_approval bound to the exact candidate; an obligation-bearing run additionally requires a Ladder 4 seal and, for optional_deepagents, the two-key native acknowledgement.",
        output_behavior="Writes JSON evidence artifacts and prints a compact run summary (with the discharge tally for obligation runs).",
        failure_mode="Fails closed before execution on drift, expiry, backend mismatch, output-root escape, denied capability, lane-policy drift, a legacy approval for obligations, or a missing native ack; refuses each over-envelope mint with a fixing-edit-carrying blocked record.",
        notes="Protocol backend execution only; no native deepagents construction, models, tools, shell, Goose, MCP, source writes, git mutation, or hidden memory. Obligation mints are enforced against the sealed envelope (grants-not-loans budget conservation).",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents replay-run",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reconstructs deepagents run state from event records only.",
        write_boundary="Writes replay report JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None; replay never reruns backend/model/tool work.",
        output_behavior="Writes replay JSON and prints status.",
        failure_mode="Exits non-zero on invalid event chain.",
        notes="Replay is deterministic validation, not execution.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents evidence-bundle",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Bundles deepagents candidate, approval, run, receipt, ledger, and replay evidence.",
        write_boundary="Writes evidence bundle JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None; evidence bundle does not grant authority.",
        output_behavior="Writes evidence bundle JSON and prints status.",
        failure_mode="Exits non-zero on missing or invalid chain artifacts.",
        notes="Evidence-only surface.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents resume-approved",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Resumes a checkpointed protocol backend run only when candidate and approval still bind exactly.",
        write_boundary="Appends hash-chained events and rewrites run envelope, replay, ledger, and receipt under the approved output root.",
        approval_mode=MODE_HITL_ARTIFACT_REQUIRED,
        approval_boundary="Requires the original approval and checkpoint bound to the same candidate.",
        output_behavior="Writes resumed JSON evidence artifacts and prints a compact run summary.",
        failure_mode="Fails closed on changed candidate, changed approval, invalid checkpoint, or output-root escape.",
        notes="Resume does not widen authority beyond the original approved protocol lane.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents run-plan",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Synthesizes legacy passive planning artifacts; not the promoted approved lane.",
        write_boundary="Writes synthetic runtime envelope and subagent receipts only to explicit artifact paths.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator explicitly invokes the compatibility command; no approval artifact is consumed.",
        output_behavior="Writes JSON receipts.",
        failure_mode="Exits non-zero on verification failure.",
        notes="Backward-compatible synthetic/passive harness. Use execution-candidate -> approve-candidate -> run-approved for promoted protocol execution.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-deepagents collect-results",
        entrypoint="builder_ii.deepagents_cli:deepagents_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Collects subagent results into a final proposal result.",
        write_boundary="Writes proposal result JSON only to explicit artifact output paths.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Delegated to CLI invocation.",
        output_behavior="Writes JSON proposal.",
        failure_mode="Exits non-zero on failure.",
        notes="Collects deepagents subagent planning outcomes.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl propose-patch",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a design-only patch proposal artifact.",
        write_boundary="Writes patch proposal JSON file to specified output.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Saves JSON file containing diff and digest.",
        failure_mode="Exits non-zero if diff path is missing.",
        notes="Passive foundation step for B2 patch apply.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl approve-patch",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders a proposal's diff and patch digest, then mints a digest-bound approval artifact after an interactive digest-prefix confirmation. No patch is applied and no source is written.",
        write_boundary="Writes an approval JSON file to the specified output path only.",
        approval_mode=MODE_NONE,
        approval_boundary="The operator must transcribe the patch-digest prefix at an interactive prompt; there is no non-interactive approval mode.",
        output_behavior="Saves the approval JSON bound to the proposal content and patch digests, with an expiry.",
        failure_mode="Exits non-zero (writing nothing) if the proposal is invalid, has no digest, or the typed prefix does not match.",
        notes="Governed approval-minting step: the approval it produces is evidence of a human decision, not authority in itself.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl apply-patch",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Applies a patch specifically from an approved proposal to a clean repository after rollback plan creation.",
        write_boundary="Modifies source tree according to the diff. Writes postflight and receipt records.",
        approval_mode=MODE_HITL_ARTIFACT_REQUIRED,
        approval_boundary="Requires a schema-valid, unexpired hitl_patch_approval artifact bound to the proposal's content and patch digests, verified inside apply_hitl_patch. Digest-chained binding, not a cryptographic signature.",
        output_behavior="Applies diff to working tree.",
        failure_mode="Reverts and exits non-zero if git apply fails or repository is unclean.",
        notes="B2 patch application via git apply only; requires HITL approval and verification receipt; emits rollback bundle with forward_patch_for_reverse_apply.patch; no commit/push.",
        allows_artifact_writes=True,
        allows_source_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl approve-rollback",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders a rollback plan's summary and digest, then mints a plan-bound rollback approval artifact after an interactive digest-prefix confirmation. No rollback is executed and no source is written.",
        write_boundary="Writes a rollback approval JSON file to the specified output path only.",
        approval_mode=MODE_NONE,
        approval_boundary="The operator must transcribe the rollback-plan-digest prefix at an interactive prompt; there is no non-interactive approval mode.",
        output_behavior="Saves the rollback approval JSON bound to the rollback plan content and patch digests, with an expiry.",
        failure_mode="Exits non-zero (writing nothing) if the rollback plan is invalid or the typed prefix does not match.",
        notes="Governed rollback-approval-minting step: a rollback is itself a mutation, so it gets its own approval distinct from the machine-generated rollback plan. The approval is evidence of a human decision, not authority in itself.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl rollback",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Restores the codebase to its pre-apply state via `git apply -R` of the stored forward patch, after a working-tree drift preflight.",
        write_boundary="Modifies the source tree via `git apply -R` only; writes a rollback receipt carrying post-rollback equivalence evidence.",
        approval_mode=MODE_HITL_ARTIFACT_REQUIRED,
        approval_boundary="Requires a schema-valid, unexpired hitl_rollback_approval artifact bound to the rollback plan's content and patch digests (not merely the machine-generated rollback plan), verified inside rollback_hitl_patch.",
        output_behavior="Applies `git apply -R` to the stored forward patch; refuses if the working tree drifted since apply, and refuses to record success unless the tree provably returned to the pre-apply state.",
        failure_mode="Refuses before touching the tree and writes a rollback-failure receipt carrying a recovery block (pre-apply HEAD, exact restore command with data-loss warning, chain-invalidation event) on drift, failed reverse apply, or post-rollback state mismatch; exits non-zero.",
        notes="B2 patch rollback governed path. Distinct rollback approval + drift-hardened preflight (plan item 1.4); success receipts carry pre/post status-digest equivalence proof.",
        allows_source_writes=True,
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl run-command",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_4,
        promotion_state=STATE_FORBIDDEN_UNPROMOTED,
        runtime_boundary="Fail-closed. Arbitrary approved command execution is disabled until rebuilt as fixed-profile bounded runner.",
        write_boundary="No execution; request/receipt artifact commands remain available separately.",
        approval_mode=MODE_FORBIDDEN_UNPROMOTED,
        approval_boundary="Use builder-verify run-approved for bounded execution.",
        output_behavior="Refuses with message pointing to builder-verify run-approved.",
        failure_mode="Always exits non-zero with RunCommandDisabledError semantics.",
        notes="Authority seam hardened: denylist-based subprocess execution removed. Prefer builder-verify run-approved.",
    ),
    CommandAuthorityRecord(
        name="builder-hitl request",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Collects and validates HITL request details.",
        write_boundary="Writes HITL request JSON artifact.",
        approval_mode=MODE_HITL_ARTIFACT_REQUIRED,
        approval_boundary="Requires explicit operator approval signature.",
        output_behavior="Writes JSON file.",
        failure_mode="Exits non-zero if required refs are missing.",
        notes="Prepares execution requests under HITL governance.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl receipt",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Records execution completion or failure receipt metadata.",
        write_boundary="Writes HITL receipt JSON artifact.",
        approval_mode=MODE_HITL_ARTIFACT_REQUIRED,
        approval_boundary="Operator must sign hitl request and verify receipts.",
        output_behavior="Writes JSON file.",
        failure_mode="Exits non-zero on invalid request reference.",
        notes="Records governance confirmation without running code.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl validate",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates request and receipt artifact files against schema.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints verification results.",
        failure_mode="Exits non-zero if malformed JSON or invalid schema.",
        notes="Audit validation utility.",
    ),
    CommandAuthorityRecord(
        name="builder-hitl promotion-request",
        entrypoint="builder_ii.hitl_promotion_cli:hitl_promotion_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive promotion request statically.",
        write_boundary="Writes promotion request JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Promotion request rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl promotion-review",
        entrypoint="builder_ii.hitl_promotion_cli:hitl_promotion_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive promotion review statically.",
        write_boundary="Writes promotion review JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Promotion review rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl promotion-decision",
        entrypoint="builder_ii.hitl_promotion_cli:hitl_promotion_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive promotion decision statically.",
        write_boundary="Writes promotion decision JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Promotion decision rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl approval-boundary",
        entrypoint="builder_ii.hitl_promotion_cli:hitl_promotion_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive approval boundary statically.",
        write_boundary="Writes approval boundary JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Approval boundary rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl rejection-record",
        entrypoint="builder_ii.hitl_promotion_cli:hitl_promotion_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive rejection record statically.",
        write_boundary="Writes rejection record JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Rejection record rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl validate-promotion",
        entrypoint="builder_ii.hitl_promotion_cli:hitl_promotion_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates passive promotion bridge artifact files against schema.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints verification results.",
        failure_mode="Exits non-zero on schema error.",
        notes="Validation audit only.",
    ),
    CommandAuthorityRecord(
        name="builder-hitl candidate-manifest",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive execution candidate manifest statically.",
        write_boundary="Writes candidate manifest JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Writes JSON files.",
        failure_mode="Exits non-zero on format mismatch.",
        notes="Candidate manifest rendering only.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-hitl validate-candidate-manifest",
        entrypoint="builder_ii.hitl_execution_cli:hitl_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates passive candidate manifest and validation report files against schema.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints verification results.",
        failure_mode="Exits non-zero on schema error.",
        notes="Validation audit only.",
    ),
    CommandAuthorityRecord(
        name="builder-orchestration plan",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates plan structure statically without launching active agents.",
        write_boundary="Writes plan JSON file.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs serialized orchestration plan.",
        failure_mode="Exits non-zero if target profile is invalid.",
        notes="Creates the plan under governance.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-orchestration render-assignment",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive Goal 2 assignment and orchestration plans from existing source artifacts and SHA-256 refs.",
        write_boundary="Writes assignment/orchestration JSON only to explicit artifact output paths.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints or writes deterministic assignment and orchestration assignment plan artifacts.",
        failure_mode="Fails closed on missing refs, digest mismatches, invalid model recommendations, unsafe governance, or authority escalation.",
        notes="Render only; does not call models, execute tools, invoke Goose/deepagents/MCP, run shell, or mutate target repositories.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-orchestration validate",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates v1 orchestration and Goal 2 assignment/orchestration artifacts.",
        write_boundary="Writes validation-report JSON only when an explicit output path is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints verification results and can write passive validation reports for Goal 2 artifacts.",
        failure_mode="Exits non-zero if validation fails.",
        notes="Validation-only auditor; validation never grants execution authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-orchestration dry-run",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a passive dry-run explaining Goal 2 planned bindings without executing anything.",
        write_boundary="Writes dry-run JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints or writes dry-run JSON with denied capabilities, required promotions, evidence expectations, and handoff expectations.",
        failure_mode="Exits non-zero if the source orchestration assignment plan is invalid or claims authority.",
        notes="Dry-run remains non-runtime and cannot call models, tools, Goose, deepagents, MCP, shell, network, verification, or target writes.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-orchestration lane-policy",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders the Ladder 4 obligation lane policy from a fixed in-code table and checks each command-form discharge mechanism against COMMAND_AUTHORITY_REGISTRY (read-only).",
        write_boundary="Writes lane policy JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints or writes the deterministic, digest-bound lane policy artifact.",
        failure_mode="Exits non-zero if the rendered policy fails schema validation or names an unregistered command-form discharge mechanism.",
        notes="Derived-view artifact only; does not mint obligations, run agents, or edit the command registry it reads.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-orchestration validate-lane-policy",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates an orchestration lane policy artifact file (schema, totality, digest) and re-checks command-form discharge mechanisms against COMMAND_AUTHORITY_REGISTRY (read-only).",
        write_boundary="No writes; reads and validates an existing artifact file only.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation diagnostics only.",
        failure_mode="Exits non-zero on invalid JSON, schema/totality/digest errors, or an unregistered discharge mechanism.",
        notes="Validation-only auditor; validation never grants execution authority.",
    ),
    CommandAuthorityRecord(
        name="builder-orchestration mint-obligation",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Builds a governed obligation artifact statically: derives and checks the lane against a supplied lane policy, pins its digest, and validates the result. Does not run, spawn, or enforce a runtime budget envelope.",
        write_boundary="Writes obligation JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None. The obligation is inert until a separately sealed runner consumes it (Ladder 4 PR-4).",
        output_behavior="Prints or writes the validated, digest-bound obligation artifact.",
        failure_mode="Exits non-zero on lane-policy mismatch, anti-dump/schema violations, an invalid parent_ref, or a budget/briefing bound violation.",
        notes="Law 1 ticket minter. Mint-time budget conservation and dynamic-mint enforcement are the sealed runner's job (PR-4); this surface only emits a well-formed obligation.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-orchestration validate-obligation",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates an orchestration obligation artifact file: schema, anti-dump, parent_ref XOR, budget shape, and digest re-derivation (tamper detection).",
        write_boundary="No writes; reads and validates an existing artifact file only.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation diagnostics only.",
        failure_mode="Exits non-zero on invalid JSON, schema violations, or a digest mismatch.",
        notes="Validation-only auditor; validation never grants execution authority.",
    ),
    CommandAuthorityRecord(
        name="builder-orchestration status",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Deterministic read-only walk over a `builder-deepagents run-approved --obligation` output directory: re-derives the event chain fresh from the per-event files (tamper-sensitive) and renders one row per obligation with its board state (OPEN / SATISFIED / UNVERIFIED / VIOLATED / BLOCKED) and granted budget partition. No model, no execution.",
        write_boundary="Writes the rendered status-board JSON only to an explicit --output artifact path; never writes to the run directory it inspects.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints the obligation status board, or writes it as JSON to --output.",
        failure_mode="Exits non-zero on a violated/broken obligation chain (tampered events, or a tampered receipt/ledger) or missing run artifacts.",
        notes="Law 2 belief board; a read-only auditor — inspection never grants execution authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-orchestration why",
        entrypoint="builder_ii.orchestration_cli:orchestration_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Deterministic read-only belief trace for one obligation, located from one of its lifecycle event files: re-walks the whole run fresh from disk and reports believed?/required evidence/attached/consumed. Only a CONTRACT_SATISFIED discharge over an intact chain is believed. No model, no execution.",
        write_boundary="Writes the belief-trace JSON only to an explicit --output artifact path; never writes to the run directory it inspects.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints the single-obligation belief/discharge verdict line, or writes the trace as JSON to --output.",
        failure_mode="Exits non-zero on a violated/broken chain, or when the referenced obligation is not believed (anything other than CONTRACT_SATISFIED).",
        notes="Law 2 (no belief without discharge); a read-only auditor — a DISCHARGED_UNVERIFIED obligation is reported as not believed.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-profile-pack scaffold",
        entrypoint="builder_ii.profile_pack_cli:profile_pack_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Scaffolds passive profile-pack manifests from local source refs and hashes only.",
        write_boundary="Writes profile-pack manifest JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints manifest JSON or writes it to the requested output file.",
        failure_mode="Exits non-zero if source refs are missing or generated manifest validation fails.",
        notes="No runtime, model, Goose, deepagents, MCP, shell, verification, target-repo, or git authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-profile-pack wizard",
        entrypoint="builder_ii.profile_pack_cli:profile_pack_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Prompts the four scaffold decisions, registry-validating the target profile against the live registry at prompt time, then emits exactly what `builder-profile-pack scaffold` emits.",
        write_boundary="Writes profile-pack manifest JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None. It plans a manifest; rendering and applying are separate commands.",
        output_behavior="Prints manifest JSON or writes it to the requested output file.",
        failure_mode="Exits 2 on a rejected flag or after three invalid answers, without writing artifacts; exits non-zero if source refs are missing or generated manifest validation fails.",
        notes="Holds no authority `builder-profile-pack scaffold` does not: both call one emitter. No runtime, model, Goose, deepagents, MCP, shell, verification, target-repo, or git authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-profile-pack render",
        entrypoint="builder_ii.profile_pack_cli:profile_pack_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders a passive profile-pack render plan without materializing runtime behavior.",
        write_boundary="Writes render-plan JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints render-plan JSON or writes it to the requested output file.",
        failure_mode="Exits non-zero on invalid manifests, unknown profile kinds, or authority leakage.",
        notes="Render means deterministic artifact planning only; no execution or authorization.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-profile-pack validate",
        entrypoint="builder_ii.profile_pack_cli:profile_pack_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates profile-pack lifecycle artifacts and can emit a passive validation report.",
        write_boundary="Writes validation-report JSON only when an explicit output path is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation errors or a validation report; exits non-zero on invalid subjects.",
        failure_mode="Fails closed on unknown artifact kinds, missing schema versions, duplicate ids, or boundary leaks.",
        notes="Validation does not execute, authorize, promote, or prove planned verification ran.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-profile-pack dry-run",
        entrypoint="builder_ii.profile_pack_cli:profile_pack_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a passive dry-run artifact showing what would render without executing anything.",
        write_boundary="Writes dry-run JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints dry-run JSON or writes it to the requested output file.",
        failure_mode="Exits non-zero if manifest/render-plan validation fails or dry-run boundaries are violated.",
        notes="Dry-run remains non-runtime and cannot start Goose, construct deepagents, call models, call MCP, or run verification.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-model-policy validate",
        entrypoint="builder_ii.model_policy_cli:model_policy_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates passive model client registry, routing policy, and recommendation artifacts.",
        write_boundary="Writes validation report JSON only when an explicit output path is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints verification results or writes report JSON; exits non-zero on invalid artifacts.",
        failure_mode="Fails closed on unknown artifact kinds, missing schemas, or boundary leaks.",
        notes="Audit validation only; never calls models or provider endpoints.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-model-policy render",
        entrypoint="builder_ii.model_policy_cli:model_policy_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders passive model routing recommendation artifacts from registry and policy metadata.",
        write_boundary="Writes recommendation JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints recommendation JSON or writes it to requested output file.",
        failure_mode="Exits non-zero on invalid policy/registry metadata or unknown candidate IDs.",
        notes="Produces advisory recommendations without executing models or granting execution authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-model-policy dry-run",
        entrypoint="builder_ii.model_policy_cli:model_policy_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Performs a passive routing recommendation dry-run showing recommended models without executing anything.",
        write_boundary="Writes dry-run recommendation JSON only to an explicit artifact output path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints dry-run JSON or writes it to requested output file.",
        failure_mode="Exits non-zero on validation failures or if any candidate lacks risk classification.",
        notes="Dry-run remains non-runtime and cannot invoke models or network endpoints.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-model call",
        entrypoint="builder_ii.model_cli:model_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Executes a governed model call using an enabled model client.",
        write_boundary="Writes model call envelope and receipt JSON to output paths.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Delegated to CLI invocation.",
        output_behavior="Writes JSON envelope and receipt.",
        failure_mode="Exits non-zero on failure or validation error.",
        notes="Governed model execution gateway call command.",
        allows_model_execution=True,
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-model validate-receipt",
        entrypoint="builder_ii.model_cli:model_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a model call receipt artifact against its schema.",
        write_boundary="No target repo writes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Exits non-zero on schema validation failures.",
        failure_mode="Exits non-zero on schema validation failures.",
        notes="Audit validation only.",
    ),
    CommandAuthorityRecord(
        name="builder-model standalone-call",
        entrypoint="builder_ii.model_cli:model_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Executes a governed model call without logging to the workflow ledger. Intended for testing and offline evaluation only; no session state is produced.",
        write_boundary="Writes model call envelope and receipt JSON to explicit output paths only.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Delegated to CLI invocation. No ledger event is recorded; operator is responsible for audit trail outside of session context.",
        output_behavior="Writes JSON envelope and receipt to requested output paths.",
        failure_mode="Exits non-zero on model execution failure, policy violation, or validation error.",
        notes="Ledger-free variant of builder-model call for test/standalone use. Does not satisfy operational ledger-bound authority requirements.",
        allows_model_execution=True,
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-platform matrix",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Renders the static source-derived completion truth matrix as JSON after validating shape and authority references.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON to stdout.",
        failure_mode="Exits non-zero if required rows, state labels, evidence refs, or command authority refs are invalid.",
        notes="Artifact-only truth rendering. It does not run verification, models, tools, Goose, deepagents, shell commands, or MCP calls.",
    ),
    CommandAuthorityRecord(
        name="builder-platform status",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Summarizes the completion truth matrix without inspecting runtime systems or target repositories.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints concise human-readable platform truth state to stdout.",
        failure_mode="Exits non-zero if the matrix or command authority coverage is invalid.",
        notes="States that builder-II is passive-foundation-complete and operationally incomplete, and names R0 -> R1 -> B1.",
    ),
    CommandAuthorityRecord(
        name="builder-platform known-limitations",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Renders the known-limitations document from the completion truth matrix after validating matrix shape; no verification, model, tool, Goose, deepagents, shell, or MCP behavior.",
        write_boundary="Writes only the explicit --output document path when provided; stdout rendering leaves the workspace untouched.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints the known-limitations markdown to stdout or writes it to the explicit --output path.",
        failure_mode="Exits non-zero if the matrix shape, evidence refs, or command authority refs are invalid.",
        notes="Plan 4.2 beta surface. docs/KNOWN_LIMITATIONS.md must equal this renderer's output (pinned test); the D7 verification-lane scope language is part of the rendered document.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-platform audit-docs",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Scans README.md and docs/**/*.md for false operational-completion claims without invoking external tools.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON docs-truth audit report to stdout.",
        failure_mode="Exits non-zero when docs imply operational completion for non-OPERATIONALLY_VERIFIED capabilities or contain known stale claims.",
        notes="Docs truth enforcement only. It cannot rewrite docs or promote runtime authority.",
    ),
    CommandAuthorityRecord(
        name="builder-platform r1-closure",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Generates config schema, resolution, setup plan, overlay plan, rollback snapshot, onboarding intent, and R1 closure report artifacts in the requested output directory without runtime execution.",
        write_boundary="Writes only explicit R1 closure and proof artifacts into the provided output directory. No target repository or source files are modified.",
        approval_mode=MODE_NONE,
        approval_boundary="None. Generating closure and onboarding proof artifacts never applies mutation.",
        output_behavior="Writes r1-closure-report.json and chain artifacts to output-dir and prints JSON report summary to stdout.",
        failure_mode="Exits non-zero if any config, setup, onboarding, command authority, platform matrix, or docs truth validation fails.",
        notes="Proves the passive setup/onboarding golden path for R1 closure. Does not start runtime, models, tools, Goose, deepagents, or MCP, does not execute setup apply or rollback, and does not promote B1/B2.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-platform validate-r1-closure",
        entrypoint="builder_ii.platform_status_cli:platform_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates an R1 closure report artifact and its referenced R1 chain evidence files without executing runtime or model operations.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation report JSON to stdout.",
        failure_mode="Exits non-zero on malformed report, digest drift, disabled authority claims, missing R1 chain evidence, or docs/matrix/authority failures.",
        notes="Read-only validation of R1 closure reports and evidence chain. Does not promote runtime authority or execute setup mutation.",
    ),
    CommandAuthorityRecord(
        name="builder-memory atom",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Wraps one explicit validated source artifact as a governed memory atom without runtime execution, model authority, shell execution, hidden memory, or vector-store retrieval.",
        write_boundary="Writes one memory atom JSON artifact only to the explicit output path when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints memory atom JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero on unknown source kinds, source validation failures, digest drift, unsupported claim boundaries, or source-truth inflation attempts.",
        notes="Source-bound artifact memory only. Handoff-derived atoms require explicit source refs and summaries never become authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-memory index",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Builds a deterministic memory index from explicit memory atom artifacts only; no runtime execution, model calls, shell execution, hidden retrieval, or vector-store behavior.",
        write_boundary="Writes one memory index JSON artifact only to the explicit output path when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints memory index JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero on malformed atoms, mixed target profiles, duplicate atom refs, digest drift, or invalid index metadata.",
        notes="Explicit atom indexing only. No background indexing, memory mutation, or target repo writes are enabled.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-memory search",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Searches an explicit memory index with deterministic lexical scoring only; no model calls, semantic retrieval, hidden memory, shell execution, or runtime behavior.",
        write_boundary="Writes one memory search result JSON artifact only to the explicit output path when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints memory search result JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero on malformed indexes, invalid deterministic search metadata, or digest drift.",
        notes="Search remains explainable and non-authoritative. Opaque vector stores and autonomous writes stay disabled.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-memory reconstruct",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Reconstructs reviewable context from an explicit memory index without runtime execution, model authority, shell execution, hidden retrieval, or target repo mutation.",
        write_boundary="Writes one memory reconstruction JSON artifact only to the explicit output path when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints memory reconstruction JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero on malformed indexes, invalid reconstruction metadata, digest drift, or unsupported source-truth claims.",
        notes="Reconstruction is replay-stable review data only. It does not grant execution authority or mutate memory.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-memory validate-atom",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a memory atom artifact without runtime execution, model calls, shell execution, or memory mutation.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation success or failure diagnostics to stdout.",
        failure_mode="Exits non-zero on malformed memory atom artifacts, digest drift, or invalid claim boundaries.",
        notes="Validation only. It cannot create hidden memory, mutate source artifacts, or promote authority.",
    ),
    CommandAuthorityRecord(
        name="builder-memory validate-index",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a memory index artifact without runtime execution, model calls, shell execution, or memory mutation.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation success or failure diagnostics to stdout.",
        failure_mode="Exits non-zero on malformed memory indexes, digest drift, or inconsistent counts.",
        notes="Validation only. No background indexing, hidden retrieval, or target repo writes are enabled.",
    ),
    CommandAuthorityRecord(
        name="builder-memory validate-reconstruction",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a memory reconstruction artifact without runtime execution, model calls, shell execution, or memory mutation.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation success or failure diagnostics to stdout.",
        failure_mode="Exits non-zero on malformed reconstructions, digest drift, or invalid selected/excluded atom refs.",
        notes="Validation only. Reconstruction artifacts remain review artifacts and never become authority.",
    ),
    CommandAuthorityRecord(
        name="builder-memory validate-search-result",
        entrypoint="builder_ii.memory_cli:memory_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a memory search result artifact without runtime execution, model calls, shell execution, or memory mutation.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation success or failure diagnostics to stdout.",
        failure_mode="Exits non-zero on malformed search results, digest drift, or invalid deterministic scoring metadata.",
        notes="Validation only. Search remains explicit, explainable, and non-authoritative.",
    ),
    CommandAuthorityRecord(
        name="builder-config schema",
        entrypoint="builder_ii.config_cli:config_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Renders the static generic-first config schema; no runtime, model, shell, Goose, deepagents, MCP, tool, or patch execution.",
        write_boundary="Writes schema JSON only to an explicit artifact output path when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints schema JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero only on output path write failure.",
        notes="R1.1 schema artifact only; it grants no setup, runtime, model, tool, MCP, Goose, deepagents, or patch authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-config resolve",
        entrypoint="builder_ii.config_cli:config_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Resolves passive config sources and validates path policy without running subprocesses or invoking runtime systems.",
        write_boundary="Writes resolution JSON only to an explicit artifact output path when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints source resolution JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero on invalid values, unsafe artifact-root policy, unknown profiles, or output path write failure.",
        notes="Records source precedence and legacy aliases. It cannot call models, tools, MCP, Goose, deepagents, shell commands, or apply patches.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-config validate",
        entrypoint="builder_ii.config_cli:config_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates config schema or resolution artifacts without runtime, model, shell, Goose, deepagents, MCP, tool, or patch execution.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints validation report JSON to stdout.",
        failure_mode="Exits non-zero on malformed artifacts, digest drift, unsupported kinds, or invalid current resolution.",
        notes="Validation only; no setup writes, runtime construction, provider calls, or target repo mutation.",
    ),
    CommandAuthorityRecord(
        name="builder-setup plan",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a passive setup plan from resolved config; no setup apply, rollback, runtime start, model call, shell execution, Goose start, deepagents construction, MCP/tool invocation, or patch authority.",
        write_boundary="Writes setup plan JSON only to an explicit artifact output path when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints setup plan JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero on invalid resolution, unsafe path policy, malformed plan, or output path write failure.",
        notes="Planned writes are descriptive only. R1.1 setup plans are artifact_is_authority=false and cannot mutate target repos or user Goose config.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-setup validate-plan",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a passive setup plan artifact without applying setup, rollback, Goose, deepagents, model, MCP/tool, shell, or patch behavior.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints setup plan validation report JSON to stdout.",
        failure_mode="Exits non-zero on malformed plan, digest drift, authority claims, or embedded resolution errors.",
        notes="Validation only. A valid setup plan remains artifact_is_authority=false.",
    ),
    CommandAuthorityRecord(
        name="builder-setup overlay-plan",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a passive setup overlay plan from a setup plan; runtime execution, model execution, shell execution, Goose runtime, deepagents runtime, MCP/tool invocation, patch authority, setup apply, and setup rollback execution are disabled.",
        write_boundary="Writes setup overlay JSON only to an explicit artifact output path when --output is supplied.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints setup overlay JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero on malformed setup plan, unsafe path classification, digest drift, or output path write failure.",
        notes="Artifact-only preview/diff/safety bridge. It writes no Goose config, .goosehints, skills, recipes, target repo files, or source files.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-setup validate-overlay-plan",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a passive setup overlay plan without setup apply, rollback execution, runtime start, model call, shell execution, Goose, deepagents, MCP/tool, or patch behavior.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints setup overlay validation report JSON to stdout.",
        failure_mode="Exits non-zero on malformed overlay, unsafe path classification, authority claims, or digest drift.",
        notes="Validation only. A valid setup overlay remains planned_only=true and artifact_is_authority=false.",
    ),
    CommandAuthorityRecord(
        name="builder-setup rollback-snapshot",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a passive setup rollback snapshot artifact by inspecting prior file states; runtime execution, model execution, shell execution, Goose runtime, deepagents runtime, MCP/tool invocation, patch authority, setup apply, and setup rollback execution are disabled.",
        write_boundary="Writes rollback snapshot JSON only to an explicit artifact output path when --output is supplied; it does not write target paths or secure prior-content stores.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints rollback snapshot JSON and optionally writes the same artifact to the requested output path.",
        failure_mode="Exits non-zero on malformed overlay, unsafe prior-state metadata, authority claims, digest drift, or output path write failure.",
        notes="Snapshot artifact only. It records digests, sizes, markers, and redacted previews; raw secrets and raw prior content are not stored in normal JSON artifacts.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-setup validate-rollback-snapshot",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates a passive setup rollback snapshot without rollback execution, setup apply, runtime start, model call, shell execution, Goose, deepagents, MCP/tool, or patch behavior.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints rollback snapshot validation report JSON to stdout.",
        failure_mode="Exits non-zero on malformed snapshot, raw-content claims, authority claims, or digest drift.",
        notes="Validation only. A valid rollback snapshot remains snapshot_only=true and artifact_is_authority=false.",
    ),
    CommandAuthorityRecord(
        name="builder-setup apply",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_2,
        promotion_state=STATE_ENABLED,
        runtime_boundary="Digest-bound governed setup write only; runtime execution, model execution, shell/subprocess execution, Goose runtime, deepagents runtime, MCP/tool invocation, patch authority, rollback execution, and B1 verification execution are disabled.",
        write_boundary="Writes only declared setup target paths from a validated overlay plan plus the explicit setup receipt output; source writes are disabled except declared artifact-root setup metadata/config paths.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must approve the overlay_plan_digest before any mutation: --approve-digest matching overlay_plan_digest (scripted), or an interactive typed digest-prefix confirmation when the flag is omitted; --rollback-snapshot must match the overlay. The receipt records approval_mode (explicit_digest_bound_cli_flag or interactive_digest_prefix_confirmation).",
        output_behavior="Writes a setup apply receipt JSON to the explicit --output path and prints it to stdout.",
        failure_mode="Fails closed on missing/wrong digest, mismatched snapshot, unsafe path, symlink, undeclared path, unsupported operation, or partial write failure; emits failure receipt where practical and does not rollback.",
        notes="R1.3A setup apply only. Rollback execution, B1, runtime/model/tool/MCP/Goose/deepagents/patch authority, autonomous apply, and arbitrary/source-code writes remain unpromoted.",
        allows_source_writes=True,
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-setup validate-receipt",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates setup apply receipts without setup apply, rollback execution, runtime start, model call, shell execution, Goose, deepagents, MCP/tool, or patch behavior.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints receipt validation report JSON to stdout.",
        failure_mode="Exits non-zero on malformed receipt, digest drift, authority claims, or forbidden execution fields.",
        notes="Validation only. Receipt artifacts are not runtime authority and rollback_executed must remain false.",
    ),
    CommandAuthorityRecord(
        name="builder-setup rollback",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_2,
        promotion_state=STATE_ENABLED,
        runtime_boundary="Digest-bound governed setup rollback execution only; B1 verification execution, B2 patch rollback, generic repository rollback, git rollback, shell/subprocess, runtime execution, model/provider, MCP/tool, Goose runtime, deepagents runtime, patch authority, and autonomous rollback are disabled.",
        write_boundary="Touches only changed_paths recorded in an applied setup receipt and covered by the supplied rollback snapshot; writes a setup rollback receipt only to explicit --output.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Operator must approve the setup receipt digest before any mutation: --approve-digest matching the receipt digest (scripted), or an interactive typed digest-prefix confirmation when the flag is omitted; the rollback snapshot must match receipt digests. The rollback receipt records approval_mode (explicit_digest_bound_cli_flag or interactive_digest_prefix_confirmation).",
        output_behavior="Writes a setup rollback receipt JSON to the explicit --output path and prints it to stdout.",
        failure_mode="Preflights deterministic denials before mutation and fails closed on ineligible receipts, digest mismatch, undeclared path, uncovered path, symlink, traversal, filesystem conflict, unsupported prior state, or unavailable raw prior content.",
        notes="R1.3B setup rollback only. R1.3A already owns setup apply; B1, B2 patch rollback, generic/git rollback, runtime/model/tool/MCP/Goose/deepagents/patch authority, and autonomous rollback remain unpromoted.",
        allows_source_writes=True,
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-setup validate-rollback-receipt",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates setup rollback receipts without setup apply, rollback execution, runtime start, model call, shell execution, Goose, deepagents, MCP/tool, git, generic rollback, B1, B2, or patch behavior.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints setup rollback receipt validation report JSON to stdout.",
        failure_mode="Exits non-zero on malformed rollback receipt, digest drift, authority claims, or forbidden execution fields.",
        notes="Validation only. Setup rollback receipts record R1.3B setup rollback evidence and do not grant B1/B2/runtime/model/MCP/Goose/deepagents/patch/git authority.",
    ),
    CommandAuthorityRecord(
        name="builder-setup init",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Non-interactive governed onboarding wrapper generating passive setup plan, overlay plan, rollback snapshot, and intent report; no Goose, model, MCP, deepagents, patch, or shell execution.",
        write_boundary="Writes passive setup artifacts under explicit output directory only; no setup mutation or receipt generation.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints setup plan summary, digests, and deferred apply command to stdout.",
        failure_mode="Exits non-zero on schema error or digest mismatch.",
        notes="R1.5 onboarding wrapper.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-setup wizard",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Interactive governed onboarding wizard generating passive setup plan, overlay plan, rollback snapshot, and intent report; no Goose, model, MCP, deepagents, patch, or shell execution.",
        write_boundary="Writes passive setup artifacts under explicit output directory only; no setup mutation or receipt generation.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints setup plan summary, digests, and deferred apply command to stdout.",
        failure_mode="Exits non-zero on schema error or digest mismatch.",
        notes="R1.5 interactive onboarding wizard.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-setup validate-onboarding-intent",
        entrypoint="builder_ii.setup_cli:setup_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates onboarding intent reports without setup apply, rollback execution, runtime start, model call, shell execution, Goose, deepagents, MCP/tool, git, or patch behavior.",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints onboarding intent validation report JSON to stdout.",
        failure_mode="Exits non-zero on malformed intent report, digest drift, authority claims, or forbidden command strings.",
        notes="Validation only. Validates R1.5 onboarding intent reports.",
    ),
    CommandAuthorityRecord(
        name="builder workflow plan",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a passive governed workflow plan; no model, shell, Goose, deepagents, MCP, or target-repo execution.",
        write_boundary="Writes workflow session, profile, routing, orchestration, work-plan, event, replay, ledger, and status artifacts under the workflow output directory.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after writing passive artifacts.",
        failure_mode="Exits non-zero on invalid target, stale output directory, missing source refs, or schema failure.",
        notes="First stage of the governed workflow state machine.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder workflow promote",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Records passive HITL promotion artifacts only; does not authorize execution.",
        write_boundary="Writes promotion request, review, decision, approval-boundary, transition, event, replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after recording the promotion boundary.",
        failure_mode="Exits non-zero if the workflow is not at planned stage or promotion artifacts fail validation.",
        notes="Promotion here means candidate-design boundary only, not runtime approval.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder workflow candidate",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Records a passive execution candidate manifest without invoking commands.",
        write_boundary="Writes candidate manifest, validation report, transition, event, replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after candidate recording.",
        failure_mode="Exits non-zero if the workflow is not at promoted stage or refs are stale.",
        notes="Candidate manifest remains structural and cannot execute verification.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder workflow verify-chain",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates artifact index and chain refs without running external tools.",
        write_boundary="Writes artifact index, chain verification, transition, event, replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after chain verification.",
        failure_mode="Exits non-zero on unknown kind, invalid native schema, broken ref, digest mismatch, or stale stage.",
        notes="Chain verification validates evidence links only; it is not execution evidence.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder workflow handoff",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Writes passive handoff summaries after chain verification; no runtime activation.",
        write_boundary="Writes handoff note, golden-path summary, demo README, transition, event, replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after handoff creation.",
        failure_mode="Exits non-zero unless the workflow is chain_verified and all handoff artifacts validate.",
        notes="Handoff is review material, not authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder workflow status",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Replays workflow events to reconstruct status without executing runtime work.",
        write_boundary="Writes refreshed replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints replayed workflow status JSON.",
        failure_mode="Exits non-zero on invalid session, event sequence, previous-event mismatch, or replay failure.",
        notes="Status is derived from events, not mutable memory.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder ledger list",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reads workflow event ledgers and reconstructs status summaries only.",
        write_boundary="Read-only ledger inspection; no workspace changes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON rows for known workflow sessions.",
        failure_mode="Returns an empty list when no ledgers exist; exits non-zero on malformed sessions.",
        notes="Inspection-only ledger listing.",
    ),
    CommandAuthorityRecord(
        name="builder ledger replay",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Replays event records deterministically without executing runtime work.",
        write_boundary="Writes replay report JSON to an explicit or default workflow artifact path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints replay report JSON.",
        failure_mode="Exits non-zero on missing session, invalid event order, skipped stage, or previous-event mismatch.",
        notes="Replay reconstructs status from events, not mutable status files.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder ledger audit",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Scans event subject refs for a requested artifact SHA; no execution.",
        write_boundary="Read-only ledger inspection; no workspace changes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON audit matches including who, what, when, why, status, evidence, and next transition.",
        failure_mode="Exits non-zero when no event references the requested artifact SHA.",
        notes="Audit-by-digest surface for workflow evidence.",
    ),
    CommandAuthorityRecord(
        name="builder ledger query-receipts",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reads existing verification execution ledger records under .builder/ledger, validates records, and filters by receipt digest, chain digest, receipt status, or runner mode without replay, subprocess, shell, model, MCP, Goose, or deepagents runtime.",
        write_boundary="Read-only verification execution ledger inspection; no source, target repo, git, memory, patch, artifact, or B2 authority writes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON query results, rejected-record diagnostics, and summary counts only.",
        failure_mode="Returns an empty valid report when the ledger directory is absent; exits non-zero with JSON diagnostics when the ledger root path is invalid.",
        notes="B1.4B read-only audit/query surface. It never replays execution and grants no runtime, patch, git, subprocess, shell, model, MCP, Goose, deepagents, or B2 authority.",
    ),
    CommandAuthorityRecord(
        name="builder ledger validate-receipts",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reads existing verification execution ledger records under .builder/ledger and emits a deterministic integrity report without replay execution, subprocess, shell, model, MCP, Goose, or deepagents runtime.",
        write_boundary="Read-only verification execution ledger integrity validation; no source, target repo, git, memory, patch, artifact, or B2 authority writes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON integrity diagnostics for record digests, duplicate records, required subject refs, chain digests, and optional index continuity.",
        failure_mode="Returns an empty valid report when the ledger directory is absent; exits non-zero with JSON diagnostics on rejected records, duplicate records, subject-ref drift, chain-digest mismatch, or index-chain discontinuity.",
        notes="B1.4C passive validation only. It reconstructs ledger integrity from artifacts and never replays execution or grants runtime, patch, git, subprocess, shell, model, MCP, Goose, deepagents, or B2 authority.",
    ),
    CommandAuthorityRecord(
        name="builder ledger reconstruct-receipts",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reads existing verification execution ledger records under .builder/ledger and reconstructs passive receipt-chain projections without replay execution, subprocess, shell, model, MCP, Goose, or deepagents runtime.",
        write_boundary="Read-only verification execution ledger reconstruction; no source, target repo, git, memory, patch, artifact, or B2 authority writes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON reconstruction reports with summary, invalid/rejected records, chain continuity status, reconstructed chain rows, and evidence refs only.",
        failure_mode="Returns an empty valid report when the ledger directory is absent; exits non-zero with JSON diagnostics on rejected records, duplicate records, subject-ref drift, chain-digest mismatch, or index-chain discontinuity.",
        notes="B1.4D read-only reconstruction/report surface. It does not rerun verification and grants no runtime, patch, git, subprocess, shell, model, MCP, Goose, deepagents, or B2 authority.",
    ),
    CommandAuthorityRecord(
        name="builder ledger export",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Exports event ledger artifacts without runtime execution.",
        write_boundary="Writes event ledger export JSON to an explicit or default workflow artifact path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints exported ledger JSON or writes it to the requested output.",
        failure_mode="Exits non-zero on missing session or invalid ledger validation.",
        notes="Ledger export remains a passive artifact.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder ledger index-receipt",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Passively validates and indexes an existing B1.3 verification execution plan, approval, and receipt chain without subprocess, shell, model, MCP, Goose, deepagents, replay execution, patch behavior, git mutation, or source writes.",
        write_boundary="Writes one verification execution ledger record only under the target repo .builder/ledger directory.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints the passive ledger record JSON and writes it to the explicit or default .builder/ledger output path.",
        failure_mode="Exits non-zero on invalid plan, approval, receipt, binding mismatch, invalid ledger record, or unsafe output path.",
        notes="B1.4A passive index only. It records validated B1.3 receipt-chain evidence and grants no runtime, replay, patch, model, MCP, Goose, deepagents, shell, subprocess, git, or B2 authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-workflow plan",
        entrypoint="builder_ii.workflow_cli:workflow_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Creates a passive governed workflow plan; no model, shell, Goose, deepagents, MCP, or target-repo execution.",
        write_boundary="Writes workflow session, profile, routing, orchestration, work-plan, event, replay, ledger, and status artifacts under the workflow output directory.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after writing passive artifacts.",
        failure_mode="Exits non-zero on invalid target, stale output directory, missing source refs, or schema failure.",
        notes="Standalone script equivalent of builder workflow plan.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-workflow promote",
        entrypoint="builder_ii.workflow_cli:workflow_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Records passive HITL promotion artifacts only; does not authorize execution.",
        write_boundary="Writes promotion request, review, decision, approval-boundary, transition, event, replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after recording the promotion boundary.",
        failure_mode="Exits non-zero if the workflow is not at planned stage or promotion artifacts fail validation.",
        notes="Standalone script equivalent of builder workflow promote.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-workflow candidate",
        entrypoint="builder_ii.workflow_cli:workflow_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Records a passive execution candidate manifest without invoking commands.",
        write_boundary="Writes candidate manifest, validation report, transition, event, replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after candidate recording.",
        failure_mode="Exits non-zero if the workflow is not at promoted stage or refs are stale.",
        notes="Standalone script equivalent of builder workflow candidate.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-workflow verify-chain",
        entrypoint="builder_ii.workflow_cli:workflow_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Validates artifact index and chain refs without running external tools.",
        write_boundary="Writes artifact index, chain verification, transition, event, replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after chain verification.",
        failure_mode="Exits non-zero on unknown kind, invalid native schema, broken ref, digest mismatch, or stale stage.",
        notes="Standalone script equivalent of builder workflow verify-chain.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-workflow handoff",
        entrypoint="builder_ii.workflow_cli:workflow_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Writes passive handoff summaries after chain verification; no runtime activation.",
        write_boundary="Writes handoff note, golden-path summary, demo README, transition, event, replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints workflow status JSON after handoff creation.",
        failure_mode="Exits non-zero unless the workflow is chain_verified and all handoff artifacts validate.",
        notes="Standalone script equivalent of builder workflow handoff.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-workflow status",
        entrypoint="builder_ii.workflow_cli:workflow_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Replays workflow events to reconstruct status without executing runtime work.",
        write_boundary="Writes refreshed replay, ledger, and status artifacts.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints replayed workflow status JSON.",
        failure_mode="Exits non-zero on invalid session, event sequence, previous-event mismatch, or replay failure.",
        notes="Standalone script equivalent of builder workflow status.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-ledger list",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reads workflow event ledgers and reconstructs status summaries only.",
        write_boundary="Read-only ledger inspection; no workspace changes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON rows for known workflow sessions.",
        failure_mode="Returns an empty list when no ledgers exist; exits non-zero on malformed sessions.",
        notes="Standalone script equivalent of builder ledger list.",
    ),
    CommandAuthorityRecord(
        name="builder-ledger replay",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Replays event records deterministically without executing runtime work.",
        write_boundary="Writes replay report JSON to an explicit or default workflow artifact path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints replay report JSON.",
        failure_mode="Exits non-zero on missing session, invalid event order, skipped stage, or previous-event mismatch.",
        notes="Standalone script equivalent of builder ledger replay.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-ledger audit",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Scans event subject refs for a requested artifact SHA; no execution.",
        write_boundary="Read-only ledger inspection; no workspace changes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON audit matches including who, what, when, why, status, evidence, and next transition.",
        failure_mode="Exits non-zero when no event references the requested artifact SHA.",
        notes="Standalone script equivalent of builder ledger audit.",
    ),
    CommandAuthorityRecord(
        name="builder-ledger query-receipts",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reads existing verification execution ledger records under .builder/ledger, validates records, and filters by receipt digest, chain digest, receipt status, or runner mode without replay, subprocess, shell, model, MCP, Goose, or deepagents runtime.",
        write_boundary="Read-only verification execution ledger inspection; no source, target repo, git, memory, patch, artifact, or B2 authority writes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON query results, rejected-record diagnostics, and summary counts only.",
        failure_mode="Returns an empty valid report when the ledger directory is absent; exits non-zero with JSON diagnostics when the ledger root path is invalid.",
        notes="Standalone script equivalent of builder ledger query-receipts. B1.4B read-only audit/query only; no runtime/replay/patch/model/MCP/Goose/deepagents/shell/subprocess/git/B2 authority.",
    ),
    CommandAuthorityRecord(
        name="builder-ledger validate-receipts",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reads existing verification execution ledger records under .builder/ledger and emits a deterministic integrity report without replay execution, subprocess, shell, model, MCP, Goose, or deepagents runtime.",
        write_boundary="Read-only verification execution ledger integrity validation; no source, target repo, git, memory, patch, artifact, or B2 authority writes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON integrity diagnostics for record digests, duplicate records, required subject refs, chain digests, and optional index continuity.",
        failure_mode="Returns an empty valid report when the ledger directory is absent; exits non-zero with JSON diagnostics on rejected records, duplicate records, subject-ref drift, chain-digest mismatch, or index-chain discontinuity.",
        notes="Standalone script equivalent of builder ledger validate-receipts. B1.4C passive validation only; no runtime/replay/patch/model/MCP/Goose/deepagents/shell/subprocess/git/B2 authority.",
    ),
    CommandAuthorityRecord(
        name="builder-ledger reconstruct-receipts",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_VALIDATION_ONLY,
        runtime_boundary="Reads existing verification execution ledger records under .builder/ledger and reconstructs passive receipt-chain projections without replay execution, subprocess, shell, model, MCP, Goose, or deepagents runtime.",
        write_boundary="Read-only verification execution ledger reconstruction; no source, target repo, git, memory, patch, artifact, or B2 authority writes.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints JSON reconstruction reports with summary, invalid/rejected records, chain continuity status, reconstructed chain rows, and evidence refs only.",
        failure_mode="Returns an empty valid report when the ledger directory is absent; exits non-zero with JSON diagnostics on rejected records, duplicate records, subject-ref drift, chain-digest mismatch, or index-chain discontinuity.",
        notes="Standalone script equivalent of builder ledger reconstruct-receipts. B1.4D read-only reconstruction/report surface; no runtime/replay/patch/model/MCP/Goose/deepagents/shell/subprocess/git/B2 authority.",
    ),
    CommandAuthorityRecord(
        name="builder-ledger export",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Exports event ledger artifacts without runtime execution.",
        write_boundary="Writes event ledger export JSON to an explicit or default workflow artifact path.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints exported ledger JSON or writes it to the requested output.",
        failure_mode="Exits non-zero on missing session or invalid ledger validation.",
        notes="Standalone script equivalent of builder ledger export.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-ledger index-receipt",
        entrypoint="builder_ii.ledger_cli:ledger_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Passively validates and indexes an existing B1.3 verification execution plan, approval, and receipt chain without subprocess, shell, model, MCP, Goose, deepagents, replay execution, patch behavior, git mutation, or source writes.",
        write_boundary="Writes one verification execution ledger record only under the target repo .builder/ledger directory.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Prints the passive ledger record JSON and writes it to the explicit or default .builder/ledger output path.",
        failure_mode="Exits non-zero on invalid plan, approval, receipt, binding mismatch, invalid ledger record, or unsafe output path.",
        notes="Standalone script equivalent of builder ledger index-receipt. B1.4A passive index only; no runtime/replay/patch/model/MCP/Goose/deepagents/shell/subprocess/git/B2 authority.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-mcp",
        entrypoint="builder_ii.mcp_cli:mcp_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Delegates governed MCP policy and execution subcommands.",
        write_boundary="No direct write authority at root CLI level.",
        approval_mode=MODE_NONE,
        approval_boundary="Delegated to subcommands.",
        output_behavior="Dispatches to MCP subcommands.",
        failure_mode="Exits non-zero on failure.",
        notes="MCP execution gateway.",
    ),
    CommandAuthorityRecord(
        name="builder-mcp inventory",
        entrypoint="builder_ii.mcp_cli:mcp_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Outputs static passive MCP inventory artifact.",
        write_boundary="Writes artifact to specified path if output flag passed.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs JSON inventory.",
        failure_mode="Exits non-zero on error.",
        notes="Passive B7 artifact emission.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-mcp policy",
        entrypoint="builder_ii.mcp_cli:mcp_app",
        tier=TIER_1,
        promotion_state=STATE_ARTIFACT_ONLY,
        runtime_boundary="Validates or emits passive MCP policy artifact.",
        write_boundary="Writes artifact to specified path if output flag passed.",
        approval_mode=MODE_NONE,
        approval_boundary="None.",
        output_behavior="Outputs JSON policy.",
        failure_mode="Exits non-zero on error.",
        notes="Passive B7 artifact validation/emission.",
        allows_artifact_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-mcp call",
        entrypoint="builder_ii.mcp_cli:mcp_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Executes explicitly bounded low-risk MCP stub call from envelope.",
        write_boundary="Writes receipt and operational ledger events.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit envelope passing.",
        output_behavior="Outputs JSON receipt.",
        failure_mode="Exits non-zero and writes denied event if policy fails.",
        notes="B7 gateway for MCP execution.",
        allows_artifact_writes=True,
        allows_external_tool_invocation=True,
        allows_state_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-mcp standalone-call",
        entrypoint="builder_ii.mcp_cli:mcp_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Executes explicitly bounded low-risk MCP stub call from envelope without logging to the workflow ledger.",
        write_boundary="Writes receipt to explicit output path only.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit envelope passing.",
        output_behavior="Outputs JSON receipt.",
        failure_mode="Exits non-zero if policy fails.",
        notes="Ledger-free variant of builder-mcp call.",
        allows_artifact_writes=True,
        allows_external_tool_invocation=True,
    ),
    CommandAuthorityRecord(
        name="builder-tools invoke",
        entrypoint="builder_ii.tools_cli:tools_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Executes explicitly bounded low-risk tool stub call from envelope.",
        write_boundary="Writes receipt and operational ledger events.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit envelope passing.",
        output_behavior="Outputs JSON receipt.",
        failure_mode="Exits non-zero and writes denied event if policy fails.",
        notes="B7 gateway for tool execution.",
        allows_artifact_writes=True,
        allows_external_tool_invocation=True,
        allows_state_writes=True,
    ),
    CommandAuthorityRecord(
        name="builder-tools standalone-invoke",
        entrypoint="builder_ii.tools_cli:tools_app",
        tier=TIER_3,
        promotion_state=STATE_HITL_RUNTIME_CANDIDATE,
        runtime_boundary="Executes explicitly bounded low-risk tool stub call from envelope without logging to the workflow ledger.",
        write_boundary="Writes receipt to explicit output path only.",
        approval_mode=MODE_EXPLICIT_OPERATOR_INVOCATION,
        approval_boundary="Explicit envelope passing.",
        output_behavior="Outputs JSON receipt.",
        failure_mode="Exits non-zero if policy fails.",
        notes="Ledger-free variant of builder-tools invoke.",
        allows_artifact_writes=True,
        allows_external_tool_invocation=True,
    ),
)


# --- Dynamically Generated Subcommand Records to Close Registry Gaps ---
_EXTRA_COMMAND_NAMES: tuple[str, ...] = (
    "builder tui status",
    "builder tui roster",
    "builder tui gates",
    "builder tui hitl",
    "builder tui handoff",
    "builder tui golden",
    "builder-lanes list",
    "builder-lanes show",
    "builder-context validate",
    "builder-context summarize",
    "builder-git-state artifact",
    "builder-git-state validate",
    "builder-session plan",
    "builder-session validate",
    "builder-session config",
    "builder-session validate-config",
    "builder-session goose-projection",
    "builder-session validate-goose-projection",
    "builder-session goose-wrapper-plan",
    "builder-session validate-goose-wrapper-plan",
    "builder-session goose-readonly-plan",
    "builder-session validate-goose-readonly-plan",
    "builder-session repo-map",
    "builder-session context-pack",
    "builder-code-vault frame",
    "builder-code-vault digest",
    "builder-code-vault extractor-manifest",
    "builder-code-vault validate-extractor-manifest",
    "builder-code-vault lint",
    "builder-code-vault context",
    "builder-code-vault recall",
    "builder-code-vault validate-frame",
    "builder-code-vault validate-lint",
    "builder-code-vault validate-context",
    "builder-code-vault validate-recall",
    "builder-code-vault demo",
    "builder-code-vault validate-demo",
    "builder-code-vault bench",
    "builder-code-vault validate-bench",
    "builder-code-vault corroborate",
    "builder-code-vault validate-corroboration",
    "builder-session operator-surface",
    "builder-session command-surface",
    "builder-agent profiles",
    "builder-agent show",
    "builder-agent render",
    "builder-agent validate",
    "builder-agent artifact",
    "builder-bridge doctor",
    "builder-bridge deepagents-smoke",
    "builder-bridge render",
    "builder-bridge validate-artifact",
    "builder-bundle create",
    "builder-bundle validate",
    "builder-goose propose-command",
    "builder-goose validate-command-proposal",
    "builder-goose env",
    "builder-records record",
    "builder-records validate",
    "builder-preflight record",
    "builder-preflight validate",
    "builder-receipt record",
    "builder-receipt validate",
    "builder-chain record",
    "builder-chain validate",
    "builder-chain verify-artifacts",
    "builder-handoff record",
    "builder-handoff validate",
    "builder-intake record",
    "builder-intake validate",
    "builder-index record",
    "builder-index validate",
    "builder-promotion record",
    "builder-promotion validate",
    "builder-promotion-decision record",
    "builder-promotion-decision validate",
    "builder-state-index record",
    "builder-state-index validate",
    "builder-snapshot record",
    "builder-snapshot validate",
    "builder-notes handoff",
    "builder-notes validate",
    "builder-quality plan",
    "builder-quality validate",
    "builder-research profiles",
    "builder-research show",
    "builder-research validate-profiles",
    "builder-research plan",
    "builder-research validate",
    "builder-research adapter",
    "builder-research validate-adapter",
    "builder-performance record",
    "builder-performance validate",
    "builder-performance benchmark-validation",
    "builder-performance parity-report",
    "builder-readonly report",
    "builder-verification list",
    "builder-verification show",
    "builder-verification artifact",
    "builder-verification validate",
)


# Which base record each synthesized name inherited its authority from. A command that holds
# authority *by inheritance* is exactly the thing a reader of the policy snapshot needs to be told.
#
# Every one of these 99 inherits from a command group: a parent acquires subcommands precisely by
# having them, so every parent in this map is structurally a group. The earlier count of 34 came
# from a transcribed list of group names that had drifted from the registry. The number was never
# the point -- what matters is that a group's classification describes the group, and copying it
# onto a subcommand states something about the subcommand that nobody checked.
_SYNTHESIZED_PARENTS: dict[str, str] = {}


def _generate_extra_records(base_registry: tuple[CommandAuthorityRecord, ...]) -> list[CommandAuthorityRecord]:
    """Clone the nearest declared ancestor for each command nobody declared.

    Parentage is by word prefix. It used to be by string prefix, which made
    `builder-goose validate-command-proposal` inherit from the leaf `builder-goose validate` instead
    of from the `builder-goose` group -- the two happen to be classified identically, so the bug
    never showed, but the mechanism was assigning authority on a substring match.

    The clone records that its authority is inherited. Nothing else in the record can say so: a copy
    is indistinguishable from a declaration once the copy is made.
    """
    extra_records = []
    for name in _EXTRA_COMMAND_NAMES:
        best_parent = None
        for r in base_registry:
            if is_token_prefix(r.name, name) and (
                best_parent is None or len(command_name_words(r.name)) > len(command_name_words(best_parent.name))
            ):
                best_parent = r
        if best_parent:
            extra_records.append(
                replace(best_parent, name=name, authority_is_inherited=True, inherited_from=best_parent.name)
            )
            _SYNTHESIZED_PARENTS[name] = best_parent.name
    return extra_records


COMMAND_AUTHORITY_REGISTRY = COMMAND_AUTHORITY_REGISTRY + tuple(_generate_extra_records(COMMAND_AUTHORITY_REGISTRY))


def get_all_records() -> tuple[CommandAuthorityRecord, ...]:
    """Return all registered CommandAuthorityRecord instances."""
    return COMMAND_AUTHORITY_REGISTRY


def get_command_record(name: str) -> CommandAuthorityRecord | None:
    """Find a record by its exact name."""
    for record in COMMAND_AUTHORITY_REGISTRY:
        if record.name == name:
            return record
    return None


def validate_registry_invariants() -> list[str]:
    """Validate all registry constraints and return a list of error strings if any fail."""
    errors = []
    for r in COMMAND_AUTHORITY_REGISTRY:
        # Tier check
        if r.tier not in VALID_TIERS:
            errors.append(f"Record '{r.name}' has invalid tier '{r.tier}'")

        # Promotion state check
        if r.promotion_state not in VALID_PROMOTION_STATES:
            errors.append(f"Record '{r.name}' has invalid promotion state '{r.promotion_state}'")

        # Approval mode check
        if r.approval_mode not in VALID_APPROVAL_MODES:
            errors.append(f"Record '{r.name}' has invalid approval mode '{r.approval_mode}'")

        # Missing required string check
        if not r.runtime_boundary.strip():
            errors.append(f"Record '{r.name}' is missing runtime boundary description")
        if not r.write_boundary.strip():
            errors.append(f"Record '{r.name}' is missing write boundary description")
        if not r.output_behavior.strip():
            errors.append(f"Record '{r.name}' is missing output behavior description")
        if not r.failure_mode.strip():
            errors.append(f"Record '{r.name}' is missing failure mode description")
        if not r.approval_boundary.strip():
            errors.append(f"Record '{r.name}' is missing approval boundary description")

        # Human approval requirements
        has_authority_flag = (
            r.allows_runtime_start
            or r.allows_process_control
            or r.allows_model_execution
            or r.allows_shell_execution
            or r.allows_source_writes
            or r.allows_external_tool_invocation
        )
        if has_authority_flag:
            if r.approval_mode == MODE_NONE:
                errors.append(f"Record '{r.name}' has authority flags enabled but approval mode is 'none'")

        # Tier 0 constraints
        if r.tier == TIER_0:
            has_risky = (
                r.allows_runtime_start
                or r.allows_process_control
                or r.allows_model_execution
                or r.allows_shell_execution
                or r.allows_source_writes
                or r.allows_memory_mutation
                or r.allows_git_mutation
                or r.allows_artifact_writes
                or r.allows_state_writes
                or r.allows_external_tool_invocation
            )
            if has_risky:
                errors.append(f"Tier 0 record '{r.name}' claims forbidden execution/mutation authority")

        # Tier 1 constraints
        if r.tier == TIER_1:
            has_forbidden_tier1 = (
                r.allows_runtime_start
                or r.allows_process_control
                or r.allows_model_execution
                or r.allows_shell_execution
                or r.allows_source_writes
                or r.allows_memory_mutation
                or r.allows_git_mutation
                or r.allows_state_writes
                or r.allows_external_tool_invocation
            )
            if has_forbidden_tier1:
                errors.append(f"Tier 1 record '{r.name}' claims forbidden execution/mutation authority")

        # At every tier, not only Tier 0 and Tier 1. No record has ever claimed it, every governed
        # platform bundle asserts `memory_mutation: DISABLED`, and the B8 memory lane writes memory
        # *artifacts* under `allows_artifact_writes` instead. Forbidding it only at the tiers that
        # forbid everything left the claim resting on a test in another file; a Tier 2 or Tier 3
        # record could have claimed it and been read as a promotion candidate.
        if r.allows_memory_mutation:
            errors.append(f"Record '{r.name}' claims `allows_memory_mutation`, which no record may claim at any tier")

        errors.extend(inheritance_errors(r))

        # Contradiction check: write boundary text vs write flags
        wb_lower = r.write_boundary.lower()
        has_any_write = r.allows_source_writes or r.allows_artifact_writes or r.allows_state_writes
        if not has_any_write:
            # Should not claim active writes in description
            if (
                "write" in wb_lower
                and "no " not in wb_lower
                and "not " not in wb_lower
                and "without " not in wb_lower
                and "read-only" not in wb_lower
            ):
                errors.append(f"Record '{r.name}' write boundary text describes writes but no write flags are set")
        else:
            # Should not say "no changes" or "no modifications"
            if "no changes" in wb_lower or "no modifications" in wb_lower or "no write" in wb_lower:
                errors.append(
                    f"Record '{r.name}' write flags are enabled but write boundary text claims no writes/changes"
                )

        # Conflation check
        for field_val in (
            r.name,
            r.entrypoint,
            r.tier,
            r.promotion_state,
            r.runtime_boundary,
            r.write_boundary,
            r.approval_boundary,
            r.output_behavior,
            r.failure_mode,
            r.notes,
        ):
            if "CORE builder-II" in field_val or "CORE Builder-II" in field_val:
                errors.append(f"Record '{r.name}' contains forbidden framing 'CORE builder-II'")

    return errors


NO_CAPABILITIES = "—"


def _capabilities_cell(record: CommandAuthorityRecord) -> str:
    """Name every capability the record claims, or say plainly that it claims none.

    A column per flag would print eleven `No`s for `builder-goose start-readonly`, which hands the
    operator's terminal to a Goose runtime. Naming only what is set makes an authority-bearing row
    impossible to mistake for an inert one, and makes `—` mean what it says.
    """
    claimed = [flag.removeprefix("allows_") for flag in CAPABILITY_FLAGS if getattr(record, flag)]
    return ", ".join(f"`{name}`" for name in claimed) if claimed else NO_CAPABILITIES


def _registry_row(record: CommandAuthorityRecord) -> str:
    derivation = explain_assurance_for_record(record)
    return (
        f"| `{record.name}` | {record.tier} | `{record.promotion_state}` | {record.runtime_boundary} "
        f"| {record.write_boundary} | `{record.approval_mode}` | {record.approval_boundary} "
        f"| {_capabilities_cell(record)} | `{derivation.state}` | {derivation.because} |"
    )


def render_registry_markdown_table() -> str:
    """Render the directly-declared records: what each command may do, and how assured it is.

    This table used to carry five boolean columns -- `Allows Shell`, `Process Control`,
    `Allows Writes`, `Artifact Writes`, `State Writes` -- against a record holding eleven capability
    flags. Eight of the eleven decide the assurance state. Five of those eight had no column, so 14
    rows printed five `No`s while carrying real authority: `builder capabilities` reaches a live model
    provider and printed as five `No`s. Two of the five columns that *were* printed
    (`Artifact Writes`, `State Writes`) move no assurance state at all.

    `builder-platform audit-docs` could never catch this. It detects a doc that overstates a
    capability. This doc understated one, in the file whose whole job is to say what each command is
    permitted to do.
    """
    lines = [
        "| Command Name | Tier | State | Runtime Boundary | Write Boundary | Approval Mode | Approval Boundary | Capabilities | Assurance | Assurance Derived From |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    lines.extend(_registry_row(r) for r in COMMAND_AUTHORITY_REGISTRY if r.name not in _EXTRA_COMMAND_NAMES)
    return "\n".join(lines)


def render_synthesized_markdown_table() -> str:
    """Render the records nobody wrote: cloned from the nearest declared ancestor of their name.

    Every one of these 99 inherits from a command group -- necessarily, since a record becomes a
    group by acquiring subcommands. So every row here states a classification that describes the
    parent and was never checked against the child. `builder-git-state artifact` really does run
    `git`; `builder-session validate` really does not. Both inherited their answer.

    Rather than guess which is which, `check_command_authority` refuses to certify a requested effect
    for any inherited record. The classification stays what it was -- there is no evidence to move
    it -- but it can no longer be *spent*. Declaring one of these directly is what promotes it.
    """
    lines = [
        "| Command Name | Inherits Authority From | Tier | State | Capabilities | Assurance | Assurance Derived From |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in _EXTRA_COMMAND_NAMES:
        record = get_command_record(name)
        if record is None:  # pragma: no cover - every synthesized name resolves to a parent today
            continue
        derivation = explain_assurance_for_record(record)
        parent = _SYNTHESIZED_PARENTS[name]
        group = " (command group)" if (p := get_command_record(parent)) is not None and p.is_command_group else ""
        lines.append(
            f"| `{name}` | `{parent}`{group} | {record.tier} | `{record.promotion_state}` "
            f"| {_capabilities_cell(record)} | `{derivation.state}` | {derivation.because} |"
        )
    return "\n".join(lines)


def render_command_authority_doc() -> str:
    """Render `docs/COMMAND_AUTHORITY.md` in full.

    The doc is hashed into every governed workflow event as `policy_snapshot_ref`. Rendering the
    whole file -- not just the table inside it -- lets the pin compare byte for byte, so no prose can
    be hand-added around a generated table and inherit its authority.

    Regenerate with:  uv run python -m builder_ii.command_authority > docs/COMMAND_AUTHORITY.md
    """
    declared = sum(1 for r in COMMAND_AUTHORITY_REGISTRY if r.name not in _EXTRA_COMMAND_NAMES)
    synthesized = len(COMMAND_AUTHORITY_REGISTRY) - declared
    inert = ", ".join(f"`{flag}`" for flag in ASSURANCE_INERT_FLAGS)
    return "\n".join(
        [
            "# Command Authority",
            "",
            "Generated from `builder_ii/command_authority.py`. Do not hand-edit: this file is hashed",
            "into every governed workflow event as `policy_snapshot_ref`, and",
            "`tests/test_command_authority.py` compares it byte for byte against its generator.",
            "",
            "```",
            "uv run python -m builder_ii.command_authority > docs/COMMAND_AUTHORITY.md",
            "```",
            "",
            "## Assurance states",
            "",
            "`Assurance` is authoritative for risk interpretation. It is derived from the record, never",
            "declared by it, and `Assurance Derived From` names the single fact that decided it.",
            "",
            render_assurance_definitions_markdown(),
            "",
            "## Capabilities",
            "",
            f"A record carries {len(CAPABILITY_FLAGS)} capability flags. The `Capabilities` column names exactly the ones",
            "it sets, so a row reading `—` claims none.",
            "",
            f"{len(ASSURANCE_DERIVING_FLAGS)} of the {len(CAPABILITY_FLAGS)} raise the assurance state. Only {inert} does not, and that",
            f"is correct rather than an oversight: `{_ASSURANCE_BASELINE}` already permits writing",
            "to the artifact store, so a command that writes only artifacts is passive by definition.",
            "",
            f"## Declared records ({declared})",
            "",
            "Authority written down, command by command.",
            "",
            render_registry_markdown_table(),
            "",
            f"## Synthesized records ({synthesized})",
            "",
            "Nobody declared these commands. Each one's authority is *inherited* — copied from the",
            "nearest declared ancestor of its name, on a word boundary. That ancestor is always a",
            f"command group, because a record becomes a group by acquiring subcommands: all {synthesized} of",
            "these rows state a classification that describes their parent and was never checked",
            "against them.",
            "",
            "So `check_command_authority` refuses to certify a requested effect for an inherited",
            "record, whatever its `Capabilities` column says. The classification below is reported,",
            "not spendable. Promoting one of these means declaring it directly — with evidence — not",
            "editing its parent.",
            "",
            render_synthesized_markdown_table(),
            "",
        ]
    )


if __name__ == "__main__":  # pragma: no cover - regeneration entrypoint, stdout only, writes nothing
    print(render_command_authority_doc(), end="")
