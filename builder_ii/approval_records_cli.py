from __future__ import annotations

from pathlib import Path
from typing import cast

import typer
from rich.console import Console

from builder_ii.approval_records import (
    ApprovalDecision,
    create_approval_record_from_file,
    dumps_approval_record,
    validate_approval_record_file,
    write_approval_record,
)

approval_app = typer.Typer(help="Create and validate approval record artifacts.")
console = Console()
_VALID_DECISIONS = {"approved", "rejected"}


def _decision(value: str) -> ApprovalDecision:
    if value not in _VALID_DECISIONS:
        console.print("decision must be approved or rejected")
        raise typer.Exit(1)
    return cast(ApprovalDecision, value)


@approval_app.command("record")
def record(
    proposal_path: Path = typer.Argument(..., help="Proposal artifact path"),
    decision: str = typer.Option(..., "--decision", help="Decision: approved or rejected"),
    decided_by: str = typer.Option(..., "--decided-by", help="Operator identifier"),
    reason: str = typer.Option("", "--reason", help="Decision reason"),
    output: Path | None = typer.Option(None, "--output", help="Write approval record JSON to path"),
) -> None:
    """Create an approval record artifact."""
    artifact, errors = create_approval_record_from_file(
        proposal_path,
        decision=_decision(decision),
        decided_by=decided_by,
        reason=reason,
    )
    if errors or artifact is None:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_approval_record(artifact, output)
        console.print(f"Approval record written to {output}")
    else:
        console.out(dumps_approval_record(artifact), end="")


@approval_app.command("validate")
def validate(path: Path) -> None:
    """Validate an approval record artifact."""
    errors = validate_approval_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Approval record is valid: {path}")
