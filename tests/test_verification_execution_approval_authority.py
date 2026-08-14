from builder_ii.governance.authority import (
    COMMAND_AUTHORITY_REGISTRY,
    MODE_HITL_ARTIFACT_REQUIRED,
    MODE_NONE,
    STATE_HITL_RUNTIME_CANDIDATE,
    STATE_VALIDATION_ONLY,
    TIER_1,
    TIER_3,
)


def test_verification_execution_approval_command_authority_rows_exist() -> None:
    by_name = {record.name: record for record in COMMAND_AUTHORITY_REGISTRY}
    assert "builder-verify approve-plan" in by_name
    assert "builder-verify validate-approval" in by_name


def test_approve_plan_allows_only_explicit_artifact_output_write() -> None:
    record = {item.name: item for item in COMMAND_AUTHORITY_REGISTRY}["builder-verify approve-plan"]
    assert record.tier == TIER_1
    assert record.approval_mode == MODE_NONE
    assert not record.allows_runtime_start
    assert not record.allows_model_execution
    assert not record.allows_shell_execution
    assert not record.allows_source_writes
    assert not record.allows_memory_mutation
    assert not record.allows_git_mutation
    assert not record.allows_state_writes
    assert not record.allows_readonly_subprocess
    assert not record.allows_external_tool_invocation
    assert record.allows_artifact_writes is True
    assert "explicit verification execution approval JSON artifact" in record.write_boundary


def test_validate_approval_is_read_only_and_has_no_runtime_authority() -> None:
    record = {item.name: item for item in COMMAND_AUTHORITY_REGISTRY}["builder-verify validate-approval"]
    assert record.tier == TIER_1
    assert record.approval_mode == MODE_NONE
    assert not record.allows_runtime_start
    assert not record.allows_model_execution
    assert not record.allows_shell_execution
    assert not record.allows_source_writes
    assert not record.allows_memory_mutation
    assert not record.allows_git_mutation
    assert not record.allows_state_writes
    assert not record.allows_readonly_subprocess
    assert not record.allows_external_tool_invocation
    assert record.allows_artifact_writes is False
    assert record.write_boundary == "No changes to workspace."


def test_validate_receipt_command_authority_is_validation_only() -> None:
    by_name = {item.name: item for item in COMMAND_AUTHORITY_REGISTRY}
    assert "builder-verify validate-receipt" in by_name
    record = by_name["builder-verify validate-receipt"]

    assert record.tier == TIER_1
    assert record.promotion_state == STATE_VALIDATION_ONLY
    assert record.allows_runtime_start is False
    assert record.allows_model_execution is False
    assert record.allows_shell_execution is False
    assert record.allows_source_writes is False
    assert record.allows_git_mutation is False
    assert record.allows_artifact_writes is False
    assert record.allows_external_tool_invocation is False


def test_run_approved_command_authority_is_bounded_hitl_runtime_candidate() -> None:
    by_name = {item.name: item for item in COMMAND_AUTHORITY_REGISTRY}
    assert "builder-verify run-approved" in by_name
    record = by_name["builder-verify run-approved"]

    assert record.tier == TIER_3
    assert record.promotion_state == STATE_HITL_RUNTIME_CANDIDATE
    assert record.approval_mode == MODE_HITL_ARTIFACT_REQUIRED
    assert record.allows_runtime_start is False
    assert record.allows_model_execution is False
    assert record.allows_shell_execution is False
    assert record.allows_source_writes is False
    assert record.allows_git_mutation is False
    assert record.allows_artifact_writes is True
    assert record.allows_readonly_subprocess is True
    assert record.allows_external_tool_invocation is False
