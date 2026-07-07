from __future__ import annotations

from pathlib import Path

from builder_ii.config_schema import attach_digest
from builder_ii.verification_execution_approval import finalize_verification_execution_approval
from builder_ii.verification_execution_plan import finalize_verification_execution_plan
from builder_ii.verification_execution_receipt import (
    REQUIRED_DISABLED_AUTHORITY,
    VERIFICATION_EXECUTION_RECEIPT_KIND,
    finalize_verification_execution_receipt,
    validate_verification_execution_receipt_against_plan_and_approval,
    validate_verification_execution_receipt_artifact,
    validate_verification_execution_receipt_file,
    write_verification_execution_receipt,
)


def _sample_plan() -> dict:
    return finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )


def _sample_approval(plan: dict) -> dict:
    return finalize_verification_execution_approval(
        plan=plan,
        plan_path="/tmp/verification-execution-plan.json",
        approval_actor="Joshua Shay",
        approval_reason="Approve passive B1.1 verification plan for future B1.3 runner testing.",
        generated_at="2026-06-30T00:01:00+00:00",
    )


def _sample_receipt() -> tuple[dict, dict, dict]:
    plan = _sample_plan()
    approval = _sample_approval(plan)
    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path="/tmp/verification-execution-plan.json",
        approval_path="/tmp/verification-execution-approval.json",
        generated_at="2026-06-30T00:02:00+00:00",
    )
    return plan, approval, receipt


def _resign(receipt: dict) -> dict:
    return attach_digest(receipt, digest_key="verification_execution_receipt_digest")


def test_valid_passive_receipt_validates_against_plan_and_approval() -> None:
    plan, approval, receipt = _sample_receipt()

    assert receipt["kind"] == VERIFICATION_EXECUTION_RECEIPT_KIND
    assert receipt["receipt_status"] == "NOT_EXECUTED"
    assert receipt["execution_enabled"] is False
    assert receipt["shell_enabled"] is False
    assert receipt["subprocess_mode"] == "not_started"
    assert receipt["workspace_mutation_detected"] is False
    assert receipt["disabled_authority"] == REQUIRED_DISABLED_AUTHORITY
    assert receipt["valid"] is True
    assert receipt["errors"] == []

    assert validate_verification_execution_receipt_artifact(receipt) == []
    assert validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval) == []


def test_digest_drift_fails() -> None:
    _plan, _approval, receipt = _sample_receipt()
    receipt["target_repo"] = "/tmp/other"

    errors = validate_verification_execution_receipt_artifact(receipt)

    assert any("digest" in error and "drift" in error for error in errors)


def test_execution_enabled_true_fails_for_b1_3a() -> None:
    _plan, _approval, receipt = _sample_receipt()
    receipt["execution_enabled"] = True
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_artifact(receipt)

    assert any("execution_enabled must be false or NOT_AUTHORIZED" in error for error in errors)


def test_shell_enabled_true_fails() -> None:
    _plan, _approval, receipt = _sample_receipt()
    receipt["shell_enabled"] = True
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_artifact(receipt)

    assert any("shell_enabled must be false or NOT_AUTHORIZED" in error for error in errors)


def test_subprocess_mode_started_fails_for_b1_3a() -> None:
    _plan, _approval, receipt = _sample_receipt()
    receipt["subprocess_mode"] = "shell_false_bounded"
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_artifact(receipt)

    assert any("subprocess_mode must be not_started" in error for error in errors)


def test_workspace_mutation_detected_fails_for_b1_3a() -> None:
    _plan, _approval, receipt = _sample_receipt()
    receipt["workspace_mutation_detected"] = True
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_artifact(receipt)

    assert any("workspace_mutation_detected must be false or NOT_AUTHORIZED" in error for error in errors)


def test_missing_disabled_authority_fails() -> None:
    _plan, _approval, receipt = _sample_receipt()
    del receipt["disabled_authority"]["patch_authority"]
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_artifact(receipt)

    assert any("disabled_authority.patch_authority" in error for error in errors)


def test_plan_digest_mismatch_fails_against_plan() -> None:
    plan, approval, receipt = _sample_receipt()
    receipt["plan_digest"] = "0" * 64
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval)

    assert any("plan_digest does not match" in error for error in errors)


def test_approval_digest_mismatch_fails_against_approval() -> None:
    plan, approval, receipt = _sample_receipt()
    receipt["approval_digest"] = "0" * 64
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval)

    assert any("approval_digest does not match" in error for error in errors)


def test_unapproved_profile_fails_against_approval() -> None:
    plan, approval, receipt = _sample_receipt()
    receipt["approved_command_profiles"] = receipt["approved_command_profiles"] + ["not_approved"]
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval)

    assert any("approved_command_profiles" in error for error in errors)


def test_unapproved_step_fails_against_approval() -> None:
    plan, approval, receipt = _sample_receipt()
    receipt["skipped_steps"].append({"step_id": "not_approved", "status": "not_executed", "reason": "not approved"})
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval)

    assert any("step_id values must be approved" in error for error in errors)


def test_malformed_non_string_step_id_does_not_crash_binding_validation() -> None:
    plan, approval, receipt = _sample_receipt()
    receipt["skipped_steps"].append({"step_id": None, "status": "not_executed", "reason": "malformed receipt"})
    receipt = _resign(receipt)

    artifact_errors = validate_verification_execution_receipt_artifact(receipt)
    binding_errors = validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval)

    assert any("step_id must be a non-empty string" in error for error in artifact_errors)
    assert isinstance(binding_errors, list)


def test_process_result_shell_true_fails() -> None:
    _plan, _approval, receipt = _sample_receipt()
    receipt["process_results"] = [{"step_id": "pytest_full", "status": "not_executed", "shell": True}]
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_artifact(receipt)

    assert any("shell must be false or NOT_AUTHORIZED" in error for error in errors)


def test_environment_policy_cannot_forward_secrets() -> None:
    _plan, _approval, receipt = _sample_receipt()
    receipt["environment_policy"]["secrets_forwarded"] = True
    receipt = _resign(receipt)

    errors = validate_verification_execution_receipt_artifact(receipt)

    assert any("environment_policy.secrets_forwarded must be false or NOT_AUTHORIZED" in error for error in errors)


def test_contract_only_receipt_has_null_commit_identity_and_empty_byproducts() -> None:
    _plan, _approval, receipt = _sample_receipt()
    # A passive contract-only receipt did not run anything, so commit identity is null.
    assert receipt["target_commit"] is None
    assert receipt["target_branch"] is None
    assert receipt["observed_byproducts"] == []
    assert receipt["execution_risk_acknowledged"] is False
    assert receipt["acknowledged_risk"] is None
    assert validate_verification_execution_receipt_artifact(receipt) == []


def test_commit_identity_and_byproduct_fields_validate() -> None:
    plan = _sample_plan()
    approval = _sample_approval(plan)
    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path="/tmp/verification-execution-plan.json",
        approval_path="/tmp/verification-execution-approval.json",
        generated_at="2026-06-30T00:02:00+00:00",
        target_commit="a" * 40,
        target_branch="main",
        observed_byproducts=[".pytest_cache/v/cache/lastfailed"],
        execution_risk_acknowledged=True,
        acknowledged_risk="Operator acknowledged the target-code execution risk.",
    )
    assert receipt["target_commit"] == "a" * 40
    assert receipt["target_branch"] == "main"
    assert receipt["observed_byproducts"] == [".pytest_cache/v/cache/lastfailed"]
    assert receipt["execution_risk_acknowledged"] is True
    assert validate_verification_execution_receipt_artifact(receipt) == []


def test_non_boolean_execution_risk_ack_fails() -> None:
    _plan, _approval, receipt = _sample_receipt()
    receipt["execution_risk_acknowledged"] = "yes"
    receipt = _resign(receipt)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any("execution_risk_acknowledged must be a boolean" in error for error in errors)


def test_file_validation_round_trip(tmp_path: Path) -> None:
    _plan, _approval, receipt = _sample_receipt()
    output = tmp_path / "verification-execution-receipt.json"

    write_verification_execution_receipt(receipt, output)

    assert validate_verification_execution_receipt_file(output) == []


def test_file_validation_read_error_is_clean(tmp_path: Path) -> None:
    errors = validate_verification_execution_receipt_file(tmp_path)

    assert errors
    assert "could not be read" in errors[0]
