"""B2.0 machine-checkable promotion-gate evaluator tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from builder_ii.governance.ledger.verification_execution_ledger import (
    index_verification_execution_receipt,
    write_verification_execution_ledger_record,
)
from builder_ii.lifecycle.candidate.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.lifecycle.candidate.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    finalize_verification_execution_receipt,
    write_verification_execution_receipt,
)
from builder_ii.lifecycle.candidate.verification_promotion_gate import (
    PROMOTION_EVIDENCE_KIND,
    evaluate_verification_promotion_gates_from_files,
    validate_promotion_evidence,
)


def _write_chain(
    tmp_path: Path,
    *,
    receipt_status: str = "EXECUTED",
    workspace_mutation_detected: bool = False,
    target_commit: str | None = "abc123def456",
    expires_at: str | None = None,
) -> tuple[Path, Path, Path]:
    root = tmp_path / ".builder" / "verification"
    root.mkdir(parents=True, exist_ok=True)
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        generated_at="2026-07-08T00:00:00+00:00",
    )
    plan_path = root / "plan.json"
    write_verification_execution_plan(plan, plan_path)
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Operator",
        approval_reason="Approve bounded platform_status verification for promotion evidence.",
        approved_command_profiles=["platform_status"],
        approved_step_ids=["platform_status"],
        generated_at="2026-07-08T00:01:00+00:00",
        expires_at=expires_at,
    )
    approval_path = root / "approval.json"
    write_verification_execution_approval(approval, approval_path)
    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        generated_at="2026-07-08T00:02:00+00:00",
        receipt_status=receipt_status,
        executed_steps=[{"step_id": "platform_status", "status": "success", "profile": "platform_status"}],
        skipped_steps=[],
        process_results=[
            {
                "step_id": "platform_status",
                "profile": "platform_status",
                "command_profile_ref": "verification_profiles.builder_full.platform_status",
                "status": "success",
                "returncode": 0,
                "timeout_seconds": 30,
                "shell": False,
                "argv": ["python", "-m", "builder_ii.verification_runner_entrypoints", "platform-status"],
                "argv_digest": "0" * 64,
                "stdout_sha256": "1" * 64,
                "stderr_sha256": "2" * 64,
                "stdout_excerpt": "ok",
                "stderr_excerpt": "",
                "stdout_truncated": False,
                "stderr_truncated": False,
            }
        ],
        preflight_git_state={
            "state_label": "preflight",
            "captured": True,
            "returncode": 0,
            "porcelain_sha256": "3" * 64,
            "porcelain_lines": [],
            "stderr_sha256": "4" * 64,
            "head_sha": target_commit,
            "branch": "main",
        },
        postflight_git_state={
            "state_label": "postflight",
            "captured": True,
            "returncode": 0,
            "porcelain_sha256": "3" * 64,
            "porcelain_lines": [],
            "stderr_sha256": "4" * 64,
            "head_sha": target_commit,
            "branch": "main",
        },
        workspace_mutation_detected=workspace_mutation_detected,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
        target_commit=target_commit,
        target_branch="main",
        observed_byproducts=[],
        execution_risk_acknowledged=False,
        acknowledged_risk=None,
    )
    receipt_path = root / "receipt.json"
    write_verification_execution_receipt(receipt, receipt_path)
    return plan_path, approval_path, receipt_path


def test_promotion_gate_passes_clean_executed_chain(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_chain(tmp_path)
    evidence = evaluate_verification_promotion_gates_from_files(
        plan_path=plan_path,
        approval_path=approval_path,
        receipt_path=receipt_path,
        capability_name="HITL-approved verification execution",
        expected_profile="platform_status",
    )
    assert evidence["kind"] == PROMOTION_EVIDENCE_KIND
    assert evidence["overall_state"] == "PASS"
    assert evidence["ready_for_operator_promotion_review"] is True
    assert evidence["grants_runtime_authority"] is False
    assert evidence["flips_matrix"] is False
    assert validate_promotion_evidence(evidence) == []
    assert all(gate["state"] == "PASS" for gate in evidence["gates"])


def test_promotion_gate_fails_on_mutation(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_chain(
        tmp_path, workspace_mutation_detected=True, receipt_status="FAILED"
    )
    evidence = evaluate_verification_promotion_gates_from_files(
        plan_path=plan_path,
        approval_path=approval_path,
        receipt_path=receipt_path,
    )
    assert evidence["overall_state"] == "FAIL"
    assert "workspace_unmutated" in evidence["failed_gates"] or "receipt_executed" in evidence["failed_gates"]
    assert validate_promotion_evidence(evidence) == []


def test_promotion_gate_fails_on_expired_approval(tmp_path: Path) -> None:
    expired = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    plan_path, approval_path, receipt_path = _write_chain(tmp_path, expires_at=expired)
    evidence = evaluate_verification_promotion_gates_from_files(
        plan_path=plan_path,
        approval_path=approval_path,
        receipt_path=receipt_path,
        now=datetime.now(timezone.utc),
    )
    assert evidence["overall_state"] == "FAIL"
    assert "approval_unexpired" in evidence["failed_gates"]


def test_promotion_gate_includes_ledger_when_supplied(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_chain(tmp_path)
    ledger_record = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
        ledger_root=tmp_path / ".builder" / "ledger",
    )
    assert ledger_record.get("ledger_index") == 1
    assert ledger_record.get("previous_ledger_record_digest") is None
    ledger_path = tmp_path / ".builder" / "ledger" / "record-1.json"
    write_verification_execution_ledger_record(ledger_record, ledger_path)

    evidence = evaluate_verification_promotion_gates_from_files(
        plan_path=plan_path,
        approval_path=approval_path,
        receipt_path=receipt_path,
        ledger_path=ledger_path,
        expected_profile="platform_status",
    )
    assert evidence["overall_state"] == "PASS"
    ledger_gate = next(gate for gate in evidence["gates"] if gate["gate"] == "ledger_chain_consistent")
    assert ledger_gate["state"] == "PASS"
