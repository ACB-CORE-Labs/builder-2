from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.config import load_settings
from builder_ii.target_profiles import TargetName, build_target_profiles, render_target_profile, target_profile, validate_target_profiles

targets_app = typer.Typer(help="Inspect builder-II target profiles.")
console = Console()
_VALID_TARGETS: set[str] = {"generic", "builder", "core"}


def _normalize_target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@targets_app.command("list")
def list_targets(generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target")) -> None:
    """List available target profiles."""
    settings = load_settings()
    table = Table("Target", "Repository", "Context defaults", "Description")
    for profile in build_target_profiles(settings, generic_repo=generic_repo):
        table.add_row(profile.name, str(profile.repo), str(len(profile.context_defaults)), profile.description)
    console.print(table)


@targets_app.command("show")
def show_target(name: str, generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target")) -> None:
    """Show one target profile."""
    settings = load_settings()
    profile = target_profile(settings, _normalize_target(name), generic_repo=generic_repo)
    console.print(render_target_profile(profile))


@targets_app.command("validate")
def validate() -> None:
    """Validate target profile registry consistency."""
    settings = load_settings()
    errors = validate_target_profiles(settings)
    if not errors:
        console.print("[green]Target profiles valid[/]")
        return
    for error in errors:
        console.print(f"[red]{error}[/]")
    raise typer.Exit(1)
