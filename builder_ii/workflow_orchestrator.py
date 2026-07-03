from __future__ import annotations

import hashlib
import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.agent_profiles import create_agent_profile_record, get_agent_profile
from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.artifact_index_records import create_artifact_index_record, write_artifact_index_record
from builder_ii.config import Settings, load_settings
from builder_ii.code_vault.hierarchy import (
    create_hierarchical_frame,
    dumps_hierarchical_frame,
    validate_hierarchical_frame,
)
from builder_ii.code_vault.repo_map_adapter import hierarchical_input_from_repo_map
from builder_ii.context_packs import create_architecture_aware_context_pack
from builder_ii.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.deepagents_work_artifacts import (
    create_deepagents_work_plan,
    create_deepagents_work_validation_report,
)
from builder_ii.event_ledger import (
    EVENT_TYPE_STAGE,
    create_event_ledger,
    create_event_record,
    load_event_records,
    replay_events,
    validate_event_ledger,
    validate_ledger_replay_report,
    write_event_ledger,
    write_event_record,
    write_ledger_replay_report,
)
from builder_ii.execution_candidate_manifest import (
    create_execution_candidate_manifest,
    create_execution_candidate_manifest_validation_report,
    validate_execution_candidate_manifest,
    validate_execution_candidate_manifest_validation_report,
    write_execution_candidate_manifest,
    write_execution_candidate_manifest_validation_report,
)
from builder_ii.handoff_notes import create_handoff_note, write_handoff_note
from builder_ii.hitl_promotion_artifacts import (
    create_hitl_approval_boundary,
    create_hitl_promotion_decision,
    create_hitl_promotion_request,
    create_hitl_promotion_review,
    validate_hitl_approval_boundary,
    validate_hitl_promotion_decision,
    validate_hitl_promotion_request,
    validate_hitl_promotion_review,
    write_hitl_promotion_artifact,
)
from builder_ii.model_client_registry import create_model_client_registry, write_model_client_registry
from builder_ii.model_routing_policy import (
    create_model_routing_policy,
    create_model_routing_recommendation,
    write_model_routing_policy,
    write_model_routing_recommendation,
)
from builder_ii.orchestration_assignment import (
    create_agent_assignment_plan,
    create_orchestration_assignment_dry_run,
    create_orchestration_assignment_plan,
    create_orchestration_assignment_validation_report,
    write_agent_assignment_plan,
    write_orchestration_assignment_dry_run,
    write_orchestration_assignment_plan,
    write_orchestration_assignment_validation_report,
)
from builder_ii.profile_pack import create_profile_pack, write_profile_pack
from builder_ii.profile_pack_dry_run import create_profile_pack_dry_run, write_profile_pack_dry_run
from builder_ii.profile_pack_manifest import create_profile_pack_manifest, write_profile_pack_manifest
from builder_ii.profile_pack_render_plan import create_profile_pack_render_plan, write_profile_pack_render_plan
from builder_ii.profile_pack_validation_report import (
    create_profile_pack_validation_report,
    write_profile_pack_validation_report,
)
from builder_ii.repo_map import create_repo_map
from builder_ii.target_profiles import TargetName, target_profile, write_target_profile_artifact
from builder_ii.verification_profiles import (
    default_profile_for_target,
    get_verification_profile,
    write_profile_artifact,
)
from builder_ii.workflow_records import (
    artifact_ref,
    create_workflow_session,
    create_workflow_status,
    create_workflow_transition,
    file_ref,
    validate_workflow_session,
    validate_workflow_status,
    validate_workflow_transition,
    write_workflow_record,
)


class WorkflowError(RuntimeError):
    pass


def _utc_id() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("wf-%Y%m%dT%H%M%SZ")


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WorkflowError(f"file not found: {path}") from exc
    except json_lib.JSONDecodeError as exc:
        raise WorkflowError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise WorkflowError(f"{path} must contain a JSON object")
    return data


def _write_json(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def hashlib_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paths(output_dir: Path) -> dict[str, Path]:
    artifacts = output_dir / "artifacts"
    events = output_dir / "events"
    return {
        "output": output_dir,
        "artifacts": artifacts,
        "events": events,
        "session": artifacts / "workflow-session.json",
        "status": artifacts / "workflow-status.json",
        "replay": artifacts / "ledger-replay-report.json",
        "ledger": artifacts / "event-ledger.json",
    }


def _default_agent_for_target(target: str) -> str:
    if target == "core":
        return "core.patch_planner"
    return "patch_planner"


def _event_ref(event: dict[str, Any], path: Path) -> dict[str, Any]:
    return artifact_ref(
        event,
        path=path,
        role="event",
        name=str(event.get("event_type", "")),
    )


def _last_event_ref(events_dir: Path) -> dict[str, Any] | None:
    events = sorted(load_event_records(events_dir), key=lambda item: int(item[0].get("sequence", 0)))
    if not events:
        return None
    event, path = events[-1]
    return _event_ref(event, path)


def _collect_artifact_refs(events: list[tuple[dict[str, Any], Path]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    refs: list[dict[str, Any]] = []
    for event, _path in events:
        subject_refs = event.get("subject_refs", [])
        if not isinstance(subject_refs, list):
            continue
        for ref in subject_refs:
            if not isinstance(ref, dict):
                continue
            key = (str(ref.get("path", "")), str(ref.get("sha256", "")))
            if key in seen:
                continue
            seen.add(key)
            refs.append(ref)
    return refs


def _session_context(output_dir: Path) -> tuple[dict[str, Any], Path, dict[str, Path]]:
    paths = _paths(output_dir)
    session = _read_json(paths["session"])
    errors = validate_workflow_session(session)
    if errors:
        raise WorkflowError("workflow session is invalid: " + "; ".join(errors))
    return session, paths["session"], paths


def _write_status_from_events(session: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    paths = _paths(output_dir)
    event_records = load_event_records(paths["events"])
    replay = replay_events(event_records, session_id=str(session["session_id"]))
    replay_errors = validate_ledger_replay_report(replay)
    if replay_errors:
        raise WorkflowError("created invalid replay report: " + "; ".join(replay_errors))
    write_ledger_replay_report(replay, paths["replay"])

    ledger = create_event_ledger(
        session_id=str(session["session_id"]),
        event_records=event_records,
        replay_report=replay,
        replay_report_path=paths["replay"],
    )
    ledger_errors = validate_event_ledger(ledger)
    if ledger_errors:
        raise WorkflowError("created invalid event ledger: " + "; ".join(ledger_errors))
    write_event_ledger(ledger, paths["ledger"])

    status = create_workflow_status(
        session_id=str(session["session_id"]),
        target=str(session["target"]),
        task=str(session["task"]),
        current_stage=str(replay["current_stage"]),
        completed_stages=list(replay["completed_stages"]),
        artifact_refs=_collect_artifact_refs(event_records),
        last_event_ref=replay.get("last_event_ref"),
        event_count=int(replay["event_count"]),
        valid_replay=bool(replay["valid"]),
        replay_errors=list(replay["errors"]),
    )
    status_errors = validate_workflow_status(status)
    if status_errors:
        raise WorkflowError("created invalid workflow status: " + "; ".join(status_errors))
    write_workflow_record(status, paths["status"])
    return status


def _record_event(
    *,
    output_dir: Path,
    session: dict[str, Any],
    event_type: str,
    subject_refs: list[dict[str, Any]],
    command_surface: str,
    message: str,
    decision_result: str,
) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    paths = _paths(output_dir)
    paths["events"].mkdir(parents=True, exist_ok=True)
    prior_events = load_event_records(paths["events"])
    sequence = len(prior_events) + 1
    stage = EVENT_TYPE_STAGE[event_type]
    event = create_event_record(
        event_id=f"{session['session_id']}:{sequence:04d}:{event_type}",
        session_id=str(session["session_id"]),
        sequence=sequence,
        event_type=event_type,
        stage=stage,
        subject_refs=subject_refs,
        command_surface=command_surface,
        policy_snapshot_ref=file_ref(
            kind="builder_ii.command_authority_policy_snapshot",
            path=Path.cwd() / "docs" / "COMMAND_AUTHORITY.md",
            sha256=hashlib_file(Path.cwd() / "docs" / "COMMAND_AUTHORITY.md"),
            role="policy_snapshot",
            name="command authority registry markdown",
        ),
        previous_event_ref=_last_event_ref(paths["events"]),
        message=message,
        decision_result=decision_result,
    )
    event_path = paths["events"] / f"{sequence:04d}-{event_type}.json"
    write_event_record(event, event_path)
    status = _write_status_from_events(session, output_dir)
    return event, event_path, status


def _require_stage(output_dir: Path, required_stage: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Path]]:
    session, _session_path, paths = _session_context(output_dir)
    status = _write_status_from_events(session, output_dir)
    if status["current_stage"] != required_stage:
        raise WorkflowError(f"workflow must be at stage {required_stage}; current stage is {status['current_stage']}")
    return session, status, paths


def _artifact_paths(paths: dict[str, Path]) -> list[Path]:
    artifact_paths = [
        path for path in paths["artifacts"].glob("*.json") if path.name != "chain-verification-report.json"
    ]
    event_paths = list(paths["events"].glob("*.json"))
    return sorted([*artifact_paths, *event_paths])


def plan_workflow(
    *,
    target: TargetName = "builder",
    task: str,
    output_dir: Path,
    session_id: str | None = None,
    agent: str | None = None,
    verification: str | None = None,
    repo_path: Path | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    if not task.strip():
        raise WorkflowError("task must be a non-empty string")
    settings = settings or load_settings()
    paths = _paths(output_dir)
    if paths["session"].exists():
        raise WorkflowError(f"workflow session already exists: {paths['session']}")
    paths["artifacts"].mkdir(parents=True, exist_ok=True)
    paths["events"].mkdir(parents=True, exist_ok=True)

    selected_profile = target_profile(settings, target, generic_repo=repo_path if target == "generic" else None)
    if repo_path is not None and target != "generic":
        selected_repo = repo_path.resolve()
    else:
        selected_repo = selected_profile.repo
    if repo_path is not None and target != "generic":
        # Preserve target identity while allowing an operator-supplied repo path for demos/tests.
        from dataclasses import replace

        selected_profile = replace(selected_profile, repo=selected_repo)

    selected_agent_name = agent or _default_agent_for_target(target)
    selected_agent = get_agent_profile(selected_agent_name)  # type: ignore[arg-type]
    selected_verification = (
        get_verification_profile(verification) if verification else default_profile_for_target(target)
    )

    session = create_workflow_session(
        session_id=session_id or _utc_id(),
        target=target,
        task=task,
        output_dir=output_dir,
        artifacts_dir=paths["artifacts"],
        events_dir=paths["events"],
    )
    session_errors = validate_workflow_session(session)
    if session_errors:
        raise WorkflowError("created invalid workflow session: " + "; ".join(session_errors))
    write_workflow_record(session, paths["session"])

    target_path = paths["artifacts"] / "target-profile.json"
    write_target_profile_artifact(selected_profile, target_path)
    target_artifact = _read_json(target_path)

    agent_record = create_agent_profile_record(selected_agent, selected_profile, task=task)
    agent_path = paths["artifacts"] / "agent-profile.json"
    _write_json(agent_record, agent_path)

    verification_path = paths["artifacts"] / "verification-profile.json"
    write_profile_artifact(selected_verification, verification_path, target=target, task=task)
    verification_artifact = _read_json(verification_path)

    repo_map = create_repo_map(selected_repo, target_name=target)
    repo_map_path = paths["artifacts"] / "repo-map.json"
    _write_json(repo_map, repo_map_path)

    frame_input = hierarchical_input_from_repo_map(
        repo_map,
        repo_root=selected_repo.resolve(),
        enrich_symbols=True,
    )
    hierarchical_frame = create_hierarchical_frame(frame_input, target_name=target)
    frame_errors = validate_hierarchical_frame(hierarchical_frame)
    if frame_errors:
        raise WorkflowError("created invalid hierarchical frame: " + "; ".join(frame_errors))
    hierarchical_frame_path = paths["artifacts"] / "hierarchical-frame.json"
    hierarchical_frame_path.write_text(dumps_hierarchical_frame(hierarchical_frame), encoding="utf-8")

    context_pack = create_architecture_aware_context_pack(
        repo_map,
        target_name=target,
        hierarchical_frame=hierarchical_frame,
        task=task,
    )
    context_path = paths["artifacts"] / "context-pack.json"
    _write_json(context_pack, context_path)

    profile_pack_manifest = create_profile_pack_manifest(
        pack_id=f"{target}-workflow-profile-pack",
        target_profile=target,
        task=task,
        project_root=settings.project_root,
    )
    profile_manifest_path = paths["artifacts"] / "profile-pack-manifest.json"
    write_profile_pack_manifest(profile_pack_manifest, profile_manifest_path)

    profile_render_plan = create_profile_pack_render_plan(
        profile_pack_manifest,
        manifest_path=profile_manifest_path,
        output_root="workflow-profile-pack-rendered",
    )
    profile_render_path = paths["artifacts"] / "profile-pack-render-plan.json"
    write_profile_pack_render_plan(profile_render_plan, profile_render_path)

    profile_dry_run = create_profile_pack_dry_run(
        profile_pack_manifest,
        profile_render_plan,
        manifest_path=profile_manifest_path,
        render_plan_path=profile_render_path,
    )
    profile_dry_run_path = paths["artifacts"] / "profile-pack-dry-run.json"
    write_profile_pack_dry_run(profile_dry_run, profile_dry_run_path)

    profile_validation = create_profile_pack_validation_report(
        profile_dry_run,
        subject_path=profile_dry_run_path,
    )
    profile_validation_path = paths["artifacts"] / "profile-pack-validation-report.json"
    write_profile_pack_validation_report(profile_validation, profile_validation_path)

    profile_pack = create_profile_pack(
        manifest=profile_pack_manifest,
        render_plan=profile_render_plan,
        dry_run=profile_dry_run,
        validation_report=profile_validation,
        manifest_path=profile_manifest_path,
        render_plan_path=profile_render_path,
        dry_run_path=profile_dry_run_path,
        validation_report_path=profile_validation_path,
    )
    profile_pack_path = paths["artifacts"] / "profile-pack.json"
    write_profile_pack(profile_pack, profile_pack_path)

    model_registry = create_model_client_registry()
    model_registry_path = paths["artifacts"] / "model-client-registry.json"
    write_model_client_registry(model_registry, model_registry_path)

    model_policy = create_model_routing_policy()
    model_policy_path = paths["artifacts"] / "model-routing-policy.json"
    write_model_routing_policy(model_policy, model_policy_path)

    model_recommendation = create_model_routing_recommendation(
        policy=model_policy,
        registry=model_registry,
        request={
            "task_intent": "coding",
            "max_risk_classification": "local_network",
            "requires_tool_use": True,
        },
        policy_path=model_policy_path,
        registry_path=model_registry_path,
    )
    model_recommendation_path = paths["artifacts"] / "model-routing-recommendation.json"
    write_model_routing_recommendation(model_recommendation, model_recommendation_path)

    assignment = create_agent_assignment_plan(
        target_profile=target_artifact,
        agent_profile=agent_record,
        task=task,
        context_pack=context_pack,
        verification_profile=verification_artifact,
        model_registry=model_registry,
        model_policy=model_policy,
        model_recommendation=model_recommendation,
        profile_pack_manifest=profile_pack_manifest,
        profile_pack_render_plan=profile_render_plan,
        profile_pack_dry_run=profile_dry_run,
        profile_pack_validation_report=profile_validation,
        profile_pack=profile_pack,
        target_profile_path=target_path,
        agent_profile_path=agent_path,
        context_pack_path=context_path,
        verification_profile_path=verification_path,
        model_registry_path=model_registry_path,
        model_policy_path=model_policy_path,
        model_recommendation_path=model_recommendation_path,
        profile_pack_manifest_path=profile_manifest_path,
        profile_pack_render_plan_path=profile_render_path,
        profile_pack_dry_run_path=profile_dry_run_path,
        profile_pack_validation_report_path=profile_validation_path,
        profile_pack_path=profile_pack_path,
    )
    assignment_path = paths["artifacts"] / "agent-assignment-plan.json"
    write_agent_assignment_plan(assignment, assignment_path)

    orchestration = create_orchestration_assignment_plan(assignment, assignment_plan_path=assignment_path)
    orchestration_path = paths["artifacts"] / "orchestration-assignment-plan.json"
    write_orchestration_assignment_plan(orchestration, orchestration_path)

    orchestration_dry_run = create_orchestration_assignment_dry_run(
        orchestration,
        orchestration_assignment_plan_path=orchestration_path,
    )
    orchestration_dry_run_path = paths["artifacts"] / "orchestration-assignment-dry-run.json"
    write_orchestration_assignment_dry_run(orchestration_dry_run, orchestration_dry_run_path)

    orchestration_validation = create_orchestration_assignment_validation_report(
        orchestration,
        subject_path=orchestration_path,
    )
    orchestration_validation_path = paths["artifacts"] / "orchestration-assignment-validation-report.json"
    write_orchestration_assignment_validation_report(orchestration_validation, orchestration_validation_path)

    deepagents_policy = create_deepagents_policy_artifact(
        settings, target_name=target, task=task, generic_repo=repo_path if target == "generic" else None
    )
    deepagents_policy_path = paths["artifacts"] / "deepagents-policy.json"
    _write_json(deepagents_policy, deepagents_policy_path)

    deepagents_readiness = create_deepagents_readiness_artifact(mode="metadata_only")
    deepagents_readiness_path = paths["artifacts"] / "deepagents-readiness.json"
    _write_json(deepagents_readiness, deepagents_readiness_path)

    deepagents_work_plan = create_deepagents_work_plan(
        target=target,
        task=task,
        orchestration_assignment_plan=orchestration,
        orchestration_assignment_dry_run=orchestration_dry_run,
        deepagents_policy=deepagents_policy,
        deepagents_readiness=deepagents_readiness,
        orchestration_assignment_plan_path=orchestration_path,
        orchestration_assignment_dry_run_path=orchestration_dry_run_path,
        deepagents_policy_path=deepagents_policy_path,
        deepagents_readiness_path=deepagents_readiness_path,
        proposed_subagents=["repo_mapper", "patch_planner", "verification_planner"],
        expected_outputs=["deepagents_work_plan", "execution_candidate_manifest"],
        review_gates=["operator_review", "HITL_approval_boundary"],
    )
    deepagents_work_plan_path = paths["artifacts"] / "deepagents-work-plan.json"
    _write_json(deepagents_work_plan, deepagents_work_plan_path)

    deepagents_validation = create_deepagents_work_validation_report(
        deepagents_work_plan,
        subject_path=deepagents_work_plan_path,
    )
    deepagents_validation_path = paths["artifacts"] / "deepagents-work-validation-report.json"
    _write_json(deepagents_validation, deepagents_validation_path)

    transition = create_workflow_transition(
        session_id=str(session["session_id"]),
        from_stage="initialized",
        to_stage="planned",
        command="builder workflow plan",
        subject_refs=[
            artifact_ref(session, path=paths["session"], role="workflow_session", name="workflow session"),
            artifact_ref(
                _read_json(hierarchical_frame_path),
                path=hierarchical_frame_path,
                role="hierarchical_frame",
                name="CodeVault hierarchical frame",
            ),
            artifact_ref(profile_pack, path=profile_pack_path, role="profile_pack", name="profile pack"),
            artifact_ref(
                model_recommendation,
                path=model_recommendation_path,
                role="model_routing",
                name="model routing recommendation",
            ),
            artifact_ref(
                orchestration, path=orchestration_path, role="orchestration_assignment", name="orchestration assignment"
            ),
            artifact_ref(
                deepagents_work_plan,
                path=deepagents_work_plan_path,
                role="deepagents_work_plan",
                name="deepagents work plan",
            ),
        ],
        reason="Passive workflow plan recorded without runtime authority.",
    )
    transition_errors = validate_workflow_transition(transition)
    if transition_errors:
        raise WorkflowError("created invalid workflow transition: " + "; ".join(transition_errors))
    transition_path = paths["artifacts"] / "workflow-transition-plan.json"
    write_workflow_record(transition, transition_path)

    event_subjects = list(transition["subject_refs"])
    event_subjects.append(
        artifact_ref(transition, path=transition_path, role="workflow_transition", name="plan transition")
    )
    _event, _event_path, status = _record_event(
        output_dir=output_dir,
        session=session,
        event_type="workflow_planned",
        subject_refs=event_subjects,
        command_surface="builder workflow plan",
        message="Passive workflow planning chain created.",
        decision_result="planned",
    )
    return status


def promote_workflow(*, output_dir: Path, requested_by: str = "operator") -> dict[str, Any]:
    session, _status, paths = _require_stage(output_dir, "planned")
    work_plan_path = paths["artifacts"] / "deepagents-work-plan.json"
    work_plan = _read_json(work_plan_path)
    request = create_hitl_promotion_request(
        proposal=work_plan,
        proposal_path=work_plan_path,
        target_profile_ref=artifact_ref(
            _read_json(paths["artifacts"] / "target-profile.json"),
            path=paths["artifacts"] / "target-profile.json",
            role="target_profile",
        ),
        requested_by=requested_by,
        reason="Promote passive deepagents work plan into candidate-design boundary.",
    )
    request_errors = validate_hitl_promotion_request(request)
    if request_errors:
        raise WorkflowError("created invalid promotion request: " + "; ".join(request_errors))
    request_path = paths["artifacts"] / "hitl-promotion-request.json"
    write_hitl_promotion_artifact(request, request_path)

    review = create_hitl_promotion_review(
        promotion_request=request,
        promotion_request_path=request_path,
        disposition="acceptable_for_decision",
        findings=["Passive planning artifacts are bound by SHA-256 and remain review evidence only."],
        warnings=["No runtime execution, model call, shell command, or target repository mutation is permitted."],
        recommendation="Acceptable for execution-candidate design only.",
        reviewed_by=requested_by,
    )
    review_errors = validate_hitl_promotion_review(review)
    if review_errors:
        raise WorkflowError("created invalid promotion review: " + "; ".join(review_errors))
    review_path = paths["artifacts"] / "hitl-promotion-review.json"
    write_hitl_promotion_artifact(review, review_path)

    decision = create_hitl_promotion_decision(
        promotion_request_ref=artifact_ref(request, path=request_path, role="promotion_request"),
        promotion_review_ref=artifact_ref(review, path=review_path, role="promotion_review"),
        decision_result="approved_for_candidate_design",
        decided_by=requested_by,
        reason="Approval is limited to candidate-manifest design; runtime remains disabled.",
        source_review_disposition=str(review["disposition"]),
        source_review_blocking_issues=list(review["blocking_issues"]),
    )
    decision_errors = validate_hitl_promotion_decision(decision)
    if decision_errors:
        raise WorkflowError("created invalid promotion decision: " + "; ".join(decision_errors))
    decision_path = paths["artifacts"] / "hitl-promotion-decision.json"
    write_hitl_promotion_artifact(decision, decision_path)

    boundary = create_hitl_approval_boundary(
        promotion_decision_ref=artifact_ref(decision, path=decision_path, role="promotion_decision"),
        promotion_request_ref=artifact_ref(request, path=request_path, role="promotion_request"),
        permitted_candidate_scope={"allowed_profiles": [str(session["target"])]},
        denied_boundaries=[
            "runtime execution",
            "model execution",
            "shell execution",
            "Goose runtime activation",
            "deepagents construction",
            "MCP invocation",
            "target repo writes",
            "memory mutation",
        ],
        source_decision_result=str(decision["decision_result"]),
        source_decision_record_state=str(decision["record_state"]),
    )
    boundary_errors = validate_hitl_approval_boundary(boundary)
    if boundary_errors:
        raise WorkflowError("created invalid approval boundary: " + "; ".join(boundary_errors))
    boundary_path = paths["artifacts"] / "hitl-approval-boundary.json"
    write_hitl_promotion_artifact(boundary, boundary_path)

    transition = create_workflow_transition(
        session_id=str(session["session_id"]),
        from_stage="planned",
        to_stage="promoted",
        command="builder workflow promote",
        subject_refs=[
            artifact_ref(request, path=request_path, role="promotion_request"),
            artifact_ref(review, path=review_path, role="promotion_review"),
            artifact_ref(decision, path=decision_path, role="promotion_decision"),
            artifact_ref(boundary, path=boundary_path, role="approval_boundary"),
        ],
        reason="Passive HITL promotion boundary recorded.",
    )
    transition_path = paths["artifacts"] / "workflow-transition-promote.json"
    transition_errors = validate_workflow_transition(transition)
    if transition_errors:
        raise WorkflowError("created invalid workflow transition: " + "; ".join(transition_errors))
    write_workflow_record(transition, transition_path)
    subjects = list(transition["subject_refs"])
    subjects.append(
        artifact_ref(transition, path=transition_path, role="workflow_transition", name="promotion transition")
    )
    _event, _event_path, status = _record_event(
        output_dir=output_dir,
        session=session,
        event_type="workflow_promoted",
        subject_refs=subjects,
        command_surface="builder workflow promote",
        message="Passive HITL promotion boundary created.",
        decision_result=str(decision["decision_result"]),
    )
    return status


def candidate_workflow(*, output_dir: Path) -> dict[str, Any]:
    session, _status, paths = _require_stage(output_dir, "promoted")
    artifacts = paths["artifacts"]
    boundary = _read_json(artifacts / "hitl-approval-boundary.json")
    decision = _read_json(artifacts / "hitl-promotion-decision.json")
    review = _read_json(artifacts / "hitl-promotion-review.json")
    request = _read_json(artifacts / "hitl-promotion-request.json")
    proposal = _read_json(artifacts / "deepagents-work-plan.json")
    target_artifact = _read_json(artifacts / "target-profile.json")
    verification_artifact = _read_json(artifacts / "verification-profile.json")

    command_authority_path = Path.cwd() / "docs" / "COMMAND_AUTHORITY.md"
    command_authority_ref = {
        "kind": "builder_ii.command_authority",
        "path": str(command_authority_path),
        "sha256": hashlib_file(command_authority_path),
        "role": "command_authority",
        "name": "command authority registry markdown",
    }

    manifest = create_execution_candidate_manifest(
        approval_boundary_ref=artifact_ref(
            boundary, path=artifacts / "hitl-approval-boundary.json", role="approval_boundary"
        ),
        promotion_decision_ref=artifact_ref(
            decision, path=artifacts / "hitl-promotion-decision.json", role="promotion_decision"
        ),
        promotion_review_ref=artifact_ref(
            review, path=artifacts / "hitl-promotion-review.json", role="promotion_review"
        ),
        promotion_request_ref=artifact_ref(
            request, path=artifacts / "hitl-promotion-request.json", role="promotion_request"
        ),
        source_proposal_refs=[
            artifact_ref(proposal, path=artifacts / "deepagents-work-plan.json", role="source_proposal")
        ],
        target_profile_ref=artifact_ref(target_artifact, path=artifacts / "target-profile.json", role="target_profile"),
        command_authority_ref=command_authority_ref,
        verification_profile_ref=artifact_ref(
            verification_artifact, path=artifacts / "verification-profile.json", role="verification_profile"
        ),
        rollback_requirements={
            "rollback_required": True,
            "no_mutation_assertion": True,
        },
        verification_requirements={
            "verification_required": True,
            "verification_executed": False,
        },
        candidate_scope={
            "target_profile": session["target"],
            "core_workbench_coupling": "NONE",
            "command_previews": ["builder-hitl validate-candidate-manifest"],
        },
        source_approval_boundary_record_state=str(boundary.get("record_state", "")),
        source_approval_boundary_decision_result=str(boundary.get("source_decision_result", "")),
        source_approval_boundary_decision_record_state=str(boundary.get("source_decision_record_state", "")),
        source_approval_boundary_requires_separate_execution_candidate=bool(
            boundary.get("requires_separate_execution_candidate")
        ),
    )
    manifest_errors = validate_execution_candidate_manifest(manifest)
    if manifest_errors:
        raise WorkflowError("created invalid execution candidate manifest: " + "; ".join(manifest_errors))
    manifest_path = artifacts / "execution-candidate-manifest.json"
    write_execution_candidate_manifest(manifest, manifest_path)

    validation = create_execution_candidate_manifest_validation_report(
        [artifact_ref(manifest, path=manifest_path, role="subject", name="execution candidate manifest")],
        valid=True,
        errors=[],
        warnings=["Validation is structural only; no runtime execution occurred."],
        checked_invariants=[
            "all authority flags false",
            "rollback/no-mutation assertion present",
            "verification requirement present",
            "command preview classified by command authority registry",
        ],
    )
    validation_errors = validate_execution_candidate_manifest_validation_report(validation)
    if validation_errors:
        raise WorkflowError("created invalid candidate validation report: " + "; ".join(validation_errors))
    validation_path = artifacts / "execution-candidate-validation-report.json"
    write_execution_candidate_manifest_validation_report(validation, validation_path)

    transition = create_workflow_transition(
        session_id=str(session["session_id"]),
        from_stage="promoted",
        to_stage="candidate",
        command="builder workflow candidate",
        subject_refs=[
            artifact_ref(manifest, path=manifest_path, role="execution_candidate_manifest"),
            artifact_ref(validation, path=validation_path, role="execution_candidate_validation_report"),
        ],
        reason="Passive execution candidate recorded without activation authority.",
    )
    transition_path = artifacts / "workflow-transition-candidate.json"
    transition_errors = validate_workflow_transition(transition)
    if transition_errors:
        raise WorkflowError("created invalid workflow transition: " + "; ".join(transition_errors))
    write_workflow_record(transition, transition_path)
    subjects = list(transition["subject_refs"])
    subjects.append(
        artifact_ref(transition, path=transition_path, role="workflow_transition", name="candidate transition")
    )
    _event, _event_path, status = _record_event(
        output_dir=output_dir,
        session=session,
        event_type="workflow_candidate_recorded",
        subject_refs=subjects,
        command_surface="builder workflow candidate",
        message="Passive execution candidate manifest created.",
        decision_result="candidate_recorded",
    )
    return status


def verify_chain_workflow(*, output_dir: Path) -> dict[str, Any]:
    session, _status, paths = _require_stage(output_dir, "candidate")
    artifacts = paths["artifacts"]
    index = create_artifact_index_record(artifacts, recursive=False)
    index_path = artifacts / "artifact-index.json"
    write_artifact_index_record(index, index_path)

    chain_paths = _artifact_paths(paths)
    chain = verify_artifact_chain(chain_paths)
    chain_path = artifacts / "chain-verification-report.json"
    _write_json(chain, chain_path)
    if not chain.get("valid"):
        raise WorkflowError("artifact chain verification failed: " + "; ".join(chain.get("errors", [])))

    transition = create_workflow_transition(
        session_id=str(session["session_id"]),
        from_stage="candidate",
        to_stage="chain_verified",
        command="builder workflow verify-chain",
        subject_refs=[
            artifact_ref(index, path=index_path, role="artifact_index"),
            artifact_ref(chain, path=chain_path, role="artifact_chain_verification_report"),
        ],
        reason="Artifact index and chain verification completed for passive workflow artifacts.",
    )
    transition_path = artifacts / "workflow-transition-verify-chain.json"
    transition_errors = validate_workflow_transition(transition)
    if transition_errors:
        raise WorkflowError("created invalid workflow transition: " + "; ".join(transition_errors))
    write_workflow_record(transition, transition_path)
    subjects = list(transition["subject_refs"])
    subjects.append(
        artifact_ref(transition, path=transition_path, role="workflow_transition", name="verify-chain transition")
    )
    _event, _event_path, status = _record_event(
        output_dir=output_dir,
        session=session,
        event_type="workflow_chain_verified",
        subject_refs=subjects,
        command_surface="builder workflow verify-chain",
        message="Passive workflow artifact chain verified.",
        decision_result="chain_verified",
    )
    return status


def handoff_workflow(*, output_dir: Path) -> dict[str, Any]:
    session, _status, paths = _require_stage(output_dir, "chain_verified")
    artifacts = paths["artifacts"]
    chain_path = artifacts / "chain-verification-report.json"
    chain = _read_json(chain_path)
    ledger = _read_json(paths["ledger"])
    replay = _read_json(paths["replay"])

    handoff = create_handoff_note(
        target_name=str(session["target"]),
        summary="Passive governed workflow chain reached handoff readiness. No runtime execution, model calls, shell commands, MCP calls, Goose activation, deepagents construction, or target repository writes occurred.",
        next_recommended_action="Review the chain verification report and decide whether a separate promoted runtime capability is warranted.",
        changed_files_summary=[],
        verification_summary="Artifact chain verification is referenced. Planned verification commands were not executed by this workflow.",
        verification_evidence_refs=[
            artifact_ref(
                chain, path=chain_path, role="artifact_chain_verification_report", name="chain verification report"
            )
        ],
        open_risks=[
            "Runtime activation remains disabled.",
            "Candidate manifest validation is structural only.",
            "Planned verification commands still require separate HITL execution promotion.",
        ],
        status="READY_FOR_REVIEW",
    )
    handoff_path = artifacts / "handoff-note.json"
    write_handoff_note(handoff, handoff_path)

    golden = {
        "kind": "builder_ii.golden_path_chain",
        "schema_version": 1,
        "session_id": session["session_id"],
        "target": session["target"],
        "task": session["task"],
        "status": "ready_for_review",
        "workflow_status_ref": artifact_ref(_read_json(paths["status"]), path=paths["status"], role="workflow_status"),
        "event_ledger_ref": artifact_ref(ledger, path=paths["ledger"], role="event_ledger"),
        "replay_report_ref": artifact_ref(replay, path=paths["replay"], role="ledger_replay_report"),
        "chain_verification_ref": artifact_ref(chain, path=chain_path, role="artifact_chain_verification_report"),
        "handoff_ref": artifact_ref(handoff, path=handoff_path, role="handoff_note"),
        "runtime_authority": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED",
    }
    golden_path = output_dir / "GOLDEN_PATH_CHAIN_v1.json"
    _write_json(golden, golden_path)
    readme_path = output_dir / "GOLDEN_PATH_DEMO_README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# Golden Path Demo",
                "",
                f"Session: `{session['session_id']}`",
                f"Target: `{session['target']}`",
                "",
                "This workflow produced a passive, governed chain from planning through handoff.",
                "It did not execute commands, call models, start Goose, construct deepagents, invoke MCP, or write to the target repository.",
                "",
                "Review order:",
                "",
                "1. `artifacts/workflow-status.json`",
                "2. `artifacts/event-ledger.json`",
                "3. `artifacts/hierarchical-frame.json`",
                "4. `artifacts/execution-candidate-manifest.json`",
                "5. `artifacts/chain-verification-report.json`",
                "6. `artifacts/handoff-note.json`",
                "",
            ]
        ),
        encoding="utf-8",
    )

    transition = create_workflow_transition(
        session_id=str(session["session_id"]),
        from_stage="chain_verified",
        to_stage="handoff_ready",
        command="builder workflow handoff",
        subject_refs=[
            artifact_ref(handoff, path=handoff_path, role="handoff_note"),
            artifact_ref(golden, path=golden_path, role="golden_path_chain"),
        ],
        reason="Passive workflow handoff produced for operator review.",
    )
    transition_path = artifacts / "workflow-transition-handoff.json"
    transition_errors = validate_workflow_transition(transition)
    if transition_errors:
        raise WorkflowError("created invalid workflow transition: " + "; ".join(transition_errors))
    write_workflow_record(transition, transition_path)
    subjects = list(transition["subject_refs"])
    subjects.append(
        artifact_ref(transition, path=transition_path, role="workflow_transition", name="handoff transition")
    )
    _event, _event_path, status = _record_event(
        output_dir=output_dir,
        session=session,
        event_type="workflow_handoff_ready",
        subject_refs=subjects,
        command_surface="builder workflow handoff",
        message="Passive handoff and golden path summary created.",
        decision_result="handoff_ready",
    )
    return status


def workflow_status(*, output_dir: Path) -> dict[str, Any]:
    session, _session_path, _paths_map = _session_context(output_dir)
    return _write_status_from_events(session, output_dir)
