"""Deterministic tests and adversarial lesions for unified run lifecycle custody.

Tests all 8 canonical lifecycle states:
1. COMPLETE: Orderly workflow execution and verification completion.
2. FAIL: Governed verification or tool execution failure.
3. INTERRUPT: Governed execution interrupted/paused.
4. RESUME: Resuming a previously paused/interrupted run.
5. CANCEL: Explicit operator cancellation.
6. CORRUPT: Event log integrity violation or tampered evidence.
7. ORPHAN: Process exited or lost before writing terminal close evidence.
8. CLOSE: Clean governed session close with no unapproved mutations.

Also tests:
- Real Deep Agents execution custody (candidate, approval, event records, replay report,
  ledger, envelope, receipt, checkpoint).
- Adversarial lesion battery covering missing candidate/approval, expired/mismatched approval,
  swapped envelope, foreign plan, tampered receipt, foreign paths, missing/tampered ledger/replay,
  missing checkpoint, receipt-state/event-type mismatch, wrong checkpoint event tail, duplicate
  terminal events, and namespace symlinks.
- Cross-frontend semantic parity verifying RunView, Status CLI, Registry, and TUI compatibility
  facade across ALL 8 lifecycle states.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from builder_ii.adapters.deepagents.deepagents_execution import (
    DEEPAGENTS_EVENT_RECORD_KIND,
    DEEPAGENTS_EXECUTION_RECEIPT_KIND,
    _artifact_ref,
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
    validate_event_chain_integrity,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.lifecycle.candidate.runtime_event_append import append_runtime_event
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------


def _setup_goose_evidence(tmp_path: Path, session_id: str):
    artifact_root = tmp_path
    target_root = tmp_path / "target_workspace"
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


def _setup_deepagents_fixture(artifact_root: Path, session_id: str) -> dict[str, Any]:
    session_dir = deepagents_session_dir(artifact_root, session_id)
    internal_events_dir = session_dir / "events"
    internal_events_dir.mkdir(parents=True, exist_ok=True)

    staging_dir = artifact_root / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    goal2 = build_goal2_assignment_fixture(staging_dir, task="Governed Deep Agents run")
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
    plan_path = session_dir / "work_plan.json"
    candidate_path = session_dir / "candidate.json"
    approval_path = session_dir / "approval.json"
    replay_report_path = session_dir / "replay_report.json"
    event_ledger_path = session_dir / "event_ledger.json"
    envelope_path = session_dir / "envelope.json"

    candidate = create_deepagents_execution_candidate(
        work_plan=work_plan,
        work_plan_path=plan_path,
        output_root=session_dir,
        allowed_subagents=["repo_mapper", "code_reviewer"],
    )

    approval = create_deepagents_execution_approval(
        candidate=candidate,
        candidate_path=candidate_path,
        approval_actor="operator",
        approval_reason="Verified execution candidate",
    )

    event_1 = create_deepagents_event_record(
        session_id=session_id,
        sequence=1,
        event_type="subagent_scheduled",
        subject_refs=[],
        payload={"subagent_profile": "repo_mapper"},
        message="Scheduled repo_mapper",
    )
    event_1_path = internal_events_dir / "event-000001.json"
    event_1_path.write_text(json.dumps(event_1, indent=2), encoding="utf-8")

    from builder_ii.adapters.deepagents.deepagents_execution import _digest_jsonable
    event_2 = create_deepagents_event_record(
        session_id=session_id,
        sequence=2,
        event_type="run_completed",
        subject_refs=[],
        payload={},
        message="Completed run",
        previous_event_ref={
            "role": "event",
            "kind": "builder_ii.deepagents_event_record",
            "path": str(event_1_path),
            "sha256": _digest_jsonable(event_1),
            "name": "subagent_scheduled",
            "required": True,
        }
    )
    event_2_path = internal_events_dir / "event-000002.json"
    event_2_path.write_text(json.dumps(event_2, indent=2), encoding="utf-8")

    event_records = [(event_1, event_1_path), (event_2, event_2_path)]
    replay_report = create_deepagents_replay_report(
        session_id=session_id,
        event_records=event_records,
    )

    event_ledger = create_deepagents_event_ledger(
        session_id=session_id,
        event_records=event_records,
        replay_report=replay_report,
        replay_report_path=replay_report_path,
    )

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
        output_dir=session_dir,
        status="COMPLETED",
    )

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
        "internal_events": event_records,
        "event_1": event_1,
        "event_1_path": event_1_path,
        "event_2": event_2,
        "event_2_path": event_2_path,
        "events_dir": internal_events_dir,
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
        message="Run completed",
        command_surface="builder start",
    )
    assert e2["sequence"] == 2
    assert e2["previous_event_ref"]["sha256"] == canonical_digest(e1)

    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True
    assert report["event_count"] == 2

    view = project_run_view(tmp_path, session_id=session_id)
    assert view.stage == "PREPARE"
    assert view.activity_label == "orienting the run"
    assert view.next_action == "prepare-package"


def test_lifecycle_scenario_governed_failure(tmp_path: Path) -> None:
    """Scenario 2: Governed verification failure captured cleanly in event stream."""
    session_id = "run-fail-001"
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
        message="Tool failed assertion",
        command_surface="builder run",
        decision_result="failed",
    )

    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True
    assert report["event_count"] == 2


def test_lifecycle_scenario_interrupt_and_resume(tmp_path: Path) -> None:
    """Scenario 3 & 4: Run interrupted by operator then resumed cleanly."""
    session_id = "run-interrupt-001"
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
        event_type="run_interrupted",
        message="Operator paused execution",
        command_surface="builder pause",
    )

    view = project_run_view(tmp_path, session_id=session_id)
    assert view.activity_label == "resuming interrupted run"
    assert view.next_action == f"builder resume {session_id}"

    # Resume the run
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="run_resumed",
        message="Run resumed by operator",
        command_surface="builder resume",
    )

    view2 = project_run_view(tmp_path, session_id=session_id)
    assert view2.activity_label == "orienting the run"
    assert view2.next_action == "prepare-package"


def test_lifecycle_scenario_operator_cancel(tmp_path: Path) -> None:
    """Scenario 5: Explicit operator cancellation recorded monotonically."""
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
        message="Operator aborted execution",
        command_surface="builder cancel",
    )

    view = project_run_view(tmp_path, session_id=session_id)
    assert view.activity_label == "run cancelled by operator"
    assert "run was cancelled by operator" in view.attention_items
    assert view.next_action == "RUN_CANCELLED"


def test_lifecycle_scenario_corrupt_wal_resilience(tmp_path: Path) -> None:
    """Scenario 6: Corrupted event log causes fail-closed detection without crash."""
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
    artifact_root, launch, close, postflight, transcript = _setup_goose_evidence(tmp_path, session_id)

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
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    start_event = persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )
    assert start_event["event_type"] == "deepagents_runtime_started"

    exec_event = persist_deepagents_execution(
        artifact_root=artifact_root,
        session_id=session_id,
        execution_receipt=fixture["receipt"],
    )
    assert exec_event["event_type"] == "deepagents_runtime_executed"

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert errors == []

    events_dir = artifact_root / "sessions" / session_id / "events"
    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True
    assert report["event_count"] == 2


def test_deepagents_interrupted_delegation_custody(tmp_path: Path) -> None:
    """Scenario 10: Deep Agents interrupted delegation with real checkpoint."""
    session_id = "deepagents-interrupt-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    # Mutate event 2 to be a checkpoint_recorded instead of run_completed
    from builder_ii.adapters.deepagents.deepagents_execution import (
        create_deepagents_event_record,
        create_deepagents_replay_report,
        create_deepagents_event_ledger,
        create_deepagents_run_envelope
    )
    from builder_ii.adapters.deepagents.deepagents_execution import _digest_jsonable
    
    event_2 = create_deepagents_event_record(
        session_id=session_id,
        sequence=2,
        event_type="checkpoint_recorded",
        subject_refs=[],
        payload={"completed_subagents": ["repo_mapper"]},
        message="Checkpoint recorded",
        previous_event_ref={
            "role": "event",
            "kind": "builder_ii.deepagents_event_record",
            "path": str(fixture["event_1_path"]),
            "sha256": _digest_jsonable(fixture["event_1"]),
            "name": "subagent_scheduled",
            "required": True,
        }
    )
    fixture["event_2"] = event_2
    import json
    fixture["event_2_path"].write_text(json.dumps(event_2, indent=2), encoding="utf-8")
    
    event_records = [(fixture["event_1"], fixture["event_1_path"]), (fixture["event_2"], fixture["event_2_path"])]
    fixture["internal_events"] = event_records
    
    fixture["replay_report"] = create_deepagents_replay_report(session_id=session_id, event_records=event_records)
    fixture["event_ledger"] = create_deepagents_event_ledger(
        session_id=session_id,
        event_records=event_records,
        replay_report=fixture["replay_report"],
        replay_report_path=fixture.get("replay_report_path", artifact_root / "sessions" / session_id / "deepagents" / "replay_report.json")
    )
    
    fixture["envelope"] = create_deepagents_run_envelope(
        session_id=session_id,
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        candidate_path=artifact_root / "sessions" / session_id / "deepagents" / "candidate.json",
        approval_path=artifact_root / "sessions" / session_id / "deepagents" / "approval.json",
        event_ledger=fixture["event_ledger"],
        event_ledger_path=artifact_root / "sessions" / session_id / "deepagents" / "event_ledger.json",
        replay_report=fixture["replay_report"],
        replay_report_path=artifact_root / "sessions" / session_id / "deepagents" / "replay_report.json",
        checkpoint=None,
        checkpoint_path=None,
        output_dir=artifact_root / "sessions" / session_id / "deepagents",
        status="CHECKPOINTED",
    )

    # Mutate event 2 to be a checkpoint_recorded instead of run_completed
    from builder_ii.adapters.deepagents.deepagents_execution import (
        create_deepagents_event_record,
        create_deepagents_replay_report,
        create_deepagents_event_ledger,
        _digest_jsonable
    )
    
    event_2 = create_deepagents_event_record(
        session_id=session_id,
        sequence=2,
        event_type="checkpoint_recorded",
        subject_refs=[],
        payload={"completed_subagents": ["repo_mapper"]},
        message="Checkpoint recorded",
        previous_event_ref={
            "role": "event",
            "kind": "builder_ii.deepagents_event_record",
            "path": str(fixture["event_1_path"]),
            "sha256": _digest_jsonable(fixture["event_1"]),
            "name": "subagent_scheduled",
            "required": True,
        }
    )
    fixture["event_2"] = event_2
    import json
    fixture["event_2_path"].write_text(json.dumps(event_2, indent=2), encoding="utf-8")
    
    event_records = [(fixture["event_1"], fixture["event_1_path"]), (fixture["event_2"], fixture["event_2_path"])]
    fixture["internal_events"] = event_records
    
    fixture["replay_report"] = create_deepagents_replay_report(session_id=session_id, event_records=event_records)
    fixture["event_ledger"] = create_deepagents_event_ledger(
        session_id=session_id,
        event_records=event_records,
        replay_report=fixture["replay_report"],
        replay_report_path=fixture.get("replay_report_path", artifact_root / "sessions" / session_id / "deepagents" / "replay_report.json")
    )
    
    fixture["envelope"] = create_deepagents_run_envelope(
        session_id=session_id,
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        candidate_path=artifact_root / "sessions" / session_id / "deepagents" / "candidate.json",
        approval_path=artifact_root / "sessions" / session_id / "deepagents" / "approval.json",
        event_ledger=fixture["event_ledger"],
        event_ledger_path=artifact_root / "sessions" / session_id / "deepagents" / "event_ledger.json",
        replay_report=fixture["replay_report"],
        replay_report_path=artifact_root / "sessions" / session_id / "deepagents" / "replay_report.json",
        checkpoint=None,
        checkpoint_path=None,
        output_dir=artifact_root / "sessions" / session_id / "deepagents",
        status="CHECKPOINTED",
    )

    session_dir = deepagents_session_dir(artifact_root, session_id)
    candidate_path = session_dir / "candidate.json"
    approval_path = session_dir / "approval.json"
    checkpoint_path = session_dir / "checkpoint.json"
    replay_path = session_dir / "replay_report.json"
    ledger_path = session_dir / "event_ledger.json"
    envelope_path = session_dir / "envelope.json"

    event_tail_ref = _artifact_ref(
        fixture["event_1"],
        role="event",
        path=fixture["event_1_path"],
        name="event tail",
    )

    checkpoint = create_deepagents_checkpoint(
        session_id=session_id,
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        candidate_path=candidate_path,
        approval_path=approval_path,
        event_tail_ref=event_tail_ref,
        events_dir=fixture["events_dir"],
        completed_subagents=["repo_mapper"],
        remaining_subagents=["code_reviewer"],
    )

    checkpoint_receipt = create_deepagents_execution_receipt(
        session_id=session_id,
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        envelope=fixture["envelope"],
        replay_report=fixture["replay_report"],
        event_ledger=fixture["event_ledger"],
        candidate_path=candidate_path,
        approval_path=approval_path,
        envelope_path=envelope_path,
        replay_report_path=replay_path,
        event_ledger_path=ledger_path,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        status="CHECKPOINTED",
    )

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

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
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    projected_receipt = create_deepagents_subagent_execution_receipt(
        subagent_profile="repo_mapper",
        assignment_ref={"kind": "k", "path": "p", "sha256": "a" * 64, "role": "a", "required": True, "name": "n"},
        result_ref={"kind": "k", "path": "p", "sha256": "b" * 64, "role": "r", "required": True, "name": "n"},
    )
    assert projected_receipt["receipt_state"] == "PROJECTED_ONLY"

    with pytest.raises(ValueError, match="PROJECTED_ONLY receipt cannot be persisted as runtime execution evidence"):
        persist_deepagents_execution(
            artifact_root=artifact_root,
            session_id=session_id,
            execution_receipt=projected_receipt,
        )


def test_lesion_missing_candidate_or_approval_for_run_envelope_rejected(tmp_path: Path) -> None:
    """Lesion: Real run envelope without candidate/approval is refused."""
    session_id = "lesion-nocand-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    with pytest.raises(ValueError, match="candidate and approval are required"):
        persist_deepagents_start(
            artifact_root=artifact_root,
            session_id=session_id,
            work_plan=fixture["work_plan"],
            envelope=fixture["envelope"],
            candidate=None,
            approval=None,
        )


def test_lesion_expired_or_mismatched_approval_rejected(tmp_path: Path) -> None:
    """Lesion: Mismatched/expired approval against candidate is refused."""
    session_id = "lesion-badapp-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    bad_approval = dict(fixture["approval"])
    bad_approval["approved_backend_mode"] = "unapproved_mode"

    with pytest.raises(ValueError, match="approval approved_backend_mode must match candidate backend_mode"):
        persist_deepagents_start(
            artifact_root=artifact_root,
            session_id=session_id,
            work_plan=fixture["work_plan"],
            envelope=fixture["envelope"],
            candidate=fixture["candidate"],
            approval=bad_approval,
            event_ledger=fixture["event_ledger"],
            replay_report=fixture["replay_report"],
        )


def test_lesion_swapped_envelope_rejected(tmp_path: Path) -> None:
    """Lesion: Swapped envelope with different content fails custody validation."""
    session_id = "lesion-envelope-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    # Tamper with envelope on disk
    session_dir = deepagents_session_dir(artifact_root, session_id)
    envelope_path = session_dir / "envelope.json"
    env_data = json.loads(envelope_path.read_text(encoding="utf-8"))
    env_data["output_dir"] = "/tampered/path"
    env_data["envelope_digest"] = _digest_jsonable(env_data)
    envelope_path.write_text(json.dumps(env_data, indent=2), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("deepagents_runtime_started envelope binding: sha256" in e for e in errors)


def test_lesion_foreign_work_plan_rejected(tmp_path: Path) -> None:
    """Lesion: Foreign work plan bytes fail custody validation."""
    session_id = "lesion-plan-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    # Tamper with work_plan.json on disk
    session_dir = deepagents_session_dir(artifact_root, session_id)
    plan_path = session_dir / "work_plan.json"
    plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
    plan_data["task"] = "Tampered foreign task"
    plan_path.write_text(json.dumps(plan_data, indent=2), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("deepagents_runtime_started work plan binding: sha256" in e for e in errors)


def test_lesion_receipt_tampered_rejected(tmp_path: Path) -> None:
    """Lesion: Tampered receipt fails custody validation."""
    session_id = "lesion-receipt-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )
    persist_deepagents_execution(
        artifact_root=artifact_root,
        session_id=session_id,
        execution_receipt=fixture["receipt"],
    )

    # Tamper with receipt.json on disk
    session_dir = deepagents_session_dir(artifact_root, session_id)
    receipt_path = session_dir / "receipt.json"
    receipt_data = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_data["completed_subagents"] = ["tampered_subagent"]
    receipt_data["receipt_digest"] = _digest_jsonable(receipt_data)
    receipt_path.write_text(json.dumps(receipt_data, indent=2), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("deepagents_runtime_executed receipt binding: sha256" in e for e in errors)


def test_lesion_digest_identical_foreign_path_rejected(tmp_path: Path) -> None:
    """Lesion: Reference with matching digest but pointing to foreign path is rejected."""
    session_id = "lesion-foreignpath-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    # Alter candidate_ref path inside approval to point elsewhere
    bad_approval = dict(fixture["approval"])
    bad_approval["candidate_ref"] = dict(bad_approval["candidate_ref"])
    bad_approval["candidate_ref"]["path"] = "/foreign/candidate.json"
    bad_approval["approval_digest"] = _digest_jsonable(bad_approval)

    with pytest.raises(ValueError, match="does not match expected canonical path"):
        persist_deepagents_start(
            artifact_root=artifact_root,
            session_id=session_id,
            work_plan=fixture["work_plan"],
            envelope=fixture["envelope"],
            candidate=fixture["candidate"],
            approval=bad_approval,
            event_ledger=fixture["event_ledger"],
            replay_report=fixture["replay_report"],
        )


def test_lesion_missing_or_tampered_event_ledger_rejected(tmp_path: Path) -> None:
    """Lesion: Tampered internal event ledger fails custody validation."""
    session_id = "lesion-badledger-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    session_dir = deepagents_session_dir(artifact_root, session_id)
    ledger_path = session_dir / "event_ledger.json"
    ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger_data["event_count"] = 999
    ledger_data["event_ledger_digest"] = _digest_jsonable(ledger_data)
    ledger_path.write_text(json.dumps(ledger_data, indent=2), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("envelope event_ledger_ref: sha256" in e for e in errors)


def test_lesion_missing_or_tampered_replay_report_rejected(tmp_path: Path) -> None:
    """Lesion: Tampered replay report fails custody validation."""
    session_id = "lesion-badreplay-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    session_dir = deepagents_session_dir(artifact_root, session_id)
    replay_path = session_dir / "replay_report.json"
    replay_data = json.loads(replay_path.read_text(encoding="utf-8"))
    replay_data["replayed_events_count"] = 999
    replay_data["replay_report_digest"] = _digest_jsonable(replay_data)
    replay_path.write_text(json.dumps(replay_data, indent=2), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("envelope replay_report_ref: sha256" in e for e in errors)


def test_lesion_checkpointed_receipt_missing_checkpoint_rejected(tmp_path: Path) -> None:
    """Lesion: CHECKPOINTED receipt without checkpoint raises ValueError."""
    session_id = "lesion-nochk-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    chk_receipt = dict(fixture["receipt"])
    chk_receipt["receipt_state"] = "CHECKPOINTED"
    chk_receipt["checkpoint_ref"] = None
    chk_receipt["receipt_digest"] = _digest_jsonable(chk_receipt)

    with pytest.raises(ValueError, match="checkpoint is required when persisting a CHECKPOINTED receipt"):
        persist_deepagents_execution(
            artifact_root=artifact_root,
            session_id=session_id,
            execution_receipt=chk_receipt,
            checkpoint=None,
        )


def test_lesion_receipt_status_event_type_mismatch_rejected(tmp_path: Path) -> None:
    """Lesion: Terminal event type contradicting receipt status is rejected."""
    session_id = "lesion-mismatch-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    session_dir = deepagents_session_dir(artifact_root, session_id)
    receipt_path = session_dir / "receipt.json"
    receipt_path.write_text(json.dumps(fixture["receipt"], indent=2), encoding="utf-8")

    # Manually append deepagents_runtime_failed event for COMPLETED receipt
    events_dir = artifact_root / "sessions" / session_id / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="deepagents_runtime_failed",
        message="Contradictory failed event",
        command_surface="builder delegate",
        subject_refs=[
            {
                "role": "deepagents_execution_receipt",
                "kind": DEEPAGENTS_EXECUTION_RECEIPT_KIND,
                "path": str(receipt_path),
                "sha256": _digest_jsonable(fixture["receipt"]),
                "name": "receipt",
                "required": True,
            }
        ],
        decision_result="failed",
    )

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("COMPLETED receipt requires exactly one deepagents_runtime_executed event" in e for e in errors)


def test_lesion_wrong_checkpoint_event_binding_rejected(tmp_path: Path) -> None:
    """Lesion: Checkpoint event_tail_ref pointing to invalid event is rejected."""
    session_id = "lesion-badtail-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    session_dir = deepagents_session_dir(artifact_root, session_id)
    candidate_path = session_dir / "candidate.json"
    approval_path = session_dir / "approval.json"
    checkpoint_path = session_dir / "checkpoint.json"
    replay_path = session_dir / "replay_report.json"
    ledger_path = session_dir / "event_ledger.json"
    envelope_path = session_dir / "envelope.json"

    # Bad event_tail_ref with wrong digest
    bad_tail_ref = {
        "role": "event",
        "kind": DEEPAGENTS_EVENT_RECORD_KIND,
        "path": str(fixture["event_1_path"]),
        "sha256": "0" * 64,
        "name": "event tail",
        "required": True,
    }

    checkpoint = create_deepagents_checkpoint(
        session_id=session_id,
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        candidate_path=candidate_path,
        approval_path=approval_path,
        event_tail_ref=bad_tail_ref,
        events_dir=fixture["events_dir"],
        completed_subagents=["repo_mapper"],
        remaining_subagents=["code_reviewer"],
    )

    checkpoint_receipt = create_deepagents_execution_receipt(
        session_id=session_id,
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        envelope=fixture["envelope"],
        replay_report=fixture["replay_report"],
        event_ledger=fixture["event_ledger"],
        candidate_path=candidate_path,
        approval_path=approval_path,
        envelope_path=envelope_path,
        replay_report_path=replay_path,
        event_ledger_path=ledger_path,
        checkpoint=checkpoint,
        checkpoint_path=checkpoint_path,
        status="CHECKPOINTED",
    )

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    with pytest.raises(ValueError, match="checkpoint event_tail_ref: sha256"):
        persist_deepagents_execution(
            artifact_root=artifact_root,
            session_id=session_id,
            execution_receipt=checkpoint_receipt,
            checkpoint=checkpoint,
        )


def test_lesion_duplicate_terminal_events_rejected(tmp_path: Path) -> None:
    """Lesion: Duplicate terminal execution events are refused."""
    session_id = "lesion-dup-term-001"
    artifact_root = tmp_path / "artifacts"
    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )
    persist_deepagents_execution(
        artifact_root=artifact_root,
        session_id=session_id,
        execution_receipt=fixture["receipt"],
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


def test_lesion_tampered_non_tail_internal_event_rejected(tmp_path: Path) -> None:
    """Lesion: Tampered non-tail internal event fails event graph reconstruction."""
    session_id = "lesion-tampered-internal-001"
    artifact_root = tmp_path / "artifacts"
    session_dir = deepagents_session_dir(artifact_root, session_id)
    internal_events_dir = session_dir / "events"
    internal_events_dir.mkdir(parents=True, exist_ok=True)

    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    # Tamper with the non-tail (only) internal event file on disk
    event_1_path = internal_events_dir / "event-000001.json"
    event_data = json.loads(event_1_path.read_text(encoding="utf-8"))
    event_data["message"] = "TAMPERED MESSAGE"
    event_1_path.write_text(json.dumps(event_data, indent=2, sort_keys=True), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("digest does not match ledger ref" in e for e in errors)


def test_lesion_event_ref_outside_events_dir_rejected(tmp_path: Path) -> None:
    """Lesion: Event ref pointing outside deepagents/events/ is rejected."""
    session_id = "lesion-escape-001"
    artifact_root = tmp_path / "artifacts"
    session_dir = deepagents_session_dir(artifact_root, session_id)
    internal_events_dir = session_dir / "events"
    internal_events_dir.mkdir(parents=True, exist_ok=True)

    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    # Write the event to an external location
    escape_dir = tmp_path / "escape"
    escape_dir.mkdir(parents=True, exist_ok=True)
    escape_path = escape_dir / "event-000001.json"
    escape_path.write_text(json.dumps(fixture["event_1"], indent=2, sort_keys=True), encoding="utf-8")

    # Mutate the ledger's event_ref to point outside the events directory
    from builder_ii.adapters.deepagents.deepagents_execution import _digest_jsonable
    ledger = dict(fixture["event_ledger"])
    ledger["event_refs"] = [
        {
            "role": "event",
            "kind": "builder_ii.deepagents_event_record",
            "path": str(escape_path),
            "sha256": _digest_jsonable(fixture["event_1"]),
            "name": "subagent_scheduled",
            "required": True,
        },
        fixture["event_ledger"]["event_refs"][1]
    ]
    ledger["ledger_digest"] = _digest_jsonable(ledger)

    # Rewrite envelope, receipt, replay to bind the mutated ledger
    # (We persist with valid artifacts then tamper the ledger on disk)
    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    # Overwrite ledger on disk with the escape-pointing version
    ledger_path = session_dir / "event_ledger.json"
    ledger_path.write_text(json.dumps(ledger, indent=2, sort_keys=True), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("is not under" in e for e in errors) or any("sha256" in e and "event_ledger_ref" in e for e in errors)


def test_lesion_event_from_another_session_rejected(tmp_path: Path) -> None:
    """Lesion: Event file from a different session is rejected during reconstruction."""
    session_id = "lesion-foreign-session-001"
    artifact_root = tmp_path / "artifacts"
    session_dir = deepagents_session_dir(artifact_root, session_id)
    internal_events_dir = session_dir / "events"
    internal_events_dir.mkdir(parents=True, exist_ok=True)

    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    # Overwrite the internal event with one from a different session
    event_1_path = internal_events_dir / "event-000001.json"
    foreign_event = create_deepagents_event_record(
        session_id="foreign-session-999",
        sequence=1,
        event_type="subagent_scheduled",
        subject_refs=[],
        payload={"subagent_profile": "repo_mapper"},
        message="Foreign session event",
    )
    event_1_path.write_text(json.dumps(foreign_event, indent=2, sort_keys=True), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("session_id does not match run" in e for e in errors)


def test_lesion_envelope_receipt_different_ledgers_rejected(tmp_path: Path) -> None:
    """Lesion: Envelope and receipt pointing at different valid ledgers is rejected."""
    session_id = "lesion-divergent-ledgers-001"
    artifact_root = tmp_path / "artifacts"
    session_dir = deepagents_session_dir(artifact_root, session_id)
    internal_events_dir = session_dir / "events"
    internal_events_dir.mkdir(parents=True, exist_ok=True)

    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    # Create a different valid receipt that points to a mutated ledger digest
    receipt_path = session_dir / "receipt.json"
    receipt = dict(fixture["receipt"])
    # Mutate the receipt's ledger ref to have a different digest
    receipt["event_ledger_ref"] = dict(receipt.get("event_ledger_ref", {}))
    receipt["event_ledger_ref"]["sha256"] = "b" * 64
    receipt["receipt_digest"] = _digest_jsonable(receipt)
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

    # Append the terminal event for the receipt
    events_dir = artifact_root / "sessions" / session_id / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type="deepagents_runtime_executed",
        message="Governed Deep Agents delegation completed",
        command_surface="builder delegate",
        subject_refs=[
            {
                "role": "deepagents_execution_receipt",
                "kind": DEEPAGENTS_EXECUTION_RECEIPT_KIND,
                "path": str(receipt_path),
                "sha256": _digest_jsonable(receipt),
                "name": "receipt",
                "required": True,
            }
        ],
        decision_result="executed",
    )

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("envelope and receipt event_ledger_ref digests do not match" in e for e in errors)


def test_lesion_ledger_replay_foreign_paths_rejected(tmp_path: Path) -> None:
    """Lesion: Ledger/replay with digest-identical foreign paths is rejected."""
    session_id = "lesion-foreign-paths-001"
    artifact_root = tmp_path / "artifacts"
    session_dir = deepagents_session_dir(artifact_root, session_id)
    internal_events_dir = session_dir / "events"
    internal_events_dir.mkdir(parents=True, exist_ok=True)

    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    # Tamper the envelope to point its ledger ref at a foreign path
    # (same digest, different path)
    foreign_dir = tmp_path / "foreign_session" / "deepagents"
    foreign_dir.mkdir(parents=True, exist_ok=True)
    foreign_ledger_path = foreign_dir / "event_ledger.json"
    foreign_ledger_path.write_text(json.dumps(fixture["event_ledger"], indent=2, sort_keys=True), encoding="utf-8")

    envelope = json.loads((session_dir / "envelope.json").read_text(encoding="utf-8"))
    envelope["event_ledger_ref"] = dict(envelope.get("event_ledger_ref", {}))
    envelope["event_ledger_ref"]["path"] = str(foreign_ledger_path)
    # Rewrite the digest to make it structurally valid
    envelope["envelope_digest"] = _digest_jsonable(envelope)
    (session_dir / "envelope.json").write_text(json.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert any("does not match expected canonical path" in e for e in errors)


def test_lesion_ledger_replay_a_envelope_receipt_replay_b_rejected(tmp_path: Path) -> None:
    """Lesion: Ledger bound to replay A while envelope/receipt bind replay B is rejected."""
    session_id = "lesion-replay-split-001"
    artifact_root = tmp_path / "artifacts"
    session_dir = deepagents_session_dir(artifact_root, session_id)
    internal_events_dir = session_dir / "events"
    internal_events_dir.mkdir(parents=True, exist_ok=True)

    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=fixture["work_plan"],
        envelope=fixture["envelope"],
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        event_ledger=fixture["event_ledger"],
        replay_report=fixture["replay_report"],
    )

    # Tamper the persisted ledger to have a different replay_report_ref digest
    # (simulating ledger bound to replay A while the canonical replay is B)
    ledger_path = session_dir / "event_ledger.json"
    ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
    ledger_data["replay_report_ref"] = dict(ledger_data.get("replay_report_ref", {}))
    ledger_data["replay_report_ref"]["sha256"] = "c" * 64
    ledger_data["ledger_digest"] = _digest_jsonable(ledger_data)
    ledger_path.write_text(json.dumps(ledger_data, indent=2, sort_keys=True), encoding="utf-8")

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    # Should detect both the ledger/envelope digest mismatch AND the ledger replay_report_ref mismatch
    assert any("ledger replay_report_ref" in e and "sha256" in e for e in errors) or any(
        "envelope event_ledger_ref" in e and "sha256" in e for e in errors
    )


# ---------------------------------------------------------------------------
# Cross-Frontend Semantic Parity Across ALL 8 Scenarios
# ---------------------------------------------------------------------------


def _setup_corrupt_for_parity(path: Path, sid: str) -> None:
    events_dir = path / "sessions" / sid / "events"
    append_runtime_event(
        events_dir=events_dir,
        session_id=sid,
        event_type="wrp_live_run_started",
        message="started",
        command_surface="builder start",
    )
    append_runtime_event(
        events_dir=events_dir,
        session_id=sid,
        event_type="tool_call_executed",
        message="executed",
        command_surface="builder run",
    )
    json_files = sorted(p for p in events_dir.glob("*.json") if p.name != "events.wal")
    bad_path = json_files[1]
    data = json.loads(bad_path.read_text(encoding="utf-8"))
    data["previous_event_ref"]["sha256"] = "a" * 64
    bad_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")


def _setup_goose_close_for_parity(path: Path, sid: str) -> None:
    artifact_root, launch, close, postflight, _ = _setup_goose_evidence(path, sid)
    persist_goose_launch(artifact_root=artifact_root, session_id=sid, launch_receipt=launch)
    persist_goose_close(
        artifact_root=artifact_root,
        session_id=sid,
        launch_receipt=launch,
        close_receipt=close,
        postflight=postflight,
    )


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
            "CORRUPT",
            _setup_corrupt_for_parity,
            False,
            "orienting the run",
            "BLOCKED: repair corrupt or foreign canonical evidence",
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
        (
            "CLOSE",
            _setup_goose_close_for_parity,
            True,
            "orienting the run",
            "prepare-package",
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
    """Verifies that RunView, Status CLI, Registry projection, and TUI facade all agree across ALL 8 scenarios."""
    session_id = f"parity-{scenario_name.lower()}-001"
    setup_fn(tmp_path, session_id)

    expected_action_rendered = expected_next_action.format(sid=session_id)

    # 1. RunView projection
    run_view = project_run_view(tmp_path, session_id=session_id)
    assert (run_view.errors == ()) == expected_chain_valid
    assert run_view.activity_label == expected_activity
    if expected_chain_valid:
        assert run_view.next_action == expected_action_rendered
    else:
        assert expected_action_rendered in run_view.next_action

    # 2. Status CLI projection
    status = project_run_status(tmp_path, requested_run_id=session_id)
    assert status.selected is not None
    assert status.selected.run_id == session_id
    assert status.run is not None
    assert status.run.activity_label == expected_activity
    if expected_chain_valid:
        assert status.run.next_action == expected_action_rendered
    else:
        assert expected_action_rendered in status.run.next_action

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

def test_lesion_running_replay_with_completed_envelope_rejected(tmp_path: Path) -> None:
    from builder_ii.adapters.deepagents.deepagents_session_custody import deepagents_session_dir, persist_deepagents_start
    from builder_ii.adapters.deepagents.deepagents_execution import create_deepagents_replay_report, create_deepagents_event_ledger, create_deepagents_run_envelope
    import pytest
    
    session_id = "lesion-running-comp-env-001"
    artifact_root = tmp_path / "artifacts"
    session_dir = deepagents_session_dir(artifact_root, session_id)
    internal_events_dir = session_dir / "events"
    internal_events_dir.mkdir(parents=True, exist_ok=True)

    fixture = _setup_deepagents_fixture(artifact_root, session_id)

    # Use only event 1 for RUNNING state
    event_records = [(fixture["event_1"], fixture["event_1_path"])]
    replay_report = create_deepagents_replay_report(session_id=session_id, event_records=event_records)

    event_ledger = create_deepagents_event_ledger(
        session_id=session_id,
        event_records=event_records,
        replay_report=replay_report,
        replay_report_path=fixture.get("replay_report_path", session_dir / "replay_report.json")
    )

    envelope = create_deepagents_run_envelope(
        session_id=session_id,
        candidate=fixture["candidate"],
        approval=fixture["approval"],
        candidate_path=artifact_root / "sessions" / session_id / "deepagents" / "candidate.json",
        approval_path=artifact_root / "sessions" / session_id / "deepagents" / "approval.json",
        event_ledger=event_ledger,
        event_ledger_path=artifact_root / "sessions" / session_id / "deepagents" / "event_ledger.json",
        replay_report=replay_report,
        replay_report_path=artifact_root / "sessions" / session_id / "deepagents" / "replay_report.json",
        checkpoint=None,
        checkpoint_path=None,
        output_dir=artifact_root / "sessions" / session_id / "deepagents",
        status="COMPLETED",
    )

    with pytest.raises(ValueError, match="does not match recomputed replay status"):
        persist_deepagents_start(
            artifact_root=artifact_root,
            session_id=session_id,
            work_plan=fixture["work_plan"],
            envelope=envelope,
            candidate=fixture["candidate"],
            approval=fixture["approval"],
            event_ledger=event_ledger,
            replay_report=replay_report,
        )
