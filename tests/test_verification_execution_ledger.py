from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from builder_ii.ledger_cli import ledger_app
from typer.testing import CliRunner

from builder_ii.config_schema import attach_digest
from builder_ii.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_ledger import (
    LEDGER_RECORD_STATE,
    VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND,
    VERIFICATION_EXECUTION_LEDGER_QUERY_REPORT_KIND,
    VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND,
    VERIFICATION_EXECUTION_LEDGER_RECORD_KIND,
    default_verification_execution_ledger_output,
    index_verification_execution_receipt,
    query_verification_execution_ledger_by_chain_digest,
    query_verification_execution_ledger_by_receipt_digest,
    query_verification_execution_ledger_by_receipt_status,
    query_verification_execution_ledger_by_runner_mode,
    query_verification_execution_ledger_records,
    reconstruct_verification_execution_ledger,
    summarize_verification_execution_ledger_records,
    validate_receipt_chain_for_ledger,
    validate_verification_execution_ledger_integrity,
    validate_verification_execution_ledger_integrity_report,
    validate_verification_execution_ledger_reconstruction_report,
    validate_verification_execution_ledger_record,
    write_verification_execution_ledger_record,
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


def _write_valid_chain(
    tmp_path: Path,
    *,
    receipt_status: str = "EXECUTED",
    process_result_status: str = "success",
    generated_at: str = "2026-06-30T00:02:00+00:00",
) -> tuple[Path, Path, Path]:
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
        approval_actor="Jane Operator",
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
        generated_at=generated_at,
        receipt_status=receipt_status,
        executed_steps=[{"step_id": "platform_status", "status": "success", "profile": "platform_status"}],
        skipped_steps=[],
        process_results=[
            {
                "step_id": "platform_status",
                "profile": "platform_status",
                "command_profile_ref": "verification_profiles.builder_full.platform_status",
                "status": process_result_status,
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
        preflight_git_state={
            "state_label": "preflight",
            "captured": True,
            "returncode": 0,
            "porcelain_sha256": "3" * 64,
            "porcelain_lines": [],
            "stderr_sha256": "4" * 64,
        },
        postflight_git_state={
            "state_label": "postflight",
            "captured": True,
            "returncode": 0,
            "porcelain_sha256": "3" * 64,
            "porcelain_lines": [],
            "stderr_sha256": "4" * 64,
        },
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
    assert record["ledger_index"] == 1
    assert record["previous_ledger_record_digest"] is None
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


def test_ledger_index_chain_appends_with_previous_digest(tmp_path: Path) -> None:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path)
    ledger_root = tmp_path / ".builder" / "ledger"
    first = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
        ledger_root=ledger_root,
    )
    write_verification_execution_ledger_record(first, ledger_root / "first.json")

    # Second chain with a different generated_at so chain_digest differs.
    plan_path2, approval_path2, receipt_path2 = _write_valid_chain(
        tmp_path, generated_at="2026-06-30T00:03:00+00:00"
    )
    second = index_verification_execution_receipt(
        receipt_path=receipt_path2,
        plan_path=plan_path2,
        approval_path=approval_path2,
        ledger_root=ledger_root,
    )
    assert second["ledger_index"] == 2
    assert second["previous_ledger_record_digest"] == first["verification_execution_ledger_record_digest"]
    write_verification_execution_ledger_record(second, ledger_root / "second.json")

    integrity = validate_verification_execution_ledger_integrity(ledger_root=ledger_root)
    assert integrity["summary"]["chain_continuity_status"] == "continuous"
    assert integrity["valid"] is True


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


def _write_ledger_record(tmp_path: Path, filename: str, **chain_kwargs: Any) -> dict[str, Any]:
    plan_path, approval_path, receipt_path = _write_valid_chain(tmp_path, **chain_kwargs)
    record = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
    )
    write_verification_execution_ledger_record(record, tmp_path / ".builder" / "ledger" / filename)
    return record


def _receipt_digest(record: dict[str, Any]) -> str:
    for ref in record["subject_refs"]:
        if ref["role"] == "verification_execution_receipt":
            return ref["artifact_digest"]
    raise AssertionError("missing receipt ref")


def _with_record_digest(record: dict[str, Any]) -> dict[str, Any]:
    return attach_digest(record, digest_key="verification_execution_ledger_record_digest")


def test_query_returns_valid_records_deterministically(tmp_path: Path) -> None:
    failed = _write_ledger_record(
        tmp_path,
        "z-failed.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )
    executed = _write_ledger_record(tmp_path, "a-executed.json")

    report = query_verification_execution_ledger_records(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["kind"] == VERIFICATION_EXECUTION_LEDGER_QUERY_REPORT_KIND
    assert report["valid"] is True
    assert [row["chain_digest"] for row in report["records"]] == [
        executed["chain_digest"],
        failed["chain_digest"],
    ]
    assert report["summary"]["record_count"] == 2
    assert report["summary"]["by_receipt_status"] == {"EXECUTED": 1, "FAILED": 1}
    assert report["summary"]["by_process_result_status"] == {"success": 1, "timeout": 1}


def test_query_rejects_invalid_ledger_record_cleanly(tmp_path: Path) -> None:
    _write_ledger_record(tmp_path, "valid.json")
    invalid_path = tmp_path / ".builder" / "ledger" / "invalid.json"
    invalid_path.write_text(json.dumps({"kind": "wrong"}, indent=2) + "\n", encoding="utf-8")

    report = query_verification_execution_ledger_records(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["valid"] is True
    assert report["summary"]["record_count"] == 1
    assert report["summary"]["rejected_count"] == 1
    assert len(report["rejected"]) == 1
    assert report["rejected"][0]["path"].endswith(".builder/ledger/invalid.json")
    assert any("kind must be" in error for error in report["rejected"][0]["errors"])


def test_query_by_receipt_digest_works(tmp_path: Path) -> None:
    first = _write_ledger_record(tmp_path, "first.json")
    second = _write_ledger_record(
        tmp_path,
        "second.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )

    report = query_verification_execution_ledger_by_receipt_digest(
        ledger_root=tmp_path / ".builder" / "ledger",
        receipt_digest=_receipt_digest(second),
    )

    assert report["summary"]["record_count"] == 1
    assert report["records"][0]["chain_digest"] == second["chain_digest"]
    assert report["records"][0]["receipt_digest"] != _receipt_digest(first)


def test_query_by_chain_digest_works(tmp_path: Path) -> None:
    first = _write_ledger_record(tmp_path, "first.json")
    second = _write_ledger_record(
        tmp_path,
        "second.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )

    report = query_verification_execution_ledger_by_chain_digest(
        ledger_root=tmp_path / ".builder" / "ledger",
        chain_digest=first["chain_digest"],
    )

    assert report["summary"]["record_count"] == 1
    assert report["records"][0]["chain_digest"] == first["chain_digest"]
    assert report["records"][0]["chain_digest"] != second["chain_digest"]


def test_query_by_status_and_summary_counts_are_stable(tmp_path: Path) -> None:
    _write_ledger_record(tmp_path, "executed.json")
    _write_ledger_record(
        tmp_path,
        "failed.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )

    report = query_verification_execution_ledger_by_receipt_status(
        ledger_root=tmp_path / ".builder" / "ledger",
        receipt_status="FAILED",
    )
    summary = summarize_verification_execution_ledger_records(report["records"])

    assert report["summary"]["record_count"] == 1
    assert report["summary"]["available_record_count"] == 2
    assert report["summary"]["by_receipt_status"] == {"FAILED": 1}
    assert summary["by_runner_mode"] == {RUNNER_MODE_BOUNDED_APPROVED: 1}


def test_query_by_runner_mode_works(tmp_path: Path) -> None:
    record = _write_ledger_record(tmp_path, "receipt-ledger.json")

    report = query_verification_execution_ledger_by_runner_mode(
        ledger_root=tmp_path / ".builder" / "ledger",
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
    )

    assert report["summary"]["record_count"] == 1
    assert report["records"][0]["chain_digest"] == record["chain_digest"]


def test_cli_query_receipts_prints_json_and_does_not_write(tmp_path: Path) -> None:
    record = _write_ledger_record(tmp_path, "receipt-ledger.json")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    result = CliRunner().invoke(
        ledger_app,
        [
            "query-receipts",
            "--target-repo",
            str(tmp_path),
            "--chain-digest",
            record["chain_digest"],
        ],
    )
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kind"] == VERIFICATION_EXECUTION_LEDGER_QUERY_REPORT_KIND
    assert data["summary"]["record_count"] == 1
    assert data["records"][0]["chain_digest"] == record["chain_digest"]
    assert before == after


def test_query_reports_unresolvable_ledger_root_as_json_diagnostics(monkeypatch: Any, tmp_path: Path) -> None:
    from builder_ii import verification_execution_ledger as ledger_module

    def fail_resolve(self: Path) -> Path:
        raise OSError("synthetic resolve failure")

    monkeypatch.setattr(ledger_module.Path, "resolve", fail_resolve)

    report = query_verification_execution_ledger_records(
        ledger_root=tmp_path / ".builder" / "ledger",
    )

    assert report["valid"] is False
    assert report["records"] == []
    assert report["rejected"] == []
    assert any("failed to resolve ledger_root" in error for error in report["errors"])


def test_integrity_report_validates_records_deterministically(tmp_path: Path) -> None:
    failed = _write_ledger_record(
        tmp_path,
        "z-failed.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )
    executed = _write_ledger_record(tmp_path, "a-executed.json")

    report = validate_verification_execution_ledger_integrity(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["kind"] == VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND
    assert report["valid"] is True
    assert validate_verification_execution_ledger_integrity_report(report) == []
    assert [row["chain_digest"] for row in report["records"]] == [
        executed["chain_digest"],
        failed["chain_digest"],
    ]
    assert report["summary"]["record_count"] == 2
    assert report["summary"]["chain_continuity_status"] == "continuous"
    assert report["duplicates"] == []
    assert report["chain_errors"] == []


def test_integrity_detects_duplicate_records(tmp_path: Path) -> None:
    first = _write_ledger_record(tmp_path, "first.json")
    second = _write_ledger_record(tmp_path, "second.json")

    report = validate_verification_execution_ledger_integrity(ledger_root=tmp_path / ".builder" / "ledger")

    assert first["chain_digest"] == second["chain_digest"]
    assert report["valid"] is False
    assert report["summary"]["duplicate_count"] >= 1
    assert any(item["field"] == "chain_digest" for item in report["duplicates"])
    assert any("duplicate chain_digest" in error for error in report["errors"])
    assert validate_verification_execution_ledger_integrity_report(report) == []


def test_integrity_detects_tampered_record_digest(tmp_path: Path) -> None:
    _write_ledger_record(tmp_path, "receipt-ledger.json")
    path = tmp_path / ".builder" / "ledger" / "receipt-ledger.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["target_profile"] = "generic"
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = validate_verification_execution_ledger_integrity(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["valid"] is False
    assert report["summary"]["rejected_count"] == 1
    assert any("verification_execution_ledger_record_digest drift detected" in error for error in report["errors"])


def test_integrity_detects_missing_required_subject_ref_role(tmp_path: Path) -> None:
    _write_ledger_record(tmp_path, "receipt-ledger.json")
    path = tmp_path / ".builder" / "ledger" / "receipt-ledger.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["subject_refs"][2]["role"] = "not_verification_execution_receipt"
    record = _with_record_digest(record)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = validate_verification_execution_ledger_integrity(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["valid"] is False
    assert any("exactly one verification_execution_receipt ref" in error for error in report["errors"])
    assert report["summary"]["chain_error_count"] == 1


def test_integrity_detects_mismatched_subject_digest_chain(tmp_path: Path) -> None:
    _write_ledger_record(tmp_path, "receipt-ledger.json")
    path = tmp_path / ".builder" / "ledger" / "receipt-ledger.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    for ref in record["subject_refs"]:
        if ref["role"] == "verification_execution_receipt":
            ref["artifact_digest"] = "f" * 64
    record = _with_record_digest(record)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = validate_verification_execution_ledger_integrity(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["valid"] is False
    assert any(
        "chain_digest does not match plan/approval/receipt subject digests" in error for error in report["errors"]
    )


def test_integrity_detects_index_chain_discontinuity_when_rule_applies(tmp_path: Path) -> None:
    first = _write_ledger_record(tmp_path, "first.json")
    second = _write_ledger_record(
        tmp_path,
        "second.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )
    first_path = tmp_path / ".builder" / "ledger" / "first.json"
    second_path = tmp_path / ".builder" / "ledger" / "second.json"
    first["ledger_index"] = 1
    first["previous_ledger_record_digest"] = None
    first = _with_record_digest(first)
    second["ledger_index"] = 3
    second["previous_ledger_record_digest"] = first["verification_execution_ledger_record_digest"]
    second = _with_record_digest(second)
    first_path.write_text(json.dumps(first, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    second_path.write_text(json.dumps(second, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = validate_verification_execution_ledger_integrity(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["valid"] is False
    assert report["summary"]["chain_rule_applies"] is True
    assert report["summary"]["chain_continuity_status"] == "invalid"
    assert any("ledger_index must be 2" in error for error in report["errors"])


def test_integrity_duplicate_ledger_index_does_not_emit_false_prior_digest_error(tmp_path: Path) -> None:
    first = _write_ledger_record(tmp_path, "first.json")
    second = _write_ledger_record(
        tmp_path,
        "second.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )

    first_path = tmp_path / ".builder" / "ledger" / "first.json"
    second_path = tmp_path / ".builder" / "ledger" / "second.json"

    first["ledger_index"] = 1
    first["previous_ledger_record_digest"] = None
    first = _with_record_digest(first)

    second["ledger_index"] = 1
    second["previous_ledger_record_digest"] = None
    second = _with_record_digest(second)

    first_path.write_text(json.dumps(first, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    second_path.write_text(json.dumps(second, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = validate_verification_execution_ledger_integrity(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["valid"] is False
    assert any("duplicate ledger_index 1" in error for error in report["errors"])
    assert not any(
        "previous_ledger_record_digest does not match prior indexed record digest" in error
        for error in report["errors"]
    )


def test_cli_validate_receipts_prints_json_and_does_not_write(tmp_path: Path) -> None:
    _write_ledger_record(tmp_path, "receipt-ledger.json")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    result = CliRunner().invoke(
        ledger_app,
        [
            "validate-receipts",
            "--target-repo",
            str(tmp_path),
        ],
    )
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kind"] == VERIFICATION_EXECUTION_LEDGER_INTEGRITY_REPORT_KIND
    assert data["valid"] is True
    assert before == after


def test_reconstruction_report_projects_valid_ledger_chains(tmp_path: Path) -> None:
    failed = _write_ledger_record(
        tmp_path,
        "z-failed.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )
    executed = _write_ledger_record(tmp_path, "a-executed.json")

    report = reconstruct_verification_execution_ledger(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["kind"] == VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND
    assert report["valid"] is True
    assert validate_verification_execution_ledger_reconstruction_report(report) == []
    assert report["summary"]["reconstructed_chain_count"] == 2
    assert report["summary"]["invalid_record_count"] == 0
    assert report["chain_continuity_status"] == "continuous"
    assert [row["chain_digest"] for row in report["reconstructed_chains"]] == [
        executed["chain_digest"],
        failed["chain_digest"],
    ]
    assert all(
        row["evidence_ref"]["kind"] == VERIFICATION_EXECUTION_LEDGER_RECORD_KIND
        for row in report["reconstructed_chains"]
    )


def test_reconstruction_report_carries_invalid_and_rejected_records(tmp_path: Path) -> None:
    _write_ledger_record(tmp_path, "valid.json")
    invalid_path = tmp_path / ".builder" / "ledger" / "invalid.json"
    invalid_path.write_text(json.dumps({"kind": "wrong"}, indent=2) + "\n", encoding="utf-8")

    report = reconstruct_verification_execution_ledger(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["valid"] is False
    assert report["summary"]["reconstructed_chain_count"] == 1
    assert report["summary"]["invalid_record_count"] == 1
    assert report["invalid_records"][0]["source"] == "rejected"
    assert any("kind must be" in error for error in report["errors"])
    assert validate_verification_execution_ledger_reconstruction_report(report) == []


def test_reconstruction_report_carries_chain_continuity_failure(tmp_path: Path) -> None:
    first = _write_ledger_record(tmp_path, "first.json")
    second = _write_ledger_record(
        tmp_path,
        "second.json",
        receipt_status="FAILED",
        process_result_status="timeout",
        generated_at="2026-06-30T00:03:00+00:00",
    )
    first_path = tmp_path / ".builder" / "ledger" / "first.json"
    second_path = tmp_path / ".builder" / "ledger" / "second.json"
    first["ledger_index"] = 1
    first["previous_ledger_record_digest"] = None
    first = _with_record_digest(first)
    second["ledger_index"] = 3
    second["previous_ledger_record_digest"] = first["verification_execution_ledger_record_digest"]
    second = _with_record_digest(second)
    first_path.write_text(json.dumps(first, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    second_path.write_text(json.dumps(second, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = reconstruct_verification_execution_ledger(ledger_root=tmp_path / ".builder" / "ledger")

    assert report["valid"] is False
    assert report["chain_continuity_status"] == "invalid"
    assert report["summary"]["chain_rule_applies"] is True
    assert any(item["source"] == "chain_error" for item in report["invalid_records"])
    assert any("ledger_index must be 2" in error for error in report["errors"])


def test_reconstruction_report_allows_invalid_chain_row_without_chain_digest(tmp_path: Path) -> None:
    record = _write_ledger_record(tmp_path, "receipt-ledger.json")
    report = reconstruct_verification_execution_ledger(ledger_root=tmp_path / ".builder" / "ledger")
    assert validate_verification_execution_ledger_reconstruction_report(report) == []

    chain = dict(report["reconstructed_chains"][0])
    chain["valid"] = False
    chain["chain_digest"] = ""

    mutated = dict(report)
    mutated["reconstructed_chains"] = [chain]

    assert validate_verification_execution_ledger_reconstruction_report(mutated) == []
    assert record["verification_execution_ledger_record_digest"] == chain["verification_execution_ledger_record_digest"]


def test_cli_reconstruct_receipts_prints_json_and_does_not_write(tmp_path: Path) -> None:
    _write_ledger_record(tmp_path, "receipt-ledger.json")
    before = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    result = CliRunner().invoke(
        ledger_app,
        [
            "reconstruct-receipts",
            "--target-repo",
            str(tmp_path),
        ],
    )
    after = sorted(path.relative_to(tmp_path) for path in tmp_path.rglob("*"))

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kind"] == VERIFICATION_EXECUTION_LEDGER_RECONSTRUCTION_REPORT_KIND
    assert data["valid"] is True
    assert data["summary"]["reconstructed_chain_count"] == 1
    assert before == after
