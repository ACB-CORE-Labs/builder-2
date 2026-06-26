from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.promotion_decision_records import PROMOTION_DECISION_RECORD_KIND, validate_promotion_decision_record

STATE_LEDGER_RECORD_KIND = "builder_ii.state_ledger_record"
STATE_LEDGER_RECORD_SCHEMA_VERSION = 1
_LEDGER_STATES = {"approved_for_manual_followup", "blocked"}


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def _entry_from_decision(decision: dict[str, Any], *, decision_path: str | Path) -> dict[str, Any]:
    errors: list[str] = []
    if decision.get("kind") != PROMOTION_DECISION_RECORD_KIND:
        errors.append(f"decision.kind must be {PROMOTION_DECISION_RECORD_KIND}")
    errors.extend(f"decision: {error}" for error in validate_promotion_decision_record(decision))
    readiness = decision.get("readiness", {}) if isinstance(decision.get("readiness"), dict) else {}
    approved = decision.get("approved") is True and decision.get("decision") == "approved" and not errors
    return {
        "capability_name": readiness.get("capability_name", ""),
        "target_state": readiness.get("target_state", ""),
        "ledger_state": "approved_for_manual_followup" if approved else "blocked",
        "approved": approved,
        "decision": {
            "path": str(decision_path),
            "kind": decision.get("kind", ""),
            "expected_kind": PROMOTION_DECISION_RECORD_KIND,
            "sha256": _digest(decision),
            "decision": decision.get("decision", ""),
            "approved": decision.get("approved", False),
        },
        "issues": errors + list(decision.get("blockers", [])),
    }


def create_state_ledger_record(
    decisions: list[tuple[dict[str, Any], str | Path]],
    *,
    ledger_name: str,
    notes: str = "",
) -> dict[str, Any]:
    entries = [_entry_from_decision(decision, decision_path=path) for decision, path in decisions]
    issues = [issue for entry in entries for issue in entry["issues"]]
    if not _clean(ledger_name):
        issues.append("ledger_name is required")
    return {
        "kind": STATE_LEDGER_RECORD_KIND,
        "schema_version": STATE_LEDGER_RECORD_SCHEMA_VERSION,
        "capability_state": "state_ledger_record",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "ledger_name": _clean(ledger_name),
        "status": "complete" if not issues else "incomplete",
        "complete": not issues,
        "issues": issues,
        "notes": _clean(notes),
        "counts": {
            "total": len(entries),
            "approved": sum(1 for entry in entries if entry["approved"]),
            "blocked": sum(1 for entry in entries if not entry["approved"]),
        },
        "entries": entries,
        "allowed_actions": ["record_state_ledger", "validate_state_ledger"],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": {
            "capability_state": "state_ledger_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def create_state_ledger_record_from_files(decision_paths: list[Path], *, ledger_name: str, notes: str = "") -> tuple[dict[str, Any] | None, list[str]]:
    decisions: list[tuple[dict[str, Any], Path]] = []
    for path in decision_paths:
        try:
            data = json_lib.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, [f"file not found: {path}"]
        except json_lib.JSONDecodeError as exc:
            return None, [f"decision invalid JSON: {exc}"]
        if not isinstance(data, dict):
            return None, ["decision must be a JSON object"]
        decisions.append((data, path))
    record = create_state_ledger_record(decisions, ledger_name=ledger_name, notes=notes)
    errors = validate_state_ledger_record(record)
    if errors:
        return None, errors
    return record, []


def dumps_state_ledger_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_state_ledger_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_state_ledger_record(record), encoding="utf-8")


def _validate_entry(entry: Any, index: int) -> list[str]:
    errors: list[str] = []
    prefix = f"entries[{index}]"
    if not isinstance(entry, dict):
        return [f"{prefix} must be an object"]
    if not entry.get("capability_name"):
        errors.append(f"{prefix}.capability_name is required")
    if entry.get("ledger_state") not in _LEDGER_STATES:
        errors.append(f"{prefix}.ledger_state must be approved_for_manual_followup or blocked")
    if not isinstance(entry.get("approved"), bool):
        errors.append(f"{prefix}.approved must be a boolean")
    elif entry.get("ledger_state") == "approved_for_manual_followup" and entry.get("approved") is not True:
        errors.append(f"{prefix}.approved must be true for approved_for_manual_followup")
    elif entry.get("ledger_state") == "blocked" and entry.get("approved") is not False:
        errors.append(f"{prefix}.approved must be false for blocked")
    if not isinstance(entry.get("issues"), list):
        errors.append(f"{prefix}.issues must be a list")
    decision = entry.get("decision")
    if not isinstance(decision, dict):
        errors.append(f"{prefix}.decision must be an object")
    elif decision.get("expected_kind") != PROMOTION_DECISION_RECORD_KIND:
        errors.append(f"{prefix}.decision.expected_kind must be {PROMOTION_DECISION_RECORD_KIND}")
    return errors


def validate_state_ledger_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["state ledger record must be a JSON object"]
    if record.get("kind") != STATE_LEDGER_RECORD_KIND:
        errors.append(f"kind must be {STATE_LEDGER_RECORD_KIND}")
    if record.get("schema_version") != STATE_LEDGER_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {STATE_LEDGER_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED")
    if not record.get("ledger_name"):
        errors.append("ledger_name is required")
    if record.get("status") not in ("complete", "incomplete"):
        errors.append("status must be complete or incomplete")
    if record.get("complete") is not (record.get("status") == "complete"):
        errors.append("complete must match status")
    if not isinstance(record.get("issues"), list):
        errors.append("issues must be a list")
    counts = record.get("counts")
    entries = record.get("entries")
    if not isinstance(counts, dict):
        errors.append("counts must be an object")
    if not isinstance(entries, list):
        errors.append("entries must be a list")
    else:
        for index, entry in enumerate(entries):
            errors.extend(_validate_entry(entry, index))
        if isinstance(counts, dict):
            approved_count = sum(1 for entry in entries if isinstance(entry, dict) and entry.get("approved") is True)
            blocked_count = sum(1 for entry in entries if isinstance(entry, dict) and entry.get("approved") is False)
            expected_counts = {"total": len(entries), "approved": approved_count, "blocked": blocked_count}
            if counts != expected_counts:
                errors.append(f"counts must match entries: {expected_counts}")
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


def validate_state_ledger_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_state_ledger_record(data)
