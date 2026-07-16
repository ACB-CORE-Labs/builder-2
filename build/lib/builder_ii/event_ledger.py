from __future__ import annotations

import asyncio
import json as json_lib
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any

from builder_ii.workflow_records import (
    WORKFLOW_STAGE_ORDER,
    artifact_ref,
    canonical_digest,
)

EVENT_RECORD_KIND = "builder_ii.event_record"
EVENT_RECORD_SCHEMA_VERSION = 1

EVENT_LEDGER_KIND = "builder_ii.event_ledger"
EVENT_LEDGER_SCHEMA_VERSION = 1

LEDGER_REPLAY_REPORT_KIND = "builder_ii.ledger_replay_report"
LEDGER_REPLAY_REPORT_SCHEMA_VERSION = 1

EVENT_TYPES = {
    "workflow_initialized",
    "workflow_planned",
    "workflow_promoted",
    "workflow_candidate_recorded",
    "workflow_chain_verified",
    "workflow_handoff_ready",
    "read_executed",
    "read_denied",
    "goose_readonly_started",
    "goose_readonly_closed",
    "goose_mutation_prevented",
    "deepagents_runtime_executed",
    "deepagents_runtime_failed",
    "model_call_executed",
    "model_call_failed",
    "tool_call_executed",
    "tool_call_denied",
    "tool_call_failed",
    "mcp_call_executed",
    "mcp_call_denied",
    "mcp_call_failed",
}

EVENT_TYPE_STAGE = {
    "workflow_initialized": "initialized",
    "workflow_planned": "planned",
    "workflow_promoted": "promoted",
    "workflow_candidate_recorded": "candidate",
    "workflow_chain_verified": "chain_verified",
    "workflow_handoff_ready": "handoff_ready",
}

NEXT_ALLOWED_TRANSITIONS = {
    "initialized": ["builder workflow plan"],
    "planned": ["builder workflow promote"],
    "promoted": ["builder workflow candidate"],
    "candidate": ["builder workflow verify-chain"],
    "chain_verified": ["builder workflow handoff"],
    "handoff_ready": [],
}


def _default_governance(capability_state: str) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime": "DISABLED",
        "mcp_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "core_workbench_coupling": "NONE",
    }


def _builder_ii_version() -> str:
    try:
        return metadata.version("builder-ii")
    except metadata.PackageNotFoundError:
        return "0.1.0+source"


def create_event_record(
    *,
    event_id: str,
    session_id: str,
    sequence: int,
    event_type: str,
    stage: str,
    subject_refs: list[dict[str, Any]],
    command_surface: str,
    policy_snapshot_ref: dict[str, Any],
    previous_event_ref: dict[str, Any] | None = None,
    message: str = "",
    actor: str = "builder workflow orchestrator",
    decision_result: str = "recorded",
    repo_commit: str = "NOT_QUERIED_NO_GIT_SUBPROCESS",
    builder_ii_version: str | None = None,
) -> dict[str, Any]:
    payload_sha256 = canonical_digest(
        {
            "event_type": event_type,
            "stage": stage,
            "subject_refs": list(subject_refs),
            "message": message.strip(),
            "decision_result": decision_result.strip() or "recorded",
        }
    )
    return {
        "kind": EVENT_RECORD_KIND,
        "schema_version": EVENT_RECORD_SCHEMA_VERSION,
        "event_state": "RECORDED_ONLY",
        "event_id": event_id,
        "session_id": session_id,
        "sequence": sequence,
        "event_type": event_type,
        "stage": stage,
        "recorded_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "actor": actor.strip() or "builder workflow orchestrator",
        "command_surface": command_surface.strip(),
        "message": message.strip(),
        "payload_sha256": payload_sha256,
        "policy_snapshot_ref": policy_snapshot_ref,
        "decision_result": decision_result.strip() or "recorded",
        "previous_event_sha256": previous_event_ref.get("sha256") if isinstance(previous_event_ref, dict) else None,
        "repo_commit": repo_commit.strip() or "NOT_QUERIED_NO_GIT_SUBPROCESS",
        "builder_ii_version": builder_ii_version or _builder_ii_version(),
        "next_allowed_transitions": NEXT_ALLOWED_TRANSITIONS.get(stage, []),
        "subject_refs": list(subject_refs),
        "previous_event_ref": previous_event_ref,
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "governance": _default_governance("event_record"),
    }


def create_event_ledger(
    *,
    session_id: str,
    event_records: list[tuple[dict[str, Any], Path]],
    replay_report: dict[str, Any],
    replay_report_path: Path,
) -> dict[str, Any]:
    event_refs = [
        artifact_ref(event, path=path, role="event", name=str(event.get("event_type", "")))
        for event, path in event_records
    ]
    return {
        "kind": EVENT_LEDGER_KIND,
        "schema_version": EVENT_LEDGER_SCHEMA_VERSION,
        "ledger_state": "RECORDED_ONLY",
        "session_id": session_id,
        "event_count": len(event_refs),
        "event_refs": event_refs,
        "last_event_ref": event_refs[-1] if event_refs else None,
        "replay_report_ref": artifact_ref(
            replay_report,
            path=replay_report_path,
            role="replay_report",
            name="ledger replay report",
        ),
        "reconstructed_status": {
            "valid": replay_report.get("valid", False),
            "current_stage": replay_report.get("current_stage", ""),
            "completed_stages": replay_report.get("completed_stages", []),
        },
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "governance": _default_governance("event_ledger"),
    }


def _event_sort_key(item: tuple[dict[str, Any], Path]) -> tuple[int, str]:
    event, path = item
    sequence = event.get("sequence")
    return (sequence if isinstance(sequence, int) else 10**9, str(path))


def replay_events(
    event_records: list[tuple[dict[str, Any], Path]],
    *,
    session_id: str | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    ordered = sorted(event_records, key=_event_sort_key)
    completed: list[str] = []
    current_stage = "initialized"
    last_ref: dict[str, Any] | None = None
    expected_sequence = 1
    seen_ids: set[str] = set()
    replay_session_id = session_id or (str(ordered[0][0].get("session_id", "")) if ordered else "")

    for index, (event, path) in enumerate(ordered):
        event_errors = validate_event_record(event)
        if event_errors:
            errors.extend(f"{path}: {error}" for error in event_errors)
            continue
        if replay_session_id and event.get("session_id") != replay_session_id:
            errors.append(f"{path}: session_id does not match replay session")
        event_id = str(event.get("event_id", ""))
        if event_id in seen_ids:
            errors.append(f"{path}: duplicate event_id {event_id}")
        seen_ids.add(event_id)

        sequence = event.get("sequence")
        if sequence != expected_sequence:
            errors.append(f"{path}: sequence must be {expected_sequence}")
        expected_sequence += 1

        stage = str(event.get("stage", ""))
        expected_stage = EVENT_TYPE_STAGE.get(str(event.get("event_type", "")))
        if expected_stage is not None:
            if expected_stage != stage:
                errors.append(f"{path}: stage does not match event_type")
        else:
            if stage != current_stage:
                errors.append(f"{path}: non-transition event stage {stage} must match current stage {current_stage}")

        if index == 0:
            if event.get("previous_event_ref") is not None:
                errors.append(f"{path}: first event must not have previous_event_ref")
            if event.get("previous_event_sha256") is not None:
                errors.append(f"{path}: first event must not have previous_event_sha256")
        else:
            prev_ref = event.get("previous_event_ref")
            if not isinstance(prev_ref, dict):
                errors.append(f"{path}: previous_event_ref is required after first event")
            elif last_ref and prev_ref.get("sha256") != last_ref.get("sha256"):
                errors.append(f"{path}: previous_event_ref.sha256 does not match prior event")
            if last_ref and event.get("previous_event_sha256") != last_ref.get("sha256"):
                errors.append(f"{path}: previous_event_sha256 does not match prior event")

        if stage not in WORKFLOW_STAGE_ORDER:
            errors.append(f"{path}: unknown stage {stage}")
        elif WORKFLOW_STAGE_ORDER[stage] < WORKFLOW_STAGE_ORDER[current_stage]:
            errors.append(f"{path}: stage regressed from {current_stage} to {stage}")
        elif WORKFLOW_STAGE_ORDER[stage] > WORKFLOW_STAGE_ORDER[current_stage] + 1:
            errors.append(f"{path}: stage skipped from {current_stage} to {stage}")
        else:
            current_stage = stage
            if stage not in completed:
                completed.append(stage)

        last_ref = {
            "role": "event",
            "kind": EVENT_RECORD_KIND,
            "path": str(path),
            "sha256": canonical_digest(event),
            "name": str(event.get("event_type", "")),
            "required": True,
        }

    valid = not errors
    return {
        "kind": LEDGER_REPLAY_REPORT_KIND,
        "schema_version": LEDGER_REPLAY_REPORT_SCHEMA_VERSION,
        "replay_state": "REPLAYED_ONLY",
        "session_id": replay_session_id,
        "valid": valid,
        "status": "valid" if valid else "invalid",
        "event_count": len(ordered),
        "current_stage": current_stage,
        "completed_stages": completed,
        "last_event_ref": last_ref,
        "errors": errors,
        "warnings": warnings,
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "governance": _default_governance("ledger_replay_report"),
    }


def load_event_records(events_dir: Path) -> list[tuple[dict[str, Any], Path]]:
    wal_path = events_dir / "events.wal"
    if wal_path.exists():
        try:
            from builder_ii.async_ledger_wal import AsyncLedgerWAL

            wal = AsyncLedgerWAL(wal_path)
            records = wal.read_records()
            wal.close()
            return [
                (
                    r,
                    events_dir / f"{r.get('sequence', 0):04d}-{r.get('event_type', 'unknown')}.json",
                )
                for r in records
            ]
        except Exception:
            pass

    records: list[tuple[dict[str, Any], Path]] = []
    if not events_dir.exists():
        return records
    for path in sorted(events_dir.glob("*.json")):
        try:
            data = json_lib.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("kind") == EVENT_RECORD_KIND:
                records.append((data, path))
        except Exception:
            pass
    return records


async def load_event_records_async(events_dir: Path) -> list[tuple[dict[str, Any], Path]]:
    return await asyncio.to_thread(load_event_records, events_dir)


def dumps_event_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_event_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_event_record(record), encoding="utf-8")

    wal_path = output.parent / "events.wal"
    try:
        from builder_ii.async_ledger_wal import AsyncLedgerWAL

        wal = AsyncLedgerWAL(wal_path)
        wal.write_record_sync(record)
        wal.close()
    except Exception:
        pass


async def write_event_record_async(record: dict[str, Any], output: Path) -> None:
    wal_path = output.parent / "events.wal"
    try:
        from builder_ii.async_ledger_wal import AsyncLedgerWAL

        wal = AsyncLedgerWAL(wal_path)
        await wal.write_record(record)
        wal.close()
    except Exception:
        pass
    # Write the JSON file only — do NOT call write_event_record which would
    # double-append to WAL.
    output.parent.mkdir(parents=True, exist_ok=True)
    await asyncio.to_thread(output.write_text, dumps_event_record(record), "utf-8")


def write_event_ledger(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_event_record(record), encoding="utf-8")


async def write_event_ledger_async(record: dict[str, Any], output: Path) -> None:
    await asyncio.to_thread(write_event_ledger, record, output)


def write_ledger_replay_report(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_event_record(record), encoding="utf-8")


async def write_ledger_replay_report_async(record: dict[str, Any], output: Path) -> None:
    await asyncio.to_thread(write_ledger_replay_report, record, output)


def _validate_ref(value: Any, *, field: str, required: bool = True) -> list[str]:
    if value is None:
        return [f"{field} is required"] if required else []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    errors: list[str] = []
    for key in ("role", "kind", "path", "sha256"):
        if not isinstance(value.get(key), str) or not value[key]:
            errors.append(f"{field}.{key} must be a non-empty string")
    if isinstance(value.get("sha256"), str) and len(value["sha256"]) != 64:
        errors.append(f"{field}.sha256 must be a SHA-256 hex digest")
    if not isinstance(value.get("required", True), bool):
        errors.append(f"{field}.required must be a boolean")
    return errors


def _validate_ref_list(value: Any, *, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if not allow_empty and not value:
        return [f"{field} must be a non-empty list"]
    errors: list[str] = []
    for index, item in enumerate(value):
        errors.extend(_validate_ref(item, field=f"{field}[{index}]"))
    return errors


def _validate_governance(record: dict[str, Any], capability_state: str) -> list[str]:
    errors: list[str] = []
    governance = record.get("governance")
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    if governance.get("capability_state") != capability_state:
        errors.append(f"governance.capability_state must be {capability_state}")
    for key in (
        "runtime_execution",
        "model_execution",
        "shell_execution",
        "target_repo_writes",
        "memory_mutation",
        "goose_runtime_start",
        "deepagents_runtime",
        "mcp_execution",
    ):
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "grants_runtime_authority", "grants_action_authority"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false or NOT_AUTHORIZED")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    for key in (
        "executes_model",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "invokes_mcp",
        "mutates_target_repo",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false or NOT_AUTHORIZED")
    return errors


def validate_event_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["event record must be a JSON object"]
    if record.get("kind") != EVENT_RECORD_KIND:
        errors.append(f"kind must be {EVENT_RECORD_KIND}")
    if record.get("schema_version") != EVENT_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EVENT_RECORD_SCHEMA_VERSION}")
    if record.get("event_state") != "RECORDED_ONLY":
        errors.append("event_state must be RECORDED_ONLY")
    for field in (
        "event_id",
        "session_id",
        "event_type",
        "stage",
        "recorded_at",
        "actor",
        "command_surface",
        "payload_sha256",
        "decision_result",
        "repo_commit",
        "builder_ii_version",
    ):
        if not isinstance(record.get(field), str) or not record[field]:
            errors.append(f"{field} must be a non-empty string")
    if isinstance(record.get("payload_sha256"), str) and len(record["payload_sha256"]) != 64:
        errors.append("payload_sha256 must be a SHA-256 hex digest")
    prev_sha = record.get("previous_event_sha256")
    if prev_sha is not None and (not isinstance(prev_sha, str) or len(prev_sha) != 64):
        errors.append("previous_event_sha256 must be null or a SHA-256 hex digest")
    if record.get("event_type") not in EVENT_TYPES:
        errors.append("event_type must be a known event type")
    if record.get("stage") not in WORKFLOW_STAGE_ORDER:
        errors.append("stage must be a known workflow stage")
    elif record.get("next_allowed_transitions") != NEXT_ALLOWED_TRANSITIONS.get(str(record.get("stage")), []):
        errors.append("next_allowed_transitions must match stage")
    if not isinstance(record.get("sequence"), int) or record["sequence"] < 1:
        errors.append("sequence must be a positive integer")
    if not isinstance(record.get("message", ""), str):
        errors.append("message must be a string")
    errors.extend(_validate_ref_list(record.get("subject_refs"), field="subject_refs", allow_empty=True))
    errors.extend(_validate_ref(record.get("previous_event_ref"), field="previous_event_ref", required=False))
    errors.extend(_validate_ref(record.get("policy_snapshot_ref"), field="policy_snapshot_ref"))
    errors.extend(_validate_governance(record, "event_record"))
    return errors


def validate_ledger_replay_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["ledger replay report must be a JSON object"]
    if record.get("kind") != LEDGER_REPLAY_REPORT_KIND:
        errors.append(f"kind must be {LEDGER_REPLAY_REPORT_KIND}")
    if record.get("schema_version") != LEDGER_REPLAY_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {LEDGER_REPLAY_REPORT_SCHEMA_VERSION}")
    if record.get("replay_state") != "REPLAYED_ONLY":
        errors.append("replay_state must be REPLAYED_ONLY")
    if not isinstance(record.get("session_id"), str) or not record["session_id"]:
        errors.append("session_id must be a non-empty string")
    if record.get("status") not in ("valid", "invalid"):
        errors.append("status must be valid or invalid")
    if not isinstance(record.get("valid"), bool):
        errors.append("valid must be a boolean")
    if not isinstance(record.get("event_count"), int) or record["event_count"] < 0:
        errors.append("event_count must be a non-negative integer")
    if record.get("current_stage") not in WORKFLOW_STAGE_ORDER:
        errors.append("current_stage must be a known workflow stage")
    if not isinstance(record.get("completed_stages"), list):
        errors.append("completed_stages must be a list")
    if not isinstance(record.get("errors"), list):
        errors.append("errors must be a list")
    if not isinstance(record.get("warnings"), list):
        errors.append("warnings must be a list")
    errors.extend(_validate_ref(record.get("last_event_ref"), field="last_event_ref", required=False))
    errors.extend(_validate_governance(record, "ledger_replay_report"))
    return errors


def validate_event_ledger(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["event ledger must be a JSON object"]
    if record.get("kind") != EVENT_LEDGER_KIND:
        errors.append(f"kind must be {EVENT_LEDGER_KIND}")
    if record.get("schema_version") != EVENT_LEDGER_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EVENT_LEDGER_SCHEMA_VERSION}")
    if record.get("ledger_state") != "RECORDED_ONLY":
        errors.append("ledger_state must be RECORDED_ONLY")
    if not isinstance(record.get("session_id"), str) or not record["session_id"]:
        errors.append("session_id must be a non-empty string")
    event_refs = record.get("event_refs")
    errors.extend(_validate_ref_list(event_refs, field="event_refs", allow_empty=True))
    if isinstance(event_refs, list) and record.get("event_count") != len(event_refs):
        errors.append("event_count must match len(event_refs)")
    errors.extend(_validate_ref(record.get("last_event_ref"), field="last_event_ref", required=False))
    errors.extend(_validate_ref(record.get("replay_report_ref"), field="replay_report_ref"))
    if not isinstance(record.get("reconstructed_status"), dict):
        errors.append("reconstructed_status must be an object")
    errors.extend(_validate_governance(record, "event_ledger"))
    return errors


def validate_event_ledger_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return ["artifact must be a JSON object"]
    kind = data.get("kind")
    if kind == EVENT_RECORD_KIND:
        return validate_event_record(data)
    if kind == EVENT_LEDGER_KIND:
        return validate_event_ledger(data)
    if kind == LEDGER_REPLAY_REPORT_KIND:
        return validate_ledger_replay_report(data)
    return [f"unsupported event ledger artifact kind: {kind}"]
