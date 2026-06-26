from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.agent_profiles import AgentProfileName, agent_profile_names
from builder_ii.config import load_settings
from builder_ii.deepagents_bridge import bridge_spec_for, deepagents_availability, render_bridge_spec, validate_bridge_spec
from builder_ii.target_profiles import TargetName, target_names, target_profile

bridge_app = typer.Typer(help="Render optional bridge specs.")
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


@bridge_app.command("doctor")
def doctor() -> None:
    """Report optional bridge dependency status."""
    availability = deepagents_availability()
    table = Table("Check", "Status", "Detail")
    table.add_row("deepagents import", "PASS" if availability.available else "MISS", availability.detail)
    table.add_row("runtime execution", "DISABLED", "bridge renders specs only")
    table.add_row("file writes", "DISABLED", "requires future HITL-gated capability")
    table.add_row("shell execution", "DISABLED", "requires future HITL-gated capability")
    if availability.source:
        table.add_row("source", availability.source, "")
    console.print(table)


@bridge_app.command("render")
def render(
    profile: str,
    target: str = typer.Option("generic", "--target", help="Target profile: generic, builder, core"),
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
) -> None:
    """Render a builder-II profile as a bridge spec."""
    settings = load_settings()
    selected_target = target_profile(settings, _target(target), generic_repo=generic_repo)
    spec = bridge_spec_for(_agent(profile), selected_target)
    errors = validate_bridge_spec(spec)
    if errors:
        for error in errors:
            console.print(error)
        raise typer.Exit(1)
    console.print(render_bridge_spec(spec))
