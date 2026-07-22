from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.lifecycle.candidate.preflight_records import (
    create_preflight_record_from_files,
    dumps_preflight_record,
    validate_preflight_record_file,
    write_preflight_record,
)

preflight_app = typer.Typer(help="Preflight artifact helpers.")
console = Console()


@preflight_app.command("record")
def record(
    proposal_path: Path,
    approval_path: Path,
    verification_ref: list[str] | None = typer.Option(None, "--verification-ref"),
    rollback_ref: list[str] | None = typer.Option(None, "--rollback-ref"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item, errors = create_preflight_record_from_files(
        proposal_path,
        approval_path,
        verification_refs=verification_ref or [],
        rollback_refs=rollback_ref or [],
    )
    if errors or item is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_preflight_record(item, output)
        console.print(f"Preflight record written to {output}")
    else:
        echo_stdout(dumps_preflight_record(item))


@preflight_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_preflight_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Preflight record is valid: {path}", soft_wrap=True)
