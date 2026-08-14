from __future__ import annotations

import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.core.canonical_json import canonical_digest
from builder_ii.core.platform_completion_audit import REQUIRED_CAPABILITY_ROWS
from builder_ii.governance.authority import COMMAND_AUTHORITY_REGISTRY

OPERATOR_STATUS_REPORT_KIND = "builder_ii.operator_status_report"
SCHEMA_VERSION = 2


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
    memory_artifacts: dict[str, Path] | None = None,
) -> dict[str, Any]:
    capabilities = [row.to_jsonable() for row in REQUIRED_CAPABILITY_ROWS]

    commands = []
    for cmd in COMMAND_AUTHORITY_REGISTRY:
        commands.append(
            {
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
            }
        )

    capability_counts = {}
    promoted = []
    passive = []
    blocked = []
    for row in REQUIRED_CAPABILITY_ROWS:
        state = row.state
        capability_counts[state] = capability_counts.get(state, 0) + 1
        if state == "OPERATIONALLY_VERIFIED":
            promoted.append(row.capability)
        elif state in ("PASSIVE_FOUNDATION", "ARTIFACT_ONLY", "MERGED_BUT_NOT_OPERATIONAL", "DESIGN_ONLY"):
            passive.append(row.capability)
        else:
            blocked.append(row.capability)

    command_surfaces = [cmd.name for cmd in COMMAND_AUTHORITY_REGISTRY]

    warnings = []
    memory_status = {
        "status": "missing-evidence",
        "detail": "No memory artifacts supplied or found.",
        "index_ref": None,
        "atom_count": 0,
    }

    if memory_artifacts:
        idx_path = memory_artifacts.get("memory_index")
        if idx_path and Path(idx_path).is_file():
            try:
                idx_data = json_lib.loads(Path(idx_path).read_text(encoding="utf-8"))
                memory_status = {
                    "status": "available",
                    "detail": "Memory index verified and loaded.",
                    "index_ref": str(idx_path),
                    "atom_count": idx_data.get("atom_count", 0),
                }
            except Exception as e:
                warnings.append(f"Failed to parse memory index at {idx_path}: {e}")
        else:
            warnings.append(f"Memory index path {idx_path} is not a valid file.")
    else:
        default_index_path = Path(".builder/artifacts/memory-index.json")
        if default_index_path.is_file():
            try:
                idx_data = json_lib.loads(default_index_path.read_text(encoding="utf-8"))
                memory_status = {
                    "status": "available",
                    "detail": "Default memory index verified and loaded.",
                    "index_ref": str(default_index_path),
                    "atom_count": idx_data.get("atom_count", 0),
                }
            except Exception as e:
                warnings.append(f"Failed to parse default memory index: {e}")

    report = {
        "kind": OPERATOR_STATUS_REPORT_KIND,
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status_state": "STATUS_REPORT_ONLY",
        "operator_name": operator_name.strip() or "operator",
        "target": target.strip() or "generic",
        "platform_state_summary": f"Platform has {len(promoted)} verified capabilities and {len(passive) + len(blocked)} incomplete. Active commands are gated by HITL.",
        "capability_counts_by_state": capability_counts,
        "promoted_capabilities": promoted,
        "passive_capabilities": passive,
        "blocked_or_missing_capabilities": blocked,
        "command_surfaces_available": command_surfaces,
        "warnings": warnings,
        "memory_status": memory_status,
        "disabled_authority_summary": {
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "runtime_start": "DISABLED",
            "mcp_tool_invocation": "DISABLED",
            "goose_runtime": "DISABLED",
            "deepagents_runtime": "DISABLED",
            "source_writes": "DISABLED",
            "target_repo_writes": "DISABLED",
            "hidden_memory": "DISABLED",
            "autonomous_writes": "DISABLED",
        },
        "artifact_is_authority": False,
        "grants_authority": False,
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

    for f in (
        "created_at_utc",
        "platform_state_summary",
        "capability_counts_by_state",
        "promoted_capabilities",
        "passive_capabilities",
        "blocked_or_missing_capabilities",
        "command_surfaces_available",
        "warnings",
        "memory_status",
        "disabled_authority_summary",
    ):
        if f not in record:
            errors.append(f"missing required field: {f}")

    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false or NOT_AUTHORIZED")

    gov = record.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        for key in ("artifact_is_authority", "grants_authority"):
            if gov.get(key) is not False:
                errors.append(f"governance.{key} must be false or NOT_AUTHORIZED")
        if gov.get("no_source_truth_inflation") is not True:
            errors.append("governance.no_source_truth_inflation must be true")

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
