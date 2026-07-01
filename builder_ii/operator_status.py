from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.platform_completion_audit import REQUIRED_CAPABILITY_ROWS

OPERATOR_STATUS_REPORT_KIND = "builder_ii.operator_status_report"
SCHEMA_VERSION = 1


def canonical_digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_governance() -> dict[str, Any]:
    return {
        "artifact_is_authority": False,
        "grants_authority": False,
        "no_source_truth_inflation": True,
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "core_workbench_coupling": "NONE",
    }


def create_operator_status_report(
    *,
    operator_name: str = "operator",
    target: str = "generic",
) -> dict[str, Any]:
    capabilities = [row.to_jsonable() for row in REQUIRED_CAPABILITY_ROWS]

    commands = []
    for cmd in COMMAND_AUTHORITY_REGISTRY:
        commands.append({
            "name": cmd.name,
            "tier": cmd.tier,
            "promotion_state": cmd.promotion_state,
            "allows_runtime_start": cmd.allows_runtime_start,
            "allows_model_execution": cmd.allows_model_execution,
            "allows_shell_execution": cmd.allows_shell_execution,
            "allows_source_writes": cmd.allows_source_writes,
            "allows_memory_mutation": cmd.allows_memory_mutation,
            "allows_target_repo_mutation": cmd.allows_git_mutation,
            "allows_artifact_writes": cmd.allows_artifact_writes,
            "allows_state_writes": cmd.allows_state_writes,
        })

    report = {
        "kind": OPERATOR_STATUS_REPORT_KIND,
        "schema_version": SCHEMA_VERSION,
        "status_state": "STATUS_REPORT_ONLY",
        "operator_name": operator_name.strip() or "operator",
        "target": target.strip() or "generic",
        "capabilities": capabilities,
        "commands": commands,
        "governance": _default_governance(),
    }

    report["report_digest"] = canonical_digest(report)
    return report


def validate_operator_status_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["operator status report must be a JSON object"]

    if record.get("kind") != OPERATOR_STATUS_REPORT_KIND:
        errors.append(f"kind must be {OPERATOR_STATUS_REPORT_KIND}")

    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    if record.get("status_state") != "STATUS_REPORT_ONLY":
        errors.append("status_state must be STATUS_REPORT_ONLY")

    if not isinstance(record.get("operator_name"), str) or not record["operator_name"]:
        errors.append("operator_name must be a non-empty string")

    if not isinstance(record.get("target"), str) or not record["target"]:
        errors.append("target must be a non-empty string")

    if not isinstance(record.get("capabilities"), list):
        errors.append("capabilities must be a list")

    if not isinstance(record.get("commands"), list):
        errors.append("commands must be a list")

    gov = record.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        for key in ("artifact_is_authority", "grants_authority"):
            if gov.get(key) is not False:
                errors.append(f"governance.{key} must be false")
        if gov.get("no_source_truth_inflation") is not True:
            errors.append("governance.no_source_truth_inflation must be true")
        for key in ("runtime_execution", "model_execution", "shell_execution", "target_repo_writes"):
            if gov.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if gov.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
            errors.append("governance.source_writes must be DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
        if gov.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    digest = record.get("report_digest")
    if digest:
        temp_record = dict(record)
        del temp_record["report_digest"]
        if canonical_digest(temp_record) != digest:
            errors.append("report_digest does not match canonical content")
    else:
        errors.append("report_digest is required")

    return errors


def write_operator_status_report(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = json_lib.dumps(record, indent=2, sort_keys=True) + "\n"
    path.write_text(out, encoding="utf-8")


def dumps_operator_status_report(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"
