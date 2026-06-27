from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.target_profiles import target_names

READONLY_INSPECTION_REPORT_KIND = "builder_ii.readonly_inspection_report"
READONLY_INSPECTION_REPORT_SCHEMA_VERSION = 1
_ALLOWED_PURPOSES = {"orientation", "review", "verification_planning"}


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _digest_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _inspect_file(path: Path, *, root: Path | None) -> dict[str, Any]:
    resolved = path.resolve()
    entry: dict[str, Any] = {
        "input_path": str(path),
        "resolved_path": str(resolved),
        "relative_path": "",
        "exists": resolved.exists(),
        "is_file": resolved.is_file() if resolved.exists() else False,
        "bytes": 0,
        "sha256": "",
        "status": "missing",
        "errors": [],
    }
    if root is not None:
        try:
            entry["relative_path"] = resolved.relative_to(root.resolve()).as_posix()
        except ValueError:
            entry["errors"].append("path is outside declared root")
            entry["status"] = "rejected"
            return entry
    if not resolved.exists():
        entry["errors"].append("file not found")
        return entry
    if not resolved.is_file():
        entry["errors"].append("path is not a file")
        entry["status"] = "rejected"
        return entry
    entry["bytes"] = resolved.stat().st_size
    entry["sha256"] = _digest_file(resolved)
    entry["status"] = "recorded"
    return entry


def create_readonly_inspection_report(
    *,
    target: str,
    purpose: str,
    paths: list[Path] | tuple[Path, ...],
    root: Path | None = None,
    operator_note: str = "",
) -> dict[str, Any]:
    entries = [_inspect_file(path, root=root) for path in paths]
    recorded = sum(1 for entry in entries if entry["status"] == "recorded")
    rejected = sum(1 for entry in entries if entry["status"] == "rejected")
    missing = sum(1 for entry in entries if entry["status"] == "missing")
    return {
        "kind": READONLY_INSPECTION_REPORT_KIND,
        "schema_version": READONLY_INSPECTION_REPORT_SCHEMA_VERSION,
        "capability_state": "readonly_inspection_report",
        "record_state": "RECORDED_ONLY",
        "current_state": "RUNTIME_CANDIDATE",
        "target": _clean(target),
        "purpose": _clean(purpose),
        "operator_note": _clean(operator_note),
        "declared_root": str(root.resolve()) if root is not None else "",
        "scope": {
            "mode": "EXPLICIT_PATHS_ONLY",
            "recursive_discovery": False,
            "glob_expansion": False,
            "content_capture": False,
        },
        "counts": {
            "inputs": len(paths),
            "recorded": recorded,
            "rejected": rejected,
            "missing": missing,
        },
        "files": entries,
        "performed_actions": ["read_explicit_file_metadata", "hash_explicit_files"],
        "governance": {
            "capability_state": "readonly_inspection_report",
            "runtime_execution": "EXPLICIT_READ_ONLY",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "network_access": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_readonly_inspection_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"


def write_readonly_inspection_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_readonly_inspection_report(report), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if not allow_empty and not value:
        return [f"{field} must be a non-empty list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def _validate_file_entry(entry: Any, index: int) -> list[str]:
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"files[{index}] must be an object"]
    for field in ("input_path", "resolved_path", "status"):
        if not isinstance(entry.get(field), str) or not entry[field]:
            errors.append(f"files[{index}].{field} must be a non-empty string")
    if entry.get("status") not in {"recorded", "rejected", "missing"}:
        errors.append(f"files[{index}].status must be recorded, rejected, or missing")
    for field in ("exists", "is_file"):
        if not isinstance(entry.get(field), bool):
            errors.append(f"files[{index}].{field} must be boolean")
    if not isinstance(entry.get("bytes"), int) or entry.get("bytes", -1) < 0:
        errors.append(f"files[{index}].bytes must be a non-negative integer")
    if entry.get("status") == "recorded" and not isinstance(entry.get("sha256"), str):
        errors.append(f"files[{index}].sha256 must be a string")
    if not isinstance(entry.get("errors"), list):
        errors.append(f"files[{index}].errors must be a list")
    return errors


def validate_readonly_inspection_report(report: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["readonly inspection report must be a JSON object"]
    if report.get("kind") != READONLY_INSPECTION_REPORT_KIND:
        errors.append(f"kind must be {READONLY_INSPECTION_REPORT_KIND}")
    if report.get("schema_version") != READONLY_INSPECTION_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {READONLY_INSPECTION_REPORT_SCHEMA_VERSION}")
    if report.get("record_state") != "RECORDED_ONLY":
        errors.append("record_state must be RECORDED_ONLY")
    if report.get("current_state") != "RUNTIME_CANDIDATE":
        errors.append("current_state must be RUNTIME_CANDIDATE")
    if report.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    if report.get("purpose") not in _ALLOWED_PURPOSES:
        errors.append("purpose must be orientation, review, or verification_planning")
    scope = report.get("scope")
    if not isinstance(scope, dict):
        errors.append("scope must be an object")
    else:
        if scope.get("mode") != "EXPLICIT_PATHS_ONLY":
            errors.append("scope.mode must be EXPLICIT_PATHS_ONLY")
        for field in ("recursive_discovery", "glob_expansion", "content_capture"):
            if scope.get(field) is not False:
                errors.append(f"scope.{field} must be false")
    counts = report.get("counts")
    files = report.get("files")
    if not isinstance(counts, dict):
        errors.append("counts must be an object")
    if not isinstance(files, list) or not files:
        errors.append("files must be a non-empty list")
    elif isinstance(counts, dict):
        if counts.get("inputs") != len(files):
            errors.append("counts.inputs must equal len(files)")
        expected = {
            "recorded": sum(1 for entry in files if isinstance(entry, dict) and entry.get("status") == "recorded"),
            "rejected": sum(1 for entry in files if isinstance(entry, dict) and entry.get("status") == "rejected"),
            "missing": sum(1 for entry in files if isinstance(entry, dict) and entry.get("status") == "missing"),
        }
        for key, value in expected.items():
            if counts.get(key) != value:
                errors.append(f"counts.{key} must equal {value}")
        for index, entry in enumerate(files):
            errors.extend(_validate_file_entry(entry, index))
    if report.get("performed_actions") != ["read_explicit_file_metadata", "hash_explicit_files"]:
        errors.append("performed_actions must record only explicit metadata/hash reads")
    governance = report.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        expected_disabled = ("model_execution", "shell_execution", "network_access", "source_writes", "memory_mutation")
        if governance.get("runtime_execution") != "EXPLICIT_READ_ONLY":
            errors.append("governance.runtime_execution must be EXPLICIT_READ_ONLY")
        for key in expected_disabled:
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_readonly_inspection_report_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_readonly_inspection_report(data)
