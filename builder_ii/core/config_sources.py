from __future__ import annotations

import json as json_lib
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

import yaml
from dotenv import dotenv_values

from builder_ii.core.config import BACKENDS, MODEL_ALIASES, MODEL_TIERS, normalize_model_alias
from builder_ii.core.config_schema import (
    CAPABILITY_DEFAULTS,
    CONFIG_FIELD_SPECS,
    CONFIG_SCHEMA_VERSION,
    SOURCE_PRECEDENCE,
    attach_digest,
    digest_jsonable,
)
from builder_ii.lifecycle.candidate.verification_profiles import default_profile_for_target, verification_profile_names
from builder_ii.lifecycle.setup.target_profile_defaults import get_target_defaults
from builder_ii.lifecycle.setup.target_profiles import target_names
from builder_ii.routing.agent_profiles import agent_profile_names

CONFIG_SOURCE_RESOLUTION_KIND = "builder_ii.config_source_resolution"
CONFIG_SOURCE_RESOLUTION_SCHEMA_VERSION = 1

SourceKind = str

_PATH_FIELDS = {
    "platform_artifact_root",
    "target_repo",
    "goose_config_path",
    "goose_recipe_path",
    "goose_skills_source_path",
}
_BOOL_FIELDS = {"allow_artifact_root_inside_target"}
_SECRET_MARKERS = ("secret", "token", "api_key", "apikey", "password", "credential", "bearer")
# Ordered, because a wizard renders it into prompt text. A set has no order, so a prompt built from
# one shows its options in a different sequence on every run under hash randomization.
RUNTIME_MODES: tuple[str, ...] = ("passive", "disabled", "operator_managed_legacy")
_ALLOWED_RUNTIME_MODES = set(RUNTIME_MODES)
_ALLOWED_SKILLS_POLICIES = {
    "disabled",
    "plan_only_target_agents_skills",
    "plan_only_existing_destination",
}
_ALLOWED_DEEPAGENTS_MODES = {"disabled", "metadata_only", "policy_only"}


@dataclass(frozen=True)
class SourceRef:
    kind: SourceKind
    key: str
    path: str

    def to_jsonable(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class ResolvedValue:
    name: str
    value: str | bool
    redacted_value: str | bool
    source: SourceRef
    legacy_alias_used: bool
    value_redacted: bool
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.redacted_value if self.value_redacted else self.value,
            "redacted_value": self.redacted_value,
            "source_kind": self.source.kind,
            "source_key": self.source.key,
            "source_path": self.source.path,
            "legacy_alias_used": self.legacy_alias_used,
            "value_redacted": self.value_redacted,
            "secret_value_present": bool(self.value) if self.value_redacted else False,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class ConfigResolution:
    project_root: Path
    dotenv_path: Path
    builder_config_path: Path | None
    fields: dict[str, ResolvedValue]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    def raw_value(self, field: str) -> str | bool:
        return self.fields[field].value

    def value(self, field: str) -> str:
        value = self.raw_value(field)
        if isinstance(value, bool):
            return "true" if value else "false"
        return value

    def to_jsonable(self) -> dict[str, Any]:
        target_profile = self.value("active_target_profile")
        target_repo = self.value("target_repo")
        payload = {
            "kind": CONFIG_SOURCE_RESOLUTION_KIND,
            "schema_version": CONFIG_SOURCE_RESOLUTION_SCHEMA_VERSION,
            "config_schema_version": CONFIG_SCHEMA_VERSION,
            "project_root": str(self.project_root),
            "source_precedence": list(SOURCE_PRECEDENCE),
            "dotenv_path": str(self.dotenv_path),
            "builder_config_path": str(self.builder_config_path) if self.builder_config_path else "",
            "resolved": {name: field.to_jsonable() for name, field in sorted(self.fields.items())},
            "target_repos": {
                self.value("default_target_id"): target_repo,
                target_profile: target_repo,
            },
            "capability_defaults": CAPABILITY_DEFAULTS,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "governance": {
                "artifact_is_authority": False,
                **CAPABILITY_DEFAULTS,
            },
        }
        return attach_digest(payload)


def dumps_config_resolution(resolution: ConfigResolution) -> str:
    return json_lib.dumps(resolution.to_jsonable(), indent=2, sort_keys=True) + "\n"


def write_config_resolution_artifact(resolution: ConfigResolution, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_config_resolution(resolution), encoding="utf-8")


def _is_secret_field(name: str, key: str) -> bool:
    combined = f"{name} {key}".lower()
    return any(marker in combined for marker in _SECRET_MARKERS)


def _redact(value: str | bool, *, secret: bool) -> tuple[str | bool, bool]:
    if not secret:
        return value, False
    if isinstance(value, bool) or not value:
        return value, False
    return "<redacted>", True


def _canonicalize_path(raw: str, *, project_root: Path) -> str:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = project_root / path
    return str(path.resolve(strict=False))


def _parse_bool(raw: Any) -> bool:
    if isinstance(raw, bool):
        return raw
    value = str(raw).strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off", ""}:
        return False
    raise ValueError(f"expected boolean value, got {raw!r}")


def _clean_scalar(raw: Any) -> str:
    if raw is None:
        return ""
    return str(raw).strip()


def _flatten_config(data: Mapping[str, Any], *, prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in data.items():
        dotted = f"{prefix}.{key}" if prefix else str(key)
        flattened[dotted] = value
        if isinstance(value, Mapping):
            flattened.update(_flatten_config(value, prefix=dotted))
    return flattened


def _load_builder_config_file(path: Path | None, project_root: Path) -> tuple[dict[str, Any], Path | None, list[str]]:
    warnings: list[str] = []
    candidates: list[Path] = []
    if path is not None:
        candidates.append(path)
    else:
        candidates.extend(
            [
                project_root / ".builder" / "config.json",
                project_root / ".builder" / "config.yaml",
                project_root / "builder.config.json",
                project_root / "builder.config.yaml",
                Path.home() / ".config" / "builder-ii" / "config.json",
                Path.home() / ".config" / "builder-ii" / "config.yaml",
            ]
        )

    selected = next((candidate.expanduser() for candidate in candidates if candidate.expanduser().exists()), None)
    if selected is None:
        return {}, None, warnings

    try:
        text = selected.read_text(encoding="utf-8")
        if selected.suffix.lower() in {".yaml", ".yml"}:
            loaded = yaml.safe_load(text) or {}
        else:
            loaded = json_lib.loads(text)
    except Exception as exc:
        warnings.append(f"failed to read builder config file {selected}: {exc}")
        return {}, selected.resolve(strict=False), warnings
    if not isinstance(loaded, Mapping):
        warnings.append(f"builder config file {selected} must contain an object")
        return {}, selected.resolve(strict=False), warnings
    return _flatten_config(loaded), selected.resolve(strict=False), warnings


def _source_lookup(
    *,
    field_name: str,
    primary_env: str | None,
    legacy_env_aliases: tuple[str, ...],
    process_env: Mapping[str, str],
    dotenv: Mapping[str, Any],
    builder_config: Mapping[str, Any],
    config_keys: tuple[str, ...],
    cli_overrides: Mapping[str, Any],
    target_defaults: Mapping[str, Any],
    built_in_default: Any,
    dotenv_path: Path,
    builder_config_path: Path | None,
) -> tuple[Any, SourceRef, bool, list[str]]:
    warnings: list[str] = []
    if field_name in cli_overrides and cli_overrides[field_name] is not None:
        return (
            cli_overrides[field_name],
            SourceRef("cli_override", field_name, ""),
            False,
            warnings,
        )

    for source_kind, source_map, source_path in (
        ("process_environment", process_env, ""),
        ("dotenv", dotenv, str(dotenv_path)),
    ):
        if primary_env and primary_env in source_map and _clean_scalar(source_map[primary_env]) != "":
            ignored = [
                alias for alias in legacy_env_aliases if alias in source_map and _clean_scalar(source_map[alias]) != ""
            ]
            if ignored:
                warnings.append(f"{primary_env} overrides legacy alias(es) {', '.join(ignored)} in {source_kind}")
            return (
                source_map[primary_env],
                SourceRef(source_kind, primary_env, source_path),
                False,
                warnings,
            )
        for alias in legacy_env_aliases:
            if alias in source_map and _clean_scalar(source_map[alias]) != "":
                warnings.append(f"{alias} is a legacy alias for {primary_env}; prefer {primary_env}")
                return (
                    source_map[alias],
                    SourceRef(source_kind, alias, source_path),
                    True,
                    warnings,
                )

    for key in config_keys:
        if key in builder_config and builder_config[key] is not None and _clean_scalar(builder_config[key]) != "":
            return (
                builder_config[key],
                SourceRef(
                    "builder_config_file",
                    key,
                    str(builder_config_path) if builder_config_path else "",
                ),
                False,
                warnings,
            )
    if field_name in target_defaults:
        return (
            target_defaults[field_name],
            SourceRef("target_profile_default", field_name, ""),
            False,
            warnings,
        )
    return (
        built_in_default,
        SourceRef("built_in_default", field_name, ""),
        False,
        warnings,
    )


def _target_profile_defaults(project_root: Path, active_target_profile: str) -> dict[str, Any]:
    """Build target-specific defaults by delegating to target_profile_defaults.

    This function is the bridge between the old per-field default map expected
    by _source_lookup and the canonical target_profile_defaults module.
    CORE-specific strings (repo path, agent name) are owned exclusively by
    target_profile_defaults; this function must not duplicate them.
    """
    target_data = get_target_defaults(active_target_profile)

    # Resolve the repo path: target_profile_defaults returns a Path.
    # For the "generic" and "builder" targets the default is project_root
    # itself; honour that by re-injecting the live project_root so that
    # test calls with a tmp_path still resolve correctly.
    raw_repo: Path = target_data["default_target_repo"]
    if active_target_profile in ("generic", "builder"):
        target_repo = str(project_root)
    else:
        target_repo = str(raw_repo)

    verification_profile = "builder_full"
    if active_target_profile in target_names():
        verification_profile = default_profile_for_target(active_target_profile).name

    return {
        "target_repo": target_repo,
        "active_agent_profile": target_data["default_agent_profile"],
        "active_verification_profile": verification_profile,
    }


def _resolve_field(
    *,
    spec_name: str,
    raw_value: Any,
    source: SourceRef,
    legacy_alias_used: bool,
    warnings: list[str],
    project_root: Path,
) -> ResolvedValue:
    errors: list[str] = []
    spec = next(spec for spec in CONFIG_FIELD_SPECS if spec.name == spec_name)
    value: str | bool
    try:
        if spec_name in _BOOL_FIELDS:
            value = _parse_bool(raw_value)
        else:
            value = _clean_scalar(raw_value)
            if spec.path_like:
                value = _canonicalize_path(value, project_root=project_root)
            if spec_name == "model_alias":
                value = normalize_model_alias(value)
            if spec_name == "model_backend":
                value = value.lower()
            if spec_name in {"model_tier", "runtime_mode", "deepagents_mode", "goose_skills_destination_policy"}:
                value = value.lower()
    except Exception as exc:
        value = _clean_scalar(raw_value)
        errors.append(str(exc))

    secret = spec.secret or _is_secret_field(spec_name, source.key)
    redacted, value_redacted = _redact(value, secret=secret)
    return ResolvedValue(
        name=spec_name,
        value=value,
        redacted_value=redacted,
        source=source,
        legacy_alias_used=legacy_alias_used,
        value_redacted=value_redacted,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _validate_resolved_fields(fields: dict[str, ResolvedValue]) -> tuple[list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []

    target_profile = str(fields["active_target_profile"].value)
    if target_profile not in target_names():
        errors.append("active_target_profile must be one of: generic, builder, core")
    if str(fields["active_agent_profile"].value) not in agent_profile_names():
        errors.append("active_agent_profile must be a known agent profile")
    if str(fields["active_verification_profile"].value) not in verification_profile_names():
        errors.append("active_verification_profile must be a known verification profile")
    if str(fields["model_backend"].value) not in BACKENDS:
        errors.append(f"model_backend must be one of {BACKENDS}")
    if str(fields["model_alias"].value) not in MODEL_ALIASES:
        errors.append(f"model_alias must be one of {MODEL_ALIASES}")
    if str(fields["model_tier"].value) not in MODEL_TIERS:
        errors.append(f"model_tier must be one of {MODEL_TIERS}")
    if str(fields["runtime_mode"].value) not in _ALLOWED_RUNTIME_MODES:
        errors.append(f"runtime_mode must be one of {sorted(_ALLOWED_RUNTIME_MODES)}")
    if str(fields["goose_skills_destination_policy"].value) not in _ALLOWED_SKILLS_POLICIES:
        errors.append(f"goose_skills_destination_policy must be one of {sorted(_ALLOWED_SKILLS_POLICIES)}")
    if str(fields["deepagents_mode"].value) not in _ALLOWED_DEEPAGENTS_MODES:
        errors.append(f"deepagents_mode must be one of {sorted(_ALLOWED_DEEPAGENTS_MODES)}")

    for field_name in _PATH_FIELDS:
        value = str(fields[field_name].value)
        if not Path(value).is_absolute():
            errors.append(f"{field_name} must resolve to an absolute path")

    target_repo = Path(str(fields["target_repo"].value))
    artifact_root = Path(str(fields["platform_artifact_root"].value))
    if not target_repo.exists():
        errors.append(f"target_repo does not exist: {target_repo}")
    elif not target_repo.is_dir():
        errors.append(f"target_repo is not a directory: {target_repo}")

    try:
        rel = artifact_root.relative_to(target_repo)
    except ValueError:
        rel = None
    if rel is not None:
        allow_inside = bool(fields["allow_artifact_root_inside_target"].value)
        parts = rel.parts
        if parts[:2] == (".builder", "artifacts"):
            warnings.append(
                "platform_artifact_root is inside target_repo under .builder/artifacts; "
                "allowed by built-in artifact policy"
            )
        elif allow_inside:
            warnings.append("platform_artifact_root is inside target_repo by explicit path policy opt-in")
        else:
            errors.append(
                "platform_artifact_root is inside target_repo outside .builder/artifacts; "
                "set BUILDER_ALLOW_ARTIFACT_ROOT_INSIDE_TARGET=true only for an explicit artifact policy"
            )

    for field in fields.values():
        warnings.extend(field.warnings)
        errors.extend(field.errors)
    return warnings, errors


def resolve_config_sources(
    *,
    project_root: Path | None = None,
    cli_overrides: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    dotenv_path: Path | None = None,
    builder_config_file: Path | None = None,
) -> ConfigResolution:
    root = (project_root or Path.cwd()).resolve(strict=False)
    overrides = dict(cli_overrides or {})
    process_env = dict(os.environ if environ is None else environ)
    env_path = (dotenv_path or (root / ".env")).resolve(strict=False)
    dotenv = dotenv_values(env_path) if env_path.exists() else {}
    builder_config, selected_config_path, config_warnings = _load_builder_config_file(builder_config_file, root)

    fields: dict[str, ResolvedValue] = {}
    active_target_profile = _resolve_one_for_target_bootstrap(
        root=root,
        overrides=overrides,
        process_env=process_env,
        dotenv=dotenv,
        dotenv_path=env_path,
        builder_config=builder_config,
        builder_config_path=selected_config_path,
    )
    target_defaults = _target_profile_defaults(root, active_target_profile)

    for spec in CONFIG_FIELD_SPECS:
        target_specific_defaults = target_defaults if spec.name in target_defaults else {}
        raw, source, legacy_used, warnings = _source_lookup(
            field_name=spec.name,
            primary_env=spec.primary_env,
            legacy_env_aliases=spec.legacy_env_aliases,
            process_env=process_env,
            dotenv=dotenv,
            builder_config=builder_config,
            config_keys=spec.config_keys,
            cli_overrides=overrides,
            target_defaults=target_specific_defaults,
            built_in_default=spec.default,
            dotenv_path=env_path,
            builder_config_path=selected_config_path,
        )
        fields[spec.name] = _resolve_field(
            spec_name=spec.name,
            raw_value=raw,
            source=source,
            legacy_alias_used=legacy_used,
            warnings=warnings,
            project_root=root,
        )

    warnings, errors = _validate_resolved_fields(fields)
    warnings = [*config_warnings, *warnings]
    return ConfigResolution(
        project_root=root,
        dotenv_path=env_path,
        builder_config_path=selected_config_path,
        fields=fields,
        warnings=tuple(warnings),
        errors=tuple(errors),
    )


def _resolve_one_for_target_bootstrap(
    *,
    root: Path,
    overrides: Mapping[str, Any],
    process_env: Mapping[str, str],
    dotenv: Mapping[str, Any],
    dotenv_path: Path,
    builder_config: Mapping[str, Any],
    builder_config_path: Path | None,
) -> str:
    spec = next(item for item in CONFIG_FIELD_SPECS if item.name == "active_target_profile")
    raw, source, legacy_used, warnings = _source_lookup(
        field_name=spec.name,
        primary_env=spec.primary_env,
        legacy_env_aliases=spec.legacy_env_aliases,
        process_env=process_env,
        dotenv=dotenv,
        builder_config=builder_config,
        config_keys=spec.config_keys,
        cli_overrides=overrides,
        target_defaults={},
        built_in_default=spec.default,
        dotenv_path=dotenv_path,
        builder_config_path=builder_config_path,
    )
    resolved = _resolve_field(
        spec_name=spec.name,
        raw_value=raw,
        source=source,
        legacy_alias_used=legacy_used,
        warnings=warnings,
        project_root=root,
    )
    return str(resolved.value)


def validate_config_resolution_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["config source resolution artifact must be a JSON object"]
    if data.get("kind") != CONFIG_SOURCE_RESOLUTION_KIND:
        errors.append(f"kind must be {CONFIG_SOURCE_RESOLUTION_KIND}")
    if data.get("schema_version") != CONFIG_SOURCE_RESOLUTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONFIG_SOURCE_RESOLUTION_SCHEMA_VERSION}")
    if data.get("config_schema_version") != CONFIG_SCHEMA_VERSION:
        errors.append(f"config_schema_version must be {CONFIG_SCHEMA_VERSION}")
    if data.get("source_precedence") != list(SOURCE_PRECEDENCE):
        errors.append("source_precedence must match canonical precedence")
    resolved = data.get("resolved")
    if not isinstance(resolved, dict):
        errors.append("resolved must be an object")
    else:
        for spec in CONFIG_FIELD_SPECS:
            field = resolved.get(spec.name)
            if not isinstance(field, dict):
                errors.append(f"resolved.{spec.name} is required")
                continue
            if "source_kind" not in field or "source_key" not in field:
                errors.append(f"resolved.{spec.name} must include source_kind and source_key")
            if spec.secret and field.get("value_redacted") is True:
                if field.get("value") != "<redacted>" or field.get("redacted_value") != "<redacted>":
                    errors.append(f"resolved.{spec.name} must redact secret values")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        for key, expected in CAPABILITY_DEFAULTS.items():
            if governance.get(key) != expected:
                errors.append(f"governance.{key} must be {expected}")
    digest = data.get("digest")
    if not isinstance(digest, str) or len(digest) != 64:
        errors.append("digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(data):
        errors.append("digest does not match canonical resolution payload")
    artifact_errors = data.get("errors")
    if isinstance(artifact_errors, list):
        errors.extend(str(error) for error in artifact_errors)
    return errors


def load_config_resolution_artifact(path: Path) -> dict[str, Any]:
    return json_lib.loads(path.read_text(encoding="utf-8"))
