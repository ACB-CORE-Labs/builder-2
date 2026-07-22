from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.core.git_state import (
    create_git_state_record,
    dumps_git_state_record,
    validate_git_state_record,
    validate_git_state_record_file,
    write_git_state_record,
)

git_state_app = typer.Typer(help="Manage governed git state artifacts.")
console = Console()
_VALID_TARGETS: set[str] = {"core", "builder", "generic"}
_VALID_STATES: set[str] = {"clean", "dirty"}


@git_state_app.command("artifact")
def artifact(
    target: str = typer.Option("core", "--target", help="Repository target: core, builder, or generic"),
    branch: str = typer.Option(..., "--branch", help="Name of current git branch"),
    commit_sha: str = typer.Option(..., "--commit-sha", help="40-character git commit SHA"),
    state: str = typer.Option(..., "--state", help="State of the repository: clean or dirty"),
    modified: list[str] = typer.Option([], "--modified", help="Modified file path relative to repo root (repeatable)"),
    untracked: list[str] = typer.Option(
        [], "--untracked", help="Untracked file path relative to repo root (repeatable)"
    ),
    output: Path | None = typer.Option(None, "--output", help="Write JSON artifact to path"),
) -> None:
    """Emit a no-runtime git state record artifact."""
    if target not in _VALID_TARGETS:
        console.print(f"[red]--target must be one of: {', '.join(_VALID_TARGETS)}[/]")
        raise typer.Exit(1)

    if state not in _VALID_STATES:
        console.print(f"[red]--state must be one of: {', '.join(_VALID_STATES)}[/]")
        raise typer.Exit(1)

    record = create_git_state_record(
        target=target,  # type: ignore[arg-type]
        branch=branch,
        commit_sha=commit_sha,
        state=state,  # type: ignore[arg-type]
        modified_files=modified,
        untracked_files=untracked,
    )

    errors = validate_git_state_record(record)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)

    if output is not None:
        write_git_state_record(record, output)
        console.print(f"Git state record written to {output}")
    else:
        echo_stdout(dumps_git_state_record(record))


@git_state_app.command("validate")
def validate(path: Path = typer.Argument(..., help="Path to git state record JSON file")) -> None:
    """Validate a git state record artifact file."""
    errors = validate_git_state_record_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"Git state record {path} is valid.", soft_wrap=True)
