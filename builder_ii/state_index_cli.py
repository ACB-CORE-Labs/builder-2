from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.state_ledger_records import (
    create_state_ledger_record_from_files,
    dumps_state_ledger_record,
    validate_state_ledger_record_file,
    write_state_ledger_record,
)

state_index_app = typer.Typer(help="Create and validate state index records.")
console = Console()


@state_index_app.command("record")
def record(
    decision_path: list[Path] = typer.Argument(...),
    ledger_name: str = typer.Option(..., "--ledger-name"),
    notes: str = typer.Option("", "--notes"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item, errors = create_state_ledger_record_from_files(decision_path, ledger_name=ledger_name, notes=notes)
    if errors or item is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_state_ledger_record(item, output)
        console.print(f"State index record written to {output}")
    else:
        console.out(dumps_state_ledger_record(item), end="")


@state_index_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_state_ledger_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"State index record is valid: {path}")
