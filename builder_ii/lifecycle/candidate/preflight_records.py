from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.adapters.goose.goose_command_proposal import (
    GOOSE_COMMAND_PROPOSAL_KIND,
    validate_goose_command_proposal,
)
from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.lifecycle.candidate.approval_records import APPROVAL_RECORD_KIND, validate_approval_record

PreflightStatus = Literal["ready", "blocked"]

PREFLIGHT_RECORD_KIND = "builder_ii.preflight_record"
PREFLIGHT_RECORD_SCHEMA_VERSION = 1

_OFF_KEYS = (
    "runtime_execution",
    "goose_runtime_start",
    "model_execution",
    "agent_construction",
    "deepagents_construction",
    "shell_execution",
    "command_execution",
    "source_writes",
    "memory_mutation",
    "commit_push",
    "pull_request_creation",
    "source_collection",
    "web_search",
    "mcp_execution",
)


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean_items(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if values is None:
        return []
    return [item for item in (str(value).strip() for value in values) if item]


def _blockers(proposal: dict[str, Any], approval: dict[str, Any], verification_refs: list[str]) -> list[str]:
    blockers: list[str] = []
    proposal_errors = validate_goose_command_proposal(proposal)
    if proposal_errors:
        blockers.extend(f"proposal: {error}" for error in proposal_errors)
    approval_errors = validate_approval_record(approval)
    if approval_errors:
        blockers.extend(f"approval: {error}" for error in approval_errors)
    if approval.get("proposal", {}).get("sha256") != _digest(proposal):
        blockers.append("approval proposal digest does not match proposal")
    if approval.get("decision", {}).get("value") != "approved":
        blockers.append("approval decision is not approved")
    if not verification_refs:
        blockers.append("verification refs are required")
    return blockers


def create_preflight_record(
    proposal: dict[str, Any],
    approval: dict[str, Any],
    *,
    proposal_path: str | Path,
    approval_path: str | Path,
    verification_refs: tuple[str, ...] | list[str] | None = None,
    rollback_refs: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    verification = _clean_items(verification_refs)
    rollback = _clean_items(rollback_refs) or ["delete this record to roll back the preflight decision"]
    blockers = _blockers(proposal, approval, verification)
    status: PreflightStatus = "ready" if not blockers else "blocked"
    return {
        "kind": PREFLIGHT_RECORD_KIND,
        "schema_version": PREFLIGHT_RECORD_SCHEMA_VERSION,
        "capability_state": "preflight_record",
        "record_state": "RECORDED_ONLY",
        "current_runtime_state": "DISABLED",
        "status": status,
        "ready": status == "ready",
        "blockers": blockers,
        "proposal": {
            "path": str(proposal_path),
            "kind": proposal.get("kind", ""),
            "sha256": _digest(proposal),
            "expected_kind": GOOSE_COMMAND_PROPOSAL_KIND,
            "summary": proposal.get("command", ""),
            "risk_level": proposal.get("risk_level", ""),
        },
        "approval": {
            "path": str(approval_path),
            "kind": approval.get("kind", ""),
            "sha256": _digest(approval),
            "expected_kind": APPROVAL_RECORD_KIND,
            "decision": approval.get("decision", {}).get("value", ""),
            "decided_by": approval.get("decision", {}).get("decided_by", ""),
        },
        "target": proposal.get("target", {}),
        "agent_profile": proposal.get("agent_profile", {}),
        "verification_refs": verification,
        "rollback_refs": rollback,
        "allowed_actions": ["validate_inputs", "render_preflight_record", "validate_preflight_record"],
        "denied_actions": list(proposal.get("denied_actions", [])),
        "performed_actions": [],
        "result": {"status": None, "stdout": "", "stderr": ""},
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": build_standard_governance("preflight_record"),
    }


def create_preflight_record_from_files(
    proposal_path: Path,
    approval_path: Path,
    *,
    verification_refs: tuple[str, ...] | list[str] | None = None,
    rollback_refs: tuple[str, ...] | list[str] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    try:
        proposal = json_lib.loads(proposal_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"file not found: {proposal_path}"]
    except json_lib.JSONDecodeError as exc:
        return None, [f"proposal invalid JSON: {exc}"]
    try:
        approval = json_lib.loads(approval_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"file not found: {approval_path}"]
    except json_lib.JSONDecodeError as exc:
        return None, [f"approval invalid JSON: {exc}"]
    if not isinstance(proposal, dict):
        errors.append("proposal must be a JSON object")
    if not isinstance(approval, dict):
        errors.append("approval must be a JSON object")
    if errors:
        return None, errors
    record = create_preflight_record(
        proposal,
        approval,
        proposal_path=proposal_path,
        approval_path=approval_path,
        verification_refs=verification_refs,
        rollback_refs=rollback_refs,
    )
    record_errors = validate_preflight_record(record)
    if record_errors:
        return None, record_errors
    return record, []


def dumps_preflight_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_preflight_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_preflight_record(record), encoding="utf-8")


def validate_preflight_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["preflight record must be a JSON object"]
    if record.get("kind") != PREFLIGHT_RECORD_KIND:
        errors.append(f"kind must be {PREFLIGHT_RECORD_KIND}")
    if record.get("schema_version") != PREFLIGHT_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PREFLIGHT_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED or NOT_AUTHORIZED")
    if record.get("status") not in ("ready", "blocked"):
        errors.append("status must be ready or blocked")
    if record.get("ready") is not (record.get("status") == "ready"):
        errors.append("ready must match status")
    if not isinstance(record.get("blockers"), list):
        errors.append("blockers must be a list")
    if record.get("status") == "ready" and record.get("blockers") != []:
        errors.append("ready records must not have blockers")
    if record.get("status") == "blocked" and not record.get("blockers"):
        errors.append("blocked records must include blockers")
    if record.get("proposal", {}).get("expected_kind") != GOOSE_COMMAND_PROPOSAL_KIND:
        errors.append(f"proposal.expected_kind must be {GOOSE_COMMAND_PROPOSAL_KIND}")
    if record.get("approval", {}).get("expected_kind") != APPROVAL_RECORD_KIND:
        errors.append(f"approval.expected_kind must be {APPROVAL_RECORD_KIND}")
    if record.get("status") == "ready" and not record.get("verification_refs"):
        errors.append("ready records require verification_refs")
    for key in ("grants_runtime_authority", "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false or NOT_AUTHORIZED")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    result = record.get("result")
    if (
        not isinstance(result, dict)
        or result.get("status") is not None
        or result.get("stdout") != ""
        or result.get("stderr") != ""
    ):
        errors.append("result must be empty")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(validate_standard_governance(governance, "preflight_record"))
    return errors


def validate_preflight_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_preflight_record(data)
