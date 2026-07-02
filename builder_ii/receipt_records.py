from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.preflight_records import PREFLIGHT_RECORD_KIND, validate_preflight_record

ReceiptStatus = Literal["passed", "failed", "blocked"]

RECEIPT_RECORD_KIND = "builder_ii.receipt_record"
RECEIPT_RECORD_SCHEMA_VERSION = 1


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: str | Path | None) -> str:
    return "" if value is None else str(value).strip()


def _clean_list(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if values is None:
        return []
    return [item for item in (str(value).strip() for value in values) if item]


def _input_blockers(preflight: dict[str, Any], evidence_refs: list[str]) -> list[str]:
    blockers: list[str] = []
    preflight_errors = validate_preflight_record(preflight)
    if preflight_errors:
        blockers.extend(f"preflight: {error}" for error in preflight_errors)
    if preflight.get("kind") != PREFLIGHT_RECORD_KIND:
        blockers.append(f"preflight.kind must be {PREFLIGHT_RECORD_KIND}")
    if preflight.get("status") != "ready" or preflight.get("ready") is not True:
        blockers.append("preflight record is not ready")
    if not evidence_refs:
        blockers.append("evidence refs are required")
    return blockers


def create_receipt_record(
    preflight: dict[str, Any],
    *,
    preflight_path: str | Path,
    status: ReceiptStatus,
    recorded_by: str,
    evidence_refs: tuple[str, ...] | list[str] | None = None,
    summary: str = "",
    rollback_refs: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    evidence = _clean_list(evidence_refs)
    blockers = _input_blockers(preflight, evidence)
    rollback = _clean_list(rollback_refs) or ["delete this record to roll back the receipt"]
    return {
        "kind": RECEIPT_RECORD_KIND,
        "schema_version": RECEIPT_RECORD_SCHEMA_VERSION,
        "capability_state": "receipt_record",
        "record_state": "RECORDED_ONLY",
        "current_runtime_state": "DISABLED",
        "status": status,
        "accepted": status == "passed" and not blockers,
        "blockers": blockers,
        "preflight": {
            "path": str(preflight_path),
            "kind": preflight.get("kind", ""),
            "expected_kind": PREFLIGHT_RECORD_KIND,
            "sha256": _digest(preflight),
            "status": preflight.get("status", ""),
            "ready": preflight.get("ready", False),
        },
        "target": preflight.get("target", {}),
        "agent_profile": preflight.get("agent_profile", {}),
        "recorded_by": _clean(recorded_by),
        "summary": _clean(summary),
        "evidence_refs": evidence,
        "rollback_refs": rollback,
        "allowed_actions": ["validate_preflight_record", "render_receipt_record", "validate_receipt_record"],
        "denied_actions": list(preflight.get("denied_actions", [])),
        "performed_actions": [],
        "observed_result": {"status": status, "stdout_ref": "", "stderr_ref": ""},
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": {
            "capability_state": "receipt_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def create_receipt_record_from_file(
    preflight_path: Path,
    *,
    status: ReceiptStatus,
    recorded_by: str,
    evidence_refs: tuple[str, ...] | list[str] | None = None,
    summary: str = "",
    rollback_refs: tuple[str, ...] | list[str] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        preflight = json_lib.loads(preflight_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"file not found: {preflight_path}"]
    except json_lib.JSONDecodeError as exc:
        return None, [f"preflight invalid JSON: {exc}"]
    except Exception as exc:
        return None, [f"failed to read file: {exc}"]
    if not isinstance(preflight, dict):
        return None, ["preflight must be a JSON object"]
    record = create_receipt_record(
        preflight,
        preflight_path=preflight_path,
        status=status,
        recorded_by=recorded_by,
        evidence_refs=evidence_refs,
        summary=summary,
        rollback_refs=rollback_refs,
    )
    errors = validate_receipt_record(record)
    if errors:
        return None, errors
    return record, []


def dumps_receipt_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_receipt_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_receipt_record(record), encoding="utf-8")


def validate_receipt_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["receipt record must be a JSON object"]
    if record.get("kind") != RECEIPT_RECORD_KIND:
        errors.append(f"kind must be {RECEIPT_RECORD_KIND}")
    if record.get("schema_version") != RECEIPT_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RECEIPT_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED")
    if record.get("status") not in ("passed", "failed", "blocked"):
        errors.append("status must be passed, failed, or blocked")
    if not isinstance(record.get("blockers"), list):
        errors.append("blockers must be a list")
    if record.get("accepted") is not (record.get("status") == "passed" and record.get("blockers") == []):
        errors.append("accepted must match status and blockers")
    if record.get("preflight", {}).get("expected_kind") != PREFLIGHT_RECORD_KIND:
        errors.append(f"preflight.expected_kind must be {PREFLIGHT_RECORD_KIND}")
    if not record.get("recorded_by"):
        errors.append("recorded_by is required")
    if not record.get("evidence_refs"):
        errors.append("evidence_refs is required")
    for key in ("grants_runtime_authority", "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    observed = record.get("observed_result")
    if not isinstance(observed, dict):
        errors.append("observed_result must be an object")
    elif (
        observed.get("status") != record.get("status")
        or observed.get("stdout_ref") != ""
        or observed.get("stderr_ref") != ""
    ):
        errors.append("observed_result must match status and keep refs empty")
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


def validate_receipt_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_receipt_record(data)
