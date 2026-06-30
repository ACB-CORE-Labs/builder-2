from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.target_profiles import target_names
from builder_ii.verification_execution_plan import (
    dumps_verification_execution_plan,
    finalize_verification_execution_plan,
    validate_verification_execution_plan_artifact,
    validate_verification_execution_plan_file,
    write_verification_execution_plan,
)
from builder_ii.verification_profiles import verification_profile_names


verify_app = typer.Typer(help="Render and validate passive verification execution plan artifacts.")
console = Console()


def _target_profile(value: str) -> str:
    if value not in target_names():
        console.print("target-profile must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value


def _verification_profile(value: str) -> str:
    if value not in verification_profile_names():
        console.print("verification-profile must be a known verification profile")
        raise typer.Exit(1)
    return value


@verify_app.command("plan")
def plan(
    target_profile: str = typer.Option(..., "--target-profile", help="Target profile: generic, builder, core"),
    verification_profile: str = typer.Option(..., "--verification-profile", help="Verification profile name"),
    output: Path = typer.Option(..., "--output", help="Explicit JSON artifact path to write"),
    target_repo: str = typer.Option(".", "--target-repo", help="Target repository path recorded in the plan"),
    artifact_root: str = typer.Option(".builder/verification", "--artifact-root", help="Artifact root recorded in the plan"),
) -> None:
    """Emit a planned-only verification execution plan without running verification."""
    artifact = finalize_verification_execution_plan(
        target_profile=_target_profile(target_profile),
        verification_profile=_verification_profile(verification_profile),
        target_repo=target_repo,
        artifact_root=artifact_root,
    )
    errors = validate_verification_execution_plan_artifact(artifact)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    try:
        write_verification_execution_plan(artifact, output)
    except OSError as exc:
        console.print(f"Verification execution plan could not be written: {exc}")
        raise typer.Exit(1) from None
    console.out(dumps_verification_execution_plan(artifact), end="")


@verify_app.command("validate-plan")
def validate_plan(
    path: Path = typer.Argument(..., help="Path to a verification execution plan JSON artifact"),
) -> None:
    """Validate a verification execution plan artifact without running verification."""
    errors = validate_verification_execution_plan_file(path)
    report = {"valid": not errors, "errors": errors, "path": str(path)}
    console.out(json_lib.dumps(report, indent=2, sort_keys=True) + "\n", end="")
    if errors:
        raise typer.Exit(1)
