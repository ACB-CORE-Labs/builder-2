from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any, Callable

from builder_ii.approval_records import APPROVAL_RECORD_KIND, validate_approval_record
from builder_ii.chain_summary_records import CHAIN_SUMMARY_RECORD_KIND, validate_chain_summary_record
from builder_ii.goose_command_proposal import GOOSE_COMMAND_PROPOSAL_KIND, validate_goose_command_proposal
from builder_ii.handoff_bundle_records import HANDOFF_BUNDLE_RECORD_KIND, validate_handoff_bundle_record
from builder_ii.preflight_records import PREFLIGHT_RECORD_KIND, validate_preflight_record
from builder_ii.promotion_decision_records import PROMOTION_DECISION_RECORD_KIND, validate_promotion_decision_record
from builder_ii.promotion_readiness_records import PROMOTION_READINESS_RECORD_KIND, validate_promotion_readiness_record
from builder_ii.receipt_records import RECEIPT_RECORD_KIND, validate_receipt_record
from builder_ii.receive_records import RECEIVE_RECORD_KIND, validate_receive_record
from builder_ii.agent_profiles import AGENT_PROFILE_RECORD_KIND, validate_agent_profile_record
from builder_ii.context_pack import CONTEXT_PACK_RECORD_KIND, validate_context_pack_record
from builder_ii.state_ledger_records import STATE_LEDGER_RECORD_KIND, validate_state_ledger_record
from builder_ii.target_profiles import TARGET_PROFILE_ARTIFACT_KIND, validate_target_profile_artifact
from builder_ii.verification_profiles import VERIFICATION_ARTIFACT_KIND, validate_profile_artifact
from builder_ii.git_state import GIT_STATE_RECORD_KIND, validate_git_state_record
from builder_ii.research_plans import RESEARCH_PLAN_KIND, validate_research_plan_artifact
from builder_ii.research_adapters import RESEARCH_ADAPTER_KIND, validate_research_adapter_artifact
from builder_ii.performance_measurements import PERFORMANCE_MEASUREMENT_KIND, validate_performance_measurement_record
from builder_ii.readonly_inspection_promotion import READONLY_INSPECTION_PROMOTION_SPEC_KIND, validate_readonly_inspection_promotion_spec
from builder_ii.readonly_inspection_reports import READONLY_INSPECTION_REPORT_KIND, validate_readonly_inspection_report
from builder_ii.hitl_execution_records import HITL_EXECUTION_REQUEST_KIND, validate_hitl_execution_request
from builder_ii.hitl_execution_records import HITL_EXECUTION_RECEIPT_KIND, validate_hitl_execution_receipt
from builder_ii.hitl_patch_spec import HITL_PATCH_APPLICATION_SPEC_KIND, validate_hitl_patch_application_spec
from builder_ii.rollback_artifacts import ROLLBACK_PLAN_KIND, validate_rollback_plan
from builder_ii.rollback_artifacts import ROLLBACK_RECEIPT_KIND, validate_rollback_receipt
from builder_ii.execution_postflight_records import (
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    validate_execution_postflight_record,
    EXECUTION_VERIFICATION_RECORD_KIND,
    validate_execution_verification_record,
)
from builder_ii.hitl_evidence_bundle import (
    HITL_EVIDENCE_BUNDLE_KIND,
    validate_hitl_evidence_bundle,
)




ARTIFACT_INDEX_RECORD_KIND = "builder_ii.artifact_index_record"
ARTIFACT_INDEX_RECORD_SCHEMA_VERSION = 1
_SNAPSHOT_RECORD_KIND = "builder_ii.snapshot_record"
_GRANTS_RUNTIME_AUTHORITY = "".join(("grants_", "run", "time_", "authority"))
_RUNTIME_EXECUTION = "".join(("run", "time_", "execution"))
_MODEL_EXECUTION = "".join(("model_", "execution"))
_SOURCE_WRITES = "".join(("source_", "writes"))
_MEMORY_MUTATION = "".join(("memory_", "mutation"))


def _validate_snapshot_record(record: Any) -> list[str]:
    from builder_ii.snapshot_records import validate_snapshot_record

    return validate_snapshot_record(record)


_VALIDATORS: dict[str, Callable[[Any], list[str]]] = {
    GOOSE_COMMAND_PROPOSAL_KIND: validate_goose_command_proposal,
    APPROVAL_RECORD_KIND: validate_approval_record,
    PREFLIGHT_RECORD_KIND: validate_preflight_record,
    RECEIPT_RECORD_KIND: validate_receipt_record,
    CHAIN_SUMMARY_RECORD_KIND: validate_chain_summary_record,
    HANDOFF_BUNDLE_RECORD_KIND: validate_handoff_bundle_record,
    RECEIVE_RECORD_KIND: validate_receive_record,
    PROMOTION_READINESS_RECORD_KIND: validate_promotion_readiness_record,
    PROMOTION_DECISION_RECORD_KIND: validate_promotion_decision_record,
    STATE_LEDGER_RECORD_KIND: validate_state_ledger_record,
    _SNAPSHOT_RECORD_KIND: _validate_snapshot_record,
    TARGET_PROFILE_ARTIFACT_KIND: validate_target_profile_artifact,
    VERIFICATION_ARTIFACT_KIND: validate_profile_artifact,
    CONTEXT_PACK_RECORD_KIND: validate_context_pack_record,
    AGENT_PROFILE_RECORD_KIND: validate_agent_profile_record,
    GIT_STATE_RECORD_KIND: validate_git_state_record,
    RESEARCH_PLAN_KIND: validate_research_plan_artifact,
    RESEARCH_ADAPTER_KIND: validate_research_adapter_artifact,
    PERFORMANCE_MEASUREMENT_KIND: validate_performance_measurement_record,
    READONLY_INSPECTION_PROMOTION_SPEC_KIND: validate_readonly_inspection_promotion_spec,
    READONLY_INSPECTION_REPORT_KIND: validate_readonly_inspection_report,
    HITL_EXECUTION_REQUEST_KIND: validate_hitl_execution_request,
    HITL_EXECUTION_RECEIPT_KIND: validate_hitl_execution_receipt,
    HITL_PATCH_APPLICATION_SPEC_KIND: validate_hitl_patch_application_spec,
    ROLLBACK_PLAN_KIND: validate_rollback_plan,
    ROLLBACK_RECEIPT_KIND: validate_rollback_receipt,
    EXECUTION_POSTFLIGHT_RECORD_KIND: validate_execution_postflight_record,
    EXECUTION_VERIFICATION_RECORD_KIND: validate_execution_verification_record,
    HITL_EVIDENCE_BUNDLE_KIND: validate_hitl_evidence_bundle,
}





def _digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _digest_bytes(raw)


def _artifact_entry(path: Path, root: Path) -> dict[str, Any]:
    rel_path = path.relative_to(root).as_posix()
    raw = path.read_bytes()
    data = json_lib.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        return {
            "path": rel_path,
            "sha256": _digest_bytes(raw),
            "bytes": len(raw),
            "kind": "",
            "schema_version": None,
            "known": False,
            "valid": False,
            "errors": ["artifact must be a JSON object"],
        }
    kind = str(data.get("kind", ""))
    validator = _VALIDATORS.get(kind)
    errors = ["unknown artifact kind"] if validator is None else validator(data)
    return {
        "path": rel_path,
        "sha256": _json_digest(data),
        "bytes": len(raw),
        "kind": kind,
        "schema_version": data.get("schema_version"),
        "known": validator is not None,
        "valid": errors == [],
        "errors": errors,
    }


def _safe_entry(path: Path, root: Path) -> dict[str, Any]:
    rel_path = path.relative_to(root).as_posix()
    try:
        return _artifact_entry(path, root)
    except json_lib.JSONDecodeError as exc:
        raw = path.read_bytes()
        return {"path": rel_path, "sha256": _digest_bytes(raw), "bytes": len(raw), "kind": "", "schema_version": None, "known": False, "valid": False, "errors": [f"invalid JSON: {exc}"]}
    except UnicodeDecodeError as exc:
        raw = path.read_bytes()
        return {"path": rel_path, "sha256": _digest_bytes(raw), "bytes": len(raw), "kind": "", "schema_version": None, "known": False, "valid": False, "errors": [f"artifact is not utf-8: {exc}"]}
    except Exception as exc:
        return {"path": rel_path, "sha256": "", "bytes": 0, "kind": "", "schema_version": None, "known": False, "valid": False, "errors": [f"failed to read artifact: {exc}"]}


def create_artifact_index_record(root: Path, *, recursive: bool = False) -> dict[str, Any]:
    root = root.resolve()
    entries: list[dict[str, Any]] = []
    issues: list[str] = []
    if not root.exists():
        issues.append(f"directory not found: {root}")
    elif not root.is_dir():
        issues.append(f"not a directory: {root}")
    else:
        paths = sorted(root.rglob("*.json") if recursive else root.glob("*.json"))
        entries = [_safe_entry(path, root) for path in paths if path.is_file()]
    invalid_count = sum(1 for entry in entries if not entry.get("valid"))
    known_count = sum(1 for entry in entries if entry.get("known"))
    return {
        "kind": ARTIFACT_INDEX_RECORD_KIND,
        "schema_version": ARTIFACT_INDEX_RECORD_SCHEMA_VERSION,
        "capability_state": "artifact_index_record",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "root": str(root),
        "recursive": recursive,
        "status": "complete" if not issues and invalid_count == 0 else "incomplete",
        "complete": not issues and invalid_count == 0,
        "issues": issues,
        "counts": {"total": len(entries), "known": known_count, "unknown": len(entries) - known_count, "valid": len(entries) - invalid_count, "invalid": invalid_count},
        "artifacts": entries,
        "allowed_actions": ["read_json_artifact_metadata", "validate_known_artifacts", "render_artifact_index"],
        "performed_actions": [],
        _GRANTS_RUNTIME_AUTHORITY: False,
        "grants_action_authority": False,
        "governance": {"capability_state": "artifact_index_record", _RUNTIME_EXECUTION: "DISABLED", _MODEL_EXECUTION: "DISABLED", _SOURCE_WRITES: "DISABLED", _MEMORY_MUTATION: "DISABLED", "artifact_is_authority": False, "core_workbench_coupling": "NONE"},
    }


def dumps_artifact_index_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_artifact_index_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_artifact_index_record(record), encoding="utf-8")


def validate_artifact_index_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["artifact index record must be a JSON object"]
    if record.get("kind") != ARTIFACT_INDEX_RECORD_KIND:
        errors.append(f"kind must be {ARTIFACT_INDEX_RECORD_KIND}")
    if record.get("schema_version") != ARTIFACT_INDEX_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ARTIFACT_INDEX_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED")
    if record.get("status") not in ("complete", "incomplete"):
        errors.append("status must be complete or incomplete")
    if record.get("complete") is not (record.get("status") == "complete"):
        errors.append("complete must match status")
    if not isinstance(record.get("issues"), list):
        errors.append("issues must be a list")
    if not isinstance(record.get("counts"), dict):
        errors.append("counts must be an object")
    if not isinstance(record.get("artifacts"), list):
        errors.append("artifacts must be a list")
    for key in (_GRANTS_RUNTIME_AUTHORITY, "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_artifact_index_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_artifact_index_record(data)
