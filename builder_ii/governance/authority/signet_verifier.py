"""Assurance lattice derivation — reviewable risk seal on each authority decision.

Named signet_verifier for packaging: maps flags/promotion state to AssuranceState.
This is NOT a separate cryptographic primitive; digests live on artifacts elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, cast

from builder_ii.governance.authority.assurance import (
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
)
from builder_ii.governance.authority.authority_registry import (
    CAPABILITY_FLAGS,
    CommandAuthorityRecord,
)
from builder_ii.governance.authority.tier_definitions import (
    MODE_EXPLICIT_OPERATOR_INVOCATION,
    STATE_ENABLED,
    STATE_FORBIDDEN_UNPROMOTED,
    STATE_READ_ONLY_RUNTIME_CANDIDATE,
    TIER_2,
    TIER_4,
)


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
