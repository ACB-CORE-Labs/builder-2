from __future__ import annotations

import hashlib
import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.core.platform_completion_audit import REQUIRED_CAPABILITY_ROWS

OPERATOR_NEXT_ACTION_REPORT_KIND = "builder_ii.operator_next_action_report"
SCHEMA_VERSION = 2


def canonical_digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_governance() -> dict[str, Any]:
    return {
        "artifact_is_authority": False,
        "grants_authority": False,
        "no_source_truth_inflation": True,
    }


def create_operator_next_action_report() -> dict[str, Any]:
    state_str = "".join(f"{row.capability}:{row.state}" for row in REQUIRED_CAPABILITY_ROWS)
    current_state_digest = hashlib.sha256(state_str.encode("utf-8")).hexdigest()

    ordered_next_actions = []
    missing_evidence = []

    for row in REQUIRED_CAPABILITY_ROWS:
        if row.state != "OPERATIONALLY_VERIFIED":
            blocked_by = list(row.blockers)

            # Simple evidence check
            # For each incomplete, identify missing evidence files
            for file_path in row.evidence_files:
                if not Path(file_path).exists():
                    missing_evidence.append(file_path)

            action = {
                "capability": row.capability,
                "state": row.state,
                "reason": f"Capability '{row.capability}' is currently at state {row.state}.",
                "blocked_by": blocked_by,
                "safe_commands": list(row.command_surfaces) if row.command_surfaces else ["builder-platform matrix"],
            }
            ordered_next_actions.append(action)

    missing_evidence = sorted(list(set(missing_evidence)))

    current_state_summary = f"Platform has {len(ordered_next_actions)} incomplete capabilities remaining out of {len(REQUIRED_CAPABILITY_ROWS)}."

    report = {
        "kind": OPERATOR_NEXT_ACTION_REPORT_KIND,
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "current_state_digest": current_state_digest,
        "current_state_summary": current_state_summary,
        "ordered_next_actions": ordered_next_actions,
        "non_goals": [
            "runtime execution",
            "patch application",
            "model/provider calls",
            "MCP/tool invocation",
            "Goose runtime promotion",
            "deepagents runtime",
            "autonomous writes",
            "commit/push automation",
        ],
        "missing_evidence": missing_evidence,
        "artifact_is_authority": False,
        "grants_authority": False,
        "governance": _default_governance(),
    }

    report["report_digest"] = canonical_digest(report)
    return report


def validate_operator_next_action_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["operator next action report must be a JSON object"]

    if record.get("kind") != OPERATOR_NEXT_ACTION_REPORT_KIND:
        errors.append(f"kind must be {OPERATOR_NEXT_ACTION_REPORT_KIND}")

    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")

    for f in (
        "created_at_utc",
        "current_state_digest",
        "current_state_summary",
        "ordered_next_actions",
        "non_goals",
        "missing_evidence",
    ):
        if f not in record:
            errors.append(f"missing required field: {f}")

    if not isinstance(record.get("ordered_next_actions"), list):
        errors.append("ordered_next_actions must be a list")
    else:
        for index, action in enumerate(record["ordered_next_actions"]):
            prefix = f"ordered_next_actions[{index}]"
            if not isinstance(action, dict):
                errors.append(f"{prefix} must be an object")
                continue
            for k in ("capability", "state", "reason", "blocked_by", "safe_commands"):
                if k not in action:
                    errors.append(f"{prefix} is missing required field: {k}")

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


def write_operator_next_action_report(record: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = json_lib.dumps(record, indent=2, sort_keys=True) + "\n"
    path.write_text(out, encoding="utf-8")


def dumps_operator_next_action_report(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"
