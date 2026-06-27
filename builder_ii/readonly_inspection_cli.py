from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.readonly_inspection_reports import (
    create_readonly_inspection_report,
    dumps_readonly_inspection_report,
    validate_readonly_inspection_report,
    validate_readonly_inspection_report_file,
    write_readonly_inspection_report,
)
from builder_ii.target_profiles import TargetName, target_names

readonly_app = typer.Typer(help="Create and validate explicit read-only inspection reports.")
console = Console()
_VALID_TARGETS = set(target_names())


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@readonly_app.command("report")
def report(
    path: list[Path] = typer.Option(..., "--path", help="Explicit file path to inspect. Repeat for multiple files."),
    target: str = typer.Option("generic", "--target"),
    purpose: str = typer.Option("orientation", "--purpose", help="orientation|review|verification_planning"),
    root: Path | None = typer.Option(None, "--root", help="Optional root boundary; paths outside are rejected."),
    note: str = typer.Option("", "--note"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item = create_readonly_inspection_report(
        target=_target(target),
        purpose=purpose,
        paths=path,
        root=root,
        operator_note=note,
    )
    errors = validate_readonly_inspection_report(item)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_readonly_inspection_report(item, output)
        console.print(f"Readonly inspection report written to {output}")
    else:
        console.out(dumps_readonly_inspection_report(item), end="")


@readonly_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_readonly_inspection_report_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Readonly inspection report {path} is valid.")
