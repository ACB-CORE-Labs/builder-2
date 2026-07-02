from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.verification_execution_plan_cli import verify_app
from builder_ii.verification_execution_receipt import (
    finalize_verification_execution_receipt,
    write_verification_execution_receipt,
)

runner = CliRunner()


def _write_bound_artifacts(tmp_path: Path) -> tuple[Path, Path, Path]:
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = tmp_path / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Joshua Shay",
        approval_reason="Approve passive B1.1 verification plan for future B1.3 runner testing.",
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = tmp_path / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)

    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        generated_at="2026-06-30T00:02:00+00:00",
    )
    receipt_path = tmp_path / "verification-execution-receipt.json"
    write_verification_execution_receipt(receipt, receipt_path)

    return plan_path, approval_path, receipt_path


def test_validate_receipt_reports_valid_for_bound_artifacts(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)

    result = runner.invoke(
        verify_app,
        [
            "validate-receipt",
            str(receipt_path),
            "--plan",
            str(plan_path),
            "--approval",
            str(approval_path),
        ],
    )

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert report == {
        "approval_path": str(approval_path),
        "errors": [],
        "path": str(receipt_path),
        "plan_path": str(plan_path),
        "valid": True,
    }


def test_validate_receipt_fails_with_wrong_plan(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    wrong_plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo="/tmp/other",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:03:00+00:00",
    )
    wrong_plan_path = tmp_path / "wrong-plan.json"
    write_verification_execution_plan(wrong_plan, wrong_plan_path)

    result = runner.invoke(
        verify_app,
        [
            "validate-receipt",
            str(receipt_path),
            "--plan",
            str(wrong_plan_path),
            "--approval",
            str(approval_path),
        ],
    )

    assert result.exit_code != 0
    report = json.loads(result.output)
    assert report["valid"] is False
    assert any("not bound to plan" in error or "plan_digest does not match" in error for error in report["errors"])


def test_validate_receipt_fails_with_wrong_approval(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    wrong_approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Joshua Shay",
        approval_reason="Approve passive B1.1 verification plan for future B1.3 runner testing.",
        approved_step_ids=["pytest_full"],
        generated_at="2026-06-30T00:04:00+00:00",
    )
    wrong_approval_path = tmp_path / "wrong-approval.json"
    write_verification_execution_approval(wrong_approval, wrong_approval_path)

    result = runner.invoke(
        verify_app,
        [
            "validate-receipt",
            str(receipt_path),
            "--plan",
            str(plan_path),
            "--approval",
            str(wrong_approval_path),
        ],
    )

    assert result.exit_code != 0
    report = json.loads(result.output)
    assert report["valid"] is False
    assert any("approval_digest does not match" in error for error in report["errors"])
