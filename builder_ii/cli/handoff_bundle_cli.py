from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.handoff_bundle_records import (
    create_handoff_bundle_record_from_file,
    dumps_handoff_bundle_record,
    validate_handoff_bundle_record_file,
    write_handoff_bundle_record,
)

handoff_app = typer.Typer(help="Create and validate handoff bundle records.")
console = Console()


@handoff_app.command("record")
def record(
    summary_path: Path,
    bundle_name: str = typer.Option(..., "--bundle-name"),
    notes: str = typer.Option("", "--notes"),
    include_ref: list[str] | None = typer.Option(None, "--include-ref"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item, errors = create_handoff_bundle_record_from_file(
        summary_path,
        bundle_name=bundle_name,
        notes=notes,
        include_refs=include_ref or [],
    )
    if errors or item is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_handoff_bundle_record(item, output)
        console.print(f"Handoff bundle record written to {output}")
    else:
        echo_stdout(dumps_handoff_bundle_record(item))


@handoff_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_handoff_bundle_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Handoff bundle record is valid: {path}", soft_wrap=True)
