from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config_schema import CAPABILITY_DEFAULTS, CONFIG_SCHEMA_VERSION, attach_digest, digest_jsonable
from builder_ii.config_sources import (
    CONFIG_SOURCE_RESOLUTION_KIND,
    ConfigResolution,
    validate_config_resolution_artifact,
)

SETUP_PLAN_KIND = "builder_ii.setup_plan"
SETUP_PLAN_SCHEMA_VERSION = 1


def _field(resolution: ConfigResolution, name: str) -> str:
    return resolution.value(name)


def _planned_writes(resolution: ConfigResolution) -> list[dict[str, Any]]:
    target_repo = Path(_field(resolution, "target_repo"))
    skills_destination_policy = _field(resolution, "goose_skills_destination_policy")
    writes: list[dict[str, Any]] = [
        {
            "id": "goose_config_overlay",
            "path": _field(resolution, "goose_config_path"),
            "write_kind": "future_goose_config_overlay",
            "state": "planned_only",
            "requires_future_authority": True,
            "r1_1_performs_write": False,
        },
        {
            "id": "goose_recipe_reference",
            "path": _field(resolution, "goose_recipe_path"),
            "write_kind": "future_recipe_path_reference",
            "state": "planned_only",
            "requires_future_authority": True,
            "r1_1_performs_write": False,
        },
    ]
    if skills_destination_policy != "disabled":
        writes.append(
            {
                "id": "goose_skills_destination",
                "path": str((target_repo / ".agents" / "skills").resolve(strict=False)),
                "write_kind": "future_skill_copy_or_overlay",
                "source_path": _field(resolution, "goose_skills_source_path"),
                "destination_policy": skills_destination_policy,
                "state": "planned_only",
                "requires_future_authority": True,
                "r1_1_performs_write": False,
            }
        )
    writes.append(
        {
            "id": "target_goosehints",
            "path": str((target_repo / ".goosehints").resolve(strict=False)),
            "write_kind": "future_target_hint_file",
            "state": "planned_only",
            "requires_future_authority": True,
            "r1_1_performs_write": False,
        }
    )
    return writes


def create_setup_plan(resolution: ConfigResolution) -> dict[str, Any]:
    resolution_artifact = resolution.to_jsonable()
    target_repo = _field(resolution, "target_repo")
    artifact_root = _field(resolution, "platform_artifact_root")
    capability_map = {
        "runtime_execution": "disabled",
        "model_execution": "disabled",
        "shell_execution": "disabled",
        "source_writes": "disabled",
        "goose_runtime": "disabled",
        "deepagents_runtime": "disabled",
        "mcp_tool_invocation": "disabled",
        "patch_authority": "disabled",
        "autonomous_writes": "disabled",
        "setup_apply": "disabled",
        "setup_rollback": "disabled",
        "artifact_output": "passive_only",
    }
    plan = {
        "kind": SETUP_PLAN_KIND,
        "schema_version": SETUP_PLAN_SCHEMA_VERSION,
        "config_schema_version": CONFIG_SCHEMA_VERSION,
        "artifact_is_authority": False,
        "config_source_resolution_ref": {
            "kind": CONFIG_SOURCE_RESOLUTION_KIND,
            "digest": resolution_artifact["digest"],
        },
        "builder_repo_canonical_path": str(resolution.project_root),
        "target_repo_canonical_path": target_repo,
        "artifact_root_canonical_path": artifact_root,
        "selected_target_profile": _field(resolution, "active_target_profile"),
        "selected_agent_profile": _field(resolution, "active_agent_profile"),
        "selected_verification_profile": _field(resolution, "active_verification_profile"),
        "selected_model": {
            "backend": _field(resolution, "model_backend"),
            "alias": _field(resolution, "model_alias"),
            "tier": _field(resolution, "model_tier"),
            "execution_state": "disabled",
        },
        "goose_config_target_path": _field(resolution, "goose_config_path"),
        "goose_recipe_path": _field(resolution, "goose_recipe_path"),
        "skills_source_path": _field(resolution, "goose_skills_source_path"),
        "skills_destination_policy": _field(resolution, "goose_skills_destination_policy"),
        "deepagents_mode": _field(resolution, "deepagents_mode"),
        "capability_map": capability_map,
        "planned_writes_if_later_applied": _planned_writes(resolution),
        "no_mutation_proof": {
            "plan_generation_performs_writes": False,
            "target_repo_writes": False,
            "goose_config_writes": False,
            "skill_copy": False,
            "runtime_start": False,
            "model_calls": False,
            "shell_execution": False,
            "mcp_tool_invocation": False,
            "patch_application": False,
            "deepagents_construction": False,
            "only_explicit_output_artifact_may_be_written_by_cli": True,
        },
        "resolution_warnings": list(resolution.warnings),
        "resolution_errors": list(resolution.errors),
        "next_step_recommendation": (
            "Review this passive plan. A later R1 slice must introduce explicit apply and rollback "
            "receipts before any planned write can occur."
        ),
        "governance": {
            "artifact_is_authority": False,
            **CAPABILITY_DEFAULTS,
            "setup_apply": "disabled",
            "setup_rollback": "disabled",
        },
    }
    plan = attach_digest(plan, digest_key="plan_digest")
    return plan


def dumps_setup_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def write_setup_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_setup_plan(plan), encoding="utf-8")


def validate_setup_plan_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["setup plan artifact must be a JSON object"]
    if data.get("kind") != SETUP_PLAN_KIND:
        errors.append(f"kind must be {SETUP_PLAN_KIND}")
    if data.get("schema_version") != SETUP_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {SETUP_PLAN_SCHEMA_VERSION}")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")
    ref = data.get("config_source_resolution_ref")
    if not isinstance(ref, dict):
        errors.append("config_source_resolution_ref must be an object")
    else:
        if ref.get("kind") != CONFIG_SOURCE_RESOLUTION_KIND:
            errors.append(f"config_source_resolution_ref.kind must be {CONFIG_SOURCE_RESOLUTION_KIND}")
        digest = ref.get("digest")
        if not isinstance(digest, str) or len(digest) != 64:
            errors.append("config_source_resolution_ref.digest must be a SHA-256 hex string")
    for path_field in (
        "builder_repo_canonical_path",
        "target_repo_canonical_path",
        "artifact_root_canonical_path",
        "goose_config_target_path",
        "goose_recipe_path",
        "skills_source_path",
    ):
        value = data.get(path_field)
        if not isinstance(value, str) or not value:
            errors.append(f"{path_field} must be a non-empty string")
        elif not Path(value).is_absolute():
            errors.append(f"{path_field} must be absolute")
    selected_model = data.get("selected_model")
    if not isinstance(selected_model, dict):
        errors.append("selected_model must be an object")
    elif selected_model.get("execution_state") != "disabled":
        errors.append("selected_model.execution_state must be disabled")
    capability_map = data.get("capability_map")
    if not isinstance(capability_map, dict):
        errors.append("capability_map must be an object")
    else:
        for key in (
            "runtime_execution",
            "model_execution",
            "shell_execution",
            "source_writes",
            "goose_runtime",
            "deepagents_runtime",
            "mcp_tool_invocation",
            "patch_authority",
            "autonomous_writes",
            "setup_apply",
            "setup_rollback",
        ):
            if capability_map.get(key) != "disabled":
                errors.append(f"capability_map.{key} must be disabled")
    writes = data.get("planned_writes_if_later_applied")
    if not isinstance(writes, list):
        errors.append("planned_writes_if_later_applied must be a list")
    else:
        for idx, write in enumerate(writes):
            if not isinstance(write, dict):
                errors.append(f"planned_writes_if_later_applied[{idx}] must be an object")
                continue
            if write.get("r1_1_performs_write") is not False:
                errors.append(f"planned_writes_if_later_applied[{idx}].r1_1_performs_write must be false or NOT_AUTHORIZED")
            if write.get("state") != "planned_only":
                errors.append(f"planned_writes_if_later_applied[{idx}].state must be planned_only")
    proof = data.get("no_mutation_proof")
    if not isinstance(proof, dict):
        errors.append("no_mutation_proof must be an object")
    else:
        for key, value in proof.items():
            if key == "only_explicit_output_artifact_may_be_written_by_cli":
                if value is not True:
                    errors.append(f"no_mutation_proof.{key} must be true")
            elif value is not False:
                errors.append(f"no_mutation_proof.{key} must be false or NOT_AUTHORIZED")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    elif governance.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
    plan_digest = data.get("plan_digest")
    if not isinstance(plan_digest, str) or len(plan_digest) != 64:
        errors.append("plan_digest must be a SHA-256 hex string")
    elif plan_digest != digest_jsonable(data, digest_key="plan_digest"):
        errors.append("plan_digest does not match canonical plan payload")
    resolution_errors = data.get("resolution_errors")
    if isinstance(resolution_errors, list):
        errors.extend(str(error) for error in resolution_errors)
    return errors


def validate_setup_plan_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_setup_plan_artifact(data)


def validate_plan_resolution_pair(plan: dict[str, Any], resolution: dict[str, Any]) -> list[str]:
    errors = validate_setup_plan_artifact(plan)
    errors.extend(validate_config_resolution_artifact(resolution))
    ref = plan.get("config_source_resolution_ref")
    if isinstance(ref, dict) and ref.get("digest") != resolution.get("digest"):
        errors.append("plan config_source_resolution_ref.digest does not match resolution digest")
    return errors
