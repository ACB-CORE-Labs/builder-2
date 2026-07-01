from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.platform_completion_audit import REQUIRED_CAPABILITY_ROWS

OPERATOR_NEXT_ACTION_REPORT_KIND = "builder_ii.operator_next_action_report"
SCHEMA_VERSION = 1


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
    # Find the first incomplete platform capability
    incomplete = None
    for row in REQUIRED_CAPABILITY_ROWS:
        if row.state != "OPERATIONALLY_VERIFIED":
            incomplete = row
            break

    next_action = ""
    suggested_command = ""
    if incomplete:
        next_action = f"Capability '{incomplete.capability}' is currently at state {incomplete.state}. Next phase block is {incomplete.next_pr}."
        if incomplete.command_surfaces:
            suggested_command = incomplete.command_surfaces[0]
        else:
            suggested_command = "builder-platform matrix"
    else:
        next_action = "Platform is fully operationally verified."
        suggested_command = "builder-platform status"

    report = {
        "kind": OPERATOR_NEXT_ACTION_REPORT_KIND,
        "schema_version": SCHEMA_VERSION,
        "next_action": next_action,
        "suggested_command": suggested_command,
        "incomplete_capability": incomplete.capability if incomplete else None,
        "incomplete_state": incomplete.state if incomplete else None,
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

    if not isinstance(record.get("next_action"), str) or not record["next_action"]:
        errors.append("next_action must be a non-empty string")

    if not isinstance(record.get("suggested_command"), str) or not record["suggested_command"]:
        errors.append("suggested_command must be a non-empty string")

    gov = record.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        for key in ("artifact_is_authority", "grants_authority"):
            if gov.get(key) is not False:
                errors.append(f"governance.{key} must be false")
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
