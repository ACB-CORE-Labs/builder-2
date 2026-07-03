from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.target_profiles import target_names

PERFORMANCE_MEASUREMENT_KIND = "builder_ii.performance_measurement"
PERFORMANCE_MEASUREMENT_SCHEMA_VERSION = 1
_STATUSES = {"candidate", "accepted", "rejected"}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _clean_list(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if values is None:
        return []
    return [item for item in (_clean(value) for value in values) if item]


def create_performance_measurement_record(
    *,
    target: str,
    candidate_name: str,
    metric_name: str,
    metric_value: float,
    unit: str,
    method: str,
    source_ref: str,
    status: str = "candidate",
    baseline_value: float | None = None,
    evidence_refs: tuple[str, ...] | list[str] | None = None,
    notes: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": PERFORMANCE_MEASUREMENT_KIND,
        "schema_version": PERFORMANCE_MEASUREMENT_SCHEMA_VERSION,
        "capability_state": "performance_measurement_record",
        "record_state": "RECORDED_ONLY",
        "current_state": "DISABLED",
        "target": _clean(target),
        "candidate_name": _clean(candidate_name),
        "metric": {"name": _clean(metric_name), "value": metric_value, "unit": _clean(unit)},
        "baseline": {"value": baseline_value, "unit": _clean(unit)} if baseline_value is not None else None,
        "method": _clean(method),
        "source_ref": _clean(source_ref),
        "status": _clean(status),
        "evidence_refs": _clean_list(evidence_refs),
        "notes": _clean_list(notes),
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": {
            "capability_state": "performance_measurement_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "benchmark_execution": "DISABLED",
            "hardware_probe": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_performance_measurement_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_performance_measurement_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_performance_measurement_record(record), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if not allow_empty and not value:
        return [f"{field} must be a non-empty list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def _validate_metric(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["metric must be an object"]
    if not isinstance(value.get("name"), str) or not value["name"]:
        errors.append("metric.name must be a non-empty string")
    if not isinstance(value.get("value"), (int, float)):
        errors.append("metric.value must be numeric")
    if not isinstance(value.get("unit"), str) or not value["unit"]:
        errors.append("metric.unit must be a non-empty string")
    return errors


def validate_performance_measurement_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["performance measurement record must be a JSON object"]
    if record.get("kind") != PERFORMANCE_MEASUREMENT_KIND:
        errors.append(f"kind must be {PERFORMANCE_MEASUREMENT_KIND}")
    if record.get("schema_version") != PERFORMANCE_MEASUREMENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PERFORMANCE_MEASUREMENT_SCHEMA_VERSION}")
    if record.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if record.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED or NOT_AUTHORIZED")
    if record.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    for field in ("candidate_name", "method", "source_ref"):
        if not isinstance(record.get(field), str) or not record[field]:
            errors.append(f"{field} must be a non-empty string")
    errors.extend(_validate_metric(record.get("metric")))
    baseline = record.get("baseline")
    if baseline is not None:
        if not isinstance(baseline, dict):
            errors.append("baseline must be an object or null")
        elif (
            not isinstance(baseline.get("value"), (int, float))
            or not isinstance(baseline.get("unit"), str)
            or not baseline["unit"]
        ):
            errors.append("baseline must include numeric value and non-empty unit")
    if record.get("status") not in _STATUSES:
        errors.append("status must be candidate, accepted, or rejected")
    errors.extend(_string_list_errors(record.get("evidence_refs", []), field="evidence_refs", allow_empty=True))
    errors.extend(_string_list_errors(record.get("notes", []), field="notes", allow_empty=True))
    if record.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    for key in ("grants_runtime_authority", "grants_action_authority"):
        if record.get(key) is not False:
            errors.append(f"{key} must be false or NOT_AUTHORIZED")
    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "performance_measurement_record":
            errors.append("governance.capability_state must be performance_measurement_record")
        for key in (
            "runtime_execution",
            "model_execution",
            "benchmark_execution",
            "hardware_probe",
            "shell_execution",
            "source_writes",
            "memory_mutation",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_performance_measurement_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_performance_measurement_record(data)
