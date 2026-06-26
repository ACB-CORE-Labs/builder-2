from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.approval_records import APPROVAL_RECORD_KIND, validate_approval_record
from builder_ii.goose_command_proposal import GOOSE_COMMAND_PROPOSAL_KIND, validate_goose_command_proposal
from builder_ii.preflight_records import PREFLIGHT_RECORD_KIND, validate_preflight_record
from builder_ii.receipt_records import RECEIPT_RECORD_KIND, validate_receipt_record

CHAIN_SUMMARY_RECORD_KIND = "builder_ii.chain_summary_record"
CHAIN_SUMMARY_RECORD_SCHEMA_VERSION = 1


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"file not found: {path}"]
    except json_lib.JSONDecodeError as exc:
        return None, [f"{label} invalid JSON: {exc}"]
    except Exception as exc:
        return None, [f"failed to read {label}: {exc}"]
    if not isinstance(data, dict):
        return None, [f"{label} must be a JSON object"]
    return data, []


def _validation_errors(
    proposal: dict[str, Any],
    approval: dict[str, Any],
    preflight: dict[str, Any],
    receipt: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    for label, found, expected in (
        ("proposal", proposal.get("kind"), GOOSE_COMMAND_PROPOSAL_KIND),
        ("approval", approval.get("kind"), APPROVAL_RECORD_KIND),
        ("preflight", preflight.get("kind"), PREFLIGHT_RECORD_KIND),
        ("receipt", receipt.get("kind"), RECEIPT_RECORD_KIND),
    ):
        if found != expected:
            errors.append(f"{label}.kind must be {expected}")

    errors.extend(f"proposal: {error}" for error in validate_goose_command_proposal(proposal))
    errors.extend(f"approval: {error}" for error in validate_approval_record(approval))
    errors.extend(f"preflight: {error}" for error in validate_preflight_record(preflight))
    errors.extend(f"receipt: {error}" for error in validate_receipt_record(receipt))

    proposal_digest = _digest(proposal)
    approval_digest = _digest(approval)
    preflight_digest = _digest(preflight)
    if approval.get("proposal", {}).get("sha256") != proposal_digest:
        errors.append("approval does not reference the proposal digest")
    if preflight.get("proposal", {}).get("sha256") != proposal_digest:
        errors.append("preflight does not reference the proposal digest")
    if preflight.get("approval", {}).get("sha256") != approval_digest:
        errors.append("preflight does not reference the approval digest")
    if receipt.get("preflight", {}).get("sha256") != preflight_digest:
        errors.append("receipt does not reference the preflight digest")
    return errors


def create_chain_summary_record(
    proposal: dict[str, Any],
    approval: dict[str, Any],
    preflight: dict[str, Any],
    receipt: dict[str, Any],
    *,
    proposal_path: str | Path,
    approval_path: str | Path,
    preflight_path: str | Path,
    receipt_path: str | Path,
    summary: str = "",
) -> dict[str, Any]:
    errors = _validation_errors(proposal, approval, preflight, receipt)
    return {
        "kind": CHAIN_SUMMARY_RECORD_KIND,
        "schema_version": CHAIN_SUMMARY_RECORD_SCHEMA_VERSION,
        "capability_state": "chain_summary_record",
        "record_state": "RECORDED_ONLY",
        "current_runtime_state": "DISABLED",
        "status": "complete" if not errors else "incomplete",
        "complete": not errors,
        "issues": errors,
        "summary": summary.strip(),
        "artifacts": {
            "proposal": {"path": str(proposal_path), "kind": proposal.get("kind", ""), "sha256": _digest(proposal)},
            "approval": {"path": str(approval_path), "kind": approval.get("kind", ""), "sha256": _digest(approval)},
            "preflight": {"path": str(preflight_path), "kind": preflight.get("kind", ""), "sha256": _digest(preflight)},
            "receipt": {"path": str(receipt_path), "kind": receipt.get("kind", ""), "sha256": _digest(receipt)},
        },
        "target": proposal.get("target", {}),
        "agent_profile": proposal.get("agent_profile", {}),
        "receipt_status": receipt.get("status", ""),
        "receipt_accepted": receipt.get("accepted", False),
        "allowed_actions": ["validate_chain_inputs", "render_chain_summary", "validate_chain_summary"],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": {
            "capability_state": "chain_summary_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def create_chain_summary_record_from_files(
    proposal_path: Path,
    approval_path: Path,
    preflight_path: Path,
    receipt_path: Path,
    *,
    summary: str = "",
) -> tuple[dict[str, Any] | None, list[str]]:
    proposal, errors = _load_json(proposal_path, "proposal")
    if errors:
        return None, errors
    approval, errors = _load_json(approval_path, "approval")
    if errors:
        return None, errors
    preflight, errors = _load_json(preflight_path, "preflight")
    if errors:
        return None, errors
    receipt, errors = _load_json(receipt_path, "receipt")
    if errors:
        return None, errors
    assert proposal is not None and approval is not None and preflight is not None and receipt is not None
    record = create_chain_summary_record(
        proposal,
        approval,
        preflight,
        receipt,
        proposal_path=proposal_path,
        approval_path=approval_path,
        preflight_path=preflight_path,
        receipt_path=receipt_path,
        summary=summary,
    )
    record_errors = validate_chain_summary_record(record)
    if record_errors:
        return None, record_errors
    return record, []


def dumps_chain_summary_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_chain_summary_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_chain_summary_record(record), encoding="utf-8")


def validate_chain_summary_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["chain summary record must be a JSON object"]
    if record.get("kind") != CHAIN_SUMMARY_RECORD_KIND:
        errors.append(f"kind must be {CHAIN_SUMMARY_RECORD_KIND}")
    if record.get("schema_version") != CHAIN_SUMMARY_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CHAIN_SUMMARY_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED")
    if record.get("status") not in ("complete", "incomplete"):
        errors.append("status must be complete or incomplete")
    if record.get("complete") is not (record.get("status") == "complete"):
        errors.append("complete must match status")
    if not isinstance(record.get("issues"), list):
        errors.append("issues must be a list")
    if record.get("status") == "complete" and record.get("issues") != []:
        errors.append("complete summaries must not have issues")
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifacts must be an object")
    else:
        for key in ("proposal", "approval", "preflight", "receipt"):
            item = artifacts.get(key)
            if not isinstance(item, dict):
                errors.append(f"artifacts.{key} must be an object")
            elif not item.get("path") or not item.get("sha256"):
                errors.append(f"artifacts.{key} requires path and sha256")
    for key in ("grants_runtime_authority", "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in ("runtime_execution", "model_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_chain_summary_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_chain_summary_record(data)
