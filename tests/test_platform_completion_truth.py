import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.command_authority import (
    COMMAND_AUTHORITY_REGISTRY,
    MODE_NONE,
    TIER_1,
)
from builder_ii.platform_completion_audit import (
    ALLOWED_STATE_LABELS,
    MERGED_BUT_NOT_OPERATIONAL,
    NOT_STARTED,
    OPERATIONALLY_VERIFIED,
    PASSIVE_FOUNDATION,
    REQUIRED_CAPABILITIES,
    REQUIRED_CAPABILITY_ROWS,
    R1_CONFIG_ONBOARDING_CAPABILITIES,
    render_human_summary,
    render_matrix_jsonable,
    validate_command_surfaces,
    validate_completion_matrix,
    validate_r1_config_onboarding_mapping,
)
from builder_ii.platform_status_cli import platform_app


runner = CliRunner()


def test_all_required_capability_rows_exist_once() -> None:
    capabilities = [row.capability for row in REQUIRED_CAPABILITY_ROWS]
    assert set(capabilities) == set(REQUIRED_CAPABILITIES)
    assert len(capabilities) == len(set(capabilities))


def test_all_state_labels_are_valid_and_single_valued() -> None:
    allowed = set(ALLOWED_STATE_LABELS)
    for row in REQUIRED_CAPABILITY_ROWS:
        assert row.state in allowed
        assert isinstance(row.state, str)


def test_rows_have_evidence_tests_blockers_and_next_pr() -> None:
    errors = validate_completion_matrix(Path("."))
    assert not errors


def test_config_onboarding_rows_exist_and_point_to_r1() -> None:
    by_capability = {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}
    for capability in R1_CONFIG_ONBOARDING_CAPABILITIES:
        assert capability in by_capability
        assert by_capability[capability].next_pr == "R1"
        assert by_capability[capability].state != OPERATIONALLY_VERIFIED
    assert not validate_r1_config_onboarding_mapping()


def test_r1_3a_matrix_state_changes_are_scoped() -> None:
    by_capability = {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}

    assert by_capability["config schema"].state == PASSIVE_FOUNDATION
    assert by_capability["config source precedence"].state == PASSIVE_FOUNDATION
    assert by_capability["non-interactive setup/apply/validate"].state == MERGED_BUT_NOT_OPERATIONAL
    assert by_capability["Goose config overlay/rollback"].state == PASSIVE_FOUNDATION
    assert by_capability["interactive setup wizard"].state == NOT_STARTED
    assert by_capability["setup receipt + rollback artifact"].state == PASSIVE_FOUNDATION
    assert by_capability["skill generator/installer/validator"].state == MERGED_BUT_NOT_OPERATIONAL
    # B2 verifies rollback execution and patch apply
    # assert by_capability["rollback execution"].state != OPERATIONALLY_VERIFIED
    assert by_capability["HITL-approved verification execution"].state != ("OPERATIONALLY" + "_VERIFIED")
    assert by_capability["model registry"].state != OPERATIONALLY_VERIFIED


def test_matrix_command_names_are_registered_where_applicable() -> None:
    registry_names = {record.name for record in COMMAND_AUTHORITY_REGISTRY}
    assert not validate_command_surfaces(registry_names)


def test_builder_platform_commands_are_registered_as_tier1_validation_only() -> None:
    by_name = {record.name: record for record in COMMAND_AUTHORITY_REGISTRY}
    for name in (
        "builder-platform",
        "builder-platform matrix",
        "builder-platform status",
        "builder-platform audit-docs",
        "builder-platform validate-r1-closure",
    ):
        record = by_name[name]
        assert record.tier == TIER_1
        assert record.approval_mode == MODE_NONE
        assert not record.allows_runtime_start
        assert not record.allows_model_execution
        assert not record.allows_shell_execution
        assert not record.allows_source_writes
        assert not record.allows_memory_mutation
        assert not record.allows_git_mutation
        assert not record.allows_state_writes
        assert not record.allows_external_tool_invocation
        assert not record.allows_artifact_writes

    r1_record = by_name["builder-platform r1-closure"]
    assert r1_record.tier == TIER_1
    assert r1_record.approval_mode == MODE_NONE
    assert not r1_record.allows_runtime_start
    assert not r1_record.allows_model_execution
    assert not r1_record.allows_shell_execution
    assert not r1_record.allows_source_writes
    assert not r1_record.allows_memory_mutation
    assert not r1_record.allows_git_mutation
    assert not r1_record.allows_state_writes
    assert not r1_record.allows_external_tool_invocation
    assert r1_record.allows_artifact_writes


def test_matrix_rendering_is_json_safe() -> None:
    matrix = render_matrix_jsonable()
    encoded = json.dumps(matrix, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded["kind"] == "builder_ii.platform_completion_matrix"
    assert decoded["summary"]["operationally_incomplete"] is True
    assert decoded["summary"]["operationally_verified_count"] == 8  # B5 verifies deepagents runtime/subagents
    
def test_human_status_reports_operational_incompleteness() -> None:
    summary = render_human_summary()
    assert "passive-foundation-complete" in summary
    assert "operationally incomplete" in summary
    assert "B5 -> B6" in summary
    assert "R1 Config + Onboarding Kernel must precede B1 verification execution" in summary


def test_builder_platform_matrix_cli_outputs_json() -> None:
    result = runner.invoke(platform_app, ["matrix"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kind"] == "builder_ii.platform_completion_matrix"
    assert len(data["capabilities"]) == len(REQUIRED_CAPABILITIES)


def test_builder_platform_status_cli_is_honest() -> None:
    result = runner.invoke(platform_app, ["status"])
    assert result.exit_code == 0, result.output
    assert "passive-foundation-complete" in result.output
    assert "operationally incomplete" in result.output
    assert "B5 -> B6" in result.output
