from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.execution_candidate_manifest import (
    EXECUTION_CANDIDATE_MANIFEST_KIND,
    EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND,
    create_execution_candidate_manifest,
    validate_execution_candidate_manifest,
    validate_execution_candidate_manifest_validation_report,
    write_execution_candidate_manifest,
)
from builder_ii.hitl_promotion_artifacts import (
    _create_ref,
    validate_hitl_approval_boundary,
)

manifest_cli_app = typer.Typer(help="HITL candidate manifest CLI.")
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


@manifest_cli_app.command("candidate-manifest")
def candidate_manifest(
    approval_boundary_path: Path = typer.Option(
        ..., "--approval-boundary-path", help="Path to approval boundary JSON"
    ),
    decision_path: Path = typer.Option(
        ..., "--decision-path", help="Path to promotion decision JSON"
    ),
    review_path: Path = typer.Option(
        ..., "--review-path", help="Path to promotion review JSON"
    ),
    request_path: Path = typer.Option(
        ..., "--request-path", help="Path to promotion request JSON"
    ),
    source_proposal_path: list[Path] = typer.Option(
        ..., "--source-proposal-path", help="Path(s) to source proposal JSONs"
    ),
    target_profile_path: Path = typer.Option(
        ..., "--target-profile-path", help="Path to target profile JSON"
    ),
    command_authority_path: Path = typer.Option(
        ..., "--command-authority-path", help="Path to command authority JSON"
    ),
    verification_profile_path: Path = typer.Option(
        ..., "--verification-profile-path", help="Path to verification profile JSON"
    ),
    output: Path = typer.Option(
        ..., "--output", help="Output path for the candidate manifest JSON"
    ),
    command_preview: list[str] = typer.Option(
        None, "--command-preview", help="Inert command previews to include"
    ),
    no_mutation_assertion: bool = typer.Option(
        False, "--no-mutation-assertion", help="Assert that no mutation occurs"
    ),
    rollback_plan_path: Path | None = typer.Option(
        None, "--rollback-plan-path", help="Optional path to rollback plan JSON"
    ),
    git_state_path: Path | None = typer.Option(
        None, "--git-state-path", help="Optional path to git state JSON"
    ),
    preflight_path: Path | None = typer.Option(
        None, "--preflight-path", help="Optional path to preflight JSON"
    ),
    chain_verification_report_path: Path | None = typer.Option(
        None,
        "--chain-verification-report-path",
        help="Optional path to chain verification report JSON",
    ),
    specialized_candidate_path: Path | None = typer.Option(
        None,
        "--specialized-candidate-path",
        help="Optional path to specialized candidate JSON",
    ),
) -> None:
    """Create a passive candidate execution manifest."""
    boundary = _load_json(approval_boundary_path)
    dec = _load_json(decision_path)
    rev = _load_json(review_path)
    req = _load_json(request_path)
    target = _load_json(target_profile_path)
    cmd_auth = _load_json(command_authority_path)
    ver_prof = _load_json(verification_profile_path)

    boundary_errors = validate_hitl_approval_boundary(boundary)
    if boundary_errors:
        for err in boundary_errors:
            console.print(f"Approval boundary validation error: {err}")
        raise typer.Exit(1)

    boundary_ref = _create_ref(
        boundary, path=approval_boundary_path, role="approval_boundary"
    )
    dec_ref = _create_ref(dec, path=decision_path, role="promotion_decision")
    rev_ref = _create_ref(rev, path=review_path, role="promotion_review")
    req_ref = _create_ref(req, path=request_path, role="promotion_request")

    proposal_refs = []
    for p_path in source_proposal_path:
        p_data = _load_json(p_path)
        proposal_refs.append(_create_ref(p_data, path=p_path, role="source_proposal"))

    target_ref = _create_ref(target, path=target_profile_path, role="target_profile")
    cmd_auth_ref = _create_ref(
        cmd_auth, path=command_authority_path, role="command_authority"
    )
    ver_prof_ref = _create_ref(
        ver_prof, path=verification_profile_path, role="verification_profile"
    )

    rollback_plan_ref = None
    if rollback_plan_path is not None:
        rb_data = _load_json(rollback_plan_path)
        rollback_plan_ref = _create_ref(
            rb_data, path=rollback_plan_path, role="rollback_plan"
        )

    git_state_ref = None
    if git_state_path is not None:
        git_data = _load_json(git_state_path)
        git_state_ref = _create_ref(git_data, path=git_state_path, role="git_state")

    preflight_ref = None
    if preflight_path is not None:
        pf_data = _load_json(preflight_path)
        preflight_ref = _create_ref(pf_data, path=preflight_path, role="preflight")

    chain_ref = None
    if chain_verification_report_path is not None:
        chain_data = _load_json(chain_verification_report_path)
        chain_ref = _create_ref(
            chain_data,
            path=chain_verification_report_path,
            role="chain_verification_report",
        )

    spec_ref = None
    if specialized_candidate_path is not None:
        spec_data = _load_json(specialized_candidate_path)
        spec_ref = _create_ref(
            spec_data, path=specialized_candidate_path, role="specialized_candidate"
        )

    rollback_reqs = {
        "rollback_required": True,
        "no_mutation_assertion": no_mutation_assertion,
    }
    verification_reqs = {
        "verification_required": True,
    }

    target_name = target.get("name", "generic")
    candidate_scope = {
        "target_profile": target_name,
        "core_workbench_coupling": "NONE",
    }
    if command_preview:
        candidate_scope["command_previews"] = command_preview

    source_approval_boundary_record_state = boundary.get("record_state")
    source_approval_boundary_decision_result = boundary.get("source_decision_result")
    source_approval_boundary_decision_record_state = boundary.get(
        "source_decision_record_state"
    )
    source_approval_boundary_requires_separate_execution_candidate = boundary.get(
        "requires_separate_execution_candidate"
    )

    manifest = create_execution_candidate_manifest(
        approval_boundary_ref=boundary_ref,
        promotion_decision_ref=dec_ref,
        promotion_review_ref=rev_ref,
        promotion_request_ref=req_ref,
        source_proposal_refs=proposal_refs,
        target_profile_ref=target_ref,
        command_authority_ref=cmd_auth_ref,
        verification_profile_ref=ver_prof_ref,
        rollback_requirements=rollback_reqs,
        verification_requirements=verification_reqs,
        candidate_scope=candidate_scope,
        source_approval_boundary_record_state=source_approval_boundary_record_state,
        source_approval_boundary_decision_result=source_approval_boundary_decision_result,
        source_approval_boundary_decision_record_state=source_approval_boundary_decision_record_state,
        source_approval_boundary_requires_separate_execution_candidate=source_approval_boundary_requires_separate_execution_candidate,
        rollback_plan_ref=rollback_plan_ref,
        git_state_ref=git_state_ref,
        preflight_ref=preflight_ref,
        artifact_chain_verification_report_ref=chain_ref,
        specialized_candidate_ref=spec_ref,
    )

    errors = validate_execution_candidate_manifest(manifest)
    if errors:
        for err in errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    write_execution_candidate_manifest(manifest, output)
    console.print(f"Execution candidate manifest written to {output}")


@manifest_cli_app.command("validate-candidate-manifest")
def validate_candidate_manifest(
    paths: list[Path] = typer.Argument(
        ..., help="Paths to candidate manifest artifact JSON files"
    ),
) -> None:
    """Validate candidate manifest and validation report files."""
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
        if kind == EXECUTION_CANDIDATE_MANIFEST_KIND:
            errs = validate_execution_candidate_manifest(data)
        elif kind == EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND:
            errs = validate_execution_candidate_manifest_validation_report(data)
        else:
            errs = [
                f"Unknown or unsupported candidate manifest artifact kind: {kind} in {path}"
            ]

        if errs:
            for e in errs:
                all_errors.append(f"{path}: {e}")

    if all_errors:
        for err in all_errors:
            console.print(f"Validation error: {err}")
        raise typer.Exit(1)

    console.print("All candidate manifest artifacts valid.")


def register_manifest_commands(target_app: typer.Typer) -> None:
    """Register all candidate manifest subcommands onto target_app."""
    target_app.command("candidate-manifest")(candidate_manifest)
    target_app.command("validate-candidate-manifest")(validate_candidate_manifest)
