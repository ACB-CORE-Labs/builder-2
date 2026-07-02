from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

CONFIG_SCHEMA_KIND = "builder_ii.config_schema"
CONFIG_SCHEMA_VERSION = "1.0.0"

SOURCE_PRECEDENCE = (
    "cli_override",
    "process_environment",
    "dotenv",
    "builder_config_file",
    "target_profile_default",
    "built_in_default",
)

CAPABILITY_DEFAULTS: dict[str, str] = {
    "runtime_execution": "disabled",
    "model_execution": "disabled",
    "shell_execution": "disabled",
    "source_writes": "disabled",
    "goose_runtime": "disabled",
    "deepagents_runtime": "disabled",
    "mcp_tool_invocation": "disabled",
    "patch_authority": "disabled",
    "autonomous_writes": "disabled",
    "artifact_output": "explicit_output_path_only",
}


class ConfigFieldSpec(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)

    name: str
    value_type: str
    required: bool
    primary_env: str | None = None
    legacy_env_aliases: tuple[str, ...] = Field(default_factory=tuple)
    config_keys: tuple[str, ...] = Field(default_factory=tuple)
    default: str | bool
    description: str
    path_like: bool = False
    secret: bool = False

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.value_type,
            "required": self.required,
            "primary_env": self.primary_env,
            "legacy_env_aliases": list(self.legacy_env_aliases),
            "builder_config_keys": list(self.config_keys),
            "default": self.default,
            "description": self.description,
            "path_like": self.path_like,
            "secret": self.secret,
        }


CONFIG_FIELD_SPECS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        name="schema_version",
        value_type="string",
        required=True,
        primary_env=None,
        legacy_env_aliases=(),
        config_keys=("schema_version",),
        default=CONFIG_SCHEMA_VERSION,
        description="Version of the governed builder-II config schema.",
    ),
    ConfigFieldSpec(
        name="platform_artifact_root",
        value_type="path",
        required=True,
        primary_env="BUILDER_ARTIFACT_ROOT",
        legacy_env_aliases=("CORE_ARTIFACT_ROOT",),
        config_keys=("platform_artifact_root", "artifact_root"),
        default=".builder/artifacts",
        description="Canonical root for passive builder-II artifacts.",
        path_like=True,
    ),
    ConfigFieldSpec(
        name="default_target_id",
        value_type="string",
        required=True,
        primary_env="BUILDER_DEFAULT_TARGET_ID",
        legacy_env_aliases=("CORE_DEFAULT_TARGET_ID",),
        config_keys=("default_target_id",),
        default="builder",
        description="Default target repository id used when no target profile is supplied.",
    ),
    ConfigFieldSpec(
        name="target_repo",
        value_type="path",
        required=True,
        primary_env="BUILDER_TARGET_REPO",
        legacy_env_aliases=("CORE_REPO_PATH",),
        config_keys=("target_repo", "target.repo", "target_repo_path"),
        default=".",
        description="Canonical target repository path. CORE is only a target profile.",
        path_like=True,
    ),
    ConfigFieldSpec(
        name="active_target_profile",
        value_type="string",
        required=True,
        primary_env="BUILDER_TARGET_PROFILE",
        legacy_env_aliases=("CORE_TARGET_PROFILE",),
        config_keys=("active_target_profile", "target_profile", "target.profile"),
        default="builder",
        description="Selected target profile id.",
    ),
    ConfigFieldSpec(
        name="active_agent_profile",
        value_type="string",
        required=True,
        primary_env="BUILDER_AGENT_PROFILE",
        legacy_env_aliases=("CORE_AGENT_PROFILE",),
        config_keys=("active_agent_profile", "agent_profile", "agent.profile"),
        default="patch_planner",
        description="Selected passive agent profile id.",
    ),
    ConfigFieldSpec(
        name="active_verification_profile",
        value_type="string",
        required=True,
        primary_env="BUILDER_VERIFICATION_PROFILE",
        legacy_env_aliases=("CORE_VERIFICATION_PROFILE",),
        config_keys=("active_verification_profile", "verification_profile", "verification.profile"),
        default="builder_full",
        description="Selected passive verification profile id.",
    ),
    ConfigFieldSpec(
        name="model_backend",
        value_type="string",
        required=True,
        primary_env="BUILDER_MODEL_BACKEND",
        legacy_env_aliases=("CORE_AGENT_BACKEND",),
        config_keys=("model_backend", "model.backend"),
        default="mlx-lm",
        description="Default model backend metadata. R1.1 never invokes it.",
    ),
    ConfigFieldSpec(
        name="model_alias",
        value_type="string",
        required=True,
        primary_env="BUILDER_MODEL_ALIAS",
        legacy_env_aliases=("CORE_AGENT_MODEL_ALIAS",),
        config_keys=("model_alias", "model.alias"),
        default="qwen-coder",
        description="Default model alias metadata. R1.1 never calls a model.",
    ),
    ConfigFieldSpec(
        name="model_tier",
        value_type="string",
        required=True,
        primary_env="BUILDER_MODEL_TIER",
        legacy_env_aliases=("CORE_AGENT_MODEL_TIER",),
        config_keys=("model_tier", "model.tier"),
        default="primary",
        description="Default model tier metadata.",
    ),
    ConfigFieldSpec(
        name="model_api_token",
        value_type="string",
        required=False,
        primary_env="BUILDER_MODEL_API_TOKEN",
        legacy_env_aliases=("CORE_AGENT_API_TOKEN",),
        config_keys=("model_api_token", "model.api_token"),
        default="",
        description="Optional raw token compatibility input; artifacts redact this value.",
        secret=True,
    ),
    ConfigFieldSpec(
        name="runtime_mode",
        value_type="string",
        required=True,
        primary_env="BUILDER_RUNTIME_MODE",
        legacy_env_aliases=("CORE_RUNTIME_MODE",),
        config_keys=("runtime_mode",),
        default="passive",
        description="Platform runtime mode. R1.1 only permits passive planning metadata.",
    ),
    ConfigFieldSpec(
        name="goose_config_path",
        value_type="path",
        required=True,
        primary_env="BUILDER_GOOSE_CONFIG_PATH",
        legacy_env_aliases=("GOOSE_CONFIG_PATH", "CORE_GOOSE_CONFIG_PATH"),
        config_keys=("goose_config_path", "goose.config_path"),
        default="~/.config/goose/config.yaml",
        description="Goose config target path to describe in plans only.",
        path_like=True,
    ),
    ConfigFieldSpec(
        name="goose_recipe_path",
        value_type="path",
        required=True,
        primary_env="BUILDER_GOOSE_RECIPE_PATH",
        legacy_env_aliases=("GOOSE_RECIPE_PATH", "CORE_GOOSE_RECIPE_PATH"),
        config_keys=("goose_recipe_path", "goose.recipe_path"),
        default="recipes",
        description="Goose recipe source path to describe in plans only.",
        path_like=True,
    ),
    ConfigFieldSpec(
        name="goose_skills_source_path",
        value_type="path",
        required=True,
        primary_env="BUILDER_GOOSE_SKILLS_SOURCE",
        legacy_env_aliases=("CORE_SKILLS_SOURCE_PATH",),
        config_keys=("goose_skills_source_path", "goose.skills_source_path"),
        default=".agents/skills",
        description="Skills source path to describe in plans only.",
        path_like=True,
    ),
    ConfigFieldSpec(
        name="goose_skills_destination_policy",
        value_type="string",
        required=True,
        primary_env="BUILDER_GOOSE_SKILLS_DESTINATION_POLICY",
        legacy_env_aliases=("CORE_SKILLS_DESTINATION_POLICY",),
        config_keys=("goose_skills_destination_policy", "goose.skills_destination_policy"),
        default="plan_only_target_agents_skills",
        description="Passive policy for future skill destination materialization.",
    ),
    ConfigFieldSpec(
        name="deepagents_mode",
        value_type="string",
        required=True,
        primary_env="BUILDER_DEEPAGENTS_MODE",
        legacy_env_aliases=("CORE_DEEPAGENTS_MODE",),
        config_keys=("deepagents_mode", "deepagents.mode"),
        default="disabled",
        description="Deepagents mode metadata. Runtime construction remains disabled.",
    ),
    ConfigFieldSpec(
        name="allow_artifact_root_inside_target",
        value_type="boolean",
        required=True,
        primary_env="BUILDER_ALLOW_ARTIFACT_ROOT_INSIDE_TARGET",
        legacy_env_aliases=("CORE_ALLOW_ARTIFACT_ROOT_INSIDE_TARGET",),
        config_keys=("allow_artifact_root_inside_target", "path_policy.allow_artifact_root_inside_target"),
        default=False,
        description="Explicit opt-in for artifact roots inside arbitrary target source paths.",
    ),
)


def _canonical_json(data: dict[str, Any]) -> str:
    return json_lib.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_jsonable(data: dict[str, Any], *, digest_key: str = "digest") -> str:
    payload = dict(data)
    payload.pop(digest_key, None)
    encoded = _canonical_json(payload).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def attach_digest(data: dict[str, Any], *, digest_key: str = "digest") -> dict[str, Any]:
    payload = dict(data)
    payload[digest_key] = digest_jsonable(payload, digest_key=digest_key)
    return payload


def legacy_alias_map() -> dict[str, dict[str, str]]:
    aliases: dict[str, dict[str, str]] = {}
    for spec in CONFIG_FIELD_SPECS:
        if not spec.primary_env:
            continue
        for alias in spec.legacy_env_aliases:
            aliases[alias] = {
                "alias_for": spec.primary_env,
                "field": spec.name,
                "compatibility_state": "backwards_compatible_alias_only",
            }
    return aliases


def create_config_schema_artifact() -> dict[str, Any]:
    artifact = {
        "kind": CONFIG_SCHEMA_KIND,
        "schema_version": CONFIG_SCHEMA_VERSION,
        "source_precedence": list(SOURCE_PRECEDENCE),
        "fields": {spec.name: spec.to_jsonable() for spec in CONFIG_FIELD_SPECS},
        "target_repo_entries": {
            "shape": "mapping target id -> canonical repo path",
            "required_default_id": "default_target_id",
            "supported_initial_targets": ["generic", "builder", "core"],
        },
        "goose": {
            "config_path_field": "goose_config_path",
            "recipe_path_field": "goose_recipe_path",
            "skills_source_path_field": "goose_skills_source_path",
            "skills_destination_policy_field": "goose_skills_destination_policy",
            "runtime_state": "disabled",
        },
        "deepagents": {
            "mode_field": "deepagents_mode",
            "runtime_state": "disabled",
        },
        "capability_defaults": CAPABILITY_DEFAULTS,
        "path_safety_policy": {
            "canonicalize_paths": True,
            "artifact_root_inside_target": "allowed only for .builder/artifacts or explicit opt-in",
            "target_repo_mutation": "disabled",
        },
        "legacy_compatibility": {
            "preferred_env_prefix": "BUILDER_",
            "legacy_aliases": legacy_alias_map(),
            "core_boundary": "CORE remains a target profile/adapter, not the platform identity.",
        },
        "governance": {
            "artifact_is_authority": False,
            **CAPABILITY_DEFAULTS,
        },
    }
    return attach_digest(artifact)


def dumps_config_schema() -> str:
    return json_lib.dumps(create_config_schema_artifact(), indent=2, sort_keys=True) + "\n"


def write_config_schema_artifact(output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_config_schema(), encoding="utf-8")


def validate_config_schema_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["config schema artifact must be a JSON object"]
    if data.get("kind") != CONFIG_SCHEMA_KIND:
        errors.append(f"kind must be {CONFIG_SCHEMA_KIND}")
    if data.get("schema_version") != CONFIG_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONFIG_SCHEMA_VERSION}")
    if data.get("source_precedence") != list(SOURCE_PRECEDENCE):
        errors.append("source_precedence must match the canonical R1.1 order")
    fields = data.get("fields")
    if not isinstance(fields, dict):
        errors.append("fields must be an object")
    else:
        for spec in CONFIG_FIELD_SPECS:
            field = fields.get(spec.name)
            if not isinstance(field, dict):
                errors.append(f"fields.{spec.name} is required")
                continue
            if field.get("primary_env") != spec.primary_env:
                errors.append(f"fields.{spec.name}.primary_env mismatch")
            if field.get("legacy_env_aliases") != list(spec.legacy_env_aliases):
                errors.append(f"fields.{spec.name}.legacy_env_aliases mismatch")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        for key, expected in CAPABILITY_DEFAULTS.items():
            if governance.get(key) != expected:
                errors.append(f"governance.{key} must be {expected}")
    digest = data.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(data):
        errors.append("digest does not match canonical schema payload")
    return errors
