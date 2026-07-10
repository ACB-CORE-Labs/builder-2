from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from builder_ii.assurance import (
    ASSURANCE_STATE_DEFINITIONS,
    ASSURANCE_STATES,
    LOCAL_STATE_MUTATION_VERIFIED,
    SAFETY_CRITICAL_PROHIBITED,
    render_assurance_definitions_markdown,
)
from builder_ii.command_authority import (
    COMMAND_AUTHORITY_REGISTRY,
    TIER_4,
    _assurance_probe,
    assurance_state_for_record,
    explain_assurance_for_record,
)
from builder_ii.platform_completion_audit import REQUIRED_CAPABILITY_ROWS, assurance_state_for_row

_DOC = Path(__file__).resolve().parent.parent / "docs" / "PLATFORM_COMPLETION_AUDIT.md"


def test_every_assurance_state_is_defined() -> None:
    """The field the docs call authoritative for risk cannot be eight undefined words."""
    assert tuple(ASSURANCE_STATE_DEFINITIONS) == ASSURANCE_STATES
    for state, definition in ASSURANCE_STATE_DEFINITIONS.items():
        assert definition.strip(), f"{state} has no definition"


def test_the_audit_doc_mirrors_the_vocabulary_verbatim() -> None:
    """Generated, never hand-written -- and a hand-edit must break the pin, not survive it."""
    rendered = render_assurance_definitions_markdown()
    doc = _DOC.read_text(encoding="utf-8")

    assert rendered in doc, "docs/PLATFORM_COMPLETION_AUDIT.md has drifted from ASSURANCE_STATE_DEFINITIONS"

    mutated = doc.replace(
        "It attests the envelope of the invocation.",
        "It attests that the code which ran was safe.",
    )
    assert mutated != doc, "the sentence this pin defends is no longer in the doc"
    assert rendered not in mutated, "a hand-edit to a definition must fail this pin"


def test_safety_critical_prohibited_is_carried_by_nothing_exactly_as_its_definition_claims() -> None:
    """The definition says the state is derivable but nothing carries it. Check, do not assume.

    A definition is a claim about the system. This one is checkable, so it is checked. The earlier
    sentence read "No mapping derives it" -- true then, and it would have gone quietly false the
    moment `allows_memory_mutation` was routed here, because this pin only ever looked at rows and
    records. A definition that describes the mapping must be checked against the mapping.
    """
    definition = ASSURANCE_STATE_DEFINITIONS[SAFETY_CRITICAL_PROHIBITED]
    assert "no row or record carries it" in definition
    assert "refused regardless of the evidence" in definition

    derivable = explain_assurance_for_record(_assurance_probe(allows_memory_mutation=True)).state
    assert derivable == SAFETY_CRITICAL_PROHIBITED, "the definition says the state is derivable"

    derived_from_rows = {assurance_state_for_row(row) for row in REQUIRED_CAPABILITY_ROWS}
    derived_from_records = {assurance_state_for_record(record) for record in COMMAND_AUTHORITY_REGISTRY}

    assert SAFETY_CRITICAL_PROHIBITED not in derived_from_rows
    assert SAFETY_CRITICAL_PROHIBITED not in derived_from_records


def test_the_refused_capability_is_never_given_the_safest_label() -> None:
    """`allows_memory_mutation` must not derive a state that promises absence of danger.

    `LOCAL_STATE_MUTATION_VERIFIED` ends "starts no runtime, spawns no process, and calls no
    provider" -- a positive safety claim. Every other place in the codebase that classifies this flag
    buckets it with `runtime_start`, `process_control`, `shell_execution`, `model_execution`. Giving
    the one capability builder-II refuses to promote the safest label available is the same defect
    that made `builder-runtime clear-marker` read as passive, one level up.
    """
    memory = explain_assurance_for_record(_assurance_probe(allows_memory_mutation=True))
    state_writes = explain_assurance_for_record(_assurance_probe(allows_state_writes=True))

    assert memory.state == SAFETY_CRITICAL_PROHIBITED
    assert state_writes.state == LOCAL_STATE_MUTATION_VERIFIED
    assert memory.state != state_writes.state, "two different claims must not share one state"

    safe_promise = ASSURANCE_STATE_DEFINITIONS[LOCAL_STATE_MUTATION_VERIFIED]
    assert "calls no provider" in safe_promise, "this pin is vacuous if the state stops promising it"


def test_a_refused_capability_dominates_every_other_signal_the_record_offers() -> None:
    """Placed above tier and promotion state: no evidence, and no tier, unblocks a refusal."""
    tier_4 = _assurance_probe(allows_memory_mutation=True)
    assert explain_assurance_for_record(replace(tier_4, tier=TIER_4)).state == SAFETY_CRITICAL_PROHIBITED
    assert explain_assurance_for_record(replace(tier_4, name="demo probe")).state == SAFETY_CRITICAL_PROHIBITED
    assert explain_assurance_for_record(replace(tier_4, allows_source_writes=True)).state == SAFETY_CRITICAL_PROHIBITED


def test_local_state_mutation_is_carried_by_a_real_command() -> None:
    """A state nothing derives is decoration. `SAFETY_CRITICAL_PROHIBITED` says so of itself.

    `LOCAL_STATE_MUTATION_VERIFIED` was added because `builder-runtime clear-marker` derived
    `PASSIVE_ARTIFACT_VERIFIED` -- "writes nothing outside the artifact store" -- while deleting the
    runtime marker. If a future change makes this state unreachable, the lattice has grown a word for
    nothing, and this pin says so.
    """
    carriers = [r.name for r in COMMAND_AUTHORITY_REGISTRY if assurance_state_for_record(r) == LOCAL_STATE_MUTATION_VERIFIED]
    assert "builder-runtime clear-marker" in carriers, f"nothing derives {LOCAL_STATE_MUTATION_VERIFIED}: {carriers}"

    definition = ASSURANCE_STATE_DEFINITIONS[LOCAL_STATE_MUTATION_VERIFIED]
    assert "outside the artifact store" in definition
    assert "spawns no process" in definition, "a local-state write that spawns a process is bounded execution"
