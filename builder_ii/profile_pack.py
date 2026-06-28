from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.profile_pack_dry_run import PROFILE_PACK_DRY_RUN_KIND, validate_profile_pack_dry_run
from builder_ii.profile_pack_manifest import PROFILE_PACK_MANIFEST_KIND, canonical_digest, validate_profile_pack_manifest
from builder_ii.profile_pack_render_plan import PROFILE_PACK_RENDER_PLAN_KIND, validate_profile_pack_render_plan
from builder_ii.profile_pack_validation_report import (
    PROFILE_PACK_VALIDATION_REPORT_KIND,
    validate_profile_pack_validation_report,
)

PROFILE_PACK_KIND = "builder_ii.profile_pack"
PROFILE_PACK_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _artifact_ref(data: dict[str, Any], *, path: Path | None) -> dict[str, Any]:
    return {
        "kind": str(data.get("kind", "")),
        "path": str(path) if path is not None else "",
        "sha256": canonical_digest(data),
    }


def create_profile_pack(
    *,
    manifest: dict[str, Any],
    render_plan: dict[str, Any],
    dry_run: dict[str, Any],
    validation_report: dict[str, Any],
    manifest_path: Path | None = None,
    render_plan_path: Path | None = None,
    dry_run_path: Path | None = None,
    validation_report_path: Path | None = None,
) -> dict[str, Any]:
    manifest_errors = validate_profile_pack_manifest(manifest)
    render_errors = validate_profile_pack_render_plan(render_plan)
    dry_run_errors = validate_profile_pack_dry_run(dry_run)
    report_errors = validate_profile_pack_validation_report(validation_report)
    if manifest_errors or render_errors or dry_run_errors or report_errors:
        raise ValueError(
            "profile pack lifecycle artifacts are invalid: "
            + "; ".join(manifest_errors + render_errors + dry_run_errors + report_errors)
        )

    return {
        "kind": PROFILE_PACK_KIND,
        "schema_version": PROFILE_PACK_SCHEMA_VERSION,
        "pack_state": "PACKED_ONLY",
        "pack_id": manifest["pack_id"],
        "target_profile": manifest["target_profile"],
        "task": manifest["task"],
        "manifest_ref": _artifact_ref(manifest, path=manifest_path),
        "render_plan_ref": _artifact_ref(render_plan, path=render_plan_path),
        "dry_run_ref": _artifact_ref(dry_run, path=dry_run_path),
        "validation_report_ref": _artifact_ref(validation_report, path=validation_report_path),
        "lifecycle": {
            "planned": True,
            "rendered": True,
            "dry_run": True,
            "validated": True,
            "executed": False,
            "authorized": False,
            "promoted": False,
        },
        "governance": {
            "capability_state": "profile_pack",
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


def dumps_profile_pack(pack: dict[str, Any]) -> str:
    return json_lib.dumps(pack, indent=2, sort_keys=True) + "\n"


def write_profile_pack(pack: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_profile_pack(pack), encoding="utf-8")


def _validate_ref(value: Any, *, field: str, expected_kind: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if value.get("kind") != expected_kind:
        errors.append(f"{field}.kind must be {expected_kind}")
    if not isinstance(value.get("path", ""), str):
        errors.append(f"{field}.path must be a string")
    if not isinstance(value.get("sha256"), str) or not _SHA256_RE.match(value["sha256"]):
        errors.append(f"{field}.sha256 must be a SHA-256 hex digest")
    return errors


def _validate_governance(governance: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    if governance.get("capability_state") != "profile_pack":
        errors.append("governance.capability_state must be profile_pack")
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


def validate_profile_pack(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["profile pack must be a JSON object"]
    if data.get("kind") != PROFILE_PACK_KIND:
        errors.append(f"kind must be {PROFILE_PACK_KIND}")
    if data.get("schema_version") != PROFILE_PACK_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROFILE_PACK_SCHEMA_VERSION}")
    if data.get("pack_state") != "PACKED_ONLY":
        errors.append("pack_state must be PACKED_ONLY")
    for field in ("pack_id", "target_profile", "task"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")

    errors.extend(_validate_ref(data.get("manifest_ref"), field="manifest_ref", expected_kind=PROFILE_PACK_MANIFEST_KIND))
    errors.extend(_validate_ref(data.get("render_plan_ref"), field="render_plan_ref", expected_kind=PROFILE_PACK_RENDER_PLAN_KIND))
    errors.extend(_validate_ref(data.get("dry_run_ref"), field="dry_run_ref", expected_kind=PROFILE_PACK_DRY_RUN_KIND))
    errors.extend(
        _validate_ref(
            data.get("validation_report_ref"),
            field="validation_report_ref",
            expected_kind=PROFILE_PACK_VALIDATION_REPORT_KIND,
        )
    )

    lifecycle = data.get("lifecycle")
    if not isinstance(lifecycle, dict):
        errors.append("lifecycle must be an object")
    else:
        expected = {
            "planned": True,
            "rendered": True,
            "dry_run": True,
            "validated": True,
            "executed": False,
            "authorized": False,
            "promoted": False,
        }
        for key, value in expected.items():
            if lifecycle.get(key) is not value:
                errors.append(f"lifecycle.{key} must be {str(value).lower()}")

    errors.extend(_validate_governance(data.get("governance")))
    return errors


def validate_profile_pack_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_profile_pack(data)
