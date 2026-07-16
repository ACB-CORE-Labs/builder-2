from __future__ import annotations

from typing import Literal

AssuranceState = Literal[
    "PASSIVE_ARTIFACT_VERIFIED",
    "LOCAL_STATE_MUTATION_VERIFIED",
    "READ_ONLY_RUNTIME_VERIFIED",
    "BOUNDED_EXECUTION_VERIFIED",
    "MUTATION_WITH_ROLLBACK_VERIFIED",
    "LIVE_PROVIDER_VERIFIED",
    "DEMO_ONLY_VERIFIED",
    "BLOCKED_BY_EVIDENCE",
    "SAFETY_CRITICAL_PROHIBITED",
]

PASSIVE_ARTIFACT_VERIFIED: AssuranceState = "PASSIVE_ARTIFACT_VERIFIED"
LOCAL_STATE_MUTATION_VERIFIED: AssuranceState = "LOCAL_STATE_MUTATION_VERIFIED"
READ_ONLY_RUNTIME_VERIFIED: AssuranceState = "READ_ONLY_RUNTIME_VERIFIED"
BOUNDED_EXECUTION_VERIFIED: AssuranceState = "BOUNDED_EXECUTION_VERIFIED"
MUTATION_WITH_ROLLBACK_VERIFIED: AssuranceState = "MUTATION_WITH_ROLLBACK_VERIFIED"
LIVE_PROVIDER_VERIFIED: AssuranceState = "LIVE_PROVIDER_VERIFIED"
DEMO_ONLY_VERIFIED: AssuranceState = "DEMO_ONLY_VERIFIED"
BLOCKED_BY_EVIDENCE: AssuranceState = "BLOCKED_BY_EVIDENCE"
SAFETY_CRITICAL_PROHIBITED: AssuranceState = "SAFETY_CRITICAL_PROHIBITED"

ASSURANCE_STATES: tuple[AssuranceState, ...] = (
    PASSIVE_ARTIFACT_VERIFIED,
    LOCAL_STATE_MUTATION_VERIFIED,
    READ_ONLY_RUNTIME_VERIFIED,
    BOUNDED_EXECUTION_VERIFIED,
    MUTATION_WITH_ROLLBACK_VERIFIED,
    LIVE_PROVIDER_VERIFIED,
    DEMO_ONLY_VERIFIED,
    BLOCKED_BY_EVIDENCE,
    SAFETY_CRITICAL_PROHIBITED,
)


# `docs/PLATFORM_COMPLETION_AUDIT.md` calls the assurance state "authoritative for risk
# interpretation". A field cannot be authoritative for risk in eight undefined words, and until now
# these eight were listed and never defined -- in this module, in that doc, or anywhere else.
#
# These definitions are written down from how the existing rows and command-authority records
# already use each state. They are a transcription of current truth, not new law: if a definition
# here would misdescribe a row that already carries the state, the definition is wrong, not the row.
# Each says what the capability *does*, so that classifying a new capability is a decision about
# behaviour rather than a search for the nearest-sounding label.
ASSURANCE_STATE_DEFINITIONS: dict[AssuranceState, str] = {
    PASSIVE_ARTIFACT_VERIFIED: (
        "Builds, validates, or reads governed artifacts and renders them. It starts no runtime, "
        "spawns no process, calls no provider, and writes nothing outside the artifact store."
    ),
    LOCAL_STATE_MUTATION_VERIFIED: (
        "Writes or deletes builder-II's own local state -- runtime markers, lockfiles, caches -- "
        "outside the artifact store and outside every target repository. It starts no runtime, "
        "spawns no process, and calls no provider. Nothing snapshots the write, so it is undone by "
        "re-establishing the state, never by a rollback."
    ),
    READ_ONLY_RUNTIME_VERIFIED: (
        "Starts, or hands the operator's terminal to, a runtime whose policy denies writes. The "
        "read-only boundary is enforced by that runtime's own preflight and postflight, never by "
        "the caller's intent."
    ),
    BOUNDED_EXECUTION_VERIFIED: (
        "Causes work to run -- a subprocess, an external tool, or a sealed backend -- inside a "
        "fixed, pre-approved envelope: fixed argv with shell=False or a digest-bound seal, an "
        "approval, and a digest-bound receipt. It attests the envelope of the invocation. It never "
        "attests the behaviour of the code that ran inside it."
    ),
    MUTATION_WITH_ROLLBACK_VERIFIED: (
        "Writes to the target repository's source tree or git state, and only behind an interactive "
        "digest-prefix approval, a required verification receipt, and a snapshot that makes the "
        "write reversible."
    ),
    LIVE_PROVIDER_VERIFIED: (
        "Reaches a live model provider over the network. Its output is not deterministic and is "
        "never, on its own, evidence."
    ),
    DEMO_ONLY_VERIFIED: (
        "Exercised end to end only inside the governed demo loop, against a synthetic target. A "
        "demo pass is not evidence for the corresponding real lane."
    ),
    BLOCKED_BY_EVIDENCE: (
        "No claim is supported: the capability is not operationally verified, or its command "
        "surface is a forbidden or unpromoted record. This is the state that absence takes. It is "
        "never a default for something that runs."
    ),
    SAFETY_CRITICAL_PROHIBITED: (
        "Names a capability whose promotion is refused regardless of the evidence offered for it. "
        "`allows_memory_mutation` is the only one, and `validate_registry_invariants` rejects it at "
        "every tier, so the state is derivable but no row or record carries it: a record claiming "
        "the flag is refused before anything can read its state. Unlike BLOCKED_BY_EVIDENCE, no "
        "evidence unblocks it."
    ),
}


def render_assurance_definitions_markdown() -> str:
    """Render the vocabulary for docs. The doc mirrors this; a pin keeps them identical."""
    return "\n".join(f"- `{state}` — {ASSURANCE_STATE_DEFINITIONS[state]}" for state in ASSURANCE_STATES)


def is_assurance_state(value: object) -> bool:
    return value in ASSURANCE_STATES
