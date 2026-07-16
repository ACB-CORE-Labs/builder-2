"""
deepagents_forge_cli.py

Typer CLI entry point for the deepagents Forge wizard.
This module is generic-first and must not import CORE-specific modules.
"""

from __future__ import annotations

from typing import Optional

import typer

from builder_ii.command_authority import CommandAuthorityError, enforce_command_authority
from builder_ii.deepagents_forge_emit import EmitResult, emit_agent
from builder_ii.deepagents_forge_schema import VALID_TARGET_PROFILES, DeepAgentSpec, derive_slug

app = typer.Typer(help="deepagents Forge — create governed deepagent specs.")
_VALID_PROFILES = set(VALID_TARGET_PROFILES)


@app.callback(invoke_without_command=True)
def forge_agent(
    ctx: typer.Context,
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Pre-seed the agent name."),
    profile: str = typer.Option("generic", "--profile", "-p", help="Target profile: generic | builder | core."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without writing anything."),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Headless mode."),
    persona: Optional[str] = typer.Option(None, "--persona", help="Agent persona."),
    description: Optional[str] = typer.Option(None, "--description", help="Agent description."),
    capabilities: Optional[str] = typer.Option(None, "--capabilities", help="Comma-separated capabilities."),
    hitl_gates: Optional[str] = typer.Option(None, "--hitl-gates", help="Comma-separated HITL gates."),
    output_artifact: Optional[str] = typer.Option(None, "--output-artifact", help="Output artifact path."),
    rollback_path: Optional[str] = typer.Option(None, "--rollback-path", help="Rollback path."),
    verification_profile: str = typer.Option("default", "--verification-profile", help="Verification profile name."),
) -> None:
    """Create a new deepagent through the builder-II Forge wizard."""
    if ctx.invoked_subcommand is not None:
        return

    if profile not in _VALID_PROFILES:
        typer.echo("profile must be one of: generic, builder, core", err=True)
        raise typer.Exit(code=1)

    try:
        enforce_command_authority(
            "builder-deepagents forge",
            requested_effects=() if dry_run else ("artifact_write",),
        )
    except CommandAuthorityError as exc:
        typer.echo(f"Command authority denied: {exc}", err=True)
        raise typer.Exit(code=1) from None

    if non_interactive:
        result = run_headless_forge(
            name=name or "",
            profile=profile,
            dry_run=dry_run,
            persona=persona or "",
            description=description or "",
            capabilities=_split_csv(capabilities),
            hitl_gates=_split_csv(hitl_gates),
            output_artifact=output_artifact or "",
            rollback_path=rollback_path or "",
            verification_profile=verification_profile,
        )
        for line in result.as_lines():
            typer.echo(line)
        if not result.ok:
            raise typer.Exit(code=1)
        return

    _run_interactive(seed_name=name or "", seed_profile=profile, dry_run=dry_run)


def _split_csv(value: Optional[str]) -> list[str]:
    """Split a comma-separated string into a list, stripping whitespace."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _run_interactive(seed_name: str = "", seed_profile: str = "generic", dry_run: bool = False) -> None:
    """Launch the Textual TUI forge wizard."""
    try:
        from builder_ii.deepagents_forge_tui import run_forge_tui

        run_forge_tui(seed_name=seed_name, seed_profile=seed_profile, dry_run=dry_run)
    except ImportError as exc:
        typer.echo(f"Textual TUI not available: {exc}", err=True)
        typer.echo("Install textual: pip install textual", err=True)
        raise typer.Exit(code=1) from exc


def run_headless_forge(
    name: str,
    profile: str = "generic",
    dry_run: bool = False,
    persona: str = "",
    description: str = "",
    capabilities: Optional[list[str]] = None,
    hitl_gates: Optional[list[str]] = None,
    output_artifact: str = "",
    rollback_path: str = "",
    verification_profile: str = "default",
) -> EmitResult:
    """Build a DeepAgentSpec from explicit arguments and emit without TUI."""
    spec = DeepAgentSpec(
        name=name,
        slug=derive_slug(name),
        description=description,
        target_profile=profile,
        persona=persona,
        capabilities=capabilities or [],
        hitl_gates=hitl_gates or [],
        output_artifact=output_artifact,
        rollback_path=rollback_path,
        verification_profile=verification_profile,
    )
    return emit_agent(spec, dry_run=dry_run)


if __name__ == "__main__":
    app()
