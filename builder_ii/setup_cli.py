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
from builder_ii.setup_overlay import (
    create_setup_overlay_plan,
    dumps_setup_overlay_plan,
    validate_setup_overlay_plan_artifact,
    validate_setup_overlay_plan_file,
    write_setup_overlay_plan,
)
from builder_ii.setup_rollback import (
    create_setup_rollback_snapshot,
    dumps_setup_rollback_snapshot,
    validate_setup_rollback_snapshot_artifact,
    validate_setup_rollback_snapshot_file,
    write_setup_rollback_snapshot,
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


def _overlay_validation_report(errors: list[str]) -> str:
    return json_lib.dumps(
        {
            "kind": "builder_ii.setup_overlay_plan_validation_report",
            "valid": not errors,
            "errors": errors,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def _rollback_validation_report(errors: list[str]) -> str:
    return json_lib.dumps(
        {
            "kind": "builder_ii.setup_rollback_snapshot_validation_report",
            "valid": not errors,
            "errors": errors,
        },
        indent=2,
        sort_keys=True,
    ) + "\n"


def _load_json_file(path: Path) -> dict:
    return json_lib.loads(path.read_text(encoding="utf-8"))


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


@setup_app.command("overlay-plan")
def overlay_plan(
    setup_plan_path: Path = typer.Argument(..., help="Setup plan JSON artifact path."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional explicit setup overlay artifact path."),
) -> None:
    """Create a passive setup overlay plan artifact. This never applies setup."""
    plan_errors = validate_setup_plan_file(setup_plan_path)
    if plan_errors:
        console.out(_validation_report(plan_errors), end="")
        raise typer.Exit(1)
    overlay_artifact = create_setup_overlay_plan(_load_json_file(setup_plan_path))
    errors = validate_setup_overlay_plan_artifact(overlay_artifact)
    if errors:
        console.out(_overlay_validation_report(errors), end="")
        raise typer.Exit(1)
    if output is not None:
        write_setup_overlay_plan(overlay_artifact, output)
    console.out(dumps_setup_overlay_plan(overlay_artifact), end="")


@setup_app.command("validate-overlay-plan")
def validate_overlay_plan(
    path: Path = typer.Argument(..., help="Setup overlay plan JSON artifact path."),
) -> None:
    """Validate a passive setup overlay plan artifact."""
    errors = validate_setup_overlay_plan_file(path)
    console.out(_overlay_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


@setup_app.command("rollback-snapshot")
def rollback_snapshot(
    setup_overlay_path: Path = typer.Argument(..., help="Setup overlay plan JSON artifact path."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional explicit rollback snapshot artifact path."),
) -> None:
    """Create a passive rollback snapshot artifact. This never executes rollback."""
    overlay_errors = validate_setup_overlay_plan_file(setup_overlay_path)
    if overlay_errors:
        console.out(_overlay_validation_report(overlay_errors), end="")
        raise typer.Exit(1)
    snapshot_artifact = create_setup_rollback_snapshot(_load_json_file(setup_overlay_path))
    errors = validate_setup_rollback_snapshot_artifact(snapshot_artifact)
    if errors:
        console.out(_rollback_validation_report(errors), end="")
        raise typer.Exit(1)
    if output is not None:
        write_setup_rollback_snapshot(snapshot_artifact, output)
    console.out(dumps_setup_rollback_snapshot(snapshot_artifact), end="")


@setup_app.command("validate-rollback-snapshot")
def validate_rollback_snapshot(
    path: Path = typer.Argument(..., help="Setup rollback snapshot JSON artifact path."),
) -> None:
    """Validate a passive setup rollback snapshot artifact."""
    errors = validate_setup_rollback_snapshot_file(path)
    console.out(_rollback_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


if __name__ == "__main__":
    setup_app()
