from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.target_profiles import TargetName, target_names
from builder_ii.verification_profiles import (
    dumps_profile_artifact,
    get_verification_profile,
    profiles_for_target,
    render_verification_profile,
    validate_profile_artifact,
    validate_profile_artifact_file,
    validate_verification_profiles,
    verification_profile_names,
    verification_profiles,
    write_profile_artifact,
)

verification_app = typer.Typer(help="Render and validate no-runtime verification profiles.")
console = Console()
_VALID_PROFILES = set(verification_profile_names())
_VALID_TARGETS = set(target_names())


def _profile(value: str):
    if value not in _VALID_PROFILES:
        console.print("unknown verification profile")
        raise typer.Exit(1)
    return value


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@verification_app.command("list")
def list_profiles(
    target: str | None = typer.Option(None, "--target", help="Optional target filter: generic, builder, core"),
) -> None:
    """List verification profiles without executing commands."""
    selected = profiles_for_target(_target(target)) if target else verification_profiles()
    table = Table("Profile", "Targets", "Purpose")
    for profile in selected:
        table.add_row(profile.name, ", ".join(profile.compatible_targets), profile.purpose)
    console.print(table)


@verification_app.command("show")
def show(
    profile: str,
    target: str | None = typer.Option(None, "--target", help="Optional selected target"),
    task: str = typer.Option("", "--task", help="Optional task context"),
    isolation: bool = typer.Option(False, "--isolation", help="Enable STRICT isolation policy in the verification profile"),
) -> None:
    """Show one verification profile as markdown."""
    selected_target = _target(target) if target else None
    selected = get_verification_profile(_profile(profile))
    if selected_target and selected_target not in selected.compatible_targets:
        console.print(f"verification profile {selected.name} is not compatible with target {selected_target}")
        raise typer.Exit(1)
    # Note: render_verification_profile doesn't currently visualize isolation flag, but we accept it for API parity.
    console.print(render_verification_profile(selected, target=selected_target, task=task))


@verification_app.command("artifact")
def artifact(
    profile: str,
    target: str | None = typer.Option(None, "--target", help="Optional selected target"),
    task: str = typer.Option("", "--task", help="Optional task context"),
    output: Path | None = typer.Option(None, "--output", help="Write JSON artifact to path"),
    isolation: bool = typer.Option(False, "--isolation", help="Enable STRICT isolation policy in the artifact governance"),
) -> None:
    """Emit a no-runtime verification profile artifact."""
    selected_target = _target(target) if target else None
    selected = get_verification_profile(_profile(profile))
    if selected_target and selected_target not in selected.compatible_targets:
        console.print(f"verification profile {selected.name} is not compatible with target {selected_target}")
        raise typer.Exit(1)
    errors = validate_profile_artifact(selected.to_artifact_dict(target=selected_target, task=task, isolation=isolation))
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_profile_artifact(selected, output, target=selected_target, task=task, isolation=isolation)
        console.print(f"Verification profile artifact written to {output}")
    else:
        typer.echo(dumps_profile_artifact(selected, target=selected_target, task=task, isolation=isolation), nl=False)


@verification_app.command("validate")
def validate(path: Path | None = typer.Argument(None)) -> None:
    """Validate the registry or a verification profile artifact without executing commands."""
    errors = validate_profile_artifact_file(path) if path else list(validate_verification_profiles())
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if path:
        console.print(f"Verification profile artifact {path} is valid.", soft_wrap=True)
    else:
        console.print("Verification profile registry is valid.", soft_wrap=True)
