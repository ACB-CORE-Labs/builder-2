from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.governance.ledger.chain_summary_records import CHAIN_SUMMARY_RECORD_KIND, validate_chain_summary_record

HANDOFF_BUNDLE_RECORD_KIND = "builder_ii.handoff_bundle_record"
HANDOFF_BUNDLE_RECORD_SCHEMA_VERSION = 1


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _clean(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def _clean_list(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if values is None:
        return []
    return [item for item in (str(value).strip() for value in values) if item]


def create_handoff_bundle_record(
    summary: dict[str, Any],
    *,
    summary_path: str | Path,
    bundle_name: str,
    notes: str = "",
    include_refs: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    issues: list[str] = []
    if summary.get("kind") != CHAIN_SUMMARY_RECORD_KIND:
        issues.append(f"summary.kind must be {CHAIN_SUMMARY_RECORD_KIND}")
    issues.extend(f"summary: {error}" for error in validate_chain_summary_record(summary))
    if not _clean(bundle_name):
        issues.append("bundle_name is required")
    artifacts = summary.get("artifacts", {}) if isinstance(summary.get("artifacts"), dict) else {}
    return {
        "kind": HANDOFF_BUNDLE_RECORD_KIND,
        "schema_version": HANDOFF_BUNDLE_RECORD_SCHEMA_VERSION,
        "capability_state": "handoff_bundle_record",
        "record_state": "RECORDED_ONLY",
        "current_runtime_state": "DISABLED",
        "status": "complete" if not issues else "incomplete",
        "complete": not issues,
        "issues": issues,
        "bundle_name": _clean(bundle_name),
        "notes": _clean(notes),
        "summary": {
            "path": str(summary_path),
            "kind": summary.get("kind", ""),
            "expected_kind": CHAIN_SUMMARY_RECORD_KIND,
            "sha256": _digest(summary),
            "status": summary.get("status", ""),
            "complete": summary.get("complete", False),
        },
        "artifact_digests": {
            name: {
                "path": item.get("path", ""),
                "kind": item.get("kind", ""),
                "sha256": item.get("sha256", ""),
            }
            for name, item in artifacts.items()
            if isinstance(item, dict)
        },
        "target": summary.get("target", {}),
        "agent_profile": summary.get("agent_profile", {}),
        "include_refs": _clean_list(include_refs),
        "allowed_actions": ["validate_summary", "render_handoff_bundle", "validate_handoff_bundle"],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": build_standard_governance("handoff_bundle_record"),
    }


def create_handoff_bundle_record_from_file(
    summary_path: Path,
    *,
    bundle_name: str,
    notes: str = "",
    include_refs: tuple[str, ...] | list[str] | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        summary = json_lib.loads(summary_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [f"file not found: {summary_path}"]
    except json_lib.JSONDecodeError as exc:
        return None, [f"summary invalid JSON: {exc}"]
    except Exception as exc:
        return None, [f"failed to read summary: {exc}"]
    if not isinstance(summary, dict):
        return None, ["summary must be a JSON object"]
    record = create_handoff_bundle_record(
        summary,
        summary_path=summary_path,
        bundle_name=bundle_name,
        notes=notes,
        include_refs=include_refs,
    )
    errors = validate_handoff_bundle_record(record)
    if errors:
        return None, errors
    return record, []


def dumps_handoff_bundle_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_handoff_bundle_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_handoff_bundle_record(record), encoding="utf-8")


def validate_handoff_bundle_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["handoff bundle record must be a JSON object"]
    if record.get("kind") != HANDOFF_BUNDLE_RECORD_KIND:
        errors.append(f"kind must be {HANDOFF_BUNDLE_RECORD_KIND}")
    if record.get("schema_version") != HANDOFF_BUNDLE_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HANDOFF_BUNDLE_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED or NOT_AUTHORIZED")
    if record.get("status") not in ("complete", "incomplete"):
        errors.append("status must be complete or incomplete")
    if record.get("complete") is not (record.get("status") == "complete"):
        errors.append("complete must match status")
    if not isinstance(record.get("issues"), list):
        errors.append("issues must be a list")
    if record.get("status") == "complete" and record.get("issues") != []:
        errors.append("complete bundles must not have issues")
    if not record.get("bundle_name"):
        errors.append("bundle_name is required")
    if record.get("summary", {}).get("expected_kind") != CHAIN_SUMMARY_RECORD_KIND:
        errors.append(f"summary.expected_kind must be {CHAIN_SUMMARY_RECORD_KIND}")
    if not isinstance(record.get("artifact_digests"), dict):
        errors.append("artifact_digests must be an object")
    for key in ("grants_runtime_authority", "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false or NOT_AUTHORIZED")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(validate_standard_governance(governance, "handoff_bundle_record"))
    return errors


def validate_handoff_bundle_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_handoff_bundle_record(data)
