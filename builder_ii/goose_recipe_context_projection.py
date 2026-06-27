from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.session_config import SESSION_CONFIG_KIND, validate_session_configuration

GOOSE_RECIPE_CONTEXT_PROJECTION_KIND = "builder_ii.goose_recipe_context_projection"
GOOSE_RECIPE_CONTEXT_PROJECTION_SCHEMA_VERSION = 1


def _recipe_name(session_config: dict[str, Any]) -> str:
    authority_mode = session_config.get("authority_mode", "read_only")
    agent = session_config.get("selected_agent_profile", {}).get("name", "")
    if authority_mode == "planned_patch":
        return "core-implement.yaml"
    if agent in {"code_reviewer", "verification_planner"}:
        return "core-review.yaml"
    return "core-plan.yaml"


def create_goose_recipe_context_projection(session_config: dict[str, Any]) -> dict[str, Any]:
    config_errors = validate_session_configuration(session_config)
    if config_errors:
        raise ValueError("session configuration is invalid: " + "; ".join(config_errors))

    target = session_config["target_profile"]
    agent = session_config["selected_agent_profile"]
    prompt = session_config["selected_prompt_profile"]
    verification = session_config["selected_verification_profile"]
    context = session_config.get("context", {})
    recipe_name = _recipe_name(session_config)

    recipe_projection = {
        "name": recipe_name,
        "description": f"Governed Goose recipe projection for {agent['name']} on {target['name']}.",
        "instructions": [
            prompt["system_prompt"],
            "Preserve builder-II semantic boundaries: planned is not executed, executed is not verified, and artifacts are not authority.",
            "Use only the resolved target/profile/context surfaces in this projection.",
            "Return reviewable artifacts, summaries, or plans according to the selected agent output contract.",
            "Do not claim verification passed without operator-captured evidence.",
        ],
        "allowed_tools": list(agent.get("allowed_tools", [])),
        "forbidden_tools": list(agent.get("forbidden_tools", [])),
        "output_contract": agent["output_contract"],
        "verification_profile": verification["name"],
    }

    context_projection = {
        "target_name": target["name"],
        "repo_path": session_config["repo_path"],
        "context_pack_ref": context.get("context_pack_ref", ""),
        "context_defaults": list(context.get("context_defaults", [])),
        "task": session_config["task"],
        "required_evidence": list(session_config.get("required_evidence", [])),
    }

    return {
        "kind": GOOSE_RECIPE_CONTEXT_PROJECTION_KIND,
        "schema_version": GOOSE_RECIPE_CONTEXT_PROJECTION_SCHEMA_VERSION,
        "projection_state": "PLANNED_ONLY",
        "source_session_configuration_kind": SESSION_CONFIG_KIND,
        "target": target["name"],
        "agent_profile": agent["name"],
        "authority_mode": session_config["authority_mode"],
        "recipe_projection": recipe_projection,
        "context_projection": context_projection,
        "governance": {
            "capability_state": "goose_recipe_context_projection",
            "runtime_execution": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_goose_recipe_context_projection(projection: dict[str, Any]) -> str:
    return json_lib.dumps(projection, indent=2, sort_keys=True) + "\n"


def write_goose_recipe_context_projection(projection: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_goose_recipe_context_projection(projection), encoding="utf-8")


def _string_list_errors(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_goose_recipe_context_projection(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["goose recipe context projection must be a JSON object"]
    if data.get("kind") != GOOSE_RECIPE_CONTEXT_PROJECTION_KIND:
        errors.append(f"kind must be {GOOSE_RECIPE_CONTEXT_PROJECTION_KIND}")
    if data.get("schema_version") != GOOSE_RECIPE_CONTEXT_PROJECTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_RECIPE_CONTEXT_PROJECTION_SCHEMA_VERSION}")
    if data.get("projection_state") != "PLANNED_ONLY":
        errors.append("projection_state must be PLANNED_ONLY")
    if data.get("source_session_configuration_kind") != SESSION_CONFIG_KIND:
        errors.append(f"source_session_configuration_kind must be {SESSION_CONFIG_KIND}")
    for field in ("target", "agent_profile", "authority_mode"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")

    recipe = data.get("recipe_projection")
    if not isinstance(recipe, dict):
        errors.append("recipe_projection must be an object")
    else:
        for field in ("name", "description", "output_contract", "verification_profile"):
            if not isinstance(recipe.get(field), str) or not recipe[field]:
                errors.append(f"recipe_projection.{field} must be a non-empty string")
        errors.extend(_string_list_errors(recipe.get("instructions"), "recipe_projection.instructions"))
        errors.extend(_string_list_errors(recipe.get("allowed_tools"), "recipe_projection.allowed_tools"))
        errors.extend(_string_list_errors(recipe.get("forbidden_tools"), "recipe_projection.forbidden_tools"))
        if "execute_shell" not in recipe.get("forbidden_tools", []):
            errors.append("recipe_projection.forbidden_tools must include execute_shell")

    context = data.get("context_projection")
    if not isinstance(context, dict):
        errors.append("context_projection must be an object")
    else:
        for field in ("target_name", "repo_path", "context_pack_ref", "task"):
            if not isinstance(context.get(field), str):
                errors.append(f"context_projection.{field} must be a string")
        errors.extend(_string_list_errors(context.get("context_defaults"), "context_projection.context_defaults"))
        errors.extend(_string_list_errors(context.get("required_evidence"), "context_projection.required_evidence"))

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "goose_recipe_context_projection":
            errors.append("governance.capability_state must be goose_recipe_context_projection")
        for key in ("runtime_execution", "goose_runtime_start", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_goose_recipe_context_projection_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_goose_recipe_context_projection(data)
