from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.core.config_schema import (
    CONFIG_SCHEMA_KIND,
    dumps_config_schema,
    validate_config_schema_artifact,
    write_config_schema_artifact,
)
from builder_ii.core.config_sources import (
    CONFIG_SOURCE_RESOLUTION_KIND,
    dumps_config_resolution,
    resolve_config_sources,
    validate_config_resolution_artifact,
    write_config_resolution_artifact,
)

config_app = typer.Typer(
    help="Render and validate passive builder-II config artifacts without runtime authority.",
    no_args_is_help=True,
)
console = Console()


def _override_map(
    *,
    target_repo: Path | None,
    artifact_root: Path | None,
    target_profile: str | None,
    agent_profile: str | None,
    verification_profile: str | None,
    model_backend: str | None,
    model_alias: str | None,
    runtime_mode: str | None,
    allow_artifact_root_inside_target: bool | None,
) -> dict[str, Any]:
    overrides: dict[str, Any] = {}
    if target_repo is not None:
        overrides["target_repo"] = str(target_repo)
    if artifact_root is not None:
        overrides["platform_artifact_root"] = str(artifact_root)
    if target_profile is not None:
        overrides["active_target_profile"] = target_profile
    if agent_profile is not None:
        overrides["active_agent_profile"] = agent_profile
    if verification_profile is not None:
        overrides["active_verification_profile"] = verification_profile
    if model_backend is not None:
        overrides["model_backend"] = model_backend
    if model_alias is not None:
        overrides["model_alias"] = model_alias
    if runtime_mode is not None:
        overrides["runtime_mode"] = runtime_mode
    if allow_artifact_root_inside_target is not None:
        overrides["allow_artifact_root_inside_target"] = allow_artifact_root_inside_target
    return overrides


def _report(kind: str, valid: bool, errors: list[str]) -> str:
    return (
        json_lib.dumps(
            {"kind": kind, "valid": valid, "errors": errors},
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


@config_app.command("schema")
def schema(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Optional explicit path for the schema artifact JSON.",
    ),
) -> None:
    """Print the canonical generic-first config schema artifact."""
    if output is not None:
        write_config_schema_artifact(output)
    echo_stdout(dumps_config_schema())


@config_app.command("resolve")
def resolve(
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional explicit artifact output path."),
    root: Path = typer.Option(Path("."), "--root", help="Project root for relative paths and .env lookup."),
    config_file: Path | None = typer.Option(None, "--config-file", help="Optional builder config JSON/YAML file."),
    target_repo: Path | None = typer.Option(None, "--target-repo", help="CLI override for BUILDER_TARGET_REPO."),
    artifact_root: Path | None = typer.Option(None, "--artifact-root", help="CLI override for BUILDER_ARTIFACT_ROOT."),
    target_profile: str | None = typer.Option(
        None, "--target-profile", help="CLI override for BUILDER_TARGET_PROFILE."
    ),
    agent_profile: str | None = typer.Option(None, "--agent-profile", help="CLI override for BUILDER_AGENT_PROFILE."),
    verification_profile: str | None = typer.Option(
        None, "--verification-profile", help="CLI override for BUILDER_VERIFICATION_PROFILE."
    ),
    model_backend: str | None = typer.Option(None, "--model-backend", help="CLI override for BUILDER_MODEL_BACKEND."),
    model_alias: str | None = typer.Option(None, "--model-alias", help="CLI override for BUILDER_MODEL_ALIAS."),
    runtime_mode: str | None = typer.Option(None, "--runtime-mode", help="CLI override for BUILDER_RUNTIME_MODE."),
    allow_artifact_root_inside_target: bool | None = typer.Option(
        None,
        "--allow-artifact-root-inside-target/--no-allow-artifact-root-inside-target",
        help="Explicit path policy override for artifact roots under target source paths.",
    ),
) -> None:
    """Resolve config sources and print a digest-bound passive resolution artifact."""
    resolution = resolve_config_sources(
        project_root=root,
        builder_config_file=config_file,
        cli_overrides=_override_map(
            target_repo=target_repo,
            artifact_root=artifact_root,
            target_profile=target_profile,
            agent_profile=agent_profile,
            verification_profile=verification_profile,
            model_backend=model_backend,
            model_alias=model_alias,
            runtime_mode=runtime_mode,
            allow_artifact_root_inside_target=allow_artifact_root_inside_target,
        ),
    )
    if output is not None:
        write_config_resolution_artifact(resolution, output)
    echo_stdout(dumps_config_resolution(resolution))
    if resolution.errors:
        raise typer.Exit(1)


@config_app.command("validate")
def validate(
    path: Path | None = typer.Argument(None, help="Optional schema or resolution artifact JSON path."),
    root: Path = typer.Option(Path("."), "--root", help="Project root when validating current resolution."),
    config_file: Path | None = typer.Option(None, "--config-file", help="Optional builder config JSON/YAML file."),
) -> None:
    """Validate a config artifact, or validate current source resolution when no path is supplied."""
    if path is None:
        resolution = resolve_config_sources(project_root=root, builder_config_file=config_file)
        artifact = resolution.to_jsonable()
        errors = validate_config_resolution_artifact(artifact)
    else:
        artifact = json_lib.loads(path.read_text(encoding="utf-8"))
        if artifact.get("kind") == CONFIG_SCHEMA_KIND:
            errors = validate_config_schema_artifact(artifact)
        elif artifact.get("kind") == CONFIG_SOURCE_RESOLUTION_KIND:
            errors = validate_config_resolution_artifact(artifact)
        else:
            errors = [f"unsupported config artifact kind: {artifact.get('kind')}"]
    echo_stdout(_report("builder_ii.config_validation_report", not errors, errors))
    if errors:
        raise typer.Exit(1)


if __name__ == "__main__":
    config_app()
