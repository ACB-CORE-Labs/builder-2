from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.profile_pack_manifest import (
    PROFILE_PACK_MANIFEST_KIND,
    canonical_digest,
    validate_profile_pack_manifest,
)

PROFILE_PACK_RENDER_PLAN_KIND = "builder_ii.profile_pack_render_plan"
PROFILE_PACK_RENDER_PLAN_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _artifact_ref(data: dict[str, Any], *, path: Path | None) -> dict[str, Any]:
    return {
        "kind": str(data.get("kind", "")),
        "path": str(path) if path is not None else "",
        "sha256": canonical_digest(data),
    }


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-") or "profile"


def _default_governance() -> dict[str, Any]:
    return {
        "capability_state": "profile_pack_render_plan",
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
    }


def _manifest_entries(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for area in manifest.get("areas", []):
        if isinstance(area, dict):
            for entry in area.get("entries", []):
                if isinstance(entry, dict):
                    entries.append(entry)
    return entries


def create_profile_pack_render_plan(
    manifest: dict[str, Any],
    *,
    manifest_path: Path | None = None,
    output_root: str = "profile-pack-rendered",
) -> dict[str, Any]:
    manifest_errors = validate_profile_pack_manifest(manifest)
    if manifest_errors:
        raise ValueError("profile pack manifest is invalid: " + "; ".join(manifest_errors))

    planned_outputs: list[dict[str, Any]] = []
    for entry in _manifest_entries(manifest):
        area = entry["area"]
        entry_id = entry["id"]
        planned_outputs.append(
            {
                "entry_id": entry_id,
                "area": area,
                "profile_kind": entry["profile_kind"],
                "authority_classification": entry["authority_classification"],
                "source_content_hash": entry["content_hash"],
                "output_path": f"{output_root}/{area}/{_slug(entry_id)}.json",
                "output_state": "RENDERED_ONLY",
                "writes_source": False,
                "executes_now": False,
            }
        )

    return {
        "kind": PROFILE_PACK_RENDER_PLAN_KIND,
        "schema_version": PROFILE_PACK_RENDER_PLAN_SCHEMA_VERSION,
        "render_state": "RENDERED_ONLY",
        "pack_id": manifest["pack_id"],
        "target_profile": manifest["target_profile"],
        "task": manifest["task"],
        "source_manifest_ref": _artifact_ref(manifest, path=manifest_path),
        "planned_outputs": planned_outputs,
        "render_boundary": {
            "renders_profiles": True,
            "writes_only_explicit_artifact_output": True,
            "executes_commands": False,
            "starts_goose": False,
            "constructs_deepagents": False,
            "calls_models": False,
            "calls_mcp_tools": False,
            "claims_authority": False,
        },
        "governance": _default_governance(),
    }


def dumps_profile_pack_render_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def write_profile_pack_render_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_profile_pack_render_plan(plan), encoding="utf-8")


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
    if governance.get("capability_state") != "profile_pack_render_plan":
        errors.append("governance.capability_state must be profile_pack_render_plan")
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
            errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "executed", "authorized", "promoted"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false or NOT_AUTHORIZED")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_profile_pack_render_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["profile pack render plan must be a JSON object"]
    if data.get("kind") != PROFILE_PACK_RENDER_PLAN_KIND:
        errors.append(f"kind must be {PROFILE_PACK_RENDER_PLAN_KIND}")
    if data.get("schema_version") != PROFILE_PACK_RENDER_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROFILE_PACK_RENDER_PLAN_SCHEMA_VERSION}")
    if data.get("render_state") != "RENDERED_ONLY":
        errors.append("render_state must be RENDERED_ONLY")
    for field in ("pack_id", "target_profile", "task"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    errors.extend(
        _validate_ref(
            data.get("source_manifest_ref"), field="source_manifest_ref", expected_kind=PROFILE_PACK_MANIFEST_KIND
        )
    )

    outputs = data.get("planned_outputs")
    seen_ids: set[str] = set()
    if not isinstance(outputs, list) or not outputs:
        errors.append("planned_outputs must be a non-empty list")
    else:
        for index, output in enumerate(outputs):
            field = f"planned_outputs[{index}]"
            if not isinstance(output, dict):
                errors.append(f"{field} must be an object")
                continue
            entry_id = output.get("entry_id")
            if not isinstance(entry_id, str) or not entry_id:
                errors.append(f"{field}.entry_id must be a non-empty string")
            elif entry_id in seen_ids:
                errors.append(f"duplicate planned output entry_id: {entry_id}")
            else:
                seen_ids.add(entry_id)
            for name in ("area", "profile_kind", "authority_classification", "output_path"):
                if not isinstance(output.get(name), str) or not output[name]:
                    errors.append(f"{field}.{name} must be a non-empty string")
            if not isinstance(output.get("source_content_hash"), str) or not _SHA256_RE.match(
                output["source_content_hash"]
            ):
                errors.append(f"{field}.source_content_hash must be a SHA-256 hex digest")
            if output.get("output_state") != "RENDERED_ONLY":
                errors.append(f"{field}.output_state must be RENDERED_ONLY")
            if output.get("writes_source") is not False:
                errors.append(f"{field}.writes_source must be false or NOT_AUTHORIZED")
            if output.get("executes_now") is not False:
                errors.append(f"{field}.executes_now must be false or NOT_AUTHORIZED")

    boundary = data.get("render_boundary")
    if not isinstance(boundary, dict):
        errors.append("render_boundary must be an object")
    else:
        if boundary.get("renders_profiles") is not True:
            errors.append("render_boundary.renders_profiles must be true")
        if boundary.get("writes_only_explicit_artifact_output") is not True:
            errors.append("render_boundary.writes_only_explicit_artifact_output must be true")
        for key in (
            "executes_commands",
            "starts_goose",
            "constructs_deepagents",
            "calls_models",
            "calls_mcp_tools",
            "claims_authority",
        ):
            if boundary.get(key) is not False:
                errors.append(f"render_boundary.{key} must be false or NOT_AUTHORIZED")
    errors.extend(_validate_governance(data.get("governance")))
    return errors


def validate_profile_pack_render_plan_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_profile_pack_render_plan(data)
