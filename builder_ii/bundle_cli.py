from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.agent_profiles import AgentProfileName, agent_profile_names
from builder_ii.bundles import (
    create_target_bundle,
    dumps_bundle,
    validate_target_bundle,
    validate_target_bundle_file,
    write_bundle,
)
from builder_ii.config import load_settings
from builder_ii.target_profiles import TargetName, target_names

bundle_app = typer.Typer(help="Create and validate governed target bundle artifacts.")
console = Console()
_VALID_AGENTS = set(agent_profile_names())
_VALID_TARGETS = set(target_names())


def _agent(value: str) -> AgentProfileName:
    if value not in _VALID_AGENTS:
        console.print("unknown agent profile")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@bundle_app.command("create")
def create(
    target: str = typer.Option("builder", "--target", help="Target profile: generic, builder, core"),
    agent: str = typer.Option("patch_planner", "--agent", help="Agent profile to bind into the bundle"),
    task: str = typer.Option("", "--task", help="Optional task description for the bundle"),
    output: Path | None = typer.Option(None, "--output", help="Write bundle JSON to path"),
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
) -> None:
    """Create a governed, no-runtime target bundle artifact."""
    settings = load_settings()
    bundle = create_target_bundle(
        settings,
        target_name=_target(target),
        agent_profile=_agent(agent),
        task=task,
        generic_repo=generic_repo,
    )
    errors = validate_target_bundle(bundle)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_bundle(bundle, output)
        console.print(f"Bundle written to {output}")
    else:
        console.out(dumps_bundle(bundle), end="")


@bundle_app.command("validate")
def validate(path: Path) -> None:
    """Validate a governed target bundle artifact without executing it."""
    errors = validate_target_bundle_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Bundle {path} is valid.")
