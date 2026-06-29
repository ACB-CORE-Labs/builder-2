from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

WORKFLOW_SESSION_KIND = "builder_ii.workflow_session"
WORKFLOW_SESSION_SCHEMA_VERSION = 1

WORKFLOW_STATUS_KIND = "builder_ii.workflow_status"
WORKFLOW_STATUS_SCHEMA_VERSION = 1

WORKFLOW_TRANSITION_KIND = "builder_ii.workflow_transition"
WORKFLOW_TRANSITION_SCHEMA_VERSION = 1

WORKFLOW_STAGES = (
    "initialized",
    "planned",
    "promoted",
    "candidate",
    "chain_verified",
    "handoff_ready",
)

WORKFLOW_STAGE_ORDER = {stage: index for index, stage in enumerate(WORKFLOW_STAGES)}

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9_.:-]+$")


def canonical_digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def artifact_ref(
    data: dict[str, Any],
    *,
    path: str | Path,
    role: str,
    name: str = "",
    required: bool = True,
) -> dict[str, Any]:
    return {
        "role": role,
        "kind": str(data.get("kind", "")),
        "path": str(path),
        "sha256": canonical_digest(data),
        "name": name,
        "required": required,
    }


def file_ref(
    *,
    kind: str,
    path: str | Path,
    sha256: str,
    role: str,
    name: str = "",
    required: bool = True,
) -> dict[str, Any]:
    return {
        "role": role,
        "kind": kind,
        "path": str(path),
        "sha256": sha256,
        "name": name,
        "required": required,
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


def _next_stages(current_stage: str) -> list[str]:
    if current_stage == "initialized":
        return ["planned"]
    if current_stage == "planned":
        return ["promoted"]
    if current_stage == "promoted":
        return ["candidate"]
    if current_stage == "candidate":
        return ["chain_verified"]
    if current_stage == "chain_verified":
        return ["handoff_ready"]
    return []


def create_workflow_session(
    *,
    session_id: str,
    target: str,
    task: str,
    output_dir: str | Path,
    artifacts_dir: str | Path,
    events_dir: str | Path,
    created_by: str = "operator",
) -> dict[str, Any]:
    return {
        "kind": WORKFLOW_SESSION_KIND,
        "schema_version": WORKFLOW_SESSION_SCHEMA_VERSION,
        "session_state": "SESSION_RECORDED_ONLY",
        "session_id": session_id,
        "target": target,
        "task": task.strip(),
        "created_by": created_by.strip() or "operator",
        "output_dir": str(output_dir),
        "artifacts_dir": str(artifacts_dir),
        "events_dir": str(events_dir),
        "initial_stage": "initialized",
        "workflow_stages": list(WORKFLOW_STAGES),
        "current_stage": "initialized",
        "next_allowed_stages": _next_stages("initialized"),
        "records_workflow_state": True,
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "governance": _default_governance("workflow_session"),
    }


def create_workflow_transition(
    *,
    session_id: str,
    from_stage: str,
    to_stage: str,
    command: str,
    subject_refs: list[dict[str, Any]],
    reason: str = "",
    previous_transition_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": WORKFLOW_TRANSITION_KIND,
        "schema_version": WORKFLOW_TRANSITION_SCHEMA_VERSION,
        "transition_state": "TRANSITION_RECORDED_ONLY",
        "session_id": session_id,
        "from_stage": from_stage,
        "to_stage": to_stage,
        "command": command,
        "reason": reason.strip(),
        "subject_refs": list(subject_refs),
        "previous_transition_ref": previous_transition_ref,
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "governance": _default_governance("workflow_transition"),
    }


def create_workflow_status(
    *,
    session_id: str,
    target: str,
    task: str,
    current_stage: str,
    completed_stages: list[str],
    artifact_refs: list[dict[str, Any]],
    last_event_ref: dict[str, Any] | None,
    event_count: int,
    valid_replay: bool,
    replay_errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": WORKFLOW_STATUS_KIND,
        "schema_version": WORKFLOW_STATUS_SCHEMA_VERSION,
        "status_state": "REPLAYED_STATUS_ONLY",
        "session_id": session_id,
        "target": target,
        "task": task.strip(),
        "current_stage": current_stage,
        "completed_stages": list(completed_stages),
        "next_allowed_stages": _next_stages(current_stage),
        "artifact_refs": list(artifact_refs),
        "last_event_ref": last_event_ref,
        "event_count": event_count,
        "valid_replay": valid_replay,
        "replay_errors": list(replay_errors or []),
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "governance": _default_governance("workflow_status"),
    }


def dumps_workflow_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_workflow_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_workflow_record(record), encoding="utf-8")


def _validate_session_id(value: Any) -> list[str]:
    if not isinstance(value, str) or not value:
        return ["session_id must be a non-empty string"]
    if not _SESSION_ID_RE.match(value):
        return ["session_id must contain only letters, numbers, dot, colon, underscore, or dash"]
    return []


def _validate_ref(value: Any, *, field: str, required: bool = True) -> list[str]:
    if value is None:
        return [f"{field} is required"] if required else []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    errors: list[str] = []
    for key in ("role", "kind", "path", "sha256"):
        if not isinstance(value.get(key), str) or not value[key]:
            errors.append(f"{field}.{key} must be a non-empty string")
    sha = value.get("sha256")
    if isinstance(sha, str) and not _SHA256_RE.match(sha):
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
            errors.append(f"governance.{key} must be DISABLED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "grants_runtime_authority", "grants_action_authority"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")
    for key in (
        "executes_model",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "invokes_mcp",
        "mutates_target_repo",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    return errors


def validate_workflow_session(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["workflow session must be a JSON object"]
    if record.get("kind") != WORKFLOW_SESSION_KIND:
        errors.append(f"kind must be {WORKFLOW_SESSION_KIND}")
    if record.get("schema_version") != WORKFLOW_SESSION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {WORKFLOW_SESSION_SCHEMA_VERSION}")
    if record.get("session_state") != "SESSION_RECORDED_ONLY":
        errors.append("session_state must be SESSION_RECORDED_ONLY")
    errors.extend(_validate_session_id(record.get("session_id")))
    if record.get("target") not in ("generic", "builder", "core"):
        errors.append("target must be one of: generic, builder, core")
    for field in ("task", "output_dir", "artifacts_dir", "events_dir", "created_by"):
        if not isinstance(record.get(field), str) or not record[field]:
            errors.append(f"{field} must be a non-empty string")
    if record.get("workflow_stages") != list(WORKFLOW_STAGES):
        errors.append("workflow_stages must match the canonical workflow stage list")
    if record.get("current_stage") != "initialized":
        errors.append("current_stage must be initialized")
    if record.get("next_allowed_stages") != ["planned"]:
        errors.append("next_allowed_stages must be ['planned']")
    if record.get("records_workflow_state") is not True:
        errors.append("records_workflow_state must be true")
    errors.extend(_validate_governance(record, "workflow_session"))
    return errors


def validate_workflow_transition(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["workflow transition must be a JSON object"]
    if record.get("kind") != WORKFLOW_TRANSITION_KIND:
        errors.append(f"kind must be {WORKFLOW_TRANSITION_KIND}")
    if record.get("schema_version") != WORKFLOW_TRANSITION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {WORKFLOW_TRANSITION_SCHEMA_VERSION}")
    if record.get("transition_state") != "TRANSITION_RECORDED_ONLY":
        errors.append("transition_state must be TRANSITION_RECORDED_ONLY")
    errors.extend(_validate_session_id(record.get("session_id")))
    from_stage = record.get("from_stage")
    to_stage = record.get("to_stage")
    if from_stage not in WORKFLOW_STAGE_ORDER:
        errors.append("from_stage must be a known workflow stage")
    if to_stage not in WORKFLOW_STAGE_ORDER:
        errors.append("to_stage must be a known workflow stage")
    if from_stage in WORKFLOW_STAGE_ORDER and to_stage in WORKFLOW_STAGE_ORDER:
        if WORKFLOW_STAGE_ORDER[to_stage] != WORKFLOW_STAGE_ORDER[from_stage] + 1:
            errors.append("transition must advance exactly one workflow stage")
    if not isinstance(record.get("command"), str) or not record["command"]:
        errors.append("command must be a non-empty string")
    if not isinstance(record.get("reason", ""), str):
        errors.append("reason must be a string")
    errors.extend(_validate_ref_list(record.get("subject_refs"), field="subject_refs"))
    errors.extend(_validate_ref(record.get("previous_transition_ref"), field="previous_transition_ref", required=False))
    errors.extend(_validate_governance(record, "workflow_transition"))
    return errors


def validate_workflow_status(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["workflow status must be a JSON object"]
    if record.get("kind") != WORKFLOW_STATUS_KIND:
        errors.append(f"kind must be {WORKFLOW_STATUS_KIND}")
    if record.get("schema_version") != WORKFLOW_STATUS_SCHEMA_VERSION:
        errors.append(f"schema_version must be {WORKFLOW_STATUS_SCHEMA_VERSION}")
    if record.get("status_state") != "REPLAYED_STATUS_ONLY":
        errors.append("status_state must be REPLAYED_STATUS_ONLY")
    errors.extend(_validate_session_id(record.get("session_id")))
    if record.get("target") not in ("generic", "builder", "core"):
        errors.append("target must be one of: generic, builder, core")
    if not isinstance(record.get("task"), str) or not record["task"]:
        errors.append("task must be a non-empty string")
    current_stage = record.get("current_stage")
    if current_stage not in WORKFLOW_STAGE_ORDER:
        errors.append("current_stage must be a known workflow stage")
    if record.get("next_allowed_stages") != _next_stages(str(current_stage)):
        errors.append("next_allowed_stages must match current_stage")
    completed = record.get("completed_stages")
    if not isinstance(completed, list) or any(stage not in WORKFLOW_STAGE_ORDER for stage in completed):
        errors.append("completed_stages must be a list of known workflow stages")
    errors.extend(_validate_ref_list(record.get("artifact_refs"), field="artifact_refs", allow_empty=True))
    errors.extend(_validate_ref(record.get("last_event_ref"), field="last_event_ref", required=False))
    if not isinstance(record.get("event_count"), int) or record["event_count"] < 0:
        errors.append("event_count must be a non-negative integer")
    if not isinstance(record.get("valid_replay"), bool):
        errors.append("valid_replay must be a boolean")
    if not isinstance(record.get("replay_errors"), list):
        errors.append("replay_errors must be a list")
    errors.extend(_validate_governance(record, "workflow_status"))
    return errors


def validate_workflow_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    if not isinstance(data, dict):
        return ["artifact must be a JSON object"]
    kind = data.get("kind")
    if kind == WORKFLOW_SESSION_KIND:
        return validate_workflow_session(data)
    if kind == WORKFLOW_STATUS_KIND:
        return validate_workflow_status(data)
    if kind == WORKFLOW_TRANSITION_KIND:
        return validate_workflow_transition(data)
    return [f"unsupported workflow artifact kind: {kind}"]
