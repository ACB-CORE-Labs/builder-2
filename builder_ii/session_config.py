from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.agent_profiles import validate_agent_profile_record
from builder_ii.config import Settings, MODEL_ALIASES, normalize_model_alias
from builder_ii.profile_resolution import AgentProfileName, ProfileResolver, TargetName, VerificationProfileName
from builder_ii.target_profiles import validate_target_profile_artifact
from builder_ii.verification_profiles import validate_profile_artifact

SESSION_CONFIG_KIND = "builder_ii.session_configuration"
SESSION_CONFIG_SCHEMA_VERSION = 1
AuthorityMode = Literal["read_only", "planned_patch"]

_ALLOWED_AUTHORITY_MODES = {"read_only", "planned_patch"}
_ALLOWED_PROVIDER_BACKENDS = {"rapid-mlx", "mlx-lm", "ollama"}
_OPT_IN_MODEL_ALIASES = {"codegeex", "qwen-coder-14b", "qwen3-coder-heavy", "deepseek"}


def _model_id_for_alias(settings: Settings, alias: str) -> str:
    return {
        "phi-reasoning": settings.mlx_model_phi,
        "qwen-coder": settings.mlx_model_qwen,
        "gemma-fast": settings.mlx_model_fast,
        "gemma-primary": settings.mlx_model_primary,
        "llama": settings.mlx_model_llama,
        "codegeex": settings.mlx_model_codegeex,
        "qwen-coder-14b": settings.mlx_model_qwen14,
        "qwen3-coder-heavy": settings.mlx_model_qwen3_coder,
        "deepseek": settings.mlx_model_deepseek,
    }[alias]


def _model_policy(settings: Settings, model_alias: str | None) -> dict[str, Any]:
    selected_alias = normalize_model_alias(model_alias or settings.model_alias, tier_fallback=settings.model_tier)
    return {
        "provider_backend": settings.backend,
        "model_alias": selected_alias,
        "model_id": _model_id_for_alias(settings, selected_alias),
        "model_tier": settings.model_tier,
        "role": "local_agent_model_lane",
        "requires_opt_in": selected_alias in _OPT_IN_MODEL_ALIASES,
        "recommended_context": "see docs/model_role_matrix.md",
        "governance": {
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "artifact_is_authority": False,
        },
    }


def create_session_configuration(
    settings: Settings,
    target_name: TargetName,
    *,
    agent_profile_name: AgentProfileName | None = None,
    prompt_profile_name: str | None = None,
    verification_profile_name: VerificationProfileName | None = None,
    repo_path: str | None = None,
    task: str = "",
    authority_mode: AuthorityMode = "read_only",
    model_alias: str | None = None,
    context_pack: str | None = None,
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    resolver = ProfileResolver(settings, generic_repo=generic_repo)
    resolved = resolver.resolve(
        target_name=target_name,
        agent_profile_name=agent_profile_name,
        prompt_profile_name=prompt_profile_name,
        verification_profile_name=verification_profile_name,
        repo_path=repo_path,
    )
    resolved_dict = resolved.to_dict()
    task_value = task or "governed local engineering session"
    return {
        "kind": SESSION_CONFIG_KIND,
        "schema_version": SESSION_CONFIG_SCHEMA_VERSION,
        "task": task_value,
        "target_profile": resolved_dict["target_profile"],
        "repo_path": resolved.repo_path,
        "selected_agent_profile": resolved_dict["selected_agent_profile"],
        "selected_prompt_profile": resolved_dict["selected_prompt_profile"],
        "selected_verification_profile": resolved_dict["selected_verification_profile"],
        "authority_mode": authority_mode,
        "context": {"context_pack_ref": context_pack or "", "context_defaults": list(resolved.context_defaults)},
        "model_policy": _model_policy(settings, model_alias),
        "goose_projection_policy": {
            "projection_state": "PLANNED_ONLY",
            "authority_mode": authority_mode,
            "goose_native_surface": {
                "env": {
                    "GOOSE_PROVIDER": "derived_from_provider_backend",
                    "GOOSE_MODEL": "derived_from_model_alias",
                    "GOOSE_TEMPERATURE": "0",
                    "BUILDER_SESSION_MODE": authority_mode,
                },
                "recipe": "derived_from_agent_profile_and_authority_mode",
                "context": "derived_from_context_pack_or_target_defaults",
                "session_name": "derived_from_target_agent_and_task",
            },
            "governance": {
                "runtime_execution": "DISABLED",
                "goose_runtime_start": "DISABLED",
                "model_execution": "DISABLED",
                "artifact_is_authority": False,
            },
        },
        "required_evidence": [
            "operator review of resolved target/profile/model/authority settings",
            "planned verification report before any completion claim",
            "human-captured verification output before promotion",
        ],
        "governance": {
            "capability_state": "session_configuration",
            "runtime_execution": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "model_execution": "DISABLED",
            "agent_construction": "DISABLED",
            "subagent_construction": "DISABLED",
            "shell_execution": "DISABLED",
            "command_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "commit_push": "DISABLED",
            "file_writes": "DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_session_configuration(config: dict[str, Any]) -> str:
    return json_lib.dumps(config, indent=2, sort_keys=True) + "\n"


def write_session_configuration(config: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_session_configuration(config), encoding="utf-8")


def _string_list_errors(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def _governance_disabled_errors(governance: Any, prefix: str, keys: tuple[str, ...]) -> list[str]:
    errors: list[str] = []
    if not isinstance(governance, dict):
        return [f"{prefix}governance must be an object"]
    for key in keys:
        if governance.get(key) != "DISABLED":
            errors.append(f"{prefix}governance.{key} must be DISABLED")
    if governance.get("artifact_is_authority") is not False:
        errors.append(f"{prefix}governance.artifact_is_authority must be false")
    return errors


def _validate_prompt_profile(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["selected_prompt_profile must be a dictionary"]
    for field in ("name", "description", "system_prompt"):
        if not isinstance(value.get(field), str) or not value[field]:
            errors.append(f"selected_prompt_profile.{field} must be a non-empty string")
    compatible = value.get("compatible_targets")
    if not isinstance(compatible, list) or any(not isinstance(item, str) for item in compatible):
        errors.append("selected_prompt_profile.compatible_targets must be a list of strings")
    return errors


def validate_session_configuration(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["session configuration must be a JSON object"]
    if data.get("kind") != SESSION_CONFIG_KIND:
        errors.append(f"kind must be {SESSION_CONFIG_KIND}")
    if data.get("schema_version") != SESSION_CONFIG_SCHEMA_VERSION:
        errors.append(f"schema_version must be {SESSION_CONFIG_SCHEMA_VERSION}")
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task must be a non-empty string")
    if data.get("authority_mode") not in _ALLOWED_AUTHORITY_MODES:
        errors.append("authority_mode must be read_only or planned_patch")
    if not isinstance(data.get("repo_path"), str) or not data["repo_path"]:
        errors.append("repo_path must be a non-empty string")

    target_profile = data.get("target_profile")
    if not isinstance(target_profile, dict):
        errors.append("target_profile must be a dictionary")
    else:
        errors.extend(validate_target_profile_artifact(target_profile))
    agent_profile = data.get("selected_agent_profile")
    if not isinstance(agent_profile, dict):
        errors.append("selected_agent_profile must be a dictionary")
    else:
        errors.extend(validate_agent_profile_record(agent_profile))
    errors.extend(_validate_prompt_profile(data.get("selected_prompt_profile")))
    verification_profile = data.get("selected_verification_profile")
    if not isinstance(verification_profile, dict):
        errors.append("selected_verification_profile must be a dictionary")
    else:
        errors.extend(validate_profile_artifact(verification_profile))

    context = data.get("context")
    if not isinstance(context, dict):
        errors.append("context must be an object")
    else:
        if not isinstance(context.get("context_pack_ref"), str):
            errors.append("context.context_pack_ref must be a string")
        errors.extend(_string_list_errors(context.get("context_defaults"), "context.context_defaults"))

    model_policy = data.get("model_policy")
    if not isinstance(model_policy, dict):
        errors.append("model_policy must be an object")
    else:
        if model_policy.get("provider_backend") not in _ALLOWED_PROVIDER_BACKENDS:
            errors.append("model_policy.provider_backend must be one of: mlx-lm, ollama, rapid-mlx")
        if model_policy.get("model_alias") not in MODEL_ALIASES:
            errors.append("model_policy.model_alias must be a known model alias")
        for field in ("model_id", "model_tier", "role", "recommended_context"):
            if not isinstance(model_policy.get(field), str) or not model_policy[field]:
                errors.append(f"model_policy.{field} must be a non-empty string")
        if not isinstance(model_policy.get("requires_opt_in"), bool):
            errors.append("model_policy.requires_opt_in must be a boolean")
        errors.extend(_governance_disabled_errors(model_policy.get("governance"), "model_policy.", ("runtime_execution", "model_execution")))

    projection = data.get("goose_projection_policy")
    if not isinstance(projection, dict):
        errors.append("goose_projection_policy must be an object")
    else:
        if projection.get("projection_state") != "PLANNED_ONLY":
            errors.append("goose_projection_policy.projection_state must be PLANNED_ONLY")
        if projection.get("authority_mode") not in _ALLOWED_AUTHORITY_MODES:
            errors.append("goose_projection_policy.authority_mode must be read_only or planned_patch")
        surface = projection.get("goose_native_surface")
        if not isinstance(surface, dict):
            errors.append("goose_projection_policy.goose_native_surface must be an object")
        else:
            env = surface.get("env")
            if not isinstance(env, dict):
                errors.append("goose_projection_policy.goose_native_surface.env must be an object")
            else:
                for key in ("GOOSE_PROVIDER", "GOOSE_MODEL", "GOOSE_TEMPERATURE", "BUILDER_SESSION_MODE"):
                    if not isinstance(env.get(key), str) or not env[key]:
                        errors.append(f"goose_projection_policy.goose_native_surface.env.{key} must be a non-empty string")
            for field in ("recipe", "context", "session_name"):
                if not isinstance(surface.get(field), str) or not surface[field]:
                    errors.append(f"goose_projection_policy.goose_native_surface.{field} must be a non-empty string")
        errors.extend(_governance_disabled_errors(projection.get("governance"), "goose_projection_policy.", ("runtime_execution", "goose_runtime_start", "model_execution")))

    errors.extend(_string_list_errors(data.get("required_evidence"), "required_evidence"))
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "session_configuration":
            errors.append("governance.capability_state must be session_configuration")
        for key in ("runtime_execution", "goose_runtime_start", "model_execution", "agent_construction", "subagent_construction", "shell_execution", "command_execution", "source_writes", "memory_mutation", "commit_push"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_session_configuration_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_session_configuration(data)
