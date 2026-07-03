from builder_ii.readonly_inspection_promotion import (
    READONLY_INSPECTION_PROMOTION_SPEC_KIND,
    READONLY_INSPECTION_PROMOTION_SPEC_SCHEMA_VERSION,
    create_readonly_inspection_promotion_spec,
    validate_readonly_inspection_promotion_spec,
)


def test_readonly_inspection_promotion_spec_shape() -> None:
    spec = create_readonly_inspection_promotion_spec(target="builder")

    assert spec["kind"] == READONLY_INSPECTION_PROMOTION_SPEC_KIND
    assert spec["schema_version"] == READONLY_INSPECTION_PROMOTION_SPEC_SCHEMA_VERSION
    assert spec["capability_name"] == "bounded_readonly_inspection"
    assert spec["target"] == "builder"
    assert spec["candidate_state"] == "DESIGN_ONLY"
    assert spec["current_state"] == "DISABLED"
    assert spec["runtime_promotion"] == "BLOCKED_UNTIL_APPROVED"
    assert spec["performed_actions"] == []
    assert spec["grants_runtime_authority"] is False
    assert spec["grants_action_authority"] is False
    assert validate_readonly_inspection_promotion_spec(spec) == []


def test_readonly_inspection_requires_all_promotion_gates() -> None:
    spec = create_readonly_inspection_promotion_spec()

    for gate in (
        "explicit_operator_paths",
        "target_profile_bound",
        "verification_profile_bound",
        "git_state_bound",
        "artifact_output_declared",
        "denied_actions_tested",
        "handoff_record_required",
    ):
        assert gate in spec["required_gates"]


def test_readonly_inspection_denies_runtime_authority_surfaces() -> None:
    spec = create_readonly_inspection_promotion_spec()

    for action in (
        "source_writes",
        "shell_execution",
        "model_execution",
        "network_access",
        "mcp_execution",
        "deepagents_runtime",
        "git_mutation",
        "commit_push",
        "memory_mutation",
    ):
        assert action in spec["denied_actions"]


def test_read_boundary_requires_explicit_operator_inputs() -> None:
    spec = create_readonly_inspection_promotion_spec(target="generic")

    assert spec["read_boundary"] == {
        "repo_paths": "EXPLICIT_OPERATOR_INPUT_REQUIRED",
        "file_allowlist": "EXPLICIT_OPERATOR_INPUT_REQUIRED",
        "git_state": "EXPLICIT_ARTIFACT_REQUIRED",
        "artifact_output": "EXPLICIT_OPERATOR_OUTPUT_REQUIRED",
    }


def test_required_artifacts_include_promotion_chain() -> None:
    spec = create_readonly_inspection_promotion_spec()

    assert "builder_ii.target_profile" in spec["required_artifacts"]
    assert "builder_ii.verification_profile" in spec["required_artifacts"]
    assert "builder_ii.git_state_record" in spec["required_artifacts"]
    assert "builder_ii.promotion_readiness_record" in spec["required_artifacts"]
    assert "builder_ii.promotion_decision_record" in spec["required_artifacts"]


def test_validation_rejects_premature_runtime_promotion() -> None:
    spec = create_readonly_inspection_promotion_spec()
    spec["candidate_state"] = "ENABLED"
    spec["current_state"] = "ENABLED"
    spec["runtime_promotion"] = "APPROVED"
    spec["performed_actions"] = ["inspect"]
    spec["grants_runtime_authority"] = True
    spec["grants_action_authority"] = True
    spec["governance"]["runtime_execution"] = "ENABLED"
    spec["governance"]["source_writes"] = "ENABLED"
    spec["governance"]["artifact_is_authority"] = True
    spec["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_readonly_inspection_promotion_spec(spec)

    assert "candidate_state must be DESIGN_ONLY" in errors
    assert "current_state must be DISABLED or NOT_AUTHORIZED" in errors
    assert "runtime_promotion must be BLOCKED_UNTIL_APPROVED" in errors
    assert "performed_actions must be empty" in errors
    assert "grants_runtime_authority must be false or NOT_AUTHORIZED" in errors
    assert "grants_action_authority must be false or NOT_AUTHORIZED" in errors
    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.source_writes must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors
    assert "governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in errors


def test_validation_rejects_missing_required_gate_and_denied_action() -> None:
    spec = create_readonly_inspection_promotion_spec()
    spec["required_gates"] = ["explicit_operator_paths"]
    spec["denied_actions"] = ["source_writes"]

    errors = validate_readonly_inspection_promotion_spec(spec)

    assert "missing required gate: target_profile_bound" in errors
    assert "missing denied action: shell_execution" in errors
