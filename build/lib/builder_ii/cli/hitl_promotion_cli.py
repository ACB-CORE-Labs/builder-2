from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.hitl_promotion_artifacts import (
    HITL_APPROVAL_BOUNDARY_KIND,
    HITL_PROMOTION_DECISION_KIND,
    HITL_PROMOTION_REQUEST_KIND,
    HITL_PROMOTION_REVIEW_KIND,
    HITL_PROMOTION_VALIDATION_REPORT_KIND,
    HITL_REJECTION_RECORD_KIND,
    _create_ref,
    create_hitl_approval_boundary,
    create_hitl_promotion_decision,
    create_hitl_promotion_request,
    create_hitl_promotion_review,
    create_hitl_rejection_record,
    validate_hitl_approval_boundary,
    validate_hitl_promotion_decision,
    validate_hitl_promotion_request,
    validate_hitl_promotion_review,
    validate_hitl_promotion_validation_report,
    validate_hitl_rejection_record,
    write_hitl_promotion_artifact,
)

hitl_promotion_app = typer.Typer(help="HITL passive promotion bridge CLI.")
console = Console()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        console.print(f"Error: file not found or is not a file: {path}")
        raise typer.Exit(1)
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            console.print(f"Error: JSON object required in {path}")
            raise typer.Exit(1)
        return data
    except Exception as exc:
        console.print(f"Error reading JSON from {path}: {exc}")
        raise typer.Exit(1)


@hitl_promotion_app.command("promotion-request")
def promotion_request(
    proposal_path: Path = typer.Option(..., "--proposal-path", help="Path to Goal 2 or Goal 3 proposal artifact"),
    output: Path = typer.Option(..., "--output", help="Output path for the promotion request JSON"),
    requested_by: str = typer.Option("operator", "--requested-by", help="Operator or agent requesting promotion"),
    reason: str = typer.Option("", "--reason", help="Reason for promotion request"),
    target_profile_path: Path | None = typer.Option(
        None, "--target-profile-path", help="Optional path to target profile artifact"
    ),
    session_manifest_path: Path | None = typer.Option(
        None, "--session-manifest-path", help="Optional path to session manifest"
    ),
) -> None:
    """Create a passive HITL promotion request artifact."""
    proposal = _load_json(proposal_path)
    proposal_ref = _create_ref(proposal, path=proposal_path, role="proposal")

    target_ref = None
    if target_profile_path is not None:
        tdata = _load_json(target_profile_path)
        target_ref = _create_ref(tdata, path=target_profile_path, role="target_profile")

    session_ref = None
    if session_manifest_path is not None:
        sdata = _load_json(session_manifest_path)
        session_ref = _create_ref(sdata, path=session_manifest_path, role="session_manifest")

    data = create_hitl_promotion_request(
        proposal=proposal,
        proposal_path=proposal_path,
        proposal_ref=proposal_ref,
        target_profile_ref=target_ref,
        session_manifest_ref=session_ref,
        requested_by=requested_by,
        reason=reason,
    )

    errors = validate_hitl_promotion_request(data)
    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    write_hitl_promotion_artifact(data, output)
    console.print(f"Promotion request written to {output}")


@hitl_promotion_app.command("promotion-review")
def promotion_review(
    request_path: Path = typer.Option(..., "--request-path", help="Path to promotion request artifact"),
    output: Path = typer.Option(..., "--output", help="Output path for review artifact"),
    disposition: str = typer.Option(
        "acceptable_for_decision",
        "--disposition",
        help="Review disposition: acceptable_for_decision, needs_revision, or blocked",
    ),
    reviewed_by: str = typer.Option("operator", "--reviewed-by", help="Reviewer identity"),
    recommendation: str = typer.Option("", "--recommendation", help="Recommendation summary"),
    finding: list[str] = typer.Option(None, "--finding", help="Review finding (can be repeated)"),
    warning: list[str] = typer.Option(None, "--warning", help="Review warning (can be repeated)"),
    blocking_issue: list[str] = typer.Option(None, "--blocking-issue", help="Blocking issue (can be repeated)"),
    policy_path: Path | None = typer.Option(None, "--policy-path", help="Optional path to policy artifact"),
) -> None:
    """Create a passive HITL promotion review artifact."""
    req_data = _load_json(request_path)
    req_ref = _create_ref(req_data, path=request_path, role="promotion_request")

    policy_ref = None
    if policy_path is not None:
        pdata = _load_json(policy_path)
        policy_ref = _create_ref(pdata, path=policy_path, role="policy")

    data = create_hitl_promotion_review(
        promotion_request=req_data,
        promotion_request_path=request_path,
        promotion_request_ref=req_ref,
        policy_ref=policy_ref,
        disposition=disposition,
        findings=finding or [],
        warnings=warning or [],
        blocking_issues=blocking_issue or [],
        recommendation=recommendation,
        reviewed_by=reviewed_by,
    )

    errors = validate_hitl_promotion_review(data)
    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    write_hitl_promotion_artifact(data, output)
    console.print(f"Promotion review written to {output}")


@hitl_promotion_app.command("promotion-decision")
def promotion_decision(
    request_path: Path = typer.Option(..., "--request-path", help="Path to promotion request artifact"),
    review_path: Path = typer.Option(..., "--review-path", help="Path to promotion review artifact"),
    output: Path = typer.Option(..., "--output", help="Output path for decision artifact"),
    decision_result: str = typer.Option(
        ...,
        "--decision-result",
        help="Decision result: approved_for_candidate_design, rejected, or needs_revision",
    ),
    decided_by: str = typer.Option("operator", "--decided-by", help="Operator making decision"),
    reason: str = typer.Option("", "--reason", help="Decision rationale"),
    blocker: list[str] = typer.Option(None, "--blocker", help="Unresolved blocker (can be repeated)"),
) -> None:
    """Create a passive HITL promotion decision artifact."""
    req_data = _load_json(request_path)
    req_ref = _create_ref(req_data, path=request_path, role="promotion_request")

    rev_data = _load_json(review_path)
    rev_ref = _create_ref(rev_data, path=review_path, role="promotion_review")

    data = create_hitl_promotion_decision(
        promotion_request_ref=req_ref,
        promotion_review_ref=rev_ref,
        decision_result=decision_result,
        decided_by=decided_by,
        reason=reason,
        blockers=blocker or [],
        source_review_disposition=str(rev_data.get("disposition", "")),
        source_review_blocking_issues=rev_data.get("blocking_issues", []),
    )

    errors = validate_hitl_promotion_decision(data)
    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    write_hitl_promotion_artifact(data, output)
    console.print(f"Promotion decision written to {output}")


@hitl_promotion_app.command("approval-boundary")
def approval_boundary(
    decision_path: Path = typer.Option(..., "--decision-path", help="Path to promotion decision artifact"),
    request_path: Path = typer.Option(..., "--request-path", help="Path to promotion request artifact"),
    output: Path = typer.Option(..., "--output", help="Output path for approval boundary artifact"),
    allowed_profile: list[str] = typer.Option(None, "--allowed-profile", help="Allowed profile name (can be repeated)"),
    denied_boundary: list[str] = typer.Option(
        None, "--denied-boundary", help="Denied boundary description (can be repeated)"
    ),
) -> None:
    """Create a passive HITL approval boundary artifact."""
    dec_data = _load_json(decision_path)
    dec_ref = _create_ref(dec_data, path=decision_path, role="promotion_decision")

    req_data = _load_json(request_path)
    req_ref = _create_ref(req_data, path=request_path, role="promotion_request")

    profiles = allowed_profile if allowed_profile else ["generic"]
    denied = denied_boundary if denied_boundary else ["runtime execution", "memory mutation", "target repo writes"]

    data = create_hitl_approval_boundary(
        promotion_decision_ref=dec_ref,
        promotion_request_ref=req_ref,
        permitted_candidate_scope={"allowed_profiles": profiles},
        denied_boundaries=denied,
        source_decision_result=str(dec_data.get("decision_result", "")),
        source_decision_record_state=str(dec_data.get("record_state", "")),
    )

    errors = validate_hitl_approval_boundary(data)
    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    write_hitl_promotion_artifact(data, output)
    console.print(f"Approval boundary written to {output}")


@hitl_promotion_app.command("rejection-record")
def rejection_record(
    request_path: Path = typer.Option(..., "--request-path", help="Path to promotion request artifact"),
    output: Path = typer.Option(..., "--output", help="Output path for rejection record"),
    rationale: str = typer.Option(..., "--rationale", help="Rejection rationale"),
    rejected_by: str = typer.Option("operator", "--rejected-by", help="Operator identity"),
    decision_path: Path | None = typer.Option(None, "--decision-path", help="Optional path to decision artifact"),
) -> None:
    """Create a passive HITL rejection record artifact."""
    req_data = _load_json(request_path)
    req_ref = _create_ref(req_data, path=request_path, role="promotion_request")

    dec_ref = None
    if decision_path is not None:
        dec_data = _load_json(decision_path)
        dec_ref = _create_ref(dec_data, path=decision_path, role="promotion_decision")

    data = create_hitl_rejection_record(
        promotion_request_ref=req_ref,
        promotion_decision_ref=dec_ref,
        rationale=rationale,
        rejected_by=rejected_by,
    )

    errors = validate_hitl_rejection_record(data)
    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    write_hitl_promotion_artifact(data, output)
    console.print(f"Rejection record written to {output}")


@hitl_promotion_app.command("validate-promotion")
def validate_promotion(
    paths: list[Path] = typer.Argument(..., help="Paths to promotion bridge artifact JSON files"),
) -> None:
    """Validate passive HITL promotion bridge artifact files against schema."""
    all_errors: list[str] = []
    for path in paths:
        if not path.is_file():
            all_errors.append(f"File not found or is not a file: {path}")
            continue
        try:
            data = json_lib.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            all_errors.append(f"Invalid JSON in {path}: {exc}")
            continue
        if not isinstance(data, dict):
            all_errors.append(f"Artifact in {path} must be a JSON object")
            continue

        kind = data.get("kind")
        if kind == HITL_PROMOTION_REQUEST_KIND:
            errs = validate_hitl_promotion_request(data)
        elif kind == HITL_PROMOTION_REVIEW_KIND:
            errs = validate_hitl_promotion_review(data)
        elif kind == HITL_PROMOTION_DECISION_KIND:
            errs = validate_hitl_promotion_decision(data)
        elif kind == HITL_APPROVAL_BOUNDARY_KIND:
            errs = validate_hitl_approval_boundary(data)
        elif kind == HITL_REJECTION_RECORD_KIND:
            errs = validate_hitl_rejection_record(data)
        elif kind == HITL_PROMOTION_VALIDATION_REPORT_KIND:
            errs = validate_hitl_promotion_validation_report(data)
        else:
            errs = [f"Unknown or unsupported promotion artifact kind: {kind} in {path}"]

        if errs:
            for e in errs:
                all_errors.append(f"{path}: {e}")

    if all_errors:
        for err in all_errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    console.print("All promotion bridge artifacts valid.")


def register_promotion_commands(target_app: typer.Typer) -> None:
    """Register all promotion subcommands onto another Typer app (such as hitl_app)."""
    target_app.command("promotion-request")(promotion_request)
    target_app.command("promotion-review")(promotion_review)
    target_app.command("promotion-decision")(promotion_decision)
    target_app.command("approval-boundary")(approval_boundary)
    target_app.command("rejection-record")(rejection_record)
    target_app.command("validate-promotion")(validate_promotion)
