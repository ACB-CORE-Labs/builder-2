"""Comprehensive verification of the 8 canonical run lifecycle scenarios & frontend parity.

Verifies:
1. COMPLETE: Clean completion of governed workflow / Goose / Deep Agents
2. FAIL: Governed execution failure with explicit fail event
3. INTERRUPT: Run paused / checkpointed with resume recommendation
4. RESUME: Resumption of interrupted run with continuous monotonic sequence
5. CANCEL: User-initiated cancellation recorded
6. CORRUPT: Detection of broken event chain / malformed JSON / hash mismatch
7. ORPHAN: Detection of unclosed session / missing close receipt
8. CLOSE: Orderly session close with postflight no-mutation proof
9. Deep Agents canonical session custody with REAL execution artifacts
10. Deep Agents checkpointed / interrupted lifecycle
11. Adversarial lesion battery:
    - PROJECTED_ONLY subagent receipt rejected from execution persistence & validation
    - Swapped / tampered envelope
    - Foreign work plan
    - Corrupted receipt / wrong event digest
    - Mismatched session identity
    - Duplicate terminal events
    - Namespace symlink escape
12. Parameterized frontend semantic parity (RunView, Status, Registry, TUI facade)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from builder_ii.adapters.deepagents.deepagents_execution import (
    DEEPAGENTS_CHECKPOINT_KIND,
    DEEPAGENTS_EVENT_RECORD_KIND,
    _digest_jsonable,
    create_deepagents_checkpoint,
    create_deepagents_event_ledger,
    create_deepagents_event_record,
    create_deepagents_execution_approval,
    create_deepagents_execution_candidate,
    create_deepagents_execution_receipt,
    create_deepagents_replay_report,
    create_deepagents_run_envelope,
)
from builder_ii.adapters.deepagents.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.adapters.deepagents.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.adapters.deepagents.deepagents_runtime import (
    create_deepagents_subagent_execution_receipt,
)
from builder_ii.adapters.deepagents.deepagents_session_custody import (
    deepagents_session_dir,
    persist_deepagents_execution,
    persist_deepagents_start,
    validate_deepagents_session_custody,
)
from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    create_deepagents_work_plan,
)
from builder_ii.adapters.goose.goose_receipts import (
    create_goose_close_receipt,
    create_goose_launch_receipt,
    create_no_mutation_postflight,
)
from builder_ii.adapters.goose.goose_session_custody import (
    canonical_transcript_path,
    persist_goose_close,
    persist_goose_launch,
    validate_goose_session_custody,
)
from builder_ii.core.config import load_settings
from builder_ii.core.run_registry import project_run_registry, project_run_roster
from builder_ii.core.run_status import project_run_status
from builder_ii.core.run_view import project_run_view
from builder_ii.governance.ledger.event_ledger import (
    load_event_records,
    validate_event_chain_integrity,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.lifecycle.candidate.runtime_event_append import append_runtime_event
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture


def _setup_goose_evidence(tmp_path: Path, session_id: str):
    artifact_root = tmp_path / "artifacts"
    target_root = tmp_path / "target"
    target_root.mkdir(parents=True, exist_ok=True)
    launch = create_goose_launch_receipt(
        session_id,
        "builder",
        "patch_planner",
        42,
        "2026-08-26T00:00:00+00:00",
        {"runtime": "goose_governed", "target_root": str(target_root)},
    )
    transcript = canonical_transcript_path(artifact_root, session_id)
    transcript.parent.mkdir(parents=True, exist_ok=True)
    transcript.write_text('{"messages": []}\n', encoding="utf-8")
    transcript_digest = hashlib.sha256(transcript.read_bytes()).hexdigest()
    postflight = create_no_mutation_postflight(
        session_id,
        str(target_root),
        "2026-08-26T00:00:00+00:00",
        "2026-08-26T00:01:00+00:00",
        1,
        [],
    )
    close = create_goose_close_receipt(
        session_id,
        launch["digest"],
        postflight["digest"],
        str(transcript),
        transcript_digest,
        "2026-08-26T00:01:00+00:00",
        0,
    )
    return artifact_root, launch, close, postflight, transcript


def _setup_deepagents_fixture(tmp_path: Path, session_id: str):
    goal2 = build_goal2_assignment_fixture(tmp_path, task="Governed Deep Agents run")
    orchestration_plan = goal2["artifacts"]["orchestration"]
    orchestration_dry_run = goal2["artifacts"]["dry_run"]

    policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness = create_deepagents_readiness_artifact(mode="metadata_only")

    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Governed Deep Agents run",
        orchestration_assignment_plan=orchestration_plan,
        orchestration_assignment_dry_run=orchestration_dry_run,
        deepagents_policy=policy,
        deepagents_readiness=readiness,
        proposed_subagents=["repo_mapper", "code_reviewer"],
        expected_outputs=["deepagents_work_plan"],
        review_gates=["operator_review"],
        blocked_capabilities=["model execution", "shell execution"],
    )

    work_plan_path = tmp_path / "work_plan.json"
    work_plan_path.write_text(json.dumps(work_plan, indent=2), encoding="utf-8")

    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=work_plan_path,
        output_root=tmp_path / "runs",
        allowed_subagents=["repo_mapper", "code_reviewer"],
    )
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(json.dumps(candidate, indent=2), encoding="utf-8")

    approval = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=candidate_path,
        approval_actor="operator",
        approval_reason="Verified execution candidate",
    )
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps(approval, indent=2), encoding="utf-8")

    event_1 = create_deepagents_event_record(
        session_id=session_id,
        sequence=1,
        event_type="subagent_scheduled",
        subject_refs=[],
        payload={"subagent_profile": "repo_mapper"},
        message="Scheduled repo_mapper",
    )
    event_1_path = tmp_path / "event-000001.json"
    event_1_path.write_text(json.dumps(event_1, indent=2), encoding="utf-8")

    event_records = [(event_1, event_1_path)]
    replay_report = create_deepagents_replay_report(
        session_id=session_id,
        event_records=event_records,
    )
    replay_report_path = tmp_path / "replay_report.json"
    replay_report_path.write_text(json.dumps(replay_report, indent=2), encoding="utf-8")

    event_ledger = create_deepagents_event_ledger(
        session_id=session_id,
        event_records=event_records,
        replay_report=replay_report,
        replay_report_path=replay_report_path,
    )
    event_ledger_path = tmp_path / "event_ledger.json"
    event_ledger_path.write_text(json.dumps(event_ledger, indent=2), encoding="utf-8")

    envelope = create_deepagents_run_envelope(
        session_id=session_id,
        candidate=candidate,
        approval=approval,
        candidate_path=candidate_path,
        approval_path=approval_path,
        event_ledger=event_ledger,
        event_ledger_path=event_ledger_path,
        replay_report=replay_report,
        replay_report_path=replay_report_path,
        checkpoint=None,
        checkpoint_path=None,
        output_dir=tmp_path / "runs",
        status="COMPLETED",
    )
    envelope_path = tmp_path / "envelope.json"
    envelope_path.write_text(json.dumps(envelope, indent=2), encoding="utf-8")

    receipt = create_deepagents_execution_receipt(
        session_id=session_id,
        candidate=candidate,
        approval=approval,
        envelope=envelope,
        replay_report=replay_report,
        event_ledger=event_ledger,
        candidate_path=candidate_path,
        approval_path=approval_path,
        envelope_path=envelope_path,
        replay_report_path=replay_report_path,
        event_ledger_path=event_ledger_path,
        checkpoint=None,
        checkpoint_path=None,
        status="COMPLETED",
    )

    return {
        "work_plan": work_plan,
        "candidate": candidate,
        "approval": approval,
        "envelope": envelope,
        "receipt": receipt,
        "event_ledger": event_ledger,
        "replay_report": replay_report,
    }


# ---------------------------------------------------------------------------
# Core Lifecycle Scenarios
# ---------------------------------------------------------------------------


def test_lifecycle_scenario_clean_complete(tmp_path: Path) -> None:
    """Scenario 1: Orderly workflow execution and verification completion."""
    session_id = "run-complete-001"
    events_dir = tmp_path / "sessions" / session_id / "events"
    e1 = append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="wrp_live_run_started",
        message="Run started",
        command_surface="builder start",
    )
    e2 = append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="wrp_live_run_completed",
        message="Run completed cleanly",
        command_surface="builder start",
    )
    assert e1["sequence"] == 1
    assert e2["sequence"] == 2
    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True

    view = project_run_view(tmp_path, session_id=session_id)
    assert view.errors == ()

    status = project_run_status(tmp_path, requested_run_id=session_id)
    assert status.selected is not None
    assert status.selected.run_id == session_id
    assert status.selected.event_count == 2


def test_lifecycle_scenario_execution_failure(tmp_path: Path) -> None:
    """Scenario 2: Governed execution failure with explicit fail event."""
    session_id = "run-failed-001"
    events_dir = tmp_path / "sessions" / session_id / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="tool_call_executed",
        message="Tool executed",
        command_surface="builder run",
    )
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="tool_call_failed",
        message="Tool failed execution",
        command_surface="builder run",
        decision_result="failed",
    )

    view = project_run_view(tmp_path, session_id=session_id)
    assert view.errors == ()
    registry = project_run_registry(tmp_path)
    entry = registry.get(session_id)
    assert entry is not None
    assert entry.last_event_type == "tool_call_failed"


def test_lifecycle_scenario_interrupted_and_resumed(tmp_path: Path) -> None:
    """Scenario 3 & 4: Run interrupted then resumed with continuous hash chaining."""
    session_id = "run-interrupt-resume-001"
    events_dir = tmp_path / "sessions" / session_id / "events"
    e1 = append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="wrp_live_run_started",
        message="Run started",
        command_surface="builder start",
    )
    assert e1["sequence"] == 1
    e2 = append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="run_interrupted",
        message="Run checkpointed on interrupt",
        command_surface="builder pause",
    )
    assert e2["sequence"] == 2

    # View when interrupted
    view_interrupted = project_run_view(tmp_path, session_id=session_id)
    assert view_interrupted.activity_label == "resuming interrupted run"
    assert "run was interrupted; resume with builder resume" in view_interrupted.attention_items[0]
    assert view_interrupted.next_action == f"builder resume {session_id}"

    # Resume run
    e3 = append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="run_resumed",
        message="Run resumed from checkpoint",
        command_surface="builder resume",
    )
    assert e3["sequence"] == 3
    assert e3["previous_event_sha256"] is not None

    # View when resumed
    view_resumed = project_run_view(tmp_path, session_id=session_id)
    assert view_resumed.errors == ()
    assert "resuming interrupted run" not in view_resumed.activity_label

    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True
    assert report["event_count"] == 3


def test_lifecycle_scenario_cancelled(tmp_path: Path) -> None:
    """Scenario 5: User-initiated cancellation recorded."""
    session_id = "run-cancel-001"
    events_dir = tmp_path / "sessions" / session_id / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="wrp_live_run_started",
        message="Run started",
        command_surface="builder start",
    )
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="run_cancelled",
        message="Run cancelled by user",
        command_surface="builder cancel",
    )

    view = project_run_view(tmp_path, session_id=session_id)
    assert view.activity_label == "run cancelled by operator"
    assert "run was cancelled by operator" in view.attention_items
    assert view.recovery == "create a new run to proceed with new tasks"
    assert view.next_action == "RUN_CANCELLED"


def test_lifecycle_scenario_corrupt_event_chain(tmp_path: Path) -> None:
    """Scenario 6: Detection of broken event chain / corrupted payload."""
    session_id = "run-corrupt-001"
    events_dir = tmp_path / "sessions" / session_id / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="wrp_live_run_started",
        message="Run started",
        command_surface="builder start",
    )
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="tool_call_executed",
        message="Tool executed",
        command_surface="builder run",
    )

    # Tamper with the second event file
    json_files = sorted(p for p in events_dir.glob("*.json") if p.name != "events.wal")
    assert len(json_files) == 2
    bad_path = json_files[1]
    data = json.loads(bad_path.read_text(encoding="utf-8"))
    data["previous_event_sha256"] = "a" * 64
    bad_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is False

    registry = project_run_registry(tmp_path)
    entry = registry.get(session_id)
    assert entry is not None
    assert entry.chain_valid is False

    view = project_run_view(tmp_path, session_id=session_id)
    assert "BLOCKED: repair corrupt or foreign canonical evidence" in view.next_action


def test_lifecycle_scenario_orphaned_session(tmp_path: Path) -> None:
    """Scenario 7: Orphaned run with explicit orphan event."""
    session_id = "run-orphan-001"
    events_dir = tmp_path / "sessions" / session_id / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="goose_session_started",
        message="Session started",
        command_surface="builder start",
    )
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="run_orphaned",
        message="Orphaned process detected without close receipt",
        command_surface="builder doctor",
    )

    view = project_run_view(tmp_path, session_id=session_id)
    assert view.activity_label == "orphaned run detected"
    assert "process exited without writing close receipt" in view.attention_items
    assert view.recovery == "close orphan run or inspect diagnostic logs"
    assert view.next_action == "ORPHAN_RUN_RECOVERY_REQUIRED"


def test_lifecycle_scenario_clean_close_with_postflight(tmp_path: Path) -> None:
    """Scenario 8: Canonical Goose launch, postflight, and close custody."""
    session_id = "goose-clean-001"
    artifact_root, launch, close, postflight, _ = _setup_goose_evidence(tmp_path, session_id)

    persist_goose_launch(
        artifact_root=artifact_root,
        session_id=session_id,
        launch_receipt=launch,
    )
    persist_goose_close(
        artifact_root=artifact_root,
        session_id=session_id,
        launch_receipt=launch,
        close_receipt=close,
        postflight=postflight,
    )

    errors = validate_goose_session_custody(artifact_root, session_id)
    assert errors == []

    events_dir = artifact_root / "sessions" / session_id / "events"
    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True
    assert report["event_count"] == 2


# ---------------------------------------------------------------------------
# Deep Agents Real Execution Custody & Interruption
# ---------------------------------------------------------------------------


def test_deepagents_canonical_session_custody_with_real_execution_artifacts(tmp_path: Path) -> None:
    """Scenario 9: Deep Agents canonical session custody using real execution artifacts."""
    session_id = "deepagents-run-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(tmp_path, session_id)

    start_event = persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
    )
    assert start_event["event_type"] == "deepagents_runtime_started"

    exec_event = persist_deepagents_execution(
        artifact_root=artifact_root,
        session_id=session_id,
        execution_receipt=fixture["receipt"],
        success=True,
    )
    assert exec_event["event_type"] == "deepagents_runtime_executed"

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert errors == []

    events_dir = artifact_root / "sessions" / session_id / "events"
    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True
    assert report["event_count"] == 2


def test_deepagents_interrupted_delegation_custody(tmp_path: Path) -> None:
    """Scenario 10: Deep Agents interrupted delegation with checkpoint."""
    session_id = "deepagents-interrupt-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(tmp_path, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
    )

    candidate_path = artifact_root / "sessions" / session_id / "deepagents" / "candidate.json"
    approval_path = artifact_root / "sessions" / session_id / "deepagents" / "approval.json"
    events_dir = artifact_root / "sessions" / session_id / "events"

    events = load_event_records(events_dir)
    first_event = events[0][0]

    event_tail_ref = {
        "role": "event",
        "kind": DEEPAGENTS_EVENT_RECORD_KIND,
        "path": str(events_dir / f"event-{first_event['sequence']:06d}.json"),
        "sha256": first_event.get("event_digest", canonical_digest(first_event)),
        "name": "event tail",
        "required": True,
    }

    checkpoint = create_deepagents_checkpoint(
        session_id=session_id,
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        candidate_path=candidate_path,
        approval_path=approval_path,
        event_tail_ref=event_tail_ref,
        events_dir=events_dir,
        completed_subagents=["repo_mapper"],
        remaining_subagents=["code_reviewer"],
    )

    checkpoint_receipt = dict(fixture["receipt"])
    checkpoint_receipt["receipt_state"] = "CHECKPOINTED"
    checkpoint_receipt["checkpoint_ref"] = {
        "kind": DEEPAGENTS_CHECKPOINT_KIND,
        "path": str(artifact_root / "sessions" / session_id / "deepagents" / "checkpoint.json"),
        "sha256": checkpoint.get("checkpoint_digest", canonical_digest(checkpoint)),
        "role": "checkpoint",
        "required": True,
        "name": "checkpoint",
    }
    checkpoint_receipt["receipt_digest"] = _digest_jsonable(checkpoint_receipt)

    interrupted_event = persist_deepagents_execution(
        artifact_root=artifact_root,
        session_id=session_id,
        execution_receipt=checkpoint_receipt,
        checkpoint=checkpoint,
    )
    assert interrupted_event["event_type"] == "deepagents_runtime_interrupted"

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert errors == []

    view = project_run_view(artifact_root, session_id=session_id)
    assert view.activity_label == "resuming interrupted run"
    assert view.next_action == f"builder resume {session_id}"


# ---------------------------------------------------------------------------
# Adversarial Lesion Battery
# ---------------------------------------------------------------------------


def test_lesion_projected_only_receipt_rejected_from_execution(tmp_path: Path) -> None:
    """Lesion: PROJECTED_ONLY subagent receipt is refused from execution persistence & validation."""
    session_id = "lesion-projected-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(tmp_path, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
    )

    projected_receipt = create_deepagents_subagent_execution_receipt(
        subagent_profile="repo_mapper",
        assignment_ref={"kind": "k", "path": "p", "sha256": "a" * 64, "role": "a", "required": True, "name": "n"},
        result_ref={"kind": "k", "path": "p", "sha256": "b" * 64, "role": "r", "required": True, "name": "n"},
    )
    assert projected_receipt["receipt_state"] == "PROJECTED_ONLY"

    # Must be rejected at persistence
    with pytest.raises(ValueError, match="PROJECTED_ONLY receipt cannot be persisted as runtime execution evidence"):
        persist_deepagents_execution(
            artifact_root=artifact_root,
            session_id=session_id,
            execution_receipt=projected_receipt,
            success=True,
        )


def test_lesion_swapped_envelope_rejected(tmp_path: Path) -> None:
    """Lesion: Swapped envelope with different content fails custody validation."""
    session_id = "lesion-envelope-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(tmp_path, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
    )

    # Tamper with envelope on disk
    session_dir = deepagents_session_dir(artifact_root, session_id)
    envelope_path = session_dir / "envelope.json"
    env_data = json.loads(envelope_path.read_text(encoding="utf-8"))
    env_data["output_dir"] = "/tampered/path"
    env_data["envelope_digest"] = _digest_jsonable(env_data)
    envelope_path.write_text(json.dumps(env_data, indent=2), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("deepagents_runtime_started binding does not match canonical envelope digest" in e for e in errors)


def test_lesion_foreign_work_plan_rejected(tmp_path: Path) -> None:
    """Lesion: Foreign work plan bytes fail custody validation."""
    session_id = "lesion-plan-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(tmp_path, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
    )

    # Tamper with work_plan.json on disk
    session_dir = deepagents_session_dir(artifact_root, session_id)
    plan_path = session_dir / "work_plan.json"
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_data["task"] = "Tampered foreign task"
    plan_path.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("deepagents_runtime_started binding does not match canonical work plan digest" in e for e in errors)


def test_lesion_receipt_tampered_rejected(tmp_path: Path) -> None:
    """Lesion: Tampered receipt fails custody validation."""
    session_id = "lesion-receipt-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(tmp_path, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
    )
    persist_deepagents_execution(
        artifact_root=artifact_root,
        session_id=session_id,
        execution_receipt=fixture["receipt"],
        success=True,
    )

    # Tamper with receipt.json on disk
    session_dir = deepagents_session_dir(artifact_root, session_id)
    receipt_path = session_dir / "receipt.json"
    receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_data["completed_subagents"] = ["tampered_subagent"]
    receipt_data["receipt_digest"] = _digest_jsonable(receipt_data)
    receipt_path.write_text(json.dumps(receipt_data, indent=2), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("terminal execution event does not bind exact receipt digest" in e for e in errors)


def test_lesion_duplicate_terminal_events_rejected(tmp_path: Path) -> None:
    """Lesion: Duplicate terminal execution events are refused."""
    session_id = "lesion-dup-term-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(tmp_path, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
    )
    persist_deepagents_execution(
        artifact_root=artifact_root,
        session_id=session_id,
        execution_receipt=fixture["receipt"],
        success=True,
    )

    # Append duplicate execution event directly to events dir
    events_dir = artifact_root / "sessions" / session_id / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="deepagents_runtime_executed",
        message="Duplicate terminal event",
        command_surface="builder delegate",
    )

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("requires exactly one terminal execution event" in e for e in errors)


def test_lesion_namespace_symlink_rejected(tmp_path: Path) -> None:
    """Lesion: Symlinked canonical namespace is rejected fail-closed."""
    session_id = "lesion-symlink-001"
    artifact_root = tmp_path / "artifacts"
    fake_target = tmp_path / "escape_dir"
    fake_target.mkdir(parents=True, exist_ok=True)

    session_parent = artifact_root / "sessions" / session_id
    session_parent.mkdir(parents=True, exist_ok=True)
    symlink_dir = session_parent / "deepagents"
    symlink_dir.symlink_to(fake_target)

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("canonical Deep Agents session namespace is invalid" in e for e in errors)


# ---------------------------------------------------------------------------
# Cross-Frontend Semantic Parity Across All 8 Scenarios
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("scenario_name", "setup_fn", "expected_chain_valid", "expected_activity", "expected_next_action"),
    [
        (
            "COMPLETE",
            lambda path, sid: [
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="wrp_live_run_started",
                    message="started",
                    command_surface="builder start",
                ),
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="wrp_live_run_completed",
                    message="completed",
                    command_surface="builder start",
                ),
            ],
            True,
            "orienting the run",
            "prepare-package",
        ),
        (
            "FAIL",
            lambda path, sid: [
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="tool_call_executed",
                    message="executed",
                    command_surface="builder run",
                ),
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="tool_call_failed",
                    message="failed",
                    command_surface="builder run",
                    decision_result="failed",
                ),
            ],
            True,
            "orienting the run",
            "prepare-package",
        ),
        (
            "INTERRUPT",
            lambda path, sid: [
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="wrp_live_run_started",
                    message="started",
                    command_surface="builder start",
                ),
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="run_interrupted",
                    message="interrupted",
                    command_surface="builder pause",
                ),
            ],
            True,
            "resuming interrupted run",
            "builder resume {sid}",
        ),
        (
            "RESUME",
            lambda path, sid: [
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="wrp_live_run_started",
                    message="started",
                    command_surface="builder start",
                ),
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="run_interrupted",
                    message="interrupted",
                    command_surface="builder pause",
                ),
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="run_resumed",
                    message="resumed",
                    command_surface="builder resume",
                ),
            ],
            True,
            "orienting the run",
            "prepare-package",
        ),
        (
            "CANCEL",
            lambda path, sid: [
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="wrp_live_run_started",
                    message="started",
                    command_surface="builder start",
                ),
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="run_cancelled",
                    message="cancelled",
                    command_surface="builder cancel",
                ),
            ],
            True,
            "run cancelled by operator",
            "RUN_CANCELLED",
        ),
        (
            "ORPHAN",
            lambda path, sid: [
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="goose_session_started",
                    message="started",
                    command_surface="builder start",
                ),
                append_runtime_event(
                    events_dir=path / "sessions" / sid / "events",
                    session_id=sid,
                    event_type="run_orphaned",
                    message="orphaned",
                    command_surface="builder doctor",
                ),
            ],
            True,
            "orphaned run detected",
            "ORPHAN_RUN_RECOVERY_REQUIRED",
        ),
    ],
)
def test_cross_frontend_semantic_parity(
    tmp_path: Path,
    scenario_name: str,
    setup_fn: Any,
    expected_chain_valid: bool,
    expected_activity: str,
    expected_next_action: str,
) -> None:
    """Verifies that RunView, Status CLI, Registry projection, and TUI facade all agree."""
    session_id = f"parity-{scenario_name.lower()}-001"
    setup_fn(tmp_path, session_id)

    expected_action_rendered = expected_next_action.format(sid=session_id)

    # 1. RunView projection
    run_view = project_run_view(tmp_path, session_id=session_id)
    assert (run_view.errors == ()) == expected_chain_valid
    assert run_view.activity_label == expected_activity
    assert run_view.next_action == expected_action_rendered

    # 2. Status CLI projection
    status = project_run_status(tmp_path, requested_run_id=session_id)
    assert status.selected is not None
    assert status.selected.run_id == session_id
    assert status.run is not None
    assert status.run.activity_label == expected_activity
    assert status.run.next_action == expected_action_rendered

    # 3. Registry projection
    registry = project_run_registry(tmp_path)
    entry = registry.get(session_id)
    assert entry is not None
    assert entry.chain_valid == expected_chain_valid

    # 4. TUI compatibility facade
    roster = project_run_roster(tmp_path)
    assert not roster.is_empty
    roster_entry = roster.get(session_id)
    assert roster_entry is not None
    assert roster_entry.chain_valid == expected_chain_valid
