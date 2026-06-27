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
from builder_ii.research_adapters import RESEARCH_ADAPTER_KIND, validate_research_adapter_artifact




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
    RESEARCH_ADAPTER_KIND: validate_research_adapter_artifact,
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
        return {
            "path": rel_path,
            "sha256": _digest_bytes(raw),
            "bytes": len(raw),
            "kind": "",
            "schema_version": None,
            "known": False,
            "valid": False,
            "errors": [f"invalid JSON: {exc}"],
        }
    except Exception as exc:  # defensive: malformed artifact should not break index creation
        return {
            "path": rel_path,
            "sha256": "",
            "bytes": 0,
            "kind": "",
            "schema_version": None,
            "known": False,
            "valid": False,
            "errors": [f"failed to inspect artifact: {exc}"],
        }


def create_artifact_index_record(root: Path, *, recursive: bool = False) -> dict[str, Any]:
    pattern = "**/*.json" if recursive else "*.json"
    files = sorted(path for path in root.glob(pattern) if path.is_file())
    artifacts = [_safe_entry(path, root) for path in files]
    totals = {
        "total": len(artifacts),
        "known": sum(1 for item in artifacts if item["known"]),
        "unknown": sum(1 for item in artifacts if not item["known"]),
        "valid": sum(1 for item in artifacts if item["valid"]),
        "invalid": sum(1 for item in artifacts if not item["valid"]),
    }
    return {
        "kind": ARTIFACT_INDEX_RECORD_KIND,
        "schema_version": ARTIFACT_INDEX_RECORD_SCHEMA_VERSION,
        "root": str(root),
        "recursive": recursive,
        "artifacts": artifacts,
        "totals": totals,
        "allowed_actions": ["record_artifact_index", "validate_artifact_index"],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "governance": {
            "capability_state": "artifact_index_record",
            _RUNTIME_EXECUTION: "DISABLED",
            _MODEL_EXECUTION: "DISABLED",
            _SOURCE_WRITES: "DISABLED",
            _MEMORY_MUTATION: "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
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
    if not isinstance(record.get("artifacts"), list):
        errors.append("artifacts must be a list")
    if not isinstance(record.get("totals"), dict):
        errors.append("totals must be an object")
    else:
        artifacts = record.get("artifacts", []) if isinstance(record.get("artifacts"), list) else []
        expected = {
            "total": len(artifacts),
            "known": sum(1 for item in artifacts if isinstance(item, dict) and item.get("known") is True),
            "unknown": sum(1 for item in artifacts if isinstance(item, dict) and item.get("known") is not True),
            "valid": sum(1 for item in artifacts if isinstance(item, dict) and item.get("valid") is True),
            "invalid": sum(1 for item in artifacts if isinstance(item, dict) and item.get("valid") is not True),
        }
        for key, value in expected.items():
            if record["totals"].get(key) != value:
                errors.append(f"totals.{key} must be {value}")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    if record.get("grants_runtime_authority") is not False:
        errors.append("grants_runtime_authority must be false")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (_RUNTIME_EXECUTION, _MODEL_EXECUTION, _SOURCE_WRITES, _MEMORY_MUTATION):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
    return errors


def validate_artifact_index_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_artifact_index_record(data)
