from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.handoff_bundle_records import HANDOFF_BUNDLE_RECORD_KIND, validate_handoff_bundle_record

ReceiveDecision = Literal["accepted", "blocked"]

RECEIVE_RECORD_KIND = "builder_ii.receive_record"
RECEIVE_RECORD_SCHEMA_VERSION = 1


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def create_receive_record(
    bundle: dict[str, Any],
    *,
    bundle_path: str | Path,
    decision: ReceiveDecision,
    received_by: str,
    notes: str = "",
) -> dict[str, Any]:
    blockers: list[str] = []
    if bundle.get("kind") != HANDOFF_BUNDLE_RECORD_KIND:
        blockers.append(f"bundle.kind must be {HANDOFF_BUNDLE_RECORD_KIND}")
    blockers.extend(f"bundle: {error}" for error in validate_handoff_bundle_record(bundle))
    if bundle.get("status") != "complete" or bundle.get("complete") is not True:
        blockers.append("handoff bundle is not complete")
    if not _clean(received_by):
        blockers.append("received_by is required")
    if decision == "accepted" and blockers:
        decision = "blocked"
    return {
        "kind": RECEIVE_RECORD_KIND,
        "schema_version": RECEIVE_RECORD_SCHEMA_VERSION,
        "capability_state": "receive_record",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "decision": decision,
        "accepted": decision == "accepted" and not blockers,
        "blockers": blockers,
        "received_by": _clean(received_by),
        "notes": _clean(notes),
        "bundle": {
            "path": str(bundle_path),
            "kind": bundle.get("kind", ""),
            "expected_kind": HANDOFF_BUNDLE_RECORD_KIND,
            "sha256": _digest(bundle),
            "status": bundle.get("status", ""),
            "complete": bundle.get("complete", False),
            "bundle_name": bundle.get("bundle_name", ""),
        },
        "artifact_digests": bundle.get("artifact_digests", {})
        if isinstance(bundle.get("artifact_digests"), dict)
        else {},
        "target": bundle.get("target", {}),
        "agent_profile": bundle.get("agent_profile", {}),
        "allowed_actions": ["validate_bundle", "render_receive_record", "validate_receive_record"],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": build_standard_governance("receive_record"),
    }


def create_receive_record_from_file(
    bundle_path: Path,
    *,
    decision: ReceiveDecision,
    received_by: str,
    notes: str = "",
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        bundle = json_lib.loads(bundle_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"file not found: {bundle_path}"]
    except json_lib.JSONDecodeError as exc:
        return None, [f"bundle invalid JSON: {exc}"]
    if not isinstance(bundle, dict):
        return None, ["bundle must be a JSON object"]
    record = create_receive_record(
        bundle, bundle_path=bundle_path, decision=decision, received_by=received_by, notes=notes
    )
    errors = validate_receive_record(record)
    if errors:
        return None, errors
    return record, []


def dumps_receive_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_receive_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_receive_record(record), encoding="utf-8")


def validate_receive_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["receive record must be a JSON object"]
    if record.get("kind") != RECEIVE_RECORD_KIND:
        errors.append(f"kind must be {RECEIVE_RECORD_KIND}")
    if record.get("schema_version") != RECEIVE_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RECEIVE_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED or NOT_AUTHORIZED")
    if record.get("decision") not in ("accepted", "blocked"):
        errors.append("decision must be accepted or blocked")
    if record.get("accepted") is not (record.get("decision") == "accepted" and record.get("blockers") == []):
        errors.append("accepted must match decision and blockers")
    if not isinstance(record.get("blockers"), list):
        errors.append("blockers must be a list")
    if not record.get("received_by"):
        errors.append("received_by is required")
    if record.get("bundle", {}).get("expected_kind") != HANDOFF_BUNDLE_RECORD_KIND:
        errors.append(f"bundle.expected_kind must be {HANDOFF_BUNDLE_RECORD_KIND}")
    for key in ("grants_runtime_authority", "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false or NOT_AUTHORIZED")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(validate_standard_governance(governance, "receive_record"))
    return errors


def validate_receive_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_receive_record(data)
