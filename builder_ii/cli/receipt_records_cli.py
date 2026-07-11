from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.receipt_records import (
    ReceiptStatus,
    create_receipt_record_from_file,
    dumps_receipt_record,
    validate_receipt_record_file,
    write_receipt_record,
)

receipt_app = typer.Typer(help="Create and validate receipt record artifacts.")
console = Console()
_VALID_STATUSES = {"passed", "failed", "blocked"}


def _status(value: str) -> ReceiptStatus:
    if value not in _VALID_STATUSES:
        console.print("status must be passed, failed, or blocked")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@receipt_app.command("record")
def record(
    preflight_path: Path,
    status: str = typer.Option(..., "--status"),
    recorded_by: str = typer.Option(..., "--recorded-by"),
    evidence_ref: list[str] | None = typer.Option(None, "--evidence-ref"),
    summary: str = typer.Option("", "--summary"),
    rollback_ref: list[str] | None = typer.Option(None, "--rollback-ref"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item, errors = create_receipt_record_from_file(
        preflight_path,
        status=_status(status),
        recorded_by=recorded_by,
        evidence_refs=evidence_ref or [],
        summary=summary,
        rollback_refs=rollback_ref or [],
    )
    if errors or item is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_receipt_record(item, output)
        console.print(f"Receipt record written to {output}")
    else:
        echo_stdout(dumps_receipt_record(item))


@receipt_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_receipt_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Receipt record is valid: {path}", soft_wrap=True)
