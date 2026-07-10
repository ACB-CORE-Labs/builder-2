from __future__ import annotations

from pathlib import Path

from builder_ii.assurance import (
    ASSURANCE_STATE_DEFINITIONS,
    ASSURANCE_STATES,
    SAFETY_CRITICAL_PROHIBITED,
    render_assurance_definitions_markdown,
)
from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY, assurance_state_for_record
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
    """The definition says no mapping derives it and no row carries it. Check, do not assume.

    A definition is a claim about the system. This one is checkable, so it is checked: if some
    future row or record ever derives SAFETY_CRITICAL_PROHIBITED, the sentence in `assurance.py`
    becomes false and this pin says so before a reader trusts it.
    """
    assert "No mapping derives it and no current row carries it" in ASSURANCE_STATE_DEFINITIONS[
        SAFETY_CRITICAL_PROHIBITED
    ]

    derived_from_rows = {assurance_state_for_row(row) for row in REQUIRED_CAPABILITY_ROWS}
    derived_from_records = {assurance_state_for_record(record) for record in COMMAND_AUTHORITY_REGISTRY}

    assert SAFETY_CRITICAL_PROHIBITED not in derived_from_rows
    assert SAFETY_CRITICAL_PROHIBITED not in derived_from_records
