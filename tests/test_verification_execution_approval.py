from __future__ import annotations

from pathlib import Path

from builder_ii.config_schema import attach_digest
from builder_ii.verification_execution_approval import (
    REQUIRED_DISABLED_AUTHORITY,
    VERIFICATION_EXECUTION_APPROVAL_KIND,
    finalize_verification_execution_approval,
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
    validate_verification_execution_approval_file,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_plan import finalize_verification_execution_plan


def _sample_plan() -> dict:
    return finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )


def _sample_approval(plan: dict | None = None) -> dict:
    return finalize_verification_execution_approval(
        plan=plan or _sample_plan(),
        plan_path="/tmp/verification-execution-plan.json",
        approval_actor="Joshua Shay",
        approval_reason="Approve passive B1.1 verification plan for future B1.3 runner testing.",
        generated_at="2026-06-30T00:00:01+00:00",
    )


def _resign(approval: dict) -> dict:
    return attach_digest(approval, digest_key="verification_execution_approval_digest")


def test_valid_approval_validates() -> None:
    plan = _sample_plan()
    approval = _sample_approval(plan)
    assert approval["kind"] == VERIFICATION_EXECUTION_APPROVAL_KIND
    assert approval["valid"] is True
    assert approval["errors"] == []
    assert approval["approved"] is True
    assert approval["execution_enabled"] is False
    assert approval["approval_enables_execution"] is False
    assert approval["artifact_is_authority"] is False
    assert approval["requires_b1_3_runner"] is True
    assert approval["disabled_authority"] == REQUIRED_DISABLED_AUTHORITY
    assert validate_verification_execution_approval_artifact(approval) == []
    assert validate_verification_execution_approval_against_plan(approval, plan) == []


def test_digest_drift_fails() -> None:
    approval = _sample_approval()
    approval["approval_reason"] = "Approve passive plan drift."
    errors = validate_verification_execution_approval_artifact(approval)
    assert any("verification_execution_approval_digest drift detected" in error for error in errors)


def test_plan_digest_mismatch_fails() -> None:
    plan = _sample_plan()
    approval = _sample_approval(plan)
    approval["plan_digest"] = "b" * 64
    approval = _resign(approval)
    errors = validate_verification_execution_approval_against_plan(approval, plan)
    assert any("plan_digest does not match referenced plan" in error for error in errors)


def test_target_profile_mismatch_fails() -> None:
    plan = _sample_plan()
    approval = _sample_approval(plan)
    approval["target_profile"] = "generic"
    approval = _resign(approval)
    errors = validate_verification_execution_approval_against_plan(approval, plan)
    assert any("target_profile does not match referenced plan" in error for error in errors)


def test_approved_command_profile_outside_plan_fails() -> None:
    plan = _sample_plan()
    approval = _sample_approval(plan)
    approval["approved_command_profiles"].append("not_in_plan")
    approval = _resign(approval)
    errors = validate_verification_execution_approval_against_plan(approval, plan)
    assert any("approved_command_profiles must be a subset" in error for error in errors)


def test_approved_step_id_outside_plan_fails() -> None:
    plan = _sample_plan()
    approval = _sample_approval(plan)
    approval["approved_step_ids"].append("not_in_plan")
    approval = _resign(approval)
    errors = validate_verification_execution_approval_against_plan(approval, plan)
    assert any("approved_step_ids must be a subset" in error for error in errors)


def test_execution_enabled_true_fails() -> None:
    approval = _sample_approval()
    approval["execution_enabled"] = True
    approval = _resign(approval)
    errors = validate_verification_execution_approval_artifact(approval)
    assert any("execution_enabled must be false or NOT_AUTHORIZED" in error for error in errors)


def test_approval_enables_execution_true_fails() -> None:
    approval = _sample_approval()
    approval["approval_enables_execution"] = True
    approval = _resign(approval)
    errors = validate_verification_execution_approval_artifact(approval)
    assert any("approval_enables_execution must be false or NOT_AUTHORIZED" in error for error in errors)


def test_artifact_is_authority_true_fails() -> None:
    approval = _sample_approval()
    approval["artifact_is_authority"] = True
    approval = _resign(approval)
    errors = validate_verification_execution_approval_artifact(approval)
    assert any("artifact_is_authority must be false or NOT_AUTHORIZED" in error for error in errors)


def test_missing_disabled_authority_fails() -> None:
    approval = _sample_approval()
    del approval["disabled_authority"]["direct_execution"]
    approval = _resign(approval)
    errors = validate_verification_execution_approval_artifact(approval)
    assert any("disabled_authority.direct_execution" in error for error in errors)


def test_raw_shell_string_in_approval_text_fails() -> None:
    approval = _sample_approval()
    approval["approval_reason"] = "uv run pytest -q"
    approval = _resign(approval)
    errors = validate_verification_execution_approval_artifact(approval)
    assert any("raw shell string" in error for error in errors)


def test_patch_model_mcp_goose_deepagents_overclaim_fails() -> None:
    cases = [
        "approve patch authority",
        "grant model execution",
        "allow MCP tool invocation",
        "enable Goose runtime",
        "authorize deepagents runtime",
    ]
    for text in cases:
        approval = _sample_approval()
        approval["approval_reason"] = text
        approval = _resign(approval)
        errors = validate_verification_execution_approval_artifact(approval)
        assert any("claims forbidden authority" in error for error in errors), text


def test_default_approval_excludes_target_code_profiles() -> None:
    approval = _sample_approval()
    # A default (unselected) approval binds only the safe builder-II-argv profiles.
    assert "pytest_full" not in approval["approved_command_profiles"]
    assert "builder_full" not in approval["approved_command_profiles"]
    assert "platform_status" in approval["approved_command_profiles"]
    assert approval["execution_risk_acknowledged"] is False
    assert approval["acknowledged_risk"] is None


def test_approving_target_code_profile_without_ack_fails() -> None:
    plan = _sample_plan()
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path="/tmp/verification-execution-plan.json",
        approval_actor="Joshua Shay",
        approval_reason="Approve the full test-suite lane.",
        approved_command_profiles=["pytest_full"],
        approved_step_ids=["pytest_full"],
        generated_at="2026-06-30T00:00:01+00:00",
    )
    assert approval["valid"] is False
    errors = validate_verification_execution_approval_artifact(approval)
    assert any("execution_risk_acknowledged must be true" in error for error in errors)
    assert any("acknowledged_risk must name" in error for error in errors)


def test_approving_target_code_profile_with_ack_validates() -> None:
    plan = _sample_plan()
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path="/tmp/verification-execution-plan.json",
        approval_actor="Joshua Shay",
        approval_reason="Approve the full test-suite lane.",
        approved_command_profiles=["pytest_full"],
        approved_step_ids=["pytest_full"],
        execution_risk_acknowledged=True,
        acknowledged_risk="Operator acknowledges the target repo's own test and conftest code runs on this host.",
        generated_at="2026-06-30T00:00:01+00:00",
    )
    assert approval["valid"] is True
    assert validate_verification_execution_approval_artifact(approval) == []
    assert validate_verification_execution_approval_against_plan(approval, plan) == []


def test_acknowledged_risk_rejects_shell_injection_tokens() -> None:
    plan = _sample_plan()
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path="/tmp/verification-execution-plan.json",
        approval_actor="Joshua Shay",
        approval_reason="Approve the full test-suite lane.",
        approved_command_profiles=["pytest_full"],
        approved_step_ids=["pytest_full"],
        execution_risk_acknowledged=True,
        acknowledged_risk="runs code && rm -rf things",
        generated_at="2026-06-30T00:00:01+00:00",
    )
    errors = validate_verification_execution_approval_artifact(approval)
    assert any("forbidden shell separator" in error for error in errors)


def test_file_validation_round_trip(tmp_path: Path) -> None:
    approval = _sample_approval()
    output = tmp_path / "verification-execution-approval.json"
    write_verification_execution_approval(approval, output)
    assert validate_verification_execution_approval_file(output) == []


def test_file_validation_directory_path_returns_clean_read_error(tmp_path: Path) -> None:
    errors = validate_verification_execution_approval_file(tmp_path)
    assert len(errors) == 1
    assert errors[0].startswith("verification execution approval file could not be read:")
