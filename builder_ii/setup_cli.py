from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.config_cli import _override_map
from builder_ii.config_sources import resolve_config_sources
from builder_ii.setup_plan import (
    create_setup_plan,
    dumps_setup_plan,
    validate_setup_plan_artifact,
    validate_setup_plan_file,
    write_setup_plan,
)


setup_app = typer.Typer(
    help="Create and validate passive setup plans without applying setup writes.",
    no_args_is_help=True,
)
console = Console()


def _validation_report(errors: list[str]) -> str:
    return json_lib.dumps(
        {
            "kind": "builder_ii.setup_plan_validation_report",
            "valid": not errors,
            "errors": errors,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


@setup_app.command("plan")
def plan(
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional explicit setup plan artifact path."),
    root: Path = typer.Option(Path("."), "--root", help="Project root for relative paths and .env lookup."),
    config_file: Path | None = typer.Option(None, "--config-file", help="Optional builder config JSON/YAML file."),
    target_repo: Path | None = typer.Option(None, "--target-repo", help="CLI override for BUILDER_TARGET_REPO."),
    artifact_root: Path | None = typer.Option(None, "--artifact-root", help="CLI override for BUILDER_ARTIFACT_ROOT."),
    target_profile: str | None = typer.Option(None, "--target-profile", help="CLI override for BUILDER_TARGET_PROFILE."),
    agent_profile: str | None = typer.Option(None, "--agent-profile", help="CLI override for BUILDER_AGENT_PROFILE."),
    verification_profile: str | None = typer.Option(None, "--verification-profile", help="CLI override for BUILDER_VERIFICATION_PROFILE."),
    model_backend: str | None = typer.Option(None, "--model-backend", help="CLI override for BUILDER_MODEL_BACKEND."),
    model_alias: str | None = typer.Option(None, "--model-alias", help="CLI override for BUILDER_MODEL_ALIAS."),
    runtime_mode: str | None = typer.Option(None, "--runtime-mode", help="CLI override for BUILDER_RUNTIME_MODE."),
    allow_artifact_root_inside_target: bool | None = typer.Option(
        None,
        "--allow-artifact-root-inside-target/--no-allow-artifact-root-inside-target",
        help="Explicit path policy override for artifact roots under target source paths.",
    ),
) -> None:
    """Create a passive setup plan artifact. This never applies the plan."""
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
    plan_artifact = create_setup_plan(resolution)
    if output is not None:
        write_setup_plan(plan_artifact, output)
    console.out(dumps_setup_plan(plan_artifact), end="")
    errors = validate_setup_plan_artifact(plan_artifact)
    if errors:
        raise typer.Exit(1)


@setup_app.command("validate-plan")
def validate_plan(
    path: Path = typer.Argument(..., help="Setup plan JSON artifact path."),
) -> None:
    """Validate a passive setup plan artifact."""
    errors = validate_setup_plan_file(path)
    console.out(_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


if __name__ == "__main__":
    setup_app()
