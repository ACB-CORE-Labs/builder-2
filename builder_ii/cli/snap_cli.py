from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.snapshot_records import (
    create_snapshot_record_from_files,
    dumps_snapshot_record,
    validate_snapshot_record_file,
    write_snapshot_record,
)

snap_app = typer.Typer(help="Snapshot record commands.")
console = Console()


@snap_app.command("record")
def record(
    artifact_index_path: Path,
    state_ledger_path: Path,
    snapshot_name: str = typer.Option(..., "--snapshot-name"),
    notes: str = typer.Option("", "--notes"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item, errors = create_snapshot_record_from_files(
        artifact_index_path, state_ledger_path, snapshot_name=snapshot_name, notes=notes
    )
    if errors or item is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_snapshot_record(item, output)
        console.print(f"Snapshot record written to {output}")
    else:
        echo_stdout(dumps_snapshot_record(item))


@snap_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_snapshot_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Snapshot record is valid: {path}", soft_wrap=True)
