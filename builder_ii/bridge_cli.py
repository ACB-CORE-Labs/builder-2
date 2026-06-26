from __future__ import annotations

import json as json_lib
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


def _print_deepagents_smoke() -> None:
    availability = deepagents_availability()
    table = Table("Check", "Status", "Detail")
    for check, status, detail in availability.rows():
        table.add_row(check, status, detail)
    console.print(table)


@bridge_app.command("doctor")
def doctor() -> None:
    """Report optional bridge dependency status."""
    _print_deepagents_smoke()


@bridge_app.command("deepagents-smoke")
def deepagents_smoke(
    json_output: bool = typer.Option(False, "--json", help="Print JSON readiness report."),
    output: Path | None = typer.Option(None, "--output", help="Write JSON readiness report to path."),
) -> None:
    """Run the optional deepagents import/readiness smoke check without enabling runtime."""
    availability = deepagents_availability()
    if json_output or output is not None:
        payload = availability.to_json_dict()
        text = json_lib.dumps(payload, indent=2, sort_keys=True) + "\n"
        if json_output:
            console.print(text, end="")
        if output is not None:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8")
    else:
        _print_deepagents_smoke()


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
