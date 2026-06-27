from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from builder_ii.agent_profiles import AgentProfileName
from builder_ii.orchestration_plan import (
    create_orchestration_plan,
    dumps_orchestration_plan,
    validate_orchestration_plan,
    validate_orchestration_plan_file,
)
from builder_ii.target_profiles import TargetName

orchestration_app = typer.Typer(help="Create and validate governed agent orchestration plan artifacts.")
console = Console()
_VALID_TARGETS = {"generic", "builder", "core"}


def _normalize_target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _parse_roles(raw: Optional[str]) -> tuple[AgentProfileName, ...] | None:
    if not raw:
        return None
    roles = tuple(part.strip() for part in raw.split(",") if part.strip())
    return roles  # type: ignore[return-value]


@orchestration_app.command("plan")
def plan_orchestration(
    target: str = typer.Argument(..., help="Target profile name: generic | builder | core"),
    task: str = typer.Option("", "--task", help="Task description"),
    roles: Optional[str] = typer.Option(None, "--roles", help="Comma-separated agent role sequence"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON artifact to this path"),
) -> None:
    """Create a governed orchestration plan artifact without constructing agents."""
    target_norm = _normalize_target(target)
    try:
        parsed_roles = _parse_roles(roles)
        if parsed_roles is None:
            plan = create_orchestration_plan(target=target_norm, task=task)
        else:
            plan = create_orchestration_plan(target=target_norm, task=task, roles=parsed_roles)
    except ValueError as exc:
        console.print(f"[red]Error creating orchestration plan: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_orchestration_plan(plan)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in generated plan: {error}[/]")
        raise typer.Exit(1)

    serialized = dumps_orchestration_plan(plan)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        console.print(f"[green]Orchestration plan written to {output}[/]")
    else:
        console.out(serialized, end="")


@orchestration_app.command("validate")
def validate_orchestration(path: Path = typer.Argument(..., help="Path to orchestration plan JSON file")) -> None:
    """Validate a governed orchestration plan artifact file."""
    errors = validate_orchestration_plan_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Orchestration plan artifact {path} is valid.[/]")


if __name__ == "__main__":
    orchestration_app()
