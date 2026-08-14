from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.lifecycle.setup.profile_pack_manifest import (
    PROFILE_PACK_MANIFEST_KIND,
    canonical_digest,
    validate_profile_pack_manifest,
)
from builder_ii.lifecycle.setup.profile_pack_render_plan import (
    PROFILE_PACK_RENDER_PLAN_KIND,
    create_profile_pack_render_plan,
    validate_profile_pack_render_plan,
)

PROFILE_PACK_DRY_RUN_KIND = "builder_ii.profile_pack_dry_run"
PROFILE_PACK_DRY_RUN_SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _artifact_ref(data: dict[str, Any], *, path: Path | None) -> dict[str, Any]:
    return {
        "kind": str(data.get("kind", "")),
        "path": str(path) if path is not None else "",
        "sha256": canonical_digest(data),
    }


def _default_governance() -> dict[str, Any]:
    return {
        "capability_state": "profile_pack_dry_run",
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


def _render_plan_manifest_binding_errors(manifest: dict[str, Any], render_plan: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("pack_id", "target_profile", "task"):
        if render_plan.get(field) != manifest.get(field):
            errors.append(f"render_plan.{field} must match manifest.{field}")
    source_manifest_ref = render_plan.get("source_manifest_ref")
    expected_digest = canonical_digest(manifest)
    if not isinstance(source_manifest_ref, dict):
        errors.append("render_plan.source_manifest_ref must be an object")
    elif source_manifest_ref.get("sha256") != expected_digest:
        errors.append("render_plan.source_manifest_ref.sha256 must match manifest digest")
    return errors


def create_profile_pack_dry_run(
    manifest: dict[str, Any],
    render_plan: dict[str, Any] | None = None,
    *,
    manifest_path: Path | None = None,
    render_plan_path: Path | None = None,
) -> dict[str, Any]:
    manifest_errors = validate_profile_pack_manifest(manifest)
    if manifest_errors:
        raise ValueError("profile pack manifest is invalid: " + "; ".join(manifest_errors))
    plan = render_plan or create_profile_pack_render_plan(manifest, manifest_path=manifest_path)
    plan_errors = validate_profile_pack_render_plan(plan)
    if plan_errors:
        raise ValueError("profile pack render plan is invalid: " + "; ".join(plan_errors))
    binding_errors = _render_plan_manifest_binding_errors(manifest, plan)
    if binding_errors:
        raise ValueError("profile pack render plan does not match manifest: " + "; ".join(binding_errors))

    checks: list[dict[str, Any]] = []
    for output in plan["planned_outputs"]:
        checks.append(
            {
                "entry_id": output["entry_id"],
                "area": output["area"],
                "profile_kind": output["profile_kind"],
                "planned_output_path": output["output_path"],
                "dry_run_status": "WOULD_RENDER_PASSIVE_ARTIFACT",
                "executes_now": False,
                "starts_goose": False,
                "constructs_deepagents": False,
                "constructs_agents": False,
                "calls_models": False,
                "calls_mcp_tools": False,
                "runs_verification": False,
                "claims_verification_evidence": False,
                "grants_authority": False,
            }
        )

    return {
        "kind": PROFILE_PACK_DRY_RUN_KIND,
        "schema_version": PROFILE_PACK_DRY_RUN_SCHEMA_VERSION,
        "dry_run_state": "DRY_RUN_ONLY",
        "pack_id": manifest["pack_id"],
        "target_profile": manifest["target_profile"],
        "task": manifest["task"],
        "source_manifest_ref": _artifact_ref(manifest, path=manifest_path),
        "source_render_plan_ref": _artifact_ref(plan, path=render_plan_path),
        "checks": checks,
        "summary": {
            "planned_count": len(checks),
            "rendered_count": 0,
            "executed_count": 0,
            "authorized_count": 0,
            "promoted_count": 0,
            "verification_status": "NOT_RUN",
        },
        "governance": _default_governance(),
    }


def dumps_profile_pack_dry_run(dry_run: dict[str, Any]) -> str:
    return json_lib.dumps(dry_run, indent=2, sort_keys=True) + "\n"


def write_profile_pack_dry_run(dry_run: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_profile_pack_dry_run(dry_run), encoding="utf-8")


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
    if governance.get("capability_state") != "profile_pack_dry_run":
        errors.append("governance.capability_state must be profile_pack_dry_run")
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


def validate_profile_pack_dry_run(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["profile pack dry run must be a JSON object"]
    if data.get("kind") != PROFILE_PACK_DRY_RUN_KIND:
        errors.append(f"kind must be {PROFILE_PACK_DRY_RUN_KIND}")
    if data.get("schema_version") != PROFILE_PACK_DRY_RUN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PROFILE_PACK_DRY_RUN_SCHEMA_VERSION}")
    if data.get("dry_run_state") != "DRY_RUN_ONLY":
        errors.append("dry_run_state must be DRY_RUN_ONLY")
    for field in ("pack_id", "target_profile", "task"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    errors.extend(
        _validate_ref(
            data.get("source_manifest_ref"), field="source_manifest_ref", expected_kind=PROFILE_PACK_MANIFEST_KIND
        )
    )
    errors.extend(
        _validate_ref(
            data.get("source_render_plan_ref"),
            field="source_render_plan_ref",
            expected_kind=PROFILE_PACK_RENDER_PLAN_KIND,
        )
    )

    checks = data.get("checks")
    seen: set[str] = set()
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty list")
    else:
        for index, check in enumerate(checks):
            field = f"checks[{index}]"
            if not isinstance(check, dict):
                errors.append(f"{field} must be an object")
                continue
            entry_id = check.get("entry_id")
            if not isinstance(entry_id, str) or not entry_id:
                errors.append(f"{field}.entry_id must be a non-empty string")
            elif entry_id in seen:
                errors.append(f"duplicate dry-run entry_id: {entry_id}")
            else:
                seen.add(entry_id)
            for name in ("area", "profile_kind", "planned_output_path"):
                if not isinstance(check.get(name), str) or not check[name]:
                    errors.append(f"{field}.{name} must be a non-empty string")
            if check.get("dry_run_status") != "WOULD_RENDER_PASSIVE_ARTIFACT":
                errors.append(f"{field}.dry_run_status must be WOULD_RENDER_PASSIVE_ARTIFACT")
            for name in (
                "executes_now",
                "starts_goose",
                "constructs_deepagents",
                "constructs_agents",
                "calls_models",
                "calls_mcp_tools",
                "runs_verification",
                "claims_verification_evidence",
                "grants_authority",
            ):
                if check.get(name) is not False:
                    errors.append(f"{field}.{name} must be false or NOT_AUTHORIZED")

    summary = data.get("summary")
    if not isinstance(summary, dict):
        errors.append("summary must be an object")
    else:
        for name in ("planned_count", "rendered_count", "executed_count", "authorized_count", "promoted_count"):
            if not isinstance(summary.get(name), int) or summary[name] < 0:
                errors.append(f"summary.{name} must be a non-negative integer")
        for name in ("rendered_count", "executed_count", "authorized_count", "promoted_count"):
            if summary.get(name) != 0:
                errors.append(f"summary.{name} must be 0")
        if summary.get("verification_status") != "NOT_RUN":
            errors.append("summary.verification_status must be NOT_RUN")
    errors.extend(_validate_governance(data.get("governance")))
    return errors


def validate_profile_pack_dry_run_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_profile_pack_dry_run(data)
