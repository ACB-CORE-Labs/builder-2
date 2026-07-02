import os
import re
import tomllib
from pathlib import Path
import pytest

from builder_ii.command_authority import (
    COMMAND_AUTHORITY_REGISTRY,
    READONLY_TUI_COMMAND_GROUPS,
    READONLY_TUI_COMMANDS,
    REQUIRED_SUBCOMMANDS,
    TIER_0,
    TIER_1,
    MODE_NONE,
    CommandAuthorityRecord,
    CommandAuthorityError,
    check_command_authority,
    enforce_command_authority,
    validate_registry_invariants,
    render_registry_markdown_table,
)


def _get_project_root() -> Path:
    return Path(__file__).parent.parent


def test_registry_internal_invariants():
    """Verify registry conforms to all specified safety constraints."""
    errors = validate_registry_invariants()
    assert not errors, f"Registry invariants violated: {errors}"


def test_pyproject_scripts_fully_covered():
    """Ensure every script in pyproject.toml is represented in the registry."""
    root = _get_project_root()
    pyproject_path = root / "pyproject.toml"
    assert pyproject_path.exists(), f"Could not find pyproject.toml at {pyproject_path}"

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    scripts = data.get("project", {}).get("scripts", {})
    assert scripts, "No scripts found in pyproject.toml project.scripts"

    registered_names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}

    for script_name in scripts.keys():
        # Verify that either the exact script name is registered,
        # or there is at least one subcommand record starting with it.
        has_match = any(
            name == script_name or name.startswith(f"{script_name} ")
            for name in registered_names
        )
        assert has_match, f"Script '{script_name}' from pyproject.toml is missing from registry"


def test_root_builder_subcommands_fully_covered():
    """Ensure every root builder CLI command decorator has an explicit registry row."""
    root = _get_project_root()
    cli_source = (root / "builder_ii" / "cli.py").read_text(encoding="utf-8")
    root_commands = {
        f"builder {match.group(1)}"
        for match in re.finditer(r"@app\.command\(\"([^\"]+)\"\)", cli_source)
    }
    registered_names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}

    assert root_commands
    assert root_commands <= registered_names


def test_required_subcommands_fully_covered():
    """Ensure all required subcommands are explicitly present in the registry."""
    registered_names = {r.name for r in COMMAND_AUTHORITY_REGISTRY}
    for sub in REQUIRED_SUBCOMMANDS:
        assert sub in registered_names, f"Required subcommand '{sub}' is missing from registry"


def test_docs_contain_all_commands_and_table():
    """Verify that docs/COMMAND_AUTHORITY.md documents every command and contains the exact table."""
    root = _get_project_root()
    doc_path = root / "docs" / "COMMAND_AUTHORITY.md"
    assert doc_path.exists(), f"docs/COMMAND_AUTHORITY.md does not exist"

    doc_content = doc_path.read_text(encoding="utf-8")

    # Verify every registered command name is mentioned in the docs
    for r in COMMAND_AUTHORITY_REGISTRY:
        assert f"`{r.name}`" in doc_content, f"Command '{r.name}' is not documented in docs/COMMAND_AUTHORITY.md"

    # Verify the table exists in the doc
    expected_table = render_registry_markdown_table()
    assert expected_table in doc_content, "The table in docs/COMMAND_AUTHORITY.md does not match the rendered table from registry"


def test_no_forbidden_identity_framing():
    """Ensure no 'CORE builder-II' conflation in pyproject, registry, or docs."""
    root = _get_project_root()
    forbidden_terms = ["CORE builder-II", "CORE Builder-II", "core builder-ii"]

    # Scan python registry file
    registry_file = root / "builder_ii" / "command_authority.py"
    reg_content = registry_file.read_text(encoding="utf-8")
    for term in forbidden_terms:
        occurrences = reg_content.count(term)
        assert occurrences <= 2, f"Registry source file contains forbidden framing '{term}'"

    # Scan doc file
    doc_path = root / "docs" / "COMMAND_AUTHORITY.md"
    doc_content = doc_path.read_text(encoding="utf-8")
    for term in forbidden_terms:
        assert term not in doc_content, f"Doc file contains forbidden framing '{term}'"


def test_adversarial_validation_violations():
    """Test that validate_registry_invariants detects invalid record mutations."""
    # 1. Tier 0 command claiming authority
    bad_record_1 = CommandAuthorityRecord(
        name="builder-test-adversarial-1",
        entrypoint="builder_ii.cli:app",
        tier=TIER_0,
        promotion_state="artifact_only",
        runtime_boundary="No runtime",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None",
        output_behavior="Stdout",
        failure_mode="Exit",
        notes="None",
        allows_shell_execution=True,  # Violation!
    )

    # 2. Authority flag without approval mode
    bad_record_2 = CommandAuthorityRecord(
        name="builder-test-adversarial-2",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state="validation_only",
        runtime_boundary="No runtime",
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,  # Violation!
        approval_boundary="None",
        output_behavior="Stdout",
        failure_mode="Exit",
        notes="None",
        allows_runtime_start=True,  # Violates Tier 1 check and needs approval mode
    )

    # 3. Missing documentation fields
    bad_record_3 = CommandAuthorityRecord(
        name="builder-test-adversarial-3",
        entrypoint="builder_ii.cli:app",
        tier=TIER_0,
        promotion_state="artifact_only",
        runtime_boundary="",  # Violation!
        write_boundary="No changes to workspace.",
        approval_mode=MODE_NONE,
        approval_boundary="None",
        output_behavior="Stdout",
        failure_mode="Exit",
        notes="None",
    )

    # 4. Contradictory write boundary text
    bad_record_4 = CommandAuthorityRecord(
        name="builder-test-adversarial-4",
        entrypoint="builder_ii.cli:app",
        tier=TIER_1,
        promotion_state="artifact_only",
        runtime_boundary="No runtime",
        write_boundary="No changes to workspace.",  # Says no changes
        approval_mode=MODE_NONE,
        approval_boundary="None",
        output_behavior="Stdout",
        failure_mode="Exit",
        notes="None",
        allows_artifact_writes=True,  # Violation (contradiction)!
    )

    from builder_ii import command_authority
    original_registry = command_authority.COMMAND_AUTHORITY_REGISTRY

    try:
        command_authority.COMMAND_AUTHORITY_REGISTRY = (bad_record_1,)
        errs = validate_registry_invariants()
        assert any("claims forbidden execution/mutation authority" in e for e in errs)

        command_authority.COMMAND_AUTHORITY_REGISTRY = (bad_record_2,)
        errs = validate_registry_invariants()
        assert any("claims forbidden execution/mutation authority" in e for e in errs)

        command_authority.COMMAND_AUTHORITY_REGISTRY = (bad_record_3,)
        errs = validate_registry_invariants()
        assert any("missing runtime boundary description" in e for e in errs)

        command_authority.COMMAND_AUTHORITY_REGISTRY = (bad_record_4,)
        errs = validate_registry_invariants()
        assert any("write flags are enabled but write boundary text claims no writes" in e for e in errs)

    finally:
        command_authority.COMMAND_AUTHORITY_REGISTRY = original_registry


def test_tier_0_and_tier_1_boundaries():
    """Explicitly verify that Tier 0 and Tier 1 commands do not cross runtime/mutation boundaries."""
    for r in COMMAND_AUTHORITY_REGISTRY:
        if r.tier == TIER_0:
            # Cannot write artifacts, cannot write state, cannot claim execution
            assert not r.allows_artifact_writes, f"{r.name} (Tier 0) cannot write artifacts"
            assert not r.allows_state_writes, f"{r.name} (Tier 0) cannot write state"
            assert not r.allows_runtime_start, f"{r.name} (Tier 0) cannot start runtime"
            assert not r.allows_process_control, f"{r.name} (Tier 0) cannot control processes"
            assert not r.allows_model_execution, f"{r.name} (Tier 0) cannot execute models"
            assert not r.allows_shell_execution, f"{r.name} (Tier 0) cannot execute shell"
            assert not r.allows_source_writes, f"{r.name} (Tier 0) cannot write source"
            assert not r.allows_memory_mutation, f"{r.name} (Tier 0) cannot mutate memory"
            assert not r.allows_git_mutation, f"{r.name} (Tier 0) cannot mutate git"
            assert not r.allows_external_tool_invocation, f"{r.name} (Tier 0) cannot invoke external tools"

        elif r.tier == TIER_1:
            # May artifact-write, but absolutely nothing else
            assert not r.allows_state_writes, f"{r.name} (Tier 1) cannot write state"
            assert not r.allows_runtime_start, f"{r.name} (Tier 1) cannot start runtime"
            assert not r.allows_process_control, f"{r.name} (Tier 1) cannot control processes"
            assert not r.allows_model_execution, f"{r.name} (Tier 1) cannot execute models"
            assert not r.allows_shell_execution, f"{r.name} (Tier 1) cannot execute shell"
            assert not r.allows_source_writes, f"{r.name} (Tier 1) cannot write source"
            assert not r.allows_memory_mutation, f"{r.name} (Tier 1) cannot mutate memory"
            assert not r.allows_git_mutation, f"{r.name} (Tier 1) cannot mutate git"
            assert not r.allows_external_tool_invocation, f"{r.name} (Tier 1) cannot invoke external tools"


def test_readonly_tui_surfaces_are_registered_tier0_observers() -> None:
    registered = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}
    for name in (*READONLY_TUI_COMMAND_GROUPS, *READONLY_TUI_COMMANDS):
        assert name in registered, f"{name} missing from COMMAND_AUTHORITY_REGISTRY"
        record = registered[name]
        assert record.tier == TIER_0
        assert record.approval_mode == MODE_NONE
        assert not record.allows_runtime_start
        assert not record.allows_process_control
        assert not record.allows_model_execution
        assert not record.allows_shell_execution
        assert not record.allows_source_writes
        assert not record.allows_memory_mutation
        assert not record.allows_git_mutation
        assert not record.allows_artifact_writes
        assert not record.allows_state_writes
        assert not record.allows_readonly_subprocess
        assert not record.allows_external_tool_invocation

    for name in READONLY_TUI_COMMANDS:
        assert name in REQUIRED_SUBCOMMANDS


def test_standalone_call_registered_in_authority() -> None:
    """builder-model standalone-call must be registered as Tier 3, declare model execution
    and artifact writes, and be in REQUIRED_SUBCOMMANDS."""
    from builder_ii.command_authority import (
        COMMAND_AUTHORITY_REGISTRY,
        REQUIRED_SUBCOMMANDS,
        TIER_3,
    )

    name = "builder-model standalone-call"
    registered = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}

    assert name in registered, f"'{name}' is missing from COMMAND_AUTHORITY_REGISTRY"
    record = registered[name]

    assert record.tier == TIER_3, f"Expected Tier 3, got tier={record.tier}"
    assert record.allows_model_execution, f"{name} must declare allows_model_execution=True"
    assert record.allows_artifact_writes, f"{name} must declare allows_artifact_writes=True"
    assert name in REQUIRED_SUBCOMMANDS, f"'{name}' must be in REQUIRED_SUBCOMMANDS"


def test_enforce_command_authority_fails_closed_for_unknown_command() -> None:
    decision = check_command_authority("builder-missing command")
    assert decision.allowed is False
    assert "not registered" in decision.reasons[0]
    with pytest.raises(CommandAuthorityError):
        enforce_command_authority("builder-missing command")


def test_enforce_command_authority_rejects_unclassified_effect() -> None:
    decision = check_command_authority("builder ask", requested_effects=("patch_application",))
    assert decision.allowed is False
    assert any("patch_application" in reason for reason in decision.reasons)


def test_enforce_command_authority_rejects_safety_critical_claim() -> None:
    decision = check_command_authority("builder ask", safety_critical_claim=True)
    assert decision.allowed is False
    assert decision.assurance_state == "SAFETY_CRITICAL_PROHIBITED"


def test_enforce_command_authority_allows_classified_effect() -> None:
    decision = enforce_command_authority("builder ask", requested_effects=("model_execution", "artifact_write"))
    assert decision.allowed is True
    assert decision.assurance_state == "LIVE_PROVIDER_VERIFIED"


def test_process_control_requires_explicit_process_control_flag() -> None:
    denied = check_command_authority("builder-runtime clear-marker", requested_effects=("process_control",))
    assert denied.allowed is False
    assert any("process_control" in reason for reason in denied.reasons)

    allowed = enforce_command_authority(
        "builder-runtime stop",
        requested_effects=("process_control", "state_write", "readonly_subprocess"),
    )
    assert allowed.allowed is True
    assert allowed.assurance_state == "BOUNDED_EXECUTION_VERIFIED"


def test_builder_memory_commands_are_registered_as_tier1_surfaces() -> None:
    registered = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}

    root = registered["builder-memory"]
    assert root.tier == TIER_1
    assert not root.allows_artifact_writes
    assert root.approval_mode == MODE_NONE

    for name in (
        "builder-memory atom",
        "builder-memory index",
        "builder-memory search",
        "builder-memory reconstruct",
    ):
        record = registered[name]
        assert record.tier == TIER_1
        assert record.allows_artifact_writes is True
        assert name in REQUIRED_SUBCOMMANDS

    for name in (
        "builder-memory validate-atom",
        "builder-memory validate-index",
        "builder-memory validate-reconstruction",
        "builder-memory validate-search-result",
    ):
        record = registered[name]
        assert record.tier == TIER_1
        assert record.allows_artifact_writes is False
        assert name in REQUIRED_SUBCOMMANDS


def test_runtime_gate_allows_passive_registered_command_without_hitl() -> None:
    from builder_ii.command_authority import enforce_command_authority

    decision = enforce_command_authority("builder-targets list", requested_effects=())

    assert decision.allowed is True
    assert decision.to_evidence()["allowed"] is True
    assert decision.to_evidence()["fail_closed"] is False


def test_runtime_gate_denies_unknown_command_fail_closed() -> None:
    from builder_ii.command_authority import check_command_authority, enforce_command_authority, CommandAuthorityError

    with pytest.raises(CommandAuthorityError) as exc_info:
        enforce_command_authority("builder-unknown mutate", requested_effects=("source_writes",))
    assert "not registered" in str(exc_info.value)

    decision = check_command_authority("builder-unknown mutate", requested_effects=("source_writes",))
    assert decision.allowed is False
    assert "not registered" in decision.reason
    assert decision.to_evidence()["fail_closed"] is True


def test_runtime_gate_denies_over_authority_effect() -> None:
    from builder_ii.command_authority import check_command_authority, enforce_command_authority, CommandAuthorityError

    with pytest.raises(CommandAuthorityError) as exc_info:
        enforce_command_authority("builder-targets list", requested_effects=("source_writes",))
    assert "not classified" in str(exc_info.value)

    decision = check_command_authority("builder-targets list", requested_effects=("source_writes",))
    assert decision.allowed is False
    assert "not classified" in decision.reason


def test_runtime_gate_requires_hitl_for_run_approved() -> None:
    from builder_ii.command_authority import check_command_authority, enforce_command_authority, CommandAuthorityError

    with pytest.raises(CommandAuthorityError) as exc_info:
        enforce_command_authority(
            "builder-verify run-approved",
            requested_effects=("artifact_write", "readonly_subprocess"),
            hitl_bound=False,
        )
    assert "HITL" in str(exc_info.value)

    decision = check_command_authority(
        "builder-verify run-approved",
        requested_effects=("artifact_write", "readonly_subprocess"),
        hitl_bound=False,
    )
    assert decision.allowed is False
    assert "HITL" in decision.reason


def test_command_authority_compatibility_hitl_bound() -> None:
    from builder_ii.command_authority import check_command_authority, enforce_command_authority, CommandAuthorityError

    # 1. Denied with no approval_ref and no hitl_bound
    with pytest.raises(CommandAuthorityError) as exc:
        enforce_command_authority(
            "builder-verify run-approved",
            requested_effects=("artifact_write", "readonly_subprocess"),
        )
    assert "HITL" in str(exc.value)

    # 2. Denied with hitl_bound=False
    with pytest.raises(CommandAuthorityError) as exc:
        enforce_command_authority(
            "builder-verify run-approved",
            requested_effects=("artifact_write", "readonly_subprocess"),
            hitl_bound=False,
        )
    assert "HITL" in str(exc.value)

    # 3. Allowed with hitl_bound=True
    decision = enforce_command_authority(
        "builder-verify run-approved",
        requested_effects=("artifact_write", "readonly_subprocess"),
        hitl_bound=True,
    )
    assert decision.allowed is True

    # 4. Allowed with approval_ref
    decision = enforce_command_authority(
        "builder-verify run-approved",
        requested_effects=("artifact_write", "readonly_subprocess"),
        approval_ref="approval-123",
    )
    assert decision.allowed is True

    # 5. Unknown commands still fail closed
    with pytest.raises(CommandAuthorityError) as exc:
        enforce_command_authority("builder-missing-command")
    assert "not registered" in str(exc.value)
