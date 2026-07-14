"""Clean entrypoint: ``builder-stratum`` → experimental STRATUM operator console.

Equivalent to ``builder stratum --experimental`` with the same guide flags.
"""

from __future__ import annotations

import typer

from builder_ii.cli.main import console

stratum_app = typer.Typer(
    name="builder-stratum",
    help="Launch STRATUM — builder-II operator console (experimental, observe + compose).",
    add_completion=False,
    invoke_without_command=True,
)


@stratum_app.callback()
def main(
    no_guide: bool = typer.Option(
        False,
        "--no-guide",
        help="Skip first-session walkthrough auto-open (also: STRATUM_SKIP_GUIDE=1).",
    ),
    guide: bool = typer.Option(
        False,
        "--guide",
        help="Force first-session walkthrough open even if previously dismissed.",
    ),
    no_splash: bool = typer.Option(
        False,
        "--no-splash",
        help="Skip the opening hero splash (image / ASCII).",
    ),
) -> None:
    """Start STRATUM with the experimental gate already satisfied."""
    from builder_ii.command_authority import enforce_command_authority

    enforce_command_authority("builder stratum")

    if guide and no_guide:
        console.print("[red]--guide and --no-guide are mutually exclusive.[/]")
        raise typer.Exit(1)

    try:
        from builder_ii.tui.app import StratumApp
    except ImportError:
        console.print("[red]TUI dependencies not found.[/] Run [bold]uv sync[/] to install textual.")
        raise typer.Exit(1) from None

    console.print(
        "[bold cyan]STRATUM[/] — builder-II operator console\n"
        "[dim]observe + compose only · docs/STRATUM.md · H help · 0 walkthrough[/]"
    )
    app = StratumApp(show_guide=guide or None, skip_guide=no_guide, show_splash=not no_splash)
    app.run()


if __name__ == "__main__":
    stratum_app()
