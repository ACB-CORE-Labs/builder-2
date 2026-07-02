from __future__ import annotations

from builder_ii.command_authority import (
    COMMAND_AUTHORITY_REGISTRY,
    REQUIRED_SUBCOMMANDS,
    TIER_1,
    validate_registry_invariants,
)


def test_onboarding_commands_registered():
    records = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}
    for cmd in (
        "builder onboarding",
        "builder-setup init",
        "builder-setup wizard",
        "builder-setup validate-onboarding-intent",
    ):
        assert cmd in REQUIRED_SUBCOMMANDS, f"{cmd} missing from REQUIRED_SUBCOMMANDS"
        assert cmd in records, f"{cmd} missing from COMMAND_AUTHORITY_REGISTRY"
        record = records[cmd]
        assert record.tier == TIER_1


def test_registry_invariants_pass():
    errors = validate_registry_invariants()
    assert not errors, f"Registry invariants violated: {errors}"


def test_no_authority_overpromotion():
    for record in COMMAND_AUTHORITY_REGISTRY:
        if record.name in (
            "builder onboarding",
            "builder-setup init",
            "builder-setup wizard",
            "builder-setup validate-onboarding-intent",
        ):
            assert not getattr(record, "allows_external_tool_invocation", False)
            assert not getattr(record, "allows_model_execution", False)
            assert not getattr(record, "allows_source_writes", False)
