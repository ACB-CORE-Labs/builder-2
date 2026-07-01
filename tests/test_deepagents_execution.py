from __future__ import annotations

import copy
import json as json_lib
from datetime import datetime, timedelta, timezone
from pathlib import Path

from typer.testing import CliRunner

from builder_ii import deepagents_execution as execution_module
from builder_ii.artifact_index_records import (
    create_artifact_index_record,
    validate_artifact_index_record,
)
from builder_ii.config import load_settings
from builder_ii.deepagents_cli import deepagents_app
from builder_ii.deepagents_execution import (
    DEEPAGENTS_CHECKPOINT_KIND,
    DEEPAGENTS_EVIDENCE_BUNDLE_KIND,
    DEEPAGENTS_EXECUTION_APPROVAL_KIND,
    DEEPAGENTS_EXECUTION_CANDIDATE_KIND,
    DEEPAGENTS_EXECUTION_RECEIPT_KIND,
    DEEPAGENTS_REPLAY_REPORT_KIND,
    create_evidence_bundle_from_files,
    create_deepagents_execution_approval,
    create_deepagents_execution_candidate,
    replay_deepagents_run,
    resume_deepagents_approved_candidate,
    run_deepagents_approved_candidate,
    validate_deepagents_evidence_bundle,
    validate_deepagents_execution_approval_against_candidate,
    validate_deepagents_execution_candidate,
    validate_deepagents_execution_receipt,
    validate_deepagents_replay_report,
)
from builder_ii.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.deepagents_work_artifacts import create_deepagents_work_plan
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _work_plan_fixture(
    tmp_path: Path,
    *,
    task: str = "Map the governed protocol lane",
) -> tuple[dict, Path]:
    goal2 = build_goal2_assignment_fixture(tmp_path, task="Deepagents governed protocol lane")
    policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness = create_deepagents_readiness_artifact(mode="metadata_only")
    policy_path = _write(tmp_path / "deepagents-policy.json", policy)
    readiness_path = _write(tmp_path / "deepagents-readiness.json", readiness)
    work_plan = create_deepagents_work_plan(
        target="builder",
        task=task,
        orchestration_assignment_plan=goal2["artifacts"]["orchestration"],
        orchestration_assignment_dry_run=goal2["artifacts"]["dry_run"],
        deepagents_policy=policy,
        deepagents_readiness=readiness,
        proposed_subagents=["repo_mapper", "code_reviewer"],
        expected_outputs=["proposal-only results"],
        review_gates=["operator_review"],
    )
    work_plan_path = _write(tmp_path / "deepagents-work-plan.json", work_plan)
    return work_plan, work_plan_path


def _candidate_and_approval(tmp_path: Path) -> tuple[dict, Path, dict, Path]:
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    output_root = tmp_path / "runs"
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=output_root,
    )
    candidate_path = _write(tmp_path / "deepagents-candidate.json", candidate)
    approval = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=candidate_path,
        approval_actor="Joshua Shay",
        approval_reason="Approve deterministic protocol fake lane.",
    )
    approval_path = _write(tmp_path / "deepagents-approval.json", approval)
    return candidate, candidate_path, approval, approval_path


def test_candidate_and_approval_bind_to_work_plan(tmp_path: Path) -> None:
    candidate, _candidate_path, approval, _approval_path = _candidate_and_approval(tmp_path)

    assert candidate["kind"] == DEEPAGENTS_EXECUTION_CANDIDATE_KIND
    assert candidate["backend_mode"] == "protocol_fake"
    assert candidate["constructs_deepagents"] is False
    assert candidate["governance"]["native_deepagents_model_invocation"] == "DISABLED"
    assert validate_deepagents_execution_candidate(candidate) == []

    assert approval["kind"] == DEEPAGENTS_EXECUTION_APPROVAL_KIND
    assert approval["approval_state"] == "APPROVED_FOR_RUNNER_ONLY"
    assert approval["approval_enables_direct_deepagents"] is False
    assert validate_deepagents_execution_approval_against_candidate(approval, candidate) == []


def test_approval_rejects_candidate_digest_drift(tmp_path: Path) -> None:
    candidate, _candidate_path, approval, _approval_path = _candidate_and_approval(tmp_path)
    drifted = copy.deepcopy(candidate)
    drifted["task"] = "Different task"

    errors = validate_deepagents_execution_approval_against_candidate(approval, drifted)

    assert any("candidate_digest" in error or "candidate_ref" in error for error in errors)


def test_approval_expiry_blocks_runner(tmp_path: Path) -> None:
    candidate, _candidate_path, approval, _approval_path = _candidate_and_approval(tmp_path)
    expired = copy.deepcopy(approval)
    expired["expires_at"] = (
        datetime.now() - timedelta(minutes=1)
    ).replace(microsecond=0).isoformat()
    expired.pop("approval_digest")
    # Rebuild through the factory to keep the digest valid while expired.
    expired = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=_candidate_path,
        approval_actor="Joshua Shay",
        approval_reason="Expired approval for test.",
        expires_at=expired["expires_at"],
    )

    errors = validate_deepagents_execution_approval_against_candidate(
        expired, candidate, check_expiry=True
    )

    assert "approval has expired" in errors


def test_run_approved_golden_path_and_evidence_bundle_cli(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)
    output_dir = tmp_path / "runs" / "golden"

    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )

    assert summary["status"] == "COMPLETED"
    receipt_path = output_dir / "deepagents-execution-receipt.json"
    replay_path = output_dir / "deepagents-replay-report.json"
    receipt = json_lib.loads(receipt_path.read_text(encoding="utf-8"))
    replay = json_lib.loads(replay_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == DEEPAGENTS_EXECUTION_RECEIPT_KIND
    assert receipt["completed_subagents"] == ["repo_mapper", "code_reviewer"]
    assert validate_deepagents_execution_receipt(receipt) == []
    assert validate_deepagents_replay_report(replay) == []
    result_event = json_lib.loads(
        (output_dir / "events" / "event-0004-subagent_result_recorded.json").read_text(
            encoding="utf-8"
        )
    )
    assert result_event["payload_sha256"] == result_event["payload"]["result_digest"]

    runner = CliRunner()
    bundle_path = output_dir / "deepagents-evidence-bundle.json"
    result = runner.invoke(
        deepagents_app,
        [
            "evidence-bundle",
            "--candidate",
            str(candidate_path),
            "--approval",
            str(approval_path),
            "--envelope",
            str(output_dir / "deepagents-run-envelope.json"),
            "--receipt",
            str(receipt_path),
            "--event-ledger",
            str(output_dir / "deepagents-event-ledger.json"),
            "--replay-report",
            str(replay_path),
            "--output",
            str(bundle_path),
        ],
    )

    assert result.exit_code == 0, result.output
    bundle = json_lib.loads(bundle_path.read_text(encoding="utf-8"))
    assert bundle["kind"] == DEEPAGENTS_EVIDENCE_BUNDLE_KIND
    assert bundle["operator_summary"]["path"] == "candidate -> approval -> run-approved -> replay-run -> evidence-bundle"
    assert validate_deepagents_evidence_bundle(bundle) == []


def test_output_root_escape_fails_closed(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)

    try:
        run_deepagents_approved_candidate(
            candidate_path=candidate_path,
            approval_path=approval_path,
            output_dir=tmp_path / "outside-run",
        )
        assert False, "output root escape should fail"
    except ValueError as exc:
        assert "output_dir must be inside candidate.output_root" in str(exc)


def test_event_budget_fails_before_runtime_artifacts(tmp_path: Path) -> None:
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        max_events=2,
    )
    candidate_path = _write(tmp_path / "budget-candidate.json", candidate)
    approval = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=candidate_path,
        approval_actor="Joshua Shay",
        approval_reason="Exercise event budget guard.",
    )
    approval_path = _write(tmp_path / "budget-approval.json", approval)

    try:
        run_deepagents_approved_candidate(
            candidate_path=candidate_path,
            approval_path=approval_path,
            output_dir=tmp_path / "runs" / "too-small",
        )
        assert False, "event budget should fail before runtime artifacts"
    except ValueError as exc:
        assert "candidate.budgets.max_events is too small" in str(exc)
        assert not (tmp_path / "runs" / "too-small").exists()


def test_result_output_budget_truncates_with_digest(tmp_path: Path) -> None:
    work_plan, work_plan_path = _work_plan_fixture(
        tmp_path,
        task="Map bounded lane " + ("x" * 2000),
    )
    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        allowed_subagents=["repo_mapper"],
        max_output_bytes=768,
    )
    candidate_path = _write(tmp_path / "output-budget-candidate.json", candidate)
    approval = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=candidate_path,
        approval_actor="Joshua Shay",
        approval_reason="Exercise bounded result truncation.",
    )
    approval_path = _write(tmp_path / "output-budget-approval.json", approval)
    output_dir = tmp_path / "runs" / "truncated"

    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )
    result_event = json_lib.loads(
        (output_dir / "events" / "event-0004-subagent_result_recorded.json").read_text(
            encoding="utf-8"
        )
    )

    assert summary["status"] == "COMPLETED"
    assert result_event["payload"]["output_truncated"] is True
    assert result_event["payload"]["original_output_sha256"]
    assert result_event["payload"]["result_mode"] == "PROPOSAL_ONLY_TRUNCATED"


def test_optional_backend_requires_readiness_gate_for_candidate(tmp_path: Path) -> None:
    work_plan, work_plan_path = _work_plan_fixture(tmp_path)

    try:
        create_deepagents_execution_candidate(
            work_plan=work_plan,
            work_plan_path=work_plan_path,
            output_root=tmp_path / "runs",
            backend_mode="optional_deepagents",
            allowed_subagents=["repo_mapper"],
        )
        assert False, "optional backend candidate should require readiness gate"
    except ValueError as exc:
        assert "optional_deepagents requires --backend-readiness-gate" in str(exc)


def test_replay_detects_hash_chain_gap(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)
    output_dir = tmp_path / "runs" / "replay-gap"
    run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )
    second_event = output_dir / "events" / "event-0002-backend_selected.json"
    data = json_lib.loads(second_event.read_text(encoding="utf-8"))
    data["previous_event_sha256"] = "0" * 64
    second_event.write_text(json_lib.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    replay = replay_deepagents_run(
        events_dir=output_dir / "events",
        output=output_dir / "bad-replay.json",
    )

    assert replay["valid"] is False
    assert any("previous_event_sha256" in error for error in replay["errors"])

    runner = CliRunner()
    cli_output = output_dir / "bad-replay-cli.json"
    result = runner.invoke(
        deepagents_app,
        [
            "replay-run",
            "--events-dir",
            str(output_dir / "events"),
            "--output",
            str(cli_output),
        ],
    )
    assert result.exit_code != 0
    assert json_lib.loads(cli_output.read_text(encoding="utf-8"))["valid"] is False


def test_checkpoint_resume_cli_completes_same_candidate(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)
    output_dir = tmp_path / "runs" / "resume"
    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
        stop_after=1,
    )
    checkpoint_path = output_dir / "deepagents-checkpoint.json"
    checkpoint = json_lib.loads(checkpoint_path.read_text(encoding="utf-8"))
    assert summary["status"] == "CHECKPOINTED"
    assert checkpoint["kind"] == DEEPAGENTS_CHECKPOINT_KIND
    assert checkpoint["remaining_subagents"] == ["code_reviewer"]

    runner = CliRunner()
    result = runner.invoke(
        deepagents_app,
        [
            "resume-approved",
            "--candidate",
            str(candidate_path),
            "--approval",
            str(approval_path),
            "--checkpoint",
            str(checkpoint_path),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0, result.output
    receipt = json_lib.loads((output_dir / "deepagents-execution-receipt.json").read_text(encoding="utf-8"))
    replay = json_lib.loads((output_dir / "deepagents-replay-report.json").read_text(encoding="utf-8"))
    assert receipt["receipt_state"] == "COMPLETED"
    assert replay["kind"] == DEEPAGENTS_REPLAY_REPORT_KIND
    assert replay["completed_subagents"] == ["repo_mapper", "code_reviewer"]

    second_result = runner.invoke(
        deepagents_app,
        [
            "resume-approved",
            "--candidate",
            str(candidate_path),
            "--approval",
            str(approval_path),
            "--checkpoint",
            str(checkpoint_path),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert second_result.exit_code != 0
    assert "run is already terminal; resume is not allowed" in second_result.output


def test_resume_rejects_checkpoint_events_dir_escape(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)
    output_dir = tmp_path / "runs" / "resume-escape"
    run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
        stop_after=1,
    )
    checkpoint_path = output_dir / "deepagents-checkpoint.json"
    checkpoint = json_lib.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["events_dir"] = str(tmp_path / "outside-events")
    checkpoint.pop("checkpoint_digest")
    checkpoint = execution_module._attach_digest(checkpoint, "checkpoint_digest")
    bad_checkpoint_path = _write(tmp_path / "bad-checkpoint.json", checkpoint)

    try:
        resume_deepagents_approved_candidate(
            candidate_path=candidate_path,
            approval_path=approval_path,
            checkpoint_path=bad_checkpoint_path,
            output_dir=output_dir,
        )
        assert False, "checkpoint events_dir escape should fail"
    except ValueError as exc:
        assert "checkpoint.events_dir must be inside candidate.output_root" in str(exc)


def test_resume_failure_records_failed_receipt(monkeypatch, tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)
    output_dir = tmp_path / "runs" / "resume-failure"
    run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
        stop_after=1,
    )

    class FailingBackend:
        name = "protocol_fake"

        def run_subagent(self, *, subagent_profile: str, task: str) -> dict:
            raise RuntimeError("resume backend failure")

    monkeypatch.setattr(execution_module, "backend_for", lambda mode, **_kwargs: FailingBackend())

    summary = resume_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        checkpoint_path=output_dir / "deepagents-checkpoint.json",
        output_dir=output_dir,
    )
    receipt = json_lib.loads((output_dir / "deepagents-execution-receipt.json").read_text(encoding="utf-8"))
    failed_event = json_lib.loads(
        (output_dir / "events" / "event-0008-run_failed.json").read_text(encoding="utf-8")
    )

    assert summary["status"] == "FAILED"
    assert receipt["receipt_state"] == "FAILED"
    assert failed_event["payload"]["error"] == "resume backend failure"


def test_repeated_runs_get_distinct_session_ids(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)

    first = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=tmp_path / "runs" / "first",
    )
    second = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=tmp_path / "runs" / "second",
    )

    assert first["session_id"] != second["session_id"]


def test_run_approved_rejects_existing_event_directory(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)
    output_dir = tmp_path / "runs" / "duplicate-output"
    run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )

    try:
        run_deepagents_approved_candidate(
            candidate_path=candidate_path,
            approval_path=approval_path,
            output_dir=output_dir,
        )
        assert False, "existing event directory should fail closed"
    except ValueError as exc:
        assert "already contains deepagents events" in str(exc)


def test_evidence_bundle_rejects_mixed_run_chain(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)
    first_dir = tmp_path / "runs" / "evidence-first"
    second_dir = tmp_path / "runs" / "evidence-second"
    run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=first_dir,
    )
    run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=second_dir,
    )

    try:
        create_evidence_bundle_from_files(
            candidate_path=candidate_path,
            approval_path=approval_path,
            envelope_path=first_dir / "deepagents-run-envelope.json",
            receipt_path=first_dir / "deepagents-execution-receipt.json",
            event_ledger_path=first_dir / "deepagents-event-ledger.json",
            replay_report_path=second_dir / "deepagents-replay-report.json",
            output_path=first_dir / "bad-evidence-bundle.json",
        )
        assert False, "mixed evidence chain should fail"
    except ValueError as exc:
        assert "invalid deepagents evidence chain" in str(exc)


def test_generated_execution_artifacts_are_indexable(tmp_path: Path) -> None:
    _candidate, candidate_path, _approval, approval_path = _candidate_and_approval(tmp_path)
    output_dir = tmp_path / "runs" / "indexed"
    run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
    )

    index = create_artifact_index_record(output_dir, recursive=True)

    assert index["complete"] is True, index["artifacts"]
    assert index["counts"]["unknown"] == 0
    assert index["counts"]["invalid"] == 0
    assert validate_artifact_index_record(index) == []
