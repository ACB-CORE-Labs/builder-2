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
    TARGET_CODE_EXECUTING_PROFILES,
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
from builder_ii.verification_promotion_gate import (
    dumps_promotion_evidence,
    evaluate_verification_promotion_gates_from_files,
    validate_promotion_evidence,
    write_promotion_evidence,
)

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
    artifact_root: str = typer.Option(
        ".builder/verification", "--artifact-root", help="Artifact root recorded in the plan"
    ),
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
    typer.echo(dumps_verification_execution_plan(artifact), nl=False)


@verify_app.command("validate-plan")
def validate_plan(
    path: Path = typer.Argument(..., help="Path to a verification execution plan JSON artifact"),
) -> None:
    """Validate a verification execution plan artifact without running verification."""
    errors = validate_verification_execution_plan_file(path)
    report = {"valid": not errors, "errors": errors, "path": str(path)}
    typer.echo(json_lib.dumps(report, indent=2, sort_keys=True), nl=False)
    if errors:
        raise typer.Exit(1)


_DEFAULT_ACKNOWLEDGED_RISK = (
    "Operator acknowledges that the approved verification profile executes the target repository's "
    "own code, including transitively imported configuration and plugin code, on this host with the "
    "operator's privileges."
)


@verify_app.command("approve-plan")
def approve_plan(
    plan_path: Path = typer.Argument(..., help="Path to a passive verification execution plan JSON artifact"),
    approval_actor: str = typer.Option(..., "--approval-actor", help="Human operator approving the plan digest"),
    approval_reason: str = typer.Option(..., "--approval-reason", help="Reason for the digest-bound approval"),
    output: Path = typer.Option(..., "--output", help="Explicit JSON approval artifact path to write"),
    profile: list[str] = typer.Option(
        [],
        "--profile",
        help="Command profile(s) to approve (repeatable). Default: all safe profiles in the plan.",
    ),
    acknowledge_execution_risk: bool = typer.Option(
        False,
        "--acknowledge-execution-risk",
        help="Acknowledge that an approved target-code profile (pytest_full/builder_full) runs the "
        "target repo's own code on this host. Required to approve such a profile.",
    ),
    acknowledged_risk: str = typer.Option(
        "", "--acknowledged-risk", help="Custom acknowledgment wording (defaults to the canonical statement)."
    ),
) -> None:
    """Emit a HITL approval artifact bound to an exact passive verification execution plan digest."""
    plan_errors = validate_verification_execution_plan_file(plan_path)
    if plan_errors:
        _print_validation_errors(plan_errors)
        raise typer.Exit(1)

    plan = _read_json_object(plan_path)
    selected = list(profile) or None
    target_code_selected = [name for name in (selected or []) if name in TARGET_CODE_EXECUTING_PROFILES]

    ack_flag = False
    ack_text: str | None = None
    if target_code_selected:
        # D7 approve-time prompt: state plainly what a target-code profile does before approving it.
        console.print(
            f"[bold yellow]Execution-risk notice[/bold yellow]: profile(s) "
            f"{', '.join(target_code_selected)} run the target repository's own code. pytest imports "
            "and executes the target repo's conftest.py, plugins, and test modules on THIS host with "
            "your user privileges. This bounds invocation, not code behavior -- it is not a sandbox."
        )
        if not acknowledge_execution_risk:
            console.print(
                "Refusing to approve a target-code profile without acknowledgment. "
                "Re-run with --acknowledge-execution-risk to proceed."
            )
            raise typer.Exit(1)
        ack_flag = True
        ack_text = acknowledged_risk.strip() or _DEFAULT_ACKNOWLEDGED_RISK

    artifact = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor=approval_actor,
        approval_reason=approval_reason,
        approved_command_profiles=selected,
        approved_step_ids=selected,
        execution_risk_acknowledged=ack_flag,
        acknowledged_risk=ack_text,
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
    typer.echo(dumps_verification_execution_approval(artifact), nl=False)


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
    typer.echo(json_lib.dumps(report, indent=2, sort_keys=True), nl=False)
    if errors:
        raise typer.Exit(1)


@verify_app.command("validate-receipt")
def validate_receipt(
    path: Path = typer.Argument(..., help="Path to a verification execution receipt JSON artifact"),
    plan: Path = typer.Option(..., "--plan", help="Path to the referenced verification execution plan JSON artifact"),
    approval: Path = typer.Option(
        ..., "--approval", help="Path to the referenced verification execution approval JSON artifact"
    ),
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
    typer.echo(json_lib.dumps(report, indent=2, sort_keys=True), nl=False)
    if errors:
        raise typer.Exit(1)


@verify_app.command("evaluate-promotion")
def evaluate_promotion(
    plan: Path = typer.Option(..., "--plan", help="Path to the verification execution plan JSON"),
    approval: Path = typer.Option(..., "--approval", help="Path to the verification execution approval JSON"),
    receipt: Path = typer.Option(..., "--receipt", help="Path to the verification execution receipt JSON"),
    ledger: Path | None = typer.Option(
        None, "--ledger", help="Optional path to a verification execution ledger record JSON"
    ),
    capability_name: str = typer.Option("", "--capability-name", help="Capability name under promotion review"),
    expected_profile: str | None = typer.Option(
        None, "--expected-profile", help="Optional profile that must appear in receipt process_results"
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional promotion-evidence artifact path"),
) -> None:
    """B2.0: evaluate machine-checkable promotion gates over a verification chain (no authority)."""
    try:
        evidence = evaluate_verification_promotion_gates_from_files(
            plan_path=plan,
            approval_path=approval,
            receipt_path=receipt,
            ledger_path=ledger,
            capability_name=capability_name,
            expected_profile=expected_profile,
        )
    except (OSError, ValueError, json_lib.JSONDecodeError) as exc:
        console.print(f"[red]failed to evaluate promotion gates: {exc}[/]")
        raise typer.Exit(1) from exc
    errors = validate_promotion_evidence(evidence)
    if errors:
        console.print(f"[red]invalid promotion evidence: {'; '.join(errors)}[/]")
        raise typer.Exit(1)
    if output is not None:
        write_promotion_evidence(evidence, output.resolve())
    console.out(dumps_promotion_evidence(evidence), end="")
    if evidence.get("overall_state") != "PASS":
        raise typer.Exit(2)


@verify_app.command("validate-promotion-evidence")
def validate_promotion_evidence_cmd(
    path: Path = typer.Argument(..., help="Path to a verification promotion evidence JSON artifact"),
) -> None:
    """Validate a B2.0 promotion-evidence artifact (schema + non-authority invariants)."""
    try:
        data = _read_json_object(path)
    except (OSError, ValueError, json_lib.JSONDecodeError) as exc:
        console.print(f"[red]failed to load promotion evidence: {exc}[/]")
        raise typer.Exit(1) from exc
    errors = validate_promotion_evidence(data)
    report = {"valid": not errors, "errors": errors, "path": str(path)}
    console.out(json_lib.dumps(report, indent=2, sort_keys=True) + "\n", end="")
    if errors:
        raise typer.Exit(1)


@verify_app.command("run-approved")
def run_approved(
    plan_path: Path = typer.Option(
        ..., "--plan", help="Path to the referenced verification execution plan JSON artifact"
    ),
    approval_path: Path = typer.Option(
        ..., "--approval", help="Path to the referenced verification execution approval JSON artifact"
    ),
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
    typer.echo(json_lib.dumps(receipt, indent=2, sort_keys=True), nl=False)
    if not receipt.get("valid", False):
        raise typer.Exit(1)
