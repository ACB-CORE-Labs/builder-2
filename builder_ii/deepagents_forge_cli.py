"""
deeagents_forge_cli.py

Typer CLI entry point for the deepagents Forge wizard.
Wired into deepagents_cli.py as the 'forge' subcommand.

Usage:
  bii deepagents forge                          # interactive TUI
  bii deepagents forge --name pr_reviewer       # pre-seed name
  bii deepagents forge --profile core           # pre-seed profile
  bii deepagents forge --dry-run                # preview only
  bii deepagents forge --non-interactive ...    # headless/CI mode

This module is generic-first and must not import CORE-specific modules.
"""

from __future__ import annotations

import sys
from typing import Optional

import typer

from builder_ii.deepagents_forge_schema import DeepAgentSpec, derive_slug
from builder_ii.deepagents_forge_emit import emit_agent, EmitResult

app = typer.Typer(help="deepagents Forge — interactively create deepagents.")


@app.command("forge")
def forge_agent(
    name: Optional[str] = typer.Option(
        None,
        "--name",
        "-n",
        help="Pre-seed the agent name.",
    ),
    profile: str = typer.Option(
        "generic",
        "--profile",
        "-p",
        help="Target profile: generic | builder | core.",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview what would be emitted without writing anything.",
    ),
    non_interactive: bool = typer.Option(
        False,
        "--non-interactive",
        help="Headless mode — supply all options via flags, no TUI.",
    ),
    # Headless-only options
    persona: Optional[str] = typer.Option(None, "--persona", help="Agent persona (headless mode)."),
    description: Optional[str] = typer.Option(None, "--description", help="Agent description (headless mode)."),
    capabilities: Optional[str] = typer.Option(
        None, "--capabilities", help="Comma-separated capabilities (headless mode)."
    ),
    hitl_gates: Optional[str] = typer.Option(
        None, "--hitl-gates", help="Comma-separated HITL gates (headless mode)."
    ),
    output_artifact: Optional[str] = typer.Option(
        None, "--output-artifact", help="Output artifact path (headless mode)."
    ),
    rollback_path: Optional[str] = typer.Option(
        None, "--rollback-path", help="Rollback path (headless mode)."
    ),
    verification_profile: str = typer.Option(
        "default",
        "--verification-profile",
        help="Verification profile name (headless mode).",
    ),
) -> None:
    """
    Interactively create a new deepagent through the builder-II Forge wizard.

    In interactive mode (default), launches the full Textual TUI wizard.
    In --non-interactive mode, builds the spec from flags and emits directly.
    """
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
    else:
        _run_interactive(
            seed_name=name or "",
            seed_profile=profile,
            dry_run=dry_run,
        )


def _split_csv(value: Optional[str]) -> list[str]:
    """Split a comma-separated string into a list, stripping whitespace."""
    if not value:
        return []
    return [v.strip() for v in value.split(",") if v.strip()]


def _run_interactive(
    seed_name: str = "",
    seed_profile: str = "generic",
    dry_run: bool = False,
) -> None:
    """Launch the Textual TUI forge wizard."""
    try:
        from builder_ii.deepagents_forge_tui import run_forge_tui
        run_forge_tui(seed_name=seed_name, seed_profile=seed_profile, dry_run=dry_run)
    except ImportError as e:
        typer.echo(f"\u274c  Textual TUI not available: {e}", err=True)
        typer.echo("   Install textual: pip install textual", err=True)
        raise typer.Exit(code=1)


def run_headless_forge(
    name: str,
    profile: str = "generic",
    dry_run: bool = False,
    persona: str = "",
    description: str = "",
    capabilities: Optional[list] = None,
    hitl_gates: Optional[list] = None,
    output_artifact: str = "",
    rollback_path: str = "",
    verification_profile: str = "default",
) -> EmitResult:
    """
    Build a DeepAgentSpec from explicit arguments and emit (no TUI).
    Safe for CI/scripted agent generation pipelines.
    """
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
