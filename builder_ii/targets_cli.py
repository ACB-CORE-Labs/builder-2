from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.config import load_settings
from builder_ii.target_profiles import (
    TargetName,
    build_target_profiles,
    render_target_profile,
    target_profile,
    validate_target_profiles,
    dumps_target_profile_artifact,
    write_target_profile_artifact,
    validate_target_profile_artifact,
    validate_target_profile_artifact_file,
)


targets_app = typer.Typer(help="Inspect builder-II target profiles.")
console = Console()
_VALID_TARGETS: set[str] = {"generic", "builder", "core"}


def _normalize_target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@targets_app.command("list")
def list_targets(generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target")) -> None:
    """List available target profiles."""
    settings = load_settings()
    table = Table("Target", "Repository", "Context defaults", "Description")
    for profile in build_target_profiles(settings, generic_repo=generic_repo):
        table.add_row(profile.name, str(profile.repo), str(len(profile.context_defaults)), profile.description)
    console.print(table)


@targets_app.command("show")
def show_target(name: str, generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target")) -> None:
    """Show one target profile."""
    settings = load_settings()
    profile = target_profile(settings, _normalize_target(name), generic_repo=generic_repo)
    console.print(render_target_profile(profile))


@targets_app.command("validate")
def validate(path: Path | None = typer.Argument(None, help="Validate target profile artifact file")) -> None:
    """Validate target profile registry consistency or an artifact file."""
    if path:
        errors = validate_target_profile_artifact_file(path)
        if errors:
            for error in errors:
                console.print(f"Validation error: {error}")
            raise typer.Exit(1)
        console.print(f"Target profile artifact {path} is valid.")
        return

    settings = load_settings()
    errors = validate_target_profiles(settings)
    if not errors:
        console.print("[green]Target profiles valid[/]")
        return
    for error in errors:
        console.print(f"[red]{error}[/]")
    raise typer.Exit(1)


@targets_app.command("artifact")
def artifact(
    name: str,
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
    output: Path | None = typer.Option(None, "--output", help="Write JSON artifact to path"),
) -> None:
    """Emit a no-runtime target profile artifact."""
    settings = load_settings()
    profile = target_profile(settings, _normalize_target(name), generic_repo=generic_repo)
    errors = validate_target_profile_artifact(profile.to_artifact_dict())
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_target_profile_artifact(profile, output)
        console.print(f"Target profile artifact written to {output}")
    else:
        console.out(dumps_target_profile_artifact(profile), end="")
