from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.core.config import load_settings
from builder_ii.lifecycle.setup.target_profiles import TargetName, target_profile
from builder_ii.routing.agent_profiles import (
    AgentProfileName,
    agent_profiles,
    create_agent_profile_record,
    dumps_agent_profile_record,
    get_agent_profile,
    profiles_for_target,
    render_agent_profile,
    validate_agent_profile_record,
    validate_agent_profile_record_file,
    validate_agent_profiles,
    write_agent_profile_record,
)

agent_app = typer.Typer(
    help="Inspect/render agent profiles; RO run candidate (read_only profiles only)."
)
console = Console()
_VALID_AGENTS = {profile.name for profile in agent_profiles()}
_VALID_TARGETS: set[str] = {"generic", "builder", "core"}


def _normalize_agent(value: str) -> AgentProfileName:
    if value not in _VALID_AGENTS:
        console.print("[red]unknown agent profile[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _normalize_target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@agent_app.command("profiles")
def profiles(
    target: str | None = typer.Option(None, "--target", help="Filter by target: generic, builder, core"),
) -> None:
    """List available generic agent profiles."""
    selected = None if target is None else _normalize_target(target)
    rows = profiles_for_target(selected) if selected is not None else agent_profiles()
    table = Table("Profile", "Authority", "Targets", "Description")
    for profile in rows:
        table.add_row(profile.name, profile.authority, ", ".join(profile.compatible_targets), profile.description)
    console.print(table)


@agent_app.command("show")
def show(name: str) -> None:
    """Show one generic agent profile without target rendering."""
    profile = get_agent_profile(_normalize_agent(name))
    console.print(render_agent_profile(profile))


@agent_app.command("render")
def render(
    name: str,
    target: str = typer.Option("generic", "--target", help="Target profile: generic, builder, core"),
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
) -> None:
    """Render an agent profile against a target profile."""
    settings = load_settings()
    profile = get_agent_profile(_normalize_agent(name))
    selected_target = target_profile(settings, _normalize_target(target), generic_repo=generic_repo)
    if selected_target.name not in profile.compatible_targets:
        console.print(f"[red]{profile.name} is not compatible with target {selected_target.name}[/]")
        raise typer.Exit(1)
    console.print(render_agent_profile(profile, selected_target))


@agent_app.command("validate")
def validate(path: Path | None = typer.Argument(None, help="Validate an agent profile record JSON file")) -> None:
    """Validate generic agent profile registry consistency or an artifact file."""
    if path:
        errors = validate_agent_profile_record_file(path)
        if errors:
            for error in errors:
                console.print(f"Validation error: {error}")
            raise typer.Exit(1)
        console.print(f"Agent profile record {path} is valid.", soft_wrap=True)
        return

    errors = validate_agent_profiles()
    if not errors:
        console.print("[green]Agent profiles valid[/]")
        return
    for error in errors:
        console.print(f"[red]{error}[/]")
    raise typer.Exit(1)


@agent_app.command("artifact")
def artifact(
    name: str,
    target: str = typer.Option("generic", "--target", help="Target profile: generic, builder, core"),
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
    task: str = typer.Option("", "--task", help="Optional task context"),
    output: Path | None = typer.Option(None, "--output", help="Write JSON artifact to path"),
) -> None:
    """Emit a no-runtime agent profile record artifact."""
    settings = load_settings()
    profile = get_agent_profile(_normalize_agent(name))
    selected_target = target_profile(settings, _normalize_target(target), generic_repo=generic_repo)
    if selected_target.name not in profile.compatible_targets:
        console.print(f"[red]{profile.name} is not compatible with target {selected_target.name}[/]")
        raise typer.Exit(1)

    record = create_agent_profile_record(profile, selected_target, task=task)
    errors = validate_agent_profile_record(record)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_agent_profile_record(record, output)
        console.print(f"Agent profile record written to {output}")
    else:
        echo_stdout(dumps_agent_profile_record(record))


@agent_app.command("run")
def run_cmd(
    profile: str = typer.Option(..., "--profile", "-p", help="Agent profile (read_only only)"),
    task: str = typer.Option(..., "--task", "-t", help="Inspection task text"),
    read_only: bool = typer.Option(True, "--read-only/--no-read-only", help="Must be true for V.2"),
    repo: Path = typer.Option(Path("."), "--repo", exists=True, file_okay=False),
    target: str = typer.Option("builder", "--target"),
    max_files: int = typer.Option(100, "--max-files", min=1, max=500),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """V.2: RO agent inspection candidate (code_reviewer/repo_mapper only).

    Requires --read-only. No deepagents construction, shell, writes, or model invoke.
    """
    from builder_ii.routing.agent_readonly_runner import AgentReadonlyError, run_readonly_agent

    if not read_only:
        console.print("[red]V.2 agent run requires --read-only (no write/shell path)[/]")
        raise typer.Exit(1)
    try:
        receipt = run_readonly_agent(
            profile_name=_normalize_agent(profile),
            task=task,
            repo_path=repo,
            target_name=_normalize_target(target),
            max_files=max_files,
        )
    except AgentReadonlyError as exc:
        console.print(f"[red]RO run refused: {exc}[/]")
        raise typer.Exit(1) from exc
    text = json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]Wrote RO receipt {output}[/]")
    else:
        echo_stdout(text)
    console.print(
        f"[green]RO run profile={receipt.get('profile_name')} "
        f"status={receipt.get('status')} deepagents={receipt.get('constructs_deepagents')}[/]"
    )
