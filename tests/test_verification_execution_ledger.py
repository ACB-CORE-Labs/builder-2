from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from builder_ii.config_schema import attach_digest
from builder_ii.ledger_cli import ledger_app
from builder_ii.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_ledger import (
    LEDGER_RECORD_STATE,
    VERIFICATION_EXECUTION_LEDGER_RECORD_KIND,
    default_verification_execution_ledger_output,
    index_verification_execution_receipt,
    validate_receipt_chain_for_ledger,
    validate_verification_execution_ledger_record,
)
from builder_ii.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    finalize_verification_execution_receipt,
    write_verification_execution_receipt,
)


def _artifact_root(tmp_path: Path) -> Path:
    root = tmp_path / ".builder" / "verification"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_valid_chain(tmp_path: Path) -> tuple[Path, Path, Path]:
    root = _artifact_root(tmp_path)
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = root / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Joshua Shay",
        approval_reason="Approve bounded platform_status verification runner proof.",
        approved_command_profiles=["platform_status"],
        approved_step_ids=["platform_status"],
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = root / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)

    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        generated_at="2026-06-30T00:02:00+00:00",
        receipt_status="EXECUTED",
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
                "argv_digest": "0" * 64,
                "stdout_sha256": "1" * 64,
                "stderr_sha256": "2" * 64,
                "stdout_excerpt": "builder-II platform status\n",
                "stderr_excerpt": "",
                "stdout_truncated": False,
                "stderr_truncated": False,
            }
        ],
        preflight_git_state={"state_label": "preflight", "captured": True, "returncode": 0, "porcelain_sha256": "3" * 64, "porcelain_lines": [], "stderr_sha256": "4" * 64},
        postflight_git_state={"state_label": "postflight", "captured": True, "returncode": 0, "porcelain_sha256": "3" * 64, "porcelain_lines": [], "stderr_sha256": "4" * 64},
        workspace_mutation_detected=False,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    )
    receipt_path = root / "verification-execution-receipt.json"
    write_verification_execution_receipt(receipt, receipt_path)
    return plan_path, approval_path, receipt_path


def test_indexes_valid_b1_3_receipt_chain_passively(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path)

    record = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
    )

    assert record["kind"] == VERIFICATION_EXECUTION_LEDGER_RECORD_KIND
    assert record["ledger_record_state"] == LEDGER_RECORD_STATE
    assert record["valid"] is True
    assert record["receipt_status"] == "EXECUTED"
    assert record["runner_mode"] == RUNNER_MODE_BOUNDED_APPROVED
    assert record["process_result_count"] == 1
    assert record["process_result_statuses"] == ["success"]
    assert [item["role"] for item in record["subject_refs"]] == [
        "verification_execution_plan",
        "verification_execution_approval",
        "verification_execution_receipt",
    ]
    assert record["executes_shell"] is False
    assert record["replays_execution"] is False
    assert record["governance"]["runtime_execution"] == "DISABLED"
    assert record["governance"]["replay_execution"] == "DISABLED"
    assert validate_verification_execution_ledger_record(record) == []


def test_ledger_record_is_deterministic_for_same_inputs(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path)

    first = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
    )
    second = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
    )

    assert first == second
    assert default_verification_execution_ledger_output(first).name.startswith("verification-execution-")


def test_invalid_receipt_chain_does_not_validate_for_ledger(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["valid"] = False
    receipt["errors"] = ["synthetic invalid receipt"]
    receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    errors = validate_receipt_chain_for_ledger(
        receipt=receipt,
        plan=json.loads(plan_path.read_text(encoding="utf-8")),
        approval=json.loads(approval_path.read_text(encoding="utf-8")),
    )
    record = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
    )

    assert any("receipt must be valid" in error for error in errors)
    assert record["valid"] is False
    assert any("receipt must be valid" in error for error in record["errors"])


def test_cli_index_receipt_writes_under_builder_ledger(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path)
    output = tmp_path / ".builder" / "ledger" / "receipt-ledger.json"

    result = CliRunner().invoke(
        ledger_app,
        [
            "index-receipt",
            "--receipt",
            str(receipt_path),
            "--plan",
            str(plan_path),
            "--approval",
            str(approval_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    written = json.loads(output.read_text(encoding="utf-8"))
    assert written["kind"] == VERIFICATION_EXECUTION_LEDGER_RECORD_KIND
    assert written["valid"] is True


def test_cli_index_receipt_rejects_output_outside_ledger_root(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path)
    output = tmp_path / ".builder" / "verification" / "not-ledger.json"

    result = CliRunner().invoke(
        ledger_app,
        [
            "index-receipt",
            "--receipt",
            str(receipt_path),
            "--plan",
            str(plan_path),
            "--approval",
            str(approval_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert not output.exists()
    assert "output path must be under" in result.output


def test_ledger_subject_refs_use_repo_relative_paths(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path)

    record = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
    )

    paths = [item["path"] for item in record["subject_refs"]]
    assert paths == [
        ".builder/verification/verification-execution-plan.json",
        ".builder/verification/verification-execution-approval.json",
        ".builder/verification/verification-execution-receipt.json",
    ]
    assert str(tmp_path) not in record["ledger_record_id"]
    assert all(str(tmp_path) not in path for path in paths)


def test_cli_index_receipt_reports_malformed_input_cleanly(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path)
    receipt_path.write_text("{not json", encoding="utf-8")
    output = tmp_path / ".builder" / "ledger" / "receipt-ledger.json"

    result = CliRunner().invoke(
        ledger_app,
        [
            "index-receipt",
            "--receipt",
            str(receipt_path),
            "--plan",
            str(plan_path),
            "--approval",
            str(approval_path),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 1
    assert "failed to load receipt chain" in result.output
    assert "Traceback" not in result.output
    assert not output.exists()
