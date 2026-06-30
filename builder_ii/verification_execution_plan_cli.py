from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.target_profiles import target_names
from builder_ii.verification_execution_approval import (
    dumps_verification_execution_approval,
    finalize_verification_execution_approval,
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
    validate_verification_execution_approval_file,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_plan import (
    dumps_verification_execution_plan,
    finalize_verification_execution_plan,
    validate_verification_execution_plan_artifact,
    validate_verification_execution_plan_file,
    write_verification_execution_plan,
)
from builder_ii.verification_execution_receipt import (
    validate_verification_execution_receipt_against_plan_and_approval,
    validate_verification_execution_receipt_file,
)
from builder_ii.verification_execution_runner import run_approved_verification
from builder_ii.verification_profiles import verification_profile_names


verify_app = typer.Typer(help="Render, approve, validate, and run bounded verification artifacts.")
console = Console()


def _target_profile(value: str) -> str:
    if value not in target_names():
        console.print("target-profile must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value


def _verification_profile(value: str) -> str:
    if value not in verification_profile_names():
        console.print("verification-profile must be a known verification profile")
        raise typer.Exit(1)
    return value


def _print_validation_errors(errors: list[str]) -> None:
    for error in errors:
        console.print(f"Validation error: {error}")


def _read_json_object(path: Path) -> dict[str, Any]:
    return json_lib.loads(path.read_text(encoding="utf-8"))


@verify_app.command("plan")
def plan(
    target_profile: str = typer.Option(..., "--target-profile", help="Target profile: generic, builder, core"),
    verification_profile: str = typer.Option(..., "--verification-profile", help="Verification profile name"),
    output: Path = typer.Option(..., "--output", help="Explicit JSON artifact path to write"),
    target_repo: str = typer.Option(".", "--target-repo", help="Target repository path recorded in the plan"),
    artifact_root: str = typer.Option(".builder/verification", "--artifact-root", help="Artifact root recorded in the plan"),
) -> None:
    """Emit a planned-only verification execution plan without running verification."""
    artifact = finalize_verification_execution_plan(
        target_profile=_target_profile(target_profile),
        verification_profile=_verification_profile(verification_profile),
        target_repo=target_repo,
        artifact_root=artifact_root,
    )
    errors = validate_verification_execution_plan_artifact(artifact)
    if errors:
        _print_validation_errors(errors)
        raise typer.Exit(1)
    try:
        write_verification_execution_plan(artifact, output)
    except OSError as exc:
        console.print(f"Verification execution plan could not be written: {exc}")
        raise typer.Exit(1) from None
    console.out(dumps_verification_execution_plan(artifact), end="")


@verify_app.command("validate-plan")
def validate_plan(
    path: Path = typer.Argument(..., help="Path to a verification execution plan JSON artifact"),
) -> None:
    """Validate a verification execution plan artifact without running verification."""
    errors = validate_verification_execution_plan_file(path)
    report = {"valid": not errors, "errors": errors, "path": str(path)}
    console.out(json_lib.dumps(report, indent=2, sort_keys=True) + "\n", end="")
    if errors:
        raise typer.Exit(1)


@verify_app.command("approve-plan")
def approve_plan(
    plan_path: Path = typer.Argument(..., help="Path to a passive verification execution plan JSON artifact"),
    approval_actor: str = typer.Option(..., "--approval-actor", help="Human operator approving the plan digest"),
    approval_reason: str = typer.Option(..., "--approval-reason", help="Reason for the digest-bound approval"),
    output: Path = typer.Option(..., "--output", help="Explicit JSON approval artifact path to write"),
) -> None:
    """Emit a HITL approval artifact bound to an exact passive verification execution plan digest."""
    plan_errors = validate_verification_execution_plan_file(plan_path)
    if plan_errors:
        _print_validation_errors(plan_errors)
        raise typer.Exit(1)

    plan = _read_json_object(plan_path)
    artifact = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor=approval_actor,
        approval_reason=approval_reason,
    )
    errors = validate_verification_execution_approval_artifact(artifact)
    errors.extend(validate_verification_execution_approval_against_plan(artifact, plan))
    if errors:
        _print_validation_errors(errors)
        raise typer.Exit(1)
    try:
        write_verification_execution_approval(artifact, output)
    except OSError as exc:
        console.print(f"Verification execution approval could not be written: {exc}")
        raise typer.Exit(1) from None
    console.out(dumps_verification_execution_approval(artifact), end="")


@verify_app.command("validate-approval")
def validate_approval(
    path: Path = typer.Argument(..., help="Path to a verification execution approval JSON artifact"),
    plan: Path = typer.Option(..., "--plan", help="Path to the referenced verification execution plan JSON artifact"),
) -> None:
    """Validate a HITL plan approval artifact against its referenced passive plan."""
    errors = validate_verification_execution_approval_file(path)
    plan_errors = validate_verification_execution_plan_file(plan)
    errors.extend(plan_errors)
    if not errors:
        approval_data = _read_json_object(path)
        plan_data = _read_json_object(plan)
        errors.extend(validate_verification_execution_approval_against_plan(approval_data, plan_data))

    report = {"valid": not errors, "errors": errors, "path": str(path), "plan_path": str(plan)}
    console.out(json_lib.dumps(report, indent=2, sort_keys=True) + "\n", end="")
    if errors:
        raise typer.Exit(1)


@verify_app.command("validate-receipt")
def validate_receipt(
    path: Path = typer.Argument(..., help="Path to a verification execution receipt JSON artifact"),
    plan: Path = typer.Option(..., "--plan", help="Path to the referenced verification execution plan JSON artifact"),
    approval: Path = typer.Option(..., "--approval", help="Path to the referenced verification execution approval JSON artifact"),
) -> None:
    """Validate a verification execution receipt against its referenced plan and approval."""
    errors = validate_verification_execution_receipt_file(path)
    plan_errors = validate_verification_execution_plan_file(plan)
    approval_errors = validate_verification_execution_approval_file(approval)
    errors.extend(plan_errors)
    errors.extend(approval_errors)
    if not errors:
        receipt_data = _read_json_object(path)
        plan_data = _read_json_object(plan)
        approval_data = _read_json_object(approval)
        errors.extend(
            validate_verification_execution_receipt_against_plan_and_approval(
                receipt_data,
                plan_data,
                approval_data,
            )
        )

    report = {
        "valid": not errors,
        "errors": errors,
        "path": str(path),
        "plan_path": str(plan),
        "approval_path": str(approval),
    }
    console.out(json_lib.dumps(report, indent=2, sort_keys=True) + "\n", end="")
    if errors:
        raise typer.Exit(1)


@verify_app.command("run-approved")
def run_approved(
    plan_path: Path = typer.Option(..., "--plan", help="Path to the referenced verification execution plan JSON artifact"),
    approval_path: Path = typer.Option(..., "--approval", help="Path to the referenced verification execution approval JSON artifact"),
    output: Path = typer.Option(..., "--output", help="Explicit receipt artifact path to write"),
    profile: str = typer.Option("platform_status", "--profile", help="Approved bounded command profile to run"),
) -> None:
    """Run one bounded, approval-bound verification profile and emit a receipt."""
    try:
        receipt = run_approved_verification(
            plan_path=plan_path,
            approval_path=approval_path,
            output=output,
            requested_profile=profile,
        )
    except (OSError, json_lib.JSONDecodeError) as exc:
        console.print(f"Verification runner could not start: {exc}")
        raise typer.Exit(1) from None
    console.out(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n", end="")
    if not receipt.get("valid", False):
        raise typer.Exit(1)
