from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import Settings, load_settings
from builder_ii.event_ledger import (
    create_event_ledger,
    create_event_record,
    replay_events,
    write_event_ledger,
    write_event_record,
)
from builder_ii.target_profiles import (
    TargetName,
    target_profile,
    write_target_profile_artifact,
)
from builder_ii.workflow_records import (
    artifact_ref,
    create_workflow_session,
    create_workflow_status,
    write_workflow_record,
)

TARGET_INSPECTION_PLAN_KIND = "builder_ii.target_inspection_plan"
TARGET_PATCH_PROPOSAL_KIND = "builder_ii.target_patch_proposal"
TARGET_VERIFICATION_PLAN_KIND = "builder_ii.target_verification_plan"
TARGET_DEMO_SCHEMA_VERSION = 1


def get_forbidden_authority_boundaries() -> dict[str, Any]:
    return {
        "runtime_authority": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "mcp": "DISABLED",
        "goose_runtime": "DISABLED",
        "deepagents_runtime": "DISABLED",
        "source_writes": "DISABLED",
        "commit_push_automation": "DISABLED",
        "core_workbench_coupling": "NONE",
    }


def create_target_inspection_plan(
    *,
    title: str,
    target_profile: str,
    target_repo: str,
    agent_profile: str,
    inspection_scope: list[str],
    target_profile_ref: dict[str, Any] | None = None,
    workflow_session_ref: dict[str, Any] | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": TARGET_INSPECTION_PLAN_KIND,
        "schema_version": TARGET_DEMO_SCHEMA_VERSION,
        "title": title.strip(),
        "target_profile": target_profile.strip(),
        "target_repo": target_repo.strip(),
        "agent_profile": agent_profile.strip(),
        "inspection_scope": list(inspection_scope),
        "governance": get_forbidden_authority_boundaries(),
        "notes": list(notes or []),
        "target_profile_ref": target_profile_ref,
        "workflow_session_ref": workflow_session_ref,
    }


def create_target_patch_proposal(
    *,
    title: str,
    target_profile: str,
    target_repo: str,
    agent_profile: str,
    proposed_changes: list[str],
    invariant_impact: str,
    inspection_plan_ref: dict[str, Any],
    target_profile_ref: dict[str, Any] | None = None,
    workflow_session_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": TARGET_PATCH_PROPOSAL_KIND,
        "schema_version": TARGET_DEMO_SCHEMA_VERSION,
        "title": title.strip(),
        "target_profile": target_profile.strip(),
        "target_repo": target_repo.strip(),
        "agent_profile": agent_profile.strip(),
        "proposed_changes": list(proposed_changes),
        "invariant_impact": invariant_impact.strip(),
        "governance": get_forbidden_authority_boundaries(),
        "inspection_plan_ref": inspection_plan_ref,
        "target_profile_ref": target_profile_ref,
        "workflow_session_ref": workflow_session_ref,
    }


def create_target_verification_plan(
    *,
    title: str,
    target_profile: str,
    target_repo: str,
    agent_profile: str,
    proposed_commands: list[str],
    pass_criteria: str,
    patch_proposal_ref: dict[str, Any],
    target_profile_ref: dict[str, Any] | None = None,
    workflow_session_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": TARGET_VERIFICATION_PLAN_KIND,
        "schema_version": TARGET_DEMO_SCHEMA_VERSION,
        "title": title.strip(),
        "target_profile": target_profile.strip(),
        "target_repo": target_repo.strip(),
        "agent_profile": agent_profile.strip(),
        "proposed_commands": list(proposed_commands),
        "pass_criteria": pass_criteria.strip(),
        "governance": get_forbidden_authority_boundaries(),
        "patch_proposal_ref": patch_proposal_ref,
        "target_profile_ref": target_profile_ref,
        "workflow_session_ref": workflow_session_ref,
    }


def _validate_governance(data: dict[str, Any], errors: list[str]) -> None:
    gov = data.get("governance")
    if not isinstance(gov, dict):
        errors.append("Missing or invalid 'governance' block.")
        return
    expected = get_forbidden_authority_boundaries()
    for key, val in expected.items():
        if gov.get(key) != val:
            errors.append(f"Forbidden authority violation: governance[{key}] expected '{val}', got '{gov.get(key)}'.")


def _validate_ref(data: dict[str, Any], field: str, errors: list[str]) -> None:
    ref = data.get(field)
    if not isinstance(ref, dict) or not ref.get("path") or not ref.get("sha256"):
        errors.append(f"Missing or invalid '{field}'.")


def validate_target_inspection_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Record must be a JSON object."]
    if data.get("kind") != TARGET_INSPECTION_PLAN_KIND:
        errors.append(f"Expected kind '{TARGET_INSPECTION_PLAN_KIND}', got '{data.get('kind')}'.")
    if data.get("schema_version") != TARGET_DEMO_SCHEMA_VERSION:
        errors.append(f"Expected schema_version {TARGET_DEMO_SCHEMA_VERSION}, got {data.get('schema_version')}.")
    for field in ("title", "target_profile", "target_repo", "agent_profile"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f"Missing required non-empty field '{field}'.")
    scope = data.get("inspection_scope")
    if not isinstance(scope, list) or len(scope) == 0 or not all(isinstance(x, str) and x.strip() for x in scope):
        errors.append("Field 'inspection_scope' must be a non-empty list of strings.")
    _validate_ref(data, "target_profile_ref", errors)
    _validate_ref(data, "workflow_session_ref", errors)
    _validate_governance(data, errors)
    return errors


def validate_target_patch_proposal(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Record must be a JSON object."]
    if data.get("kind") != TARGET_PATCH_PROPOSAL_KIND:
        errors.append(f"Expected kind '{TARGET_PATCH_PROPOSAL_KIND}', got '{data.get('kind')}'.")
    if data.get("schema_version") != TARGET_DEMO_SCHEMA_VERSION:
        errors.append(f"Expected schema_version {TARGET_DEMO_SCHEMA_VERSION}, got {data.get('schema_version')}.")
    for field in ("title", "target_profile", "target_repo", "agent_profile", "invariant_impact"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f"Missing required non-empty field '{field}'.")
    changes = data.get("proposed_changes")
    if not isinstance(changes, list) or len(changes) == 0 or not all(isinstance(x, str) and x.strip() for x in changes):
        errors.append("Field 'proposed_changes' must be a non-empty list of strings.")
    _validate_ref(data, "target_profile_ref", errors)
    _validate_ref(data, "workflow_session_ref", errors)
    _validate_ref(data, "inspection_plan_ref", errors)
    _validate_governance(data, errors)
    return errors


def validate_target_verification_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Record must be a JSON object."]
    if data.get("kind") != TARGET_VERIFICATION_PLAN_KIND:
        errors.append(f"Expected kind '{TARGET_VERIFICATION_PLAN_KIND}', got '{data.get('kind')}'.")
    if data.get("schema_version") != TARGET_DEMO_SCHEMA_VERSION:
        errors.append(f"Expected schema_version {TARGET_DEMO_SCHEMA_VERSION}, got {data.get('schema_version')}.")
    for field in ("title", "target_profile", "target_repo", "agent_profile", "pass_criteria"):
        if not isinstance(data.get(field), str) or not data[field].strip():
            errors.append(f"Missing required non-empty field '{field}'.")
    cmds = data.get("proposed_commands")
    if not isinstance(cmds, list) or len(cmds) == 0 or not all(isinstance(x, str) and x.strip() for x in cmds):
        errors.append("Field 'proposed_commands' must be a non-empty list of strings.")
    _validate_ref(data, "target_profile_ref", errors)
    _validate_ref(data, "workflow_session_ref", errors)
    _validate_ref(data, "patch_proposal_ref", errors)
    _validate_governance(data, errors)
    return errors


def _write_json(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json_lib.loads(path.read_text(encoding="utf-8"))


def write_target_inspection_plan(record: dict[str, Any], path: Path) -> None:
    errors = validate_target_inspection_plan(record)
    if errors:
        raise ValueError(f"Invalid target inspection plan: {errors}")
    _write_json(record, path)


def write_target_patch_proposal(record: dict[str, Any], path: Path) -> None:
    errors = validate_target_patch_proposal(record)
    if errors:
        raise ValueError(f"Invalid target patch proposal: {errors}")
    _write_json(record, path)


def write_target_verification_plan(record: dict[str, Any], path: Path) -> None:
    errors = validate_target_verification_plan(record)
    if errors:
        raise ValueError(f"Invalid target verification plan: {errors}")
    _write_json(record, path)


def generate_readonly_founder_demo(
    settings: Settings | None = None,
    target: TargetName = "core",
    output_dir: Path | None = None,
    *,
    session_id: str | None = None,
) -> dict[str, Path]:
    settings = settings or load_settings()
    out = output_dir or (Path.cwd() / ".builder" / "demos" / f"{target}-readonly")
    out.mkdir(parents=True, exist_ok=True)
    artifacts_dir = out / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    events_dir = out / "events"
    events_dir.mkdir(parents=True, exist_ok=True)

    profile = target_profile(settings, target)
    target_path = artifacts_dir / "target-profile.json"
    write_target_profile_artifact(profile, target_path)
    target_ref = artifact_ref(_read_json(target_path), path=target_path, role="target_profile")

    sess_id = session_id or f"wf-{target}-readonly-founder-demo"
    session = create_workflow_session(
        session_id=sess_id,
        target=target,
        task=f"Passive read-only founder inspection and planning for {target}",
        output_dir=out,
        artifacts_dir=artifacts_dir,
        events_dir=events_dir,
    )
    sess_path = artifacts_dir / "workflow-session.json"
    write_workflow_record(session, sess_path)
    sess_ref = artifact_ref(session, path=sess_path, role="workflow_session")

    event1 = create_event_record(
        event_id=f"{sess_id}:0001:workflow_initialized",
        session_id=sess_id,
        sequence=1,
        event_type="workflow_initialized",
        stage="initialized",
        subject_refs=[target_ref],
        command_surface="builder-targets generate-demo",
        policy_snapshot_ref=target_ref,
        message=f"Initialized passive read-only founder demo workflow for {target}",
    )
    event1_path = events_dir / "0001-workflow_initialized.json"
    write_event_record(event1, event1_path)
    event1_ref = artifact_ref(event1, path=event1_path, role="event_record")

    prefix = target.upper()
    inspection_path = artifacts_dir / f"{prefix}_INSPECTION_PLAN_v1.json"
    inspection_plan = create_target_inspection_plan(
        title=f"{prefix} read-only founder inspection plan",
        target_profile=target,
        target_repo=str(profile.repo),
        agent_profile=f"{target}.invariant_auditor" if target == "core" else f"{target}.repo_mapper",
        inspection_scope=["README.md", "AGENTS.md", "GROK.md", "CLAUDE.md", "docs", "tests"] if target == "core" else ["README.md", "src", "tests"],
        target_profile_ref=target_ref,
        workflow_session_ref=sess_ref,
        notes=["Passive inspection only; no execution authority granted.", "Inspect deterministic verification spine and versor condition gates."] if target == "core" else ["Passive inspection only."],
    )
    write_target_inspection_plan(inspection_plan, inspection_path)
    _write_json(inspection_plan, out / f"{prefix}_INSPECTION_PLAN_v1.json")
    inspection_ref = artifact_ref(inspection_plan, path=inspection_path, role="target_inspection_plan")

    event2 = create_event_record(
        event_id=f"{sess_id}:0002:workflow_planned",
        session_id=sess_id,
        sequence=2,
        event_type="workflow_planned",
        stage="planned",
        subject_refs=[inspection_ref],
        command_surface="builder-targets generate-demo",
        policy_snapshot_ref=target_ref,
        previous_event_ref=event1_ref,
        message=f"Generated passive inspection plan for {target}",
    )
    event2_path = events_dir / "0002-workflow_planned.json"
    write_event_record(event2, event2_path)
    event2_ref = artifact_ref(event2, path=event2_path, role="event_record")

    proposal_path = artifacts_dir / f"{prefix}_PATCH_PROPOSAL_v1.json"
    patch_proposal = create_target_patch_proposal(
        title=f"{prefix} passive patch proposal",
        target_profile=target,
        target_repo=str(profile.repo),
        agent_profile=f"{target}.patch_planner",
        proposed_changes=["Propose documentation alignment in AGENTS.md for passive inspection targets.", "Propose test fixture harness addition without modifying runtime execution engine."] if target == "core" else ["Propose non-mutating planning target setup."],
        invariant_impact="Preserves exact CGA recall, versor_condition(F) < 1e-6, and temperature 0 deterministic boundaries. No runtime execution or model loops modified." if target == "core" else "Preserves repository local boundaries.",
        inspection_plan_ref=inspection_ref,
        target_profile_ref=target_ref,
        workflow_session_ref=sess_ref,
    )
    write_target_patch_proposal(patch_proposal, proposal_path)
    _write_json(patch_proposal, out / f"{prefix}_PATCH_PROPOSAL_v1.json")
    proposal_ref = artifact_ref(patch_proposal, path=proposal_path, role="target_patch_proposal")

    event3 = create_event_record(
        event_id=f"{sess_id}:0003:workflow_promoted",
        session_id=sess_id,
        sequence=3,
        event_type="workflow_promoted",
        stage="promoted",
        subject_refs=[proposal_ref],
        command_surface="builder-targets generate-demo",
        policy_snapshot_ref=target_ref,
        previous_event_ref=event2_ref,
        message=f"Generated passive patch proposal for {target}",
    )
    event3_path = events_dir / "0003-workflow_promoted.json"
    write_event_record(event3, event3_path)
    event3_ref = artifact_ref(event3, path=event3_path, role="event_record")

    verification_path = artifacts_dir / f"{prefix}_VERIFICATION_PLAN_v1.json"
    verification_plan = create_target_verification_plan(
        title=f"{prefix} passive verification plan",
        target_profile=target,
        target_repo=str(profile.repo),
        agent_profile=f"{target}.verification_planner",
        proposed_commands=["builder verify <changed-path>", "uv run pytest -q focused_suite"] if target == "core" else ["pytest -q"],
        pass_criteria="All deterministic verification tests pass; no source writes or git mutations occur during verification planning.",
        patch_proposal_ref=proposal_ref,
        target_profile_ref=target_ref,
        workflow_session_ref=sess_ref,
    )
    write_target_verification_plan(verification_plan, verification_path)
    _write_json(verification_plan, out / f"{prefix}_VERIFICATION_PLAN_v1.json")
    verification_ref = artifact_ref(verification_plan, path=verification_path, role="target_verification_plan")

    event4 = create_event_record(
        event_id=f"{sess_id}:0004:workflow_candidate_recorded",
        session_id=sess_id,
        sequence=4,
        event_type="workflow_candidate_recorded",
        stage="candidate",
        subject_refs=[verification_ref],
        command_surface="builder-targets generate-demo",
        policy_snapshot_ref=target_ref,
        previous_event_ref=event3_ref,
        message=f"Generated passive verification plan for {target}",
    )
    event4_path = events_dir / "0004-workflow_candidate_recorded.json"
    write_event_record(event4, event4_path)

    event_records = [(event1, event1_path), (event2, event2_path), (event3, event3_path), (event4, event4_path)]
    replay = replay_events(event_records, session_id=sess_id)
    replay_path = artifacts_dir / "ledger-replay-report.json"
    _write_json(replay, replay_path)

    ledger = create_event_ledger(
        session_id=sess_id,
        event_records=event_records,
        replay_report=replay,
        replay_report_path=replay_path,
    )
    ledger_path = artifacts_dir / "event-ledger.json"
    write_event_ledger(ledger, ledger_path)

    status = create_workflow_status(
        session_id=sess_id,
        target=target,
        task=f"Passive read-only founder inspection and planning for {target}",
        current_stage=str(replay["current_stage"]),
        completed_stages=list(replay["completed_stages"]),
        artifact_refs=[target_ref, sess_ref, inspection_ref, proposal_ref, verification_ref],
        last_event_ref=replay.get("last_event_ref"),
        event_count=int(replay["event_count"]),
        valid_replay=bool(replay["valid"]),
        replay_errors=list(replay["errors"]),
    )
    status_path = artifacts_dir / "workflow-status.json"
    write_workflow_record(status, status_path)

    return {
        "inspection_plan": inspection_path,
        "patch_proposal": proposal_path,
        "verification_plan": verification_path,
        "event_ledger": ledger_path,
        "workflow_session": sess_path,
        "workflow_status": status_path,
        "replay_report": replay_path,
    }
