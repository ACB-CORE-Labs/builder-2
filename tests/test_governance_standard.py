"""Coverage for the standard governance builder/validator (Jules draft reconcile)."""

from __future__ import annotations

from typing import Any

from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance


def test_validate_non_dict() -> None:
    for val in (None, "string", [1, 2, 3], True, 123):
        assert validate_standard_governance(val, "any_state") == ["governance must be an object"]


def test_build_and_validate_happy_path() -> None:
    state = "some_capability_state"
    gov = build_standard_governance(state)
    assert validate_standard_governance(gov, state) == []


def test_validate_capability_state_mismatch() -> None:
    gov = build_standard_governance("expected_state")
    errors = validate_standard_governance(gov, "different_state")
    assert "governance.capability_state must be different_state" in errors


def test_validate_rigid_boolean_values() -> None:
    gov = build_standard_governance("some_state")
    cases: list[tuple[str, Any, str]] = [
        ("artifact_is_authority", True, "governance.artifact_is_authority must be false or NOT_AUTHORIZED"),
        ("artifacts_are_authority", True, "governance.artifacts_are_authority must be false or NOT_AUTHORIZED"),
        ("executes_commands", True, "governance.executes_commands must be false or NOT_AUTHORIZED"),
        ("proof_of_capability_only", False, "governance.proof_of_capability_only must be true or NOT_AUTHORIZED"),
        ("runtime_executor", True, "governance.runtime_executor must be false or NOT_AUTHORIZED"),
    ]
    for field, bad_value, expected in cases:
        bad = dict(gov)
        bad[field] = bad_value
        errors = validate_standard_governance(bad, "some_state")
        assert expected in errors


def test_validate_core_workbench_coupling() -> None:
    gov = build_standard_governance("some_state")
    assert validate_standard_governance(dict(gov, core_workbench_coupling="NONE"), "some_state") == []
    errors = validate_standard_governance(dict(gov, core_workbench_coupling="COUPLED"), "some_state")
    assert "governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in errors


def test_validate_source_writes_exception() -> None:
    gov = build_standard_governance("some_state")
    allowed = dict(gov, source_writes="DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    assert validate_standard_governance(allowed, "some_state") == []
    errors = validate_standard_governance(dict(gov, source_writes="ENABLED"), "some_state")
    assert any("source_writes" in e for e in errors)
