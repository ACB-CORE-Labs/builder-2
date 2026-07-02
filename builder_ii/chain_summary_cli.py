from __future__ import annotations

import json
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


@chain_app.command("verify-artifacts")
def verify_artifacts(
    paths: list[Path] = typer.Argument(..., help="Paths to artifact JSON files to verify"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write verification report JSON to path"),
) -> None:
    """Validate a set of artifacts and verify their cross-record adjacency and digests."""
    from builder_ii.artifact_chain_verification import verify_artifact_chain

    report = verify_artifact_chain(paths)

    report_json = json.dumps(report, indent=2, sort_keys=True)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report_json + "\n", encoding="utf-8")
        console.print(f"Verification report written to {output}")
    else:
        console.out(report_json)

    if not report["valid"]:
        raise typer.Exit(1)

