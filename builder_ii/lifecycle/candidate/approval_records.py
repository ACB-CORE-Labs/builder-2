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

ApprovalDecision = Literal["approved", "rejected"]

APPROVAL_RECORD_KIND = "builder_ii.approval_record"
APPROVAL_RECORD_SCHEMA_VERSION = 1

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


def _clean(value: str | Path | None) -> str:
    return "" if value is None else str(value).strip()


def create_approval_record(
    proposal: dict[str, Any],
    *,
    proposal_path: str | Path,
    decision: ApprovalDecision,
    decided_by: str,
    reason: str = "",
) -> dict[str, Any]:
    approved = decision == "approved"
    return {
        "kind": APPROVAL_RECORD_KIND,
        "schema_version": APPROVAL_RECORD_SCHEMA_VERSION,
        "capability_state": "approval_record",
        "record_state": "RECORDED_ONLY",
        "current_runtime_state": "DISABLED",
        "proposal": {
            "path": str(proposal_path),
            "kind": proposal.get("kind", ""),
            "sha256": _digest(proposal),
            "summary": proposal.get("command", ""),
            "risk_level": proposal.get("risk_level", ""),
        },
        "target": proposal.get("target", {}),
        "agent_profile": proposal.get("agent_profile", {}),
        "decision": {
            "value": decision,
            "approved": approved,
            "decided_by": _clean(decided_by),
            "reason": _clean(reason),
        },
        "allowed_actions": ["validate_proposal", "render_approval_record", "validate_approval_record"],
        "denied_actions": list(proposal.get("denied_actions", [])),
        "proposal_actions": list(proposal.get("commands_proposed", [])),
        "performed_actions": [],
        "result": {"status": None, "stdout": "", "stderr": ""},
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "rollback_refs": ["delete this record to roll back the recorded decision"],
        "governance": build_standard_governance("approval_record"),
    }


def create_approval_record_from_file(
    proposal_path: Path,
    *,
    decision: ApprovalDecision,
    decided_by: str,
    reason: str = "",
) -> tuple[dict[str, Any] | None, list[str]]:
    if not proposal_path.exists():
        return None, [f"file not found: {proposal_path}"]
    try:
        proposal = json_lib.loads(proposal_path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    except Exception as exc:
        return None, [f"failed to read file: {exc}"]
    proposal_errors = validate_goose_command_proposal(proposal)
    if proposal_errors:
        return None, [f"proposal: {error}" for error in proposal_errors]
    record = create_approval_record(
        proposal, proposal_path=proposal_path, decision=decision, decided_by=decided_by, reason=reason
    )
    errors = validate_approval_record(record)
    if errors:
        return None, errors
    return record, []


def dumps_approval_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_approval_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_approval_record(record), encoding="utf-8")


def validate_approval_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["approval record must be a JSON object"]
    if record.get("kind") != APPROVAL_RECORD_KIND:
        errors.append(f"kind must be {APPROVAL_RECORD_KIND}")
    if record.get("schema_version") != APPROVAL_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {APPROVAL_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED or NOT_AUTHORIZED")
    proposal = record.get("proposal")
    if not isinstance(proposal, dict) or proposal.get("kind") != GOOSE_COMMAND_PROPOSAL_KIND:
        errors.append(f"proposal.kind must be {GOOSE_COMMAND_PROPOSAL_KIND}")
    decision = record.get("decision")
    if not isinstance(decision, dict):
        errors.append("decision must be an object")
    else:
        value = decision.get("value")
        if value not in ("approved", "rejected"):
            errors.append("decision.value must be approved or rejected")
        if decision.get("approved") is not (value == "approved"):
            errors.append("decision.approved must match decision.value")
        if not decision.get("decided_by"):
            errors.append("decision.decided_by is required")
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
        errors.extend(validate_standard_governance(governance, "approval_record"))
    return errors


def validate_approval_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_approval_record(data)
