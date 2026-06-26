from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.chain_summary_records import (
    create_chain_summary_record_from_files,
    dumps_chain_summary_record,
    validate_chain_summary_record_file,
    write_chain_summary_record,
)

chain_app = typer.Typer(help="Create and validate chain summary records.")
console = Console()


@chain_app.command("record")
def record(
    proposal_path: Path,
    approval_path: Path,
    preflight_path: Path,
    receipt_path: Path,
    summary: str = typer.Option("", "--summary"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item, errors = create_chain_summary_record_from_files(
        proposal_path,
        approval_path,
        preflight_path,
        receipt_path,
        summary=summary,
    )
    if errors or item is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_chain_summary_record(item, output)
        console.print(f"Chain summary record written to {output}")
    else:
        console.out(dumps_chain_summary_record(item), end="")


@chain_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_chain_summary_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Chain summary record is valid: {path}")
