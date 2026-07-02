from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.agent_profiles import AgentProfileName, agent_profile_names
from builder_ii.handoff_artifacts import (
    create_handoff_artifact,
    dumps_handoff_artifact,
    validate_handoff_artifact,
    validate_handoff_artifact_file,
    write_handoff_artifact,
)
from builder_ii.target_profiles import TargetName, target_names

notes_app = typer.Typer(help="Create and validate governed handoff artifacts.")
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


@notes_app.command("handoff")
def handoff(
    target: str = typer.Option("builder", "--target", help="Target profile: generic, builder, core"),
    agent: str = typer.Option("handoff_scribe", "--agent", help="Agent profile responsible for the handoff"),
    task: str = typer.Option(..., "--task", help="Task being handed off"),
    summary: str = typer.Option(..., "--summary", help="Concise handoff summary"),
    next_steps: list[str] = typer.Option([], "--next", help="Repeatable next step"),
    blockers: list[str] = typer.Option([], "--blocker", help="Repeatable blocker"),
    verification: list[str] = typer.Option([], "--verification", help="Repeatable verification evidence item"),
    output: Path | None = typer.Option(None, "--output", help="Write handoff JSON artifact to path"),
) -> None:
    """Create a governed handoff artifact without mutating notes or running tools."""
    artifact = create_handoff_artifact(
        target=_target(target),
        agent_profile=_agent(agent),
        task=task,
        summary=summary,
        next_steps=tuple(next_steps),
        blockers=tuple(blockers),
        verification=tuple(verification),
    )
    errors = validate_handoff_artifact(artifact)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_handoff_artifact(artifact, output)
        console.print(f"Handoff artifact written to {output}")
    else:
        console.out(dumps_handoff_artifact(artifact), end="")


@notes_app.command("validate")
def validate(path: Path) -> None:
    """Validate a handoff artifact without executing it."""
    errors = validate_handoff_artifact_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Handoff artifact {path} is valid.")
