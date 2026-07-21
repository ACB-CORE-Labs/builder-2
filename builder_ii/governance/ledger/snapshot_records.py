from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.governance.ledger.artifact_index_records import (
    ARTIFACT_INDEX_RECORD_KIND,
    validate_artifact_index_record,
)
from builder_ii.governance.ledger.state_ledger_records import STATE_LEDGER_RECORD_KIND, validate_state_ledger_record

SNAPSHOT_RECORD_KIND = "builder_ii.snapshot_record"
SNAPSHOT_RECORD_SCHEMA_VERSION = 1


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def create_snapshot_record(
    artifact_index: dict[str, Any],
    state_ledger: dict[str, Any],
    *,
    artifact_index_path: str | Path,
    state_ledger_path: str | Path,
    snapshot_name: str,
    notes: str = "",
) -> dict[str, Any]:
    issues: list[str] = []
    if artifact_index.get("kind") != ARTIFACT_INDEX_RECORD_KIND:
        issues.append(f"artifact_index.kind must be {ARTIFACT_INDEX_RECORD_KIND}")
    if state_ledger.get("kind") != STATE_LEDGER_RECORD_KIND:
        issues.append(f"state_ledger.kind must be {STATE_LEDGER_RECORD_KIND}")
    issues.extend(f"artifact_index: {error}" for error in validate_artifact_index_record(artifact_index))
    issues.extend(f"state_ledger: {error}" for error in validate_state_ledger_record(state_ledger))
    if not _clean(snapshot_name):
        issues.append("snapshot_name is required")
    return {
        "kind": SNAPSHOT_RECORD_KIND,
        "schema_version": SNAPSHOT_RECORD_SCHEMA_VERSION,
        "capability_state": "snapshot_record",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "snapshot_name": _clean(snapshot_name),
        "status": "complete" if not issues else "incomplete",
        "complete": not issues,
        "issues": issues,
        "notes": _clean(notes),
        "artifact_index": {
            "path": str(artifact_index_path),
            "kind": artifact_index.get("kind", ""),
            "expected_kind": ARTIFACT_INDEX_RECORD_KIND,
            "sha256": _digest(artifact_index),
            "counts": artifact_index.get("counts", {}),
        },
        "state_ledger": {
            "path": str(state_ledger_path),
            "kind": state_ledger.get("kind", ""),
            "expected_kind": STATE_LEDGER_RECORD_KIND,
            "sha256": _digest(state_ledger),
            "counts": state_ledger.get("counts", {}),
        },
        "allowed_actions": ["record_snapshot", "validate_snapshot"],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": build_standard_governance("snapshot_record"),
    }


def create_snapshot_record_from_files(
    artifact_index_path: Path,
    state_ledger_path: Path,
    *,
    snapshot_name: str,
    notes: str = "",
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        artifact_index = json_lib.loads(artifact_index_path.read_text(encoding="utf-8"))
        state_ledger = json_lib.loads(state_ledger_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        return None, [f"file not found: {exc.filename}"]
    except json_lib.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    if not isinstance(artifact_index, dict):
        return None, ["artifact index must be a JSON object"]
    if not isinstance(state_ledger, dict):
        return None, ["state ledger must be a JSON object"]
    record = create_snapshot_record(
        artifact_index,
        state_ledger,
        artifact_index_path=artifact_index_path,
        state_ledger_path=state_ledger_path,
        snapshot_name=snapshot_name,
        notes=notes,
    )
    errors = validate_snapshot_record(record)
    if errors:
        return None, errors
    return record, []


def dumps_snapshot_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_snapshot_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_snapshot_record(record), encoding="utf-8")


def validate_snapshot_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["snapshot record must be a JSON object"]
    if record.get("kind") != SNAPSHOT_RECORD_KIND:
        errors.append(f"kind must be {SNAPSHOT_RECORD_KIND}")
    if record.get("schema_version") != SNAPSHOT_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {SNAPSHOT_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED or NOT_AUTHORIZED")
    if record.get("status") not in ("complete", "incomplete"):
        errors.append("status must be complete or incomplete")
    if record.get("complete") is not (record.get("status") == "complete"):
        errors.append("complete must match status")
    if not isinstance(record.get("issues"), list):
        errors.append("issues must be a list")
    if not record.get("snapshot_name"):
        errors.append("snapshot_name is required")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    if record.get("grants_runtime_authority") is not False:
        errors.append("grants_runtime_authority must be false or NOT_AUTHORIZED")
    if record.get("grants_action_authority") is not False:
        errors.append("grants_action_authority must be false or NOT_AUTHORIZED")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(validate_standard_governance(governance, "snapshot_record"))
    return errors


def validate_snapshot_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_snapshot_record(data)
