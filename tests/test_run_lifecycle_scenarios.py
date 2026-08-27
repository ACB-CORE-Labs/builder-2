"""Comprehensive verification of the 8 canonical run lifecycle scenarios.

Verifies:
1. COMPLETE: Clean completion of governed workflow / Goose / Deep Agents
2. FAIL: Governed execution failure with explicit fail event
3. INTERRUPT: Run paused / interrupted with clean checkpoint
4. RESUME: Resumption of interrupted run with continuous monotonic sequence
5. CANCEL: User-initiated cancellation recorded
6. CORRUPT: Detection of broken event chain / malformed JSON / hash mismatch
7. ORPHAN: Detection of unclosed session / missing close receipt
8. CLOSE: Orderly session close with postflight no-mutation proof
9. Deep Agents canonical session custody and event integration
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from builder_ii.adapters.deepagents.deepagents_runtime import (
    create_deepagents_runtime_envelope,
    create_deepagents_subagent_execution_receipt,
)
from builder_ii.adapters.deepagents.deepagents_session_custody import (
    persist_deepagents_execution,
    persist_deepagents_start,
    validate_deepagents_session_custody,
)
from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    create_deepagents_subagent_assignment,
    create_deepagents_subagent_result,
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
from builder_ii.core.run_registry import project_run_registry
from builder_ii.core.run_view import project_run_view
from builder_ii.governance.ledger.event_ledger import validate_event_chain_integrity
from builder_ii.lifecycle.candidate.runtime_event_append import append_runtime_event


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

    registry = project_run_registry(tmp_path)
    entry = registry.get(session_id)
    assert entry is not None
    assert entry.chain_valid is True
    assert entry.last_event_type == "wrp_live_run_completed"


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

    registry = project_run_registry(tmp_path)
    entry = registry.get(session_id)
    assert entry is not None
    assert entry.chain_valid is True
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
    view = project_run_view(tmp_path, session_id=session_id)
    assert view.activity_label == "resuming interrupted run"
    assert "run was interrupted; resume with builder resume" in view.attention_items[0]
    assert view.next_action == f"builder resume {session_id}"

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


def test_deepagents_canonical_session_custody(tmp_path: Path) -> None:
    """Scenario 9: Deep Agents canonical session custody and lifecycle events."""
    from builder_ii.adapters.deepagents.deepagents_policy import create_deepagents_policy_artifact
    from builder_ii.adapters.deepagents.deepagents_readiness import create_deepagents_readiness_artifact
    from builder_ii.core.config import load_settings
    from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture

    session_id = "deepagents-run-001"
    artifact_root = tmp_path / "artifacts"
    goal2 = build_goal2_assignment_fixture(tmp_path, task="Test Deep Agents Task")
    orchestration_plan = goal2["artifacts"]["orchestration"]
    orchestration_dry_run = goal2["artifacts"]["dry_run"]

    policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness = create_deepagents_readiness_artifact(mode="metadata_only")

    plan = create_deepagents_work_plan(
        target="builder",
        task="Test Deep Agents Task",
        orchestration_assignment_plan=orchestration_plan,
        orchestration_assignment_dry_run=orchestration_dry_run,
        deepagents_policy=policy,
        deepagents_readiness=readiness,
        proposed_subagents=["repo_mapper", "code_reviewer"],
        expected_outputs=["deepagents_work_plan", "subagent_assignment"],
        review_gates=["operator_review"],
        blocked_capabilities=["model execution", "shell execution"],
    )
    from builder_ii.governance.ledger.workflow_records import canonical_digest

    plan_digest = canonical_digest(plan)
    envelope = create_deepagents_runtime_envelope(
        session_id=session_id,
        work_plan_ref={"kind": plan["kind"], "path": "work_plan.json", "sha256": plan_digest, "role": "work_plan", "required": True, "name": "work plan"},
        execution_receipt_refs=[],
    )

    start_event = persist_deepagents_start(
        artifact_root=artifact_root,
        session_id=session_id,
        work_plan=plan,
        envelope=envelope,
    )
    assert start_event["event_type"] == "deepagents_runtime_started"

    assignment = create_deepagents_subagent_assignment(
        target="builder",
        task="Map repository",
        subagent_profile="repo_mapper",
        work_plan=plan,
    )
    result = create_deepagents_subagent_result(
        target="builder",
        subagent_profile="repo_mapper",
        summary="Repository mapped successfully",
        subagent_assignment=assignment,
    )
    receipt = create_deepagents_subagent_execution_receipt(
        subagent_profile="repo_mapper",
        assignment_ref={"kind": assignment["kind"], "path": "assignment.json", "sha256": canonical_digest(assignment), "role": "assignment", "required": True, "name": "assignment"},
        result_ref={"kind": result["kind"], "path": "result.json", "sha256": canonical_digest(result), "role": "result", "required": True, "name": "result"},
    )

    exec_event = persist_deepagents_execution(
        artifact_root=artifact_root,
        session_id=session_id,
        execution_receipt=receipt,
        success=True,
    )
    assert exec_event["event_type"] == "deepagents_runtime_executed"

    errors = validate_deepagents_session_custody(artifact_root, session_id)
    assert errors == []

    events_dir = artifact_root / "sessions" / session_id / "events"
    report = validate_event_chain_integrity(events_dir)
    assert report["valid"] is True
    assert report["event_count"] == 2
