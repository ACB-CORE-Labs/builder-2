from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.session_config import SESSION_CONFIG_KIND, validate_session_configuration

GOOSE_PROJECTION_KIND = "builder_ii.goose_projection"
GOOSE_PROJECTION_SCHEMA_VERSION = 1


def _provider_env(settings: Settings) -> dict[str, str]:
    if settings.backend == "ollama":
        return {"GOOSE_PROVIDER": "ollama", "OLLAMA_HOST": settings.base_url.rstrip("/")}
    host = settings.base_url.rstrip("/")
    if host.endswith("/v1"):
        host = host[: -len("/v1")]
    return {"GOOSE_PROVIDER": "openai", "OPENAI_HOST": host}


def _recipe_name(session_config: dict[str, Any]) -> str:
    authority_mode = session_config.get("authority_mode")
    agent_name = session_config.get("selected_agent_profile", {}).get("name", "")
    if authority_mode == "planned_patch":
        return "core-implement.yaml"
    if agent_name in {"code_reviewer", "verification_planner"}:
        return "core-review.yaml"
    return "core-plan.yaml"


def create_goose_projection(settings: Settings, session_config: dict[str, Any]) -> dict[str, Any]:
    config_errors = validate_session_configuration(session_config)
    if config_errors:
        raise ValueError("session configuration is invalid: " + "; ".join(config_errors))

    model_policy = session_config["model_policy"]
    authority_mode = session_config["authority_mode"]
    recipe = _recipe_name(session_config)
    env = _provider_env(settings)
    env.update(
        {
            "GOOSE_MODEL": model_policy["model_id"],
            "GOOSE_TEMPERATURE": "0.0",
            "GOOSE_MODE": "auto",
            "GOOSE_MAX_TURNS": "1000",
            "GOOSE_PLANNER_PROVIDER": env["GOOSE_PROVIDER"],
            "GOOSE_PLANNER_MODEL": model_policy["model_id"],
            "GOOSE_RECIPE_PATH": str(settings.project_root / "recipes"),
            "GOOSE_MOIM_MESSAGE_FILE": "derived_at_runtime_by_operator_launch",
            "BUILDER_MODEL_TIER": model_policy["model_tier"],
            "BUILDER_MODEL_ALIAS": model_policy["model_alias"],
            "BUILDER_SESSION_MODE": authority_mode,
        }
    )
    target = session_config["target_profile"]["name"]
    agent = session_config["selected_agent_profile"]["name"]
    return {
        "kind": GOOSE_PROJECTION_KIND,
        "schema_version": GOOSE_PROJECTION_SCHEMA_VERSION,
        "projection_state": "PLANNED_ONLY",
        "source_session_configuration_kind": SESSION_CONFIG_KIND,
        "task": session_config["task"],
        "target": target,
        "repo_path": session_config["repo_path"],
        "agent_profile": agent,
        "authority_mode": authority_mode,
        "goose_native_surface": {
            "env": env,
            "recipe_name": recipe,
            "recipe_path": str(settings.project_root / "recipes" / recipe),
            "working_directory": session_config["repo_path"],
            "session_name": f"{target}-{agent}-{authority_mode}",
            "resume": False,
            "context_pack_ref": session_config.get("context", {}).get("context_pack_ref", ""),
            "builtins": [],
            "extensions": [],
        },
        "required_evidence": list(session_config.get("required_evidence", [])),
        "governance": {
            "capability_state": "goose_projection",
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


def dumps_goose_projection(projection: dict[str, Any]) -> str:
    return json_lib.dumps(projection, indent=2, sort_keys=True) + "\n"


def write_goose_projection(projection: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_goose_projection(projection), encoding="utf-8")


def validate_goose_projection(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["goose projection must be a JSON object"]
    if data.get("kind") != GOOSE_PROJECTION_KIND:
        errors.append(f"kind must be {GOOSE_PROJECTION_KIND}")
    if data.get("schema_version") != GOOSE_PROJECTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_PROJECTION_SCHEMA_VERSION}")
    if data.get("projection_state") != "PLANNED_ONLY":
        errors.append("projection_state must be PLANNED_ONLY")
    for field in ("task", "target", "repo_path", "agent_profile", "authority_mode"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    surface = data.get("goose_native_surface")
    if not isinstance(surface, dict):
        errors.append("goose_native_surface must be an object")
    else:
        env = surface.get("env")
        if not isinstance(env, dict):
            errors.append("goose_native_surface.env must be an object")
        else:
            for key in ("GOOSE_PROVIDER", "GOOSE_MODEL", "GOOSE_TEMPERATURE", "GOOSE_PLANNER_PROVIDER", "GOOSE_PLANNER_MODEL", "GOOSE_RECIPE_PATH", "GOOSE_MOIM_MESSAGE_FILE", "BUILDER_MODEL_TIER", "BUILDER_MODEL_ALIAS", "BUILDER_SESSION_MODE"):
                if not isinstance(env.get(key), str) or not env[key]:
                    errors.append(f"goose_native_surface.env.{key} must be a non-empty string")
        for field in ("recipe_name", "recipe_path", "working_directory", "session_name", "context_pack_ref"):
            if not isinstance(surface.get(field), str):
                errors.append(f"goose_native_surface.{field} must be a string")
        if not isinstance(surface.get("resume"), bool):
            errors.append("goose_native_surface.resume must be a boolean")
        for field in ("builtins", "extensions"):
            if not isinstance(surface.get(field), list):
                errors.append(f"goose_native_surface.{field} must be a list")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "goose_projection":
            errors.append("governance.capability_state must be goose_projection")
        for key in ("runtime_execution", "goose_runtime_start", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_goose_projection_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_goose_projection(data)
