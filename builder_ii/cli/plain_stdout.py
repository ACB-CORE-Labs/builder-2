"""Plain stdout helpers for machine-parseable CLI output."""

from __future__ import annotations

import typer


def echo_stdout(text: str) -> None:
    """Write text to stdout without Rich markup or ANSI escape codes."""
    typer.echo(text, nl=False)
