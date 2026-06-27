from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from builder_ii.config import load_settings
from builder_ii.session_workflow import (
    create_session_workflow_plan,
    validate_session_workflow_plan,
    validate_session_workflow_plan_file,
)

session_app = typer.Typer(help="Inspect and plan governed local developer sessions.")
console = Console()
_VALID_TARGETS: set[str] = {"generic", "builder", "core"}


def _normalize_target(value: str) -> str:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value


@session_app.command("plan")
def plan_session(
    target: str = typer.Argument(..., help="Target profile name: generic | builder | core"),
    agent: Optional[str] = typer.Option(None, "--agent", help="Explicit agent profile name override"),
    prompt: Optional[str] = typer.Option(None, "--prompt", help="Explicit prompt profile name override"),
    verification: Optional[str] = typer.Option(None, "--verification", help="Explicit verification profile name override"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", help="Explicit target repo path override (metadata only)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON plan artifact to this path"),
) -> None:
    """Generate a governed, local read-only session plan."""
    settings = load_settings()
    target_norm = _normalize_target(target)

    try:
        plan = create_session_workflow_plan(
            settings,
            target_norm,  # type: ignore[arg-type]
            agent_profile_name=agent,  # type: ignore[arg-type]
            prompt_profile_name=prompt,
            verification_profile_name=verification,  # type: ignore[arg-type]
            repo_path=repo_path,
        )
    except ValueError as exc:
        console.print(f"[red]Error resolving session plan parameters: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_session_workflow_plan(plan)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in generated plan: {error}[/]")
        raise typer.Exit(1)

    import json as json_lib
    serialized = json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"

    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
            console.print(f"[green]Session plan written to {output}[/]")
        except Exception as exc:
            console.print(f"[red]Failed to write output file: {exc}[/]")
            raise typer.Exit(1)
    else:
        console.out(serialized, end="")


@session_app.command("validate")
def validate_session(
    path: Path = typer.Argument(..., help="Path to session plan JSON file to validate")
) -> None:
    """Validate a session plan artifact file."""
    errors = validate_session_workflow_plan_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Session plan artifact {path} is valid.[/]")


if __name__ == "__main__":
    session_app()
