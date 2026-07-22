from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.lifecycle.candidate.promotion_decision_records import (
    PromotionDecision,
    create_promotion_decision_record_from_file,
    dumps_promotion_decision_record,
    validate_promotion_decision_record_file,
    write_promotion_decision_record,
)

promotion_decision_app = typer.Typer(help="Create and validate promotion decision records.")
console = Console()
_VALID_DECISIONS = {"approved", "blocked"}


def _decision(value: str) -> PromotionDecision:
    if value not in _VALID_DECISIONS:
        console.print("decision must be approved or blocked")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@promotion_decision_app.command("record")
def record(
    readiness_path: Path,
    decision: str = typer.Option(..., "--decision"),
    decided_by: str = typer.Option(..., "--decided-by"),
    reason: str = typer.Option("", "--reason"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    item, errors = create_promotion_decision_record_from_file(
        readiness_path,
        decision=_decision(decision),
        decided_by=decided_by,
        reason=reason,
    )
    if errors or item is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_promotion_decision_record(item, output)
        console.print(f"Promotion decision record written to {output}")
    else:
        echo_stdout(dumps_promotion_decision_record(item))


@promotion_decision_app.command("validate")
def validate(path: Path) -> None:
    errors = validate_promotion_decision_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Promotion decision record is valid: {path}", soft_wrap=True)
