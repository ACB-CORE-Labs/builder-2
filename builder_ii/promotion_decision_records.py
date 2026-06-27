from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.promotion_compatibility import support_artifact_kinds
from builder_ii.promotion_readiness_records import PROMOTION_READINESS_RECORD_KIND, validate_promotion_readiness_record

PromotionDecision = Literal["approved", "blocked"]

PROMOTION_DECISION_RECORD_KIND = "builder_ii.promotion_decision_record"
PROMOTION_DECISION_RECORD_SCHEMA_VERSION = 1
_READINESS_STATUSES = {"ready", "blocked"}


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def create_promotion_decision_record(
    readiness: dict[str, Any],
    *,
    readiness_path: str | Path,
    decision: PromotionDecision,
    decided_by: str,
    reason: str = "",
) -> dict[str, Any]:
    blockers: list[str] = []
    if readiness.get("kind") != PROMOTION_READINESS_RECORD_KIND:
        blockers.append(f"readiness.kind must be {PROMOTION_READINESS_RECORD_KIND}")
    blockers.extend(f"readiness: {error}" for error in validate_promotion_readiness_record(readiness))
    if readiness.get("status") != "ready" or readiness.get("ready") is not True:
        blockers.append("promotion readiness record is not ready")
    if not _clean(decided_by):
        blockers.append("decided_by is required")
    if decision == "approved" and blockers:
        decision = "blocked"
    support_artifacts = readiness.get("support_artifacts", []) if isinstance(readiness.get("support_artifacts", []), list) else []
    return {
        "kind": PROMOTION_DECISION_RECORD_KIND,
        "schema_version": PROMOTION_DECISION_RECORD_SCHEMA_VERSION,
        "capability_state": "promotion_decision_record",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "decision": decision,
        "approved": decision == "approved" and not blockers,
        "blockers": blockers,
        "decided_by": _clean(decided_by),
        "reason": _clean(reason),
        "readiness": {
            "path": str(readiness_path),
            "kind": readiness.get("kind", ""),
            "expected_kind": PROMOTION_READINESS_RECORD_KIND,
            "sha256": _digest(readiness),
            "status": readiness.get("status", ""),
            "ready": readiness.get("ready", False),
            "capability_name": readiness.get("capability_name", ""),
            "target_state": readiness.get("target_state", ""),
            "target": readiness.get("target", ""),
            "support_artifact_count": len(support_artifacts),
            "support_artifact_kinds": support_artifact_kinds(support_artifacts),
        },
        "checks": readiness.get("checks", []) if isinstance(readiness.get("checks"), list) else [],
        "allowed_actions": ["validate_readiness_record", "render_promotion_decision", "validate_promotion_decision"],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": {
            "capability_state": "promotion_decision_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def create_promotion_decision_record_from_file(
    readiness_path: Path,
    *,
    decision: PromotionDecision,
    decided_by: str,
    reason: str = "",
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        readiness = json_lib.loads(readiness_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"file not found: {readiness_path}"]
    except json_lib.JSONDecodeError as exc:
        return None, [f"readiness invalid JSON: {exc}"]
    if not isinstance(readiness, dict):
        return None, ["readiness must be a JSON object"]
    record = create_promotion_decision_record(readiness, readiness_path=readiness_path, decision=decision, decided_by=decided_by, reason=reason)
    errors = validate_promotion_decision_record(record)
    if errors:
        return None, errors
    return record, []


def dumps_promotion_decision_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_promotion_decision_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_promotion_decision_record(record), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def _validate_readiness_ref(readiness: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(readiness, dict):
        return ["readiness must be an object"]
    if readiness.get("expected_kind") != PROMOTION_READINESS_RECORD_KIND:
        errors.append(f"readiness.expected_kind must be {PROMOTION_READINESS_RECORD_KIND}")
    if readiness.get("kind") != PROMOTION_READINESS_RECORD_KIND:
        errors.append(f"readiness.kind must be {PROMOTION_READINESS_RECORD_KIND}")
    if not readiness.get("path"):
        errors.append("readiness.path is required")
    if not readiness.get("sha256"):
        errors.append("readiness.sha256 is required")
    if readiness.get("status") not in _READINESS_STATUSES:
        errors.append("readiness.status must be ready or blocked")
    if not isinstance(readiness.get("ready"), bool):
        errors.append("readiness.ready must be a boolean")
    elif readiness.get("status") == "ready" and readiness.get("ready") is not True:
        errors.append("readiness.ready must be true when status is ready")
    elif readiness.get("status") == "blocked" and readiness.get("ready") is not False:
        errors.append("readiness.ready must be false when status is blocked")
    if not readiness.get("capability_name"):
        errors.append("readiness.capability_name is required")
    target = readiness.get("target", "")
    if target not in ("", "generic", "builder", "core"):
        errors.append("readiness.target must be one of: generic, builder, core")
    if "support_artifact_count" in readiness and (not isinstance(readiness.get("support_artifact_count"), int) or readiness["support_artifact_count"] < 0):
        errors.append("readiness.support_artifact_count must be a non-negative integer")
    if "support_artifact_kinds" in readiness:
        errors.extend(_string_list_errors(readiness.get("support_artifact_kinds"), field="readiness.support_artifact_kinds"))
    return errors


def validate_promotion_decision_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["promotion decision record must be a JSON object"]
    if record.get("kind") != PROMOTION_DECISION_RECORD_KIND:
        errors.append(f"kind must be {PROMOTION_DECISION_RECORD_KIND}")
    if record.get("schema_version") != PROMOTION_DECISION_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROMOTION_DECISION_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED")
    if record.get("decision") not in ("approved", "blocked"):
        errors.append("decision must be approved or blocked")
    blockers = record.get("blockers")
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
        blockers = []
    if record.get("decision") == "approved" and blockers:
        errors.append("approved decision must not have blockers")
    if record.get("approved") is not (record.get("decision") == "approved" and blockers == []):
        errors.append("approved must match decision and blockers")
    if not record.get("decided_by"):
        errors.append("decided_by is required")
    errors.extend(_validate_readiness_ref(record.get("readiness")))
    if not isinstance(record.get("checks"), list):
        errors.append("checks must be a list")
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


def validate_promotion_decision_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_promotion_decision_record(data)
