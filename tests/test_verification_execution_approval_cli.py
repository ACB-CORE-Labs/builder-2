from __future__ import annotations

import json
from pathlib import Path

from builder_ii.verification_execution_plan_cli import verify_app
from typer.testing import CliRunner

from builder_ii.config_schema import attach_digest
from builder_ii.verification_execution_approval import (
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
)
from builder_ii.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)

runner = CliRunner()


def _write_plan(
    path: Path,
    *,
    target_repo: str = ".",
    artifact_root: str = ".builder/verification",
) -> dict:
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=target_repo,
        artifact_root=artifact_root,
        generated_at="2026-06-30T00:00:00+00:00",
    )
    write_verification_execution_plan(plan, path)
    return plan


def test_builder_verify_approve_plan_writes_artifact_prints_json_and_validates(tmp_path: Path) -> None:
    plan_path = tmp_path / "verification-execution-plan.json"
    plan = _write_plan(plan_path)
    output = tmp_path / "verification-execution-approval.json"

    result = runner.invoke(
        verify_app,
        [
            "approve-plan",
            str(plan_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Approve passive B1.1 verification plan for future B1.3 runner testing.",
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    printed = json.loads(result.output)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert printed == written
    assert validate_verification_execution_approval_artifact(written) == []
    assert validate_verification_execution_approval_against_plan(written, plan) == []
    assert written["execution_enabled"] is False
    assert written["approval_enables_execution"] is False


def test_builder_verify_validate_approval_reports_valid(tmp_path: Path) -> None:
    plan_path = tmp_path / "verification-execution-plan.json"
    _write_plan(plan_path)
    approval_path = tmp_path / "verification-execution-approval.json"

    approve_result = runner.invoke(
        verify_app,
        [
            "approve-plan",
            str(plan_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Approve passive B1.1 verification plan for future B1.3 runner testing.",
            "--output",
            str(approval_path),
        ],
    )
    assert approve_result.exit_code == 0, approve_result.output

    validate_result = runner.invoke(
        verify_app,
        ["validate-approval", str(approval_path), "--plan", str(plan_path)],
    )
    assert validate_result.exit_code == 0, validate_result.output
    report = json.loads(validate_result.output)
    assert report == {
        "errors": [],
        "path": str(approval_path),
        "plan_path": str(plan_path),
        "valid": True,
    }


def test_builder_verify_validate_approval_fails_with_wrong_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "verification-execution-plan.json"
    _write_plan(plan_path, target_repo=".")
    wrong_plan_path = tmp_path / "wrong-plan.json"
    _write_plan(wrong_plan_path, target_repo="/tmp/other")
    approval_path = tmp_path / "verification-execution-approval.json"

    approve_result = runner.invoke(
        verify_app,
        [
            "approve-plan",
            str(plan_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Approve passive B1.1 verification plan for future B1.3 runner testing.",
            "--output",
            str(approval_path),
        ],
    )
    assert approve_result.exit_code == 0, approve_result.output

    result = runner.invoke(
        verify_app,
        ["validate-approval", str(approval_path), "--plan", str(wrong_plan_path)],
    )
    assert result.exit_code != 0
    report = json.loads(result.output)
    assert report["valid"] is False
    assert any("plan_digest does not match referenced plan" in error for error in report["errors"])


def test_builder_verify_approve_plan_fails_on_invalid_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "verification-execution-plan.json"
    plan = _write_plan(plan_path)
    plan["execution_enabled"] = True
    plan = attach_digest(plan, digest_key="verification_execution_plan_digest")
    write_verification_execution_plan(plan, plan_path)
    approval_path = tmp_path / "verification-execution-approval.json"

    result = runner.invoke(
        verify_app,
        [
            "approve-plan",
            str(plan_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Approve passive B1.1 verification plan for future B1.3 runner testing.",
            "--output",
            str(approval_path),
        ],
    )
    assert result.exit_code != 0
    assert not approval_path.exists()


def test_approve_plan_target_code_profile_without_ack_is_refused(tmp_path: Path) -> None:
    plan_path = tmp_path / "verification-execution-plan.json"
    _write_plan(plan_path)
    approval_path = tmp_path / "verification-execution-approval.json"

    result = runner.invoke(
        verify_app,
        [
            "approve-plan",
            str(plan_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Approve the full test-suite lane.",
            "--output",
            str(approval_path),
            "--profile",
            "pytest_full",
        ],
    )

    assert result.exit_code != 0
    assert "Execution-risk notice" in result.output
    assert not approval_path.exists(), "no approval may be written without the acknowledgment"


def test_approve_plan_target_code_profile_with_ack_writes_acknowledged_approval(tmp_path: Path) -> None:
    plan_path = tmp_path / "verification-execution-plan.json"
    plan = _write_plan(plan_path)
    approval_path = tmp_path / "verification-execution-approval.json"

    result = runner.invoke(
        verify_app,
        [
            "approve-plan",
            str(plan_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Approve the full test-suite lane.",
            "--output",
            str(approval_path),
            "--profile",
            "pytest_full",
            "--acknowledge-execution-risk",
        ],
    )

    assert result.exit_code == 0, result.output
    written = json.loads(approval_path.read_text(encoding="utf-8"))
    assert written["approved_command_profiles"] == ["pytest_full"]
    assert written["approved_step_ids"] == ["pytest_full"]
    assert written["execution_risk_acknowledged"] is True
    assert written["acknowledged_risk"]
    assert validate_verification_execution_approval_artifact(written) == []
    assert validate_verification_execution_approval_against_plan(written, plan) == []


def test_approve_plan_safe_profile_needs_no_ack(tmp_path: Path) -> None:
    plan_path = tmp_path / "verification-execution-plan.json"
    _write_plan(plan_path)
    approval_path = tmp_path / "verification-execution-approval.json"

    result = runner.invoke(
        verify_app,
        [
            "approve-plan",
            str(plan_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Approve the safe platform status profile.",
            "--output",
            str(approval_path),
            "--profile",
            "platform_status",
        ],
    )

    assert result.exit_code == 0, result.output
    written = json.loads(approval_path.read_text(encoding="utf-8"))
    assert written["approved_command_profiles"] == ["platform_status"]
    assert written["execution_risk_acknowledged"] is False
    assert "Execution-risk notice" not in result.output


def test_approval_commands_write_only_requested_artifact_and_validation_is_read_only(tmp_path: Path) -> None:
    plan_path = tmp_path / "verification-execution-plan.json"
    _write_plan(plan_path)
    approval_path = tmp_path / "artifacts" / "verification-execution-approval.json"
    before_files = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())
    assert before_files == [Path("verification-execution-plan.json")]

    approve_result = runner.invoke(
        verify_app,
        [
            "approve-plan",
            str(plan_path),
            "--approval-actor",
            "Jane Operator",
            "--approval-reason",
            "Approve passive B1.1 verification plan for future B1.3 runner testing.",
            "--output",
            str(approval_path),
        ],
    )
    assert approve_result.exit_code == 0, approve_result.output

    after_approve = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())
    assert after_approve == [
        Path("artifacts/verification-execution-approval.json"),
        Path("verification-execution-plan.json"),
    ]

    validate_result = runner.invoke(
        verify_app,
        ["validate-approval", str(approval_path), "--plan", str(plan_path)],
    )
    assert validate_result.exit_code == 0, validate_result.output

    after_validate = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*") if path.is_file())
    assert after_validate == after_approve
