from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.execution_candidate_manifest_cli import register_manifest_commands
from builder_ii.cli.hitl_patch_cli import register_patch_commands
from builder_ii.cli.hitl_promotion_cli import register_promotion_commands
from builder_ii.hitl_command_runner import execute_hitl_command
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_EXECUTION_REQUEST_KIND,
    create_hitl_execution_receipt,
    create_hitl_execution_request,
    validate_hitl_execution_receipt,
    validate_hitl_execution_receipt_file,
    validate_hitl_execution_request,
    validate_hitl_execution_request_file,
    write_hitl_execution_receipt,
    write_hitl_execution_request,
)

hitl_app = typer.Typer(help="HITL execution request/receipt artifact CLI (No Execution).")
console = Console()
register_promotion_commands(hitl_app)
register_manifest_commands(hitl_app)
register_patch_commands(hitl_app)


@hitl_app.command("request")
def request(
    target_name: str = typer.Option("generic", "--target-name", help="Target profile name"),
    command_proposal_ref: str = typer.Option(..., "--command-proposal-ref", help="Proposal record reference"),
    approval_record_ref: str = typer.Option(..., "--approval-record-ref", help="Approval record reference"),
    preflight_record_ref: str = typer.Option(..., "--preflight-record-ref", help="Preflight record reference"),
    requested_by: str = typer.Option(..., "--requested-by", help="Operator/agent requesting execution"),
    requested_at: str = typer.Option(..., "--requested-at", help="Timestamp of request"),
    explicit_operator_intent: str = typer.Option(..., "--explicit-operator-intent", help="Explicit intent statement"),
    command_preview: str = typer.Option(..., "--command-preview", help="Proposed command preview"),
    output: Path = typer.Option(..., "--output", help="Output path for the request artifact"),
) -> None:
    """Create a HITL execution request artifact."""
    try:
        artifact = create_hitl_execution_request(
            target_name=target_name,  # type: ignore[arg-type]
            command_proposal_ref=command_proposal_ref,
            approval_record_ref=approval_record_ref,
            preflight_record_ref=preflight_record_ref,
            requested_by=requested_by,
            requested_at=requested_at,
            explicit_operator_intent=explicit_operator_intent,
            command_preview=command_preview,
        )
    except Exception as exc:
        console.print(f"Validation error: {exc}")
        raise typer.Exit(1)

    errors = validate_hitl_execution_request(artifact)
    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_hitl_execution_request(artifact, output)
        console.print(f"HITL execution request written to {output}")
    except Exception as exc:
        console.print(f"Write error: {exc}")
        raise typer.Exit(1)


@hitl_app.command("receipt")
def receipt(
    target_name: str = typer.Option("generic", "--target-name", help="Target profile name"),
    request_ref: str = typer.Option(..., "--request-ref", help="Request artifact reference"),
    output: Path = typer.Option(..., "--output", help="Output path for the receipt artifact"),
) -> None:
    """Create a NOT_EXECUTED receipt artifact."""
    try:
        artifact = create_hitl_execution_receipt(
            target_name=target_name,  # type: ignore[arg-type]
            request_ref=request_ref,
        )
    except Exception as exc:
        console.print(f"Validation error: {exc}")
        raise typer.Exit(1)

    errors = validate_hitl_execution_receipt(artifact)
    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        write_hitl_execution_receipt(artifact, output)
        console.print(f"HITL execution receipt written to {output}")
    except Exception as exc:
        console.print(f"Write error: {exc}")
        raise typer.Exit(1)


@hitl_app.command("run-command")
def run_command(
    request: Path = typer.Option(..., "--request", help="HITL execution request artifact JSON path"),
    proposal: Path = typer.Option(..., "--proposal", help="Goose command proposal artifact JSON path"),
    approval: Path = typer.Option(..., "--approval", help="Approval record artifact JSON path"),
    output_dir: Path = typer.Option(..., "--output-dir", help="Output directory for generated artifacts"),
) -> None:
    """Execute an approved command under governed HITL authority."""
    try:
        execute_hitl_command(
            request_path=request,
            proposal_path=proposal,
            approval_path=approval,
            output_dir=output_dir,
        )
        console.print(f"Command executed. Artifacts written to {output_dir}")
    except Exception as e:
        console.print(f"Failed to execute command: {e}")
        raise typer.Exit(1)


@hitl_app.command("validate")
def validate(
    path: Path = typer.Argument(..., help="Path to request or receipt artifact JSON file"),
) -> None:
    """Validate a request or receipt artifact by kind."""
    if not path.exists():
        console.print(f"Validation error: file not found: {path}")
        raise typer.Exit(1)

    try:
        content = path.read_text(encoding="utf-8")
        data = json_lib.loads(content)
    except Exception as exc:
        console.print(f"Validation error: invalid JSON: {exc}")
        raise typer.Exit(1)

    if not isinstance(data, dict):
        console.print("Validation error: artifact must be a JSON object")
        raise typer.Exit(1)

    kind = data.get("kind")
    if kind == HITL_EXECUTION_REQUEST_KIND:
        errors = validate_hitl_execution_request_file(path)
    elif kind == HITL_EXECUTION_RECEIPT_KIND:
        errors = validate_hitl_execution_receipt_file(path)
    else:
        errors = [f"unknown or unsupported artifact kind: {kind}"]

    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    console.print(f"Artifact is valid: {path}")
