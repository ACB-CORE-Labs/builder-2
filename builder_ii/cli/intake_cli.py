from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.receive_records import (
    ReceiveDecision,
    create_receive_record_from_file,
    dumps_receive_record,
    validate_receive_record_file,
    write_receive_record,
)

intake_app = typer.Typer(help="Create and validate intake records.")
console = Console()
_VALID_DECISIONS = {"accepted", "blocked"}


def _decision(value: str) -> ReceiveDecision:
    if value not in _VALID_DECISIONS:
        console.print("decision must be accepted or blocked")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@intake_app.command("record")
def record(
    bundle_path: Path,
    decision: str = typer.Option(..., "--decision"),
    received_by: str = typer.Option(..., "--received-by"),
    notes: str = typer.Option("", "--notes"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item, errors = create_receive_record_from_file(
        bundle_path, decision=_decision(decision), received_by=received_by, notes=notes
    )
    if errors or item is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_receive_record(item, output)
        console.print(f"Intake record written to {output}")
    else:
        console.out(dumps_receive_record(item), end="")


@intake_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_receive_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Intake record is valid: {path}")
