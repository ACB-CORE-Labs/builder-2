from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.promotion_compatibility import parse_support_artifact_ref
from builder_ii.promotion_readiness_records import (
    create_promotion_readiness_record,
    dumps_promotion_readiness_record,
    validate_promotion_readiness_record,
    validate_promotion_readiness_record_file,
    write_promotion_readiness_record,
)

promotion_app = typer.Typer(help="Create and validate promotion readiness records.")
console = Console()


@promotion_app.command("record")
def record(
    capability_name: str = typer.Option(..., "--capability-name"),
    target_state: str = typer.Option("enabled", "--target-state"),
    target: str = typer.Option("", "--target"),
    docs_ref: list[str] | None = typer.Option(None, "--docs-ref"),
    tests_ref: list[str] | None = typer.Option(None, "--tests-ref"),
    cli_ref: list[str] | None = typer.Option(None, "--cli-ref"),
    failure_mode_ref: list[str] | None = typer.Option(None, "--failure-mode-ref"),
    approval_boundary_ref: list[str] | None = typer.Option(None, "--approval-boundary-ref"),
    output_artifact_ref: list[str] | None = typer.Option(None, "--output-artifact-ref"),
    rollback_ref: list[str] | None = typer.Option(None, "--rollback-ref"),
    verification_ref: list[str] | None = typer.Option(None, "--verification-ref"),
    support_artifact: list[str] | None = typer.Option(None, "--support-artifact"),
    notes: str = typer.Option("", "--notes"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item = create_promotion_readiness_record(
        capability_name=capability_name,
        target_state=target_state,
        target=target,
        docs_refs=docs_ref or [],
        tests_refs=tests_ref or [],
        cli_refs=cli_ref or [],
        failure_mode_refs=failure_mode_ref or [],
        approval_boundary_refs=approval_boundary_ref or [],
        output_artifact_refs=output_artifact_ref or [],
        rollback_refs=rollback_ref or [],
        verification_refs=verification_ref or [],
        support_artifacts=[parse_support_artifact_ref(item) for item in (support_artifact or [])],
        notes=notes,
    )
    errors = validate_promotion_readiness_record(item)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_promotion_readiness_record(item, output)
        console.print(f"Promotion readiness record written to {output}")
    else:
        console.out(dumps_promotion_readiness_record(item), end="")


@promotion_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_promotion_readiness_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Promotion readiness record is valid: {path}")
