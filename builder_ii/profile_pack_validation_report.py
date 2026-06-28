from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any, Callable

from builder_ii.profile_pack_dry_run import PROFILE_PACK_DRY_RUN_KIND, validate_profile_pack_dry_run
from builder_ii.profile_pack_manifest import PROFILE_PACK_MANIFEST_KIND, canonical_digest, validate_profile_pack_manifest
from builder_ii.profile_pack_render_plan import PROFILE_PACK_RENDER_PLAN_KIND, validate_profile_pack_render_plan

PROFILE_PACK_VALIDATION_REPORT_KIND = "builder_ii.profile_pack_validation_report"
PROFILE_PACK_VALIDATION_REPORT_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _validators() -> dict[str, Callable[[Any], list[str]]]:
    from builder_ii.profile_pack import PROFILE_PACK_KIND, validate_profile_pack

    return {
        PROFILE_PACK_MANIFEST_KIND: validate_profile_pack_manifest,
        PROFILE_PACK_RENDER_PLAN_KIND: validate_profile_pack_render_plan,
        PROFILE_PACK_DRY_RUN_KIND: validate_profile_pack_dry_run,
        PROFILE_PACK_KIND: validate_profile_pack,
        PROFILE_PACK_VALIDATION_REPORT_KIND: validate_profile_pack_validation_report,
    }


def _artifact_ref(data: dict[str, Any], *, path: Path | None) -> dict[str, Any]:
    return {
        "kind": str(data.get("kind", "")),
        "path": str(path) if path is not None else "",
        "sha256": canonical_digest(data),
    }


def create_profile_pack_validation_report(
    subject: Any,
    *,
    subject_path: Path | None = None,
) -> dict[str, Any]:
    errors: list[str] = []
    subject_kind = ""
    subject_ref: dict[str, Any] = {"kind": "", "path": str(subject_path) if subject_path else "", "sha256": ""}
    if not isinstance(subject, dict):
        errors.append("subject must be a JSON object")
    else:
        subject_kind = str(subject.get("kind", ""))
        subject_ref = _artifact_ref(subject, path=subject_path)
        validator = _validators().get(subject_kind)
        if validator is None:
            errors.append(f"unknown profile pack artifact kind: {subject_kind or '<missing>'}")
        else:
            errors.extend(validator(subject))

    valid = errors == []
    return {
        "kind": PROFILE_PACK_VALIDATION_REPORT_KIND,
        "schema_version": PROFILE_PACK_VALIDATION_REPORT_SCHEMA_VERSION,
        "validation_state": "VALIDATED_ONLY",
        "subject_kind": subject_kind,
        "subject_ref": subject_ref,
        "status": "valid" if valid else "invalid",
        "valid": valid,
        "errors": errors,
        "warnings": [],
        "checked_boundaries": [
            "planned_is_not_executed",
            "rendered_is_not_authorized",
            "dry_run_is_not_execution",
            "validated_is_not_promoted",
            "artifact_is_not_authority",
            "source_refs_require_hashes",
        ],
        "claims": {
            "planned": subject_kind == PROFILE_PACK_MANIFEST_KIND and valid,
            "rendered": subject_kind == PROFILE_PACK_RENDER_PLAN_KIND and valid,
            "dry_run": subject_kind == PROFILE_PACK_DRY_RUN_KIND and valid,
            "validated": True,
            "executed": False,
            "authorized": False,
            "promoted": False,
        },
        "governance": {
            "capability_state": "profile_pack_validation_report",
            "runtime_execution": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "deepagents_runtime_start": "DISABLED",
            "agent_construction": "DISABLED",
            "subagent_construction": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "mcp_tool_calls": "DISABLED",
            "verification_execution": "DISABLED",
            "artifact_is_authority": False,
            "executed": False,
            "authorized": False,
            "promoted": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_profile_pack_validation_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"


def write_profile_pack_validation_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_profile_pack_validation_report(report), encoding="utf-8")


def _validate_ref(value: Any, *, field: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if not isinstance(value.get("kind", ""), str):
        errors.append(f"{field}.kind must be a string")
    if not isinstance(value.get("path", ""), str):
        errors.append(f"{field}.path must be a string")
    sha = value.get("sha256", "")
    if sha and (not isinstance(sha, str) or not _SHA256_RE.match(sha)):
        errors.append(f"{field}.sha256 must be a SHA-256 hex digest when present")
    return errors


def _validate_governance(governance: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    if governance.get("capability_state") != "profile_pack_validation_report":
        errors.append("governance.capability_state must be profile_pack_validation_report")
    for key in (
        "runtime_execution",
        "goose_runtime_start",
        "deepagents_runtime_start",
        "agent_construction",
        "subagent_construction",
        "model_execution",
        "shell_execution",
        "target_repo_writes",
        "memory_mutation",
        "mcp_tool_calls",
        "verification_execution",
    ):
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "executed", "authorized", "promoted"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_profile_pack_validation_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["profile pack validation report must be a JSON object"]
    if data.get("kind") != PROFILE_PACK_VALIDATION_REPORT_KIND:
        errors.append(f"kind must be {PROFILE_PACK_VALIDATION_REPORT_KIND}")
    if data.get("schema_version") != PROFILE_PACK_VALIDATION_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROFILE_PACK_VALIDATION_REPORT_SCHEMA_VERSION}")
    if data.get("validation_state") != "VALIDATED_ONLY":
        errors.append("validation_state must be VALIDATED_ONLY")
    if not isinstance(data.get("subject_kind"), str):
        errors.append("subject_kind must be a string")
    errors.extend(_validate_ref(data.get("subject_ref"), field="subject_ref"))
    if data.get("status") not in {"valid", "invalid"}:
        errors.append("status must be valid or invalid")
    if not isinstance(data.get("valid"), bool):
        errors.append("valid must be a boolean")
    if not isinstance(data.get("errors"), list) or any(not isinstance(item, str) for item in data.get("errors", [])):
        errors.append("errors must be a list of strings")
    if not isinstance(data.get("warnings"), list) or any(not isinstance(item, str) for item in data.get("warnings", [])):
        errors.append("warnings must be a list of strings")
    boundaries = data.get("checked_boundaries")
    if not isinstance(boundaries, list) or not boundaries:
        errors.append("checked_boundaries must be a non-empty list")
    claims = data.get("claims")
    if not isinstance(claims, dict):
        errors.append("claims must be an object")
    else:
        for key in ("validated", "executed", "authorized", "promoted"):
            if not isinstance(claims.get(key), bool):
                errors.append(f"claims.{key} must be a boolean")
        for key in ("executed", "authorized", "promoted"):
            if claims.get(key) is not False:
                errors.append(f"claims.{key} must be false")
    if data.get("valid") is True and data.get("errors") != []:
        errors.append("errors must be empty when valid is true")
    if data.get("valid") is False and data.get("status") != "invalid":
        errors.append("status must be invalid when valid is false")
    errors.extend(_validate_governance(data.get("governance")))
    return errors


def validate_profile_pack_validation_report_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_profile_pack_validation_report(data)
