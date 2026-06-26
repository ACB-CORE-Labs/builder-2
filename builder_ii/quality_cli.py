from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.quality_gates import (
    create_quality_gate_artifact,
    dumps_quality_gate_artifact,
    validate_quality_gate_artifact,
    validate_quality_gate_artifact_file,
    write_quality_gate_artifact,
)
from builder_ii.target_profiles import TargetName, target_names
from builder_ii.verification_profiles import VerificationProfileName, get_verification_profile, verification_profile_names

quality_app = typer.Typer(help="Create and validate no-execution quality gate artifacts.")
console = Console()
_VALID_PROFILES = set(verification_profile_names())
_VALID_TARGETS = set(target_names())


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _profile(value: str) -> VerificationProfileName:
    if value not in _VALID_PROFILES:
        console.print("unknown verification profile")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@quality_app.command("plan")
def plan(
    target: str = typer.Option("builder", "--target", help="Target profile: generic, builder, core"),
    profile: str = typer.Option("builder_full", "--profile", help="Verification profile to bind into the gate"),
    task: str = typer.Option(..., "--task", help="Task the quality gate applies to"),
    blocker: list[str] = typer.Option([], "--blocker", help="Repeatable merge blocker"),
    rollback: list[str] = typer.Option([], "--rollback", help="Repeatable rollback requirement"),
    output: Path | None = typer.Option(None, "--output", help="Write quality gate JSON artifact to path"),
) -> None:
    """Create a quality gate artifact without executing commands."""
    selected_target = _target(target)
    selected_profile_name = _profile(profile)
    selected_profile = get_verification_profile(selected_profile_name)
    if selected_target not in selected_profile.compatible_targets:
        console.print(f"verification profile {selected_profile.name} is not compatible with target {selected_target}")
        raise typer.Exit(1)

    artifact = create_quality_gate_artifact(
        target=selected_target,
        verification_profile=selected_profile_name,
        task=task,
        merge_blockers=tuple(blocker),
        rollback_requirements=tuple(rollback),
    )
    errors = validate_quality_gate_artifact(artifact)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_quality_gate_artifact(artifact, output)
        console.print(f"Quality gate artifact written to {output}")
    else:
        console.out(dumps_quality_gate_artifact(artifact), end="")


@quality_app.command("validate")
def validate(path: Path) -> None:
    """Validate a quality gate artifact without executing it."""
    errors = validate_quality_gate_artifact_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Quality gate artifact {path} is valid.")
