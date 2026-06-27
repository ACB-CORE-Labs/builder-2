from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.promotion_compatibility import support_artifact_kinds, validate_support_artifacts

PROMOTION_READINESS_RECORD_KIND = "builder_ii.promotion_readiness_record"
PROMOTION_READINESS_RECORD_SCHEMA_VERSION = 1

_REQUIRED_CHECKS = (
    "docs",
    "tests",
    "cli_surface",
    "failure_mode",
    "approval_boundary",
    "output_artifact",
    "rollback_path",
    "verification_path",
)
_TARGETS = {"generic", "builder", "core"}


def _clean(value: str | None) -> str:
    return "" if value is None else str(value).strip()


def _clean_list(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if values is None:
        return []
    return [item for item in (str(value).strip() for value in values) if item]


def _check(name: str, refs: list[str]) -> dict[str, Any]:
    return {"name": name, "refs": refs, "ready": bool(refs), "missing": [] if refs else [f"{name} refs are required"]}


def create_promotion_readiness_record(
    *,
    capability_name: str,
    target_state: str = "enabled",
    target: str = "",
    docs_refs: tuple[str, ...] | list[str] | None = None,
    tests_refs: tuple[str, ...] | list[str] | None = None,
    cli_refs: tuple[str, ...] | list[str] | None = None,
    failure_mode_refs: tuple[str, ...] | list[str] | None = None,
    approval_boundary_refs: tuple[str, ...] | list[str] | None = None,
    output_artifact_refs: tuple[str, ...] | list[str] | None = None,
    rollback_refs: tuple[str, ...] | list[str] | None = None,
    verification_refs: tuple[str, ...] | list[str] | None = None,
    support_artifacts: list[dict[str, Any]] | None = None,
    notes: str = "",
) -> dict[str, Any]:
    checks = [
        _check("docs", _clean_list(docs_refs)),
        _check("tests", _clean_list(tests_refs)),
        _check("cli_surface", _clean_list(cli_refs)),
        _check("failure_mode", _clean_list(failure_mode_refs)),
        _check("approval_boundary", _clean_list(approval_boundary_refs)),
        _check("output_artifact", _clean_list(output_artifact_refs)),
        _check("rollback_path", _clean_list(rollback_refs)),
        _check("verification_path", _clean_list(verification_refs)),
    ]
    selected_target = _clean(target)
    support_refs = list(support_artifacts or [])
    missing = [item for check in checks for item in check["missing"]]
    if not _clean(capability_name):
        missing.append("capability_name is required")
    for error in validate_support_artifacts(support_refs, expected_target=selected_target):
        missing.append(f"support_artifacts: {error}")
    ready = not missing
    return {
        "kind": PROMOTION_READINESS_RECORD_KIND,
        "schema_version": PROMOTION_READINESS_RECORD_SCHEMA_VERSION,
        "capability_state": "promotion_readiness_record",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "capability_name": _clean(capability_name),
        "target_state": _clean(target_state),
        "target": selected_target,
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "missing": missing,
        "checks": checks,
        "support_artifacts": support_refs,
        "notes": _clean(notes),
        "allowed_actions": ["record_promotion_readiness", "validate_promotion_readiness"],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": {
            "capability_state": "promotion_readiness_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_promotion_readiness_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_promotion_readiness_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_promotion_readiness_record(record), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def _validate_check(check: Any, index: int) -> list[str]:
    """Validate shape of a single check entry."""
    errors: list[str] = []
    prefix = f"checks[{index}]"
    if not isinstance(check, dict):
        return [f"{prefix} must be an object"]
    if not isinstance(check.get("name"), str) or not check["name"]:
        errors.append(f"{prefix}.name must be a non-empty string")
    errors.extend(_string_list_errors(check.get("refs"), field=f"{prefix}.refs"))
    if not isinstance(check.get("ready"), bool):
        errors.append(f"{prefix}.ready must be a boolean")
    errors.extend(_string_list_errors(check.get("missing"), field=f"{prefix}.missing"))
    # Cross-field consistency within check
    if isinstance(check.get("refs"), list) and isinstance(check.get("ready"), bool):
        expected_ready = bool(check["refs"])
        if check["ready"] != expected_ready:
            errors.append(f"{prefix}.ready must match whether refs is non-empty")
    if isinstance(check.get("refs"), list) and isinstance(check.get("missing"), list):
        if check["refs"] and check["missing"]:
            errors.append(f"{prefix} must not have missing items when refs are present")
        if not check["refs"] and not check["missing"]:
            errors.append(f"{prefix} must have missing items when refs are empty")
    return errors


def validate_promotion_readiness_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["promotion readiness record must be a JSON object"]
    if record.get("kind") != PROMOTION_READINESS_RECORD_KIND:
        errors.append(f"kind must be {PROMOTION_READINESS_RECORD_KIND}")
    if record.get("schema_version") != PROMOTION_READINESS_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROMOTION_READINESS_RECORD_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED")
    if record.get("capability_state") != "promotion_readiness_record":
        errors.append("capability_state must be promotion_readiness_record")
    if not isinstance(record.get("capability_name"), str) or not record["capability_name"]:
        errors.append("capability_name is required")
    if not isinstance(record.get("target_state"), str) or not record["target_state"]:
        errors.append("target_state is required")
    target = record.get("target", "")
    if target not in ("", "generic", "builder", "core"):
        errors.append("target must be one of: generic, builder, core")
    if record.get("status") not in ("ready", "blocked"):
        errors.append("status must be ready or blocked")
    if not isinstance(record.get("ready"), bool):
        errors.append("ready must be a boolean")
    elif record.get("ready") is not (record.get("status") == "ready"):
        errors.append("ready must match status")
    errors.extend(_string_list_errors(record.get("missing"), field="missing"))
    # Validate checks structure and required check names
    checks = record.get("checks")
    if not isinstance(checks, list):
        errors.append("checks must be a list")
    else:
        for index, check in enumerate(checks):
            errors.extend(_validate_check(check, index))
        names = {check.get("name") for check in checks if isinstance(check, dict)}
        for required in _REQUIRED_CHECKS:
            if required not in names:
                errors.append(f"missing check: {required}")
        # Validate aggregate missing matches check-level missing
        if isinstance(record.get("missing"), list):
            check_missing = [
                item
                for check in checks
                if isinstance(check, dict) and isinstance(check.get("missing"), list)
                for item in check["missing"]
            ]
            # Top-level missing may include extra entries like "capability_name is required"
            # but must contain all check-level missing items
            top_missing = record["missing"]
            for item in check_missing:
                if item not in top_missing:
                    errors.append(f"missing must include check-level item: {item}")
    support_artifacts = record.get("support_artifacts", [])
    errors.extend(validate_support_artifacts(support_artifacts, expected_target=target if isinstance(target, str) else ""))
    if isinstance(record.get("missing"), list):
        compatibility_missing = [f"support_artifacts: {error}" for error in validate_support_artifacts(support_artifacts, expected_target=target if isinstance(target, str) else "")]
        if compatibility_missing and record.get("ready") is True:
            errors.append("ready must be false when support_artifacts are incompatible")
        for item in compatibility_missing:
            if item not in record["missing"]:
                errors.append(f"missing must include compatibility item: {item}")
    for key in ("grants_runtime_authority", "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "promotion_readiness_record":
            errors.append("governance.capability_state must be promotion_readiness_record")
        for key in ("runtime_execution", "model_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_promotion_readiness_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_promotion_readiness_record(data)
