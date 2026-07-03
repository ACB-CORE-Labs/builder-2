from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.artifact_index_records import (
    create_artifact_index_record,
    dumps_artifact_index_record,
    validate_artifact_index_record,
    validate_artifact_index_record_file,
    write_artifact_index_record,
)
from builder_ii.cli.plain_stdout import echo_stdout

index_app = typer.Typer(help="Create and validate artifact index records.")
console = Console()


@index_app.command("record")
def record(
    root: Path,
    recursive: bool = typer.Option(False, "--recursive"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item = create_artifact_index_record(root, recursive=recursive)
    errors = validate_artifact_index_record(item)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_artifact_index_record(item, output)
        console.print(f"Artifact index record written to {output}")
    else:
        echo_stdout(dumps_artifact_index_record(item))


@index_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_artifact_index_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Artifact index record is valid: {path}")
