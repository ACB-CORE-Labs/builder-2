from __future__ import annotations

import json
from pathlib import Path

from builder_ii.hitl_execution_cli import hitl_app
from typer.testing import CliRunner

from builder_ii.artifact_chain_verification import extract_references
from builder_ii.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY, TIER_1
from builder_ii.execution_candidate_manifest import (
    EXECUTION_CANDIDATE_MANIFEST_KIND,
    EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND,
    create_execution_candidate_manifest,
    create_execution_candidate_manifest_validation_report,
    validate_execution_candidate_manifest,
    validate_execution_candidate_manifest_validation_report,
)
from builder_ii.hitl_promotion_artifacts import (
    HITL_APPROVAL_BOUNDARY_KIND,
    HITL_PROMOTION_DECISION_KIND,
    HITL_PROMOTION_REQUEST_KIND,
    HITL_PROMOTION_REVIEW_KIND,
)

runner = CliRunner()


def _ref(kind: str, path: str = "file.json", sha256: str = "a" * 64) -> dict:
    return {"kind": kind, "path": path, "sha256": sha256}


def _boundary_data() -> dict:
    return {
        "kind": HITL_APPROVAL_BOUNDARY_KIND,
        "schema_version": 1,
        "record_state": "BOUNDARY_RECORDED_ONLY",
        "source_decision_result": "approved_for_candidate_design",
        "source_decision_record_state": "DECISION_RECORDED_ONLY",
        "requires_separate_execution_candidate": True,
        "promotion_decision_ref": _ref(HITL_PROMOTION_DECISION_KIND, "decision.json"),
        "promotion_request_ref": _ref(HITL_PROMOTION_REQUEST_KIND, "request.json"),
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "constructs_subagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "runtime_execution": False,
        "source_writes": False,
        "memory_mutation": False,
        "artifact_is_authority": False,
        "bypasses_command_authority": False,
        "bypasses_verification": False,
        "grants_runtime_authority": False,
        "authorizes_execution": False,
        "grants_authority": False,
        "core_workbench_coupling": "NONE",
        "governance": {
            "capability_state": "BOUNDARY_RECORDED_ONLY",
            "executes_model": False,
            "executes_tools": False,
            "executes_shell": False,
            "invokes_goose": False,
            "constructs_deepagents": False,
            "constructs_subagents": False,
            "invokes_mcp": False,
            "performs_network_calls": False,
            "mutates_target_repo": False,
            "mutates_memory": False,
            "runtime_execution": False,
            "source_writes": False,
            "memory_mutation": False,
            "artifact_is_authority": False,
            "bypasses_command_authority": False,
            "bypasses_verification": False,
            "grants_runtime_authority": False,
            "authorizes_execution": False,
            "grants_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def _decision_data() -> dict:
    return {
        "kind": HITL_PROMOTION_DECISION_KIND,
        "schema_version": 1,
        "record_state": "DECISION_RECORDED_ONLY",
        "decision_result": "approved_for_candidate_design",
        "source_review_disposition": "acceptable_for_decision",
        "source_review_blocking_issues": [],
        "records_human_decision": True,
        "requires_separate_execution_candidate": True,
    }


def _review_data() -> dict:
    return {
        "kind": HITL_PROMOTION_REVIEW_KIND,
        "schema_version": 1,
        "record_state": "REVIEWED_ONLY",
        "disposition": "acceptable_for_decision",
    }


def _request_data() -> dict:
    return {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "schema_version": 1,
        "record_state": "REQUESTED_ONLY",
    }


def _proposal_data() -> dict:
    return {
        "kind": "builder_ii.orchestration_assignment_plan",
        "schema_version": 1,
        "status": "planned",
    }


def _target_profile_data(name: str = "generic") -> dict:
    return {
        "kind": "builder_ii.target_profile",
        "schema_version": 1,
        "name": name,
        "repo": "/tmp/repo",
    }


def _cmd_auth_data() -> dict:
    return {
        "kind": "builder_ii.command_authority",
        "schema_version": 1,
    }


def _ver_profile_data() -> dict:
    return {
        "kind": "builder_ii.verification_profile",
        "schema_version": 1,
    }


def _mock_valid_manifest() -> dict:
    return create_execution_candidate_manifest(
        approval_boundary_ref=_ref(HITL_APPROVAL_BOUNDARY_KIND, "boundary.json"),
        promotion_decision_ref=_ref(HITL_PROMOTION_DECISION_KIND, "decision.json"),
        promotion_review_ref=_ref(HITL_PROMOTION_REVIEW_KIND, "review.json"),
        promotion_request_ref=_ref(HITL_PROMOTION_REQUEST_KIND, "request.json"),
        source_proposal_refs=[_ref("builder_ii.orchestration_assignment_plan", "proposal.json")],
        target_profile_ref=_ref("builder_ii.target_profile", "target.json"),
        command_authority_ref=_ref("builder_ii.command_authority", "cmd_auth.json"),
        verification_profile_ref=_ref("builder_ii.verification_profile", "ver_profile.json"),
        rollback_requirements={
            "rollback_required": True,
            "no_mutation_assertion": True,
        },
        verification_requirements={"verification_required": True},
        candidate_scope={
            "target_profile": "generic",
            "core_workbench_coupling": "NONE",
            "command_previews": ["builder-hitl validate-candidate-manifest"],
        },
        source_approval_boundary_record_state="BOUNDARY_RECORDED_ONLY",
        source_approval_boundary_decision_result="approved_for_candidate_design",
        source_approval_boundary_decision_record_state="DECISION_RECORDED_ONLY",
        source_approval_boundary_requires_separate_execution_candidate=True,
    )


def test_happy_path_manifest() -> None:
    manifest = _mock_valid_manifest()
    errors = validate_execution_candidate_manifest(manifest)
    assert not errors, f"Expected no validation errors, got: {errors}"


def test_manifest_authority_invariants() -> None:
    manifest = _mock_valid_manifest()
    assert manifest["requires_separate_activation_artifact"] is True
    assert manifest["core_workbench_coupling"] == "NONE"

    # Check all boolean authority flags are false
    for key in (
        "executes_model",
        "executes_tools",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "constructs_subagents",
        "invokes_mcp",
        "performs_network_calls",
        "mutates_target_repo",
        "mutates_memory",
        "runtime_execution",
        "source_writes",
        "memory_mutation",
        "artifact_is_authority",
        "bypasses_command_authority",
        "bypasses_verification",
        "grants_runtime_authority",
        "authorizes_execution",
        "grants_authority",
    ):
        assert manifest[key] is False
        assert manifest["governance"][key] is False

    # Violating an invariant fails closed
    manifest["executes_model"] = True
    assert "executes_model must be false or NOT_AUTHORIZED" in validate_execution_candidate_manifest(manifest)


def test_requires_separate_activation_artifact_false_fails() -> None:
    manifest = _mock_valid_manifest()
    manifest["requires_separate_activation_artifact"] = False
    assert "requires_separate_activation_artifact must be true" in validate_execution_candidate_manifest(manifest)


def test_missing_approval_boundary_fails() -> None:
    manifest = _mock_valid_manifest()
    del manifest["approval_boundary_ref"]
    assert "approval_boundary_ref is required" in validate_execution_candidate_manifest(manifest)


def test_wrong_approval_boundary_kind_fails() -> None:
    manifest = _mock_valid_manifest()
    manifest["approval_boundary_ref"]["kind"] = "builder_ii.some_other_kind"
    errors = validate_execution_candidate_manifest(manifest)
    assert any("approval_boundary_ref has wrong source kind" in err for err in errors)


def test_missing_promotion_refs_fail() -> None:
    for field in (
        "promotion_decision_ref",
        "promotion_review_ref",
        "promotion_request_ref",
    ):
        manifest = _mock_valid_manifest()
        del manifest[field]
        assert f"{field} is required" in validate_execution_candidate_manifest(manifest)


def test_missing_source_proposal_refs_fail() -> None:
    manifest = _mock_valid_manifest()
    manifest["source_proposal_refs"] = []
    assert "source_proposal_refs list cannot be empty" in validate_execution_candidate_manifest(manifest)


def test_target_profile_outside_permitted_fails() -> None:
    manifest = _mock_valid_manifest()
    manifest["candidate_scope"]["target_profile"] = "unsupported_profile"
    assert "candidate_scope.target_profile must be generic, builder, or core" in validate_execution_candidate_manifest(
        manifest
    )


def test_core_workbench_coupling_fails() -> None:
    manifest = _mock_valid_manifest()
    manifest["candidate_scope"]["core_workbench_coupling"] = "SOME_COUPLING"
    assert "candidate_scope.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in validate_execution_candidate_manifest(manifest)


def test_deephaven_rejection() -> None:
    manifest = _mock_valid_manifest()
    manifest["candidate_scope"]["deephaven_integration"] = "DeephavenEngine"
    assert "Deephaven work is forbidden" in validate_execution_candidate_manifest(manifest)[0]


def test_tier_4_command_preview_fails() -> None:
    manifest = _mock_valid_manifest()
    manifest["candidate_scope"]["command_previews"] = ["builder-deepagents delegate"]
    errors = validate_execution_candidate_manifest(manifest)
    assert any("references forbidden Tier 4 subcommand" in err for err in errors)


def test_shell_control_syntax_in_preview_fails() -> None:
    manifest = _mock_valid_manifest()
    manifest["candidate_scope"]["command_previews"] = ["builder-hitl validate-candidate-manifest ; rm -rf /"]
    errors = validate_execution_candidate_manifest(manifest)
    assert any("shell control syntax" in err for err in errors)


def test_forbidden_commands_in_preview_fails() -> None:
    for cmd in ("sh -c", "bash -c", "python -c", "curl", "wget", "chmod", "rm -rf"):
        manifest = _mock_valid_manifest()
        manifest["candidate_scope"]["command_previews"] = [f"builder-hitl validate-candidate-manifest --arg '{cmd}'"]
        errors = validate_execution_candidate_manifest(manifest)
        assert any("forbidden active command" in err for err in errors), f"Expected rejection of '{cmd}'"


def test_active_claims_wording_fails() -> None:
    for term in (
        "execute",
        "run",
        "activate",
        "authorized",
        "enabled",
        "promoted",
        "executable",
        "running",
        "applied",
        "merged",
        "verified",
    ):
        manifest = _mock_valid_manifest()
        manifest["candidate_scope"]["some_reason"] = f"This was {term} by agent."
        errors = validate_execution_candidate_manifest(manifest)
        assert any("claims active authority state" in err for err in errors), f"Expected rejection of term '{term}'"


def test_rollback_requirements_missing_fail() -> None:
    manifest = _mock_valid_manifest()
    manifest["rollback_requirements"] = {}
    assert "rollback_requirements.rollback_required must be true" in validate_execution_candidate_manifest(manifest)


def test_verification_requirements_missing_fail() -> None:
    manifest = _mock_valid_manifest()
    manifest["verification_requirements"] = {}
    assert "verification_requirements.verification_required must be true" in validate_execution_candidate_manifest(
        manifest
    )


def test_validation_report_happy_path() -> None:
    manifest_ref = _ref(EXECUTION_CANDIDATE_MANIFEST_KIND, "manifest.json")
    report = create_execution_candidate_manifest_validation_report(
        subject_refs=[manifest_ref],
        valid=True,
    )
    assert report["kind"] == EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND
    assert report["valid"] is True

    errors = validate_execution_candidate_manifest_validation_report(report)
    assert not errors, f"Validation report errors: {errors}"

    # Fails closed on authority invariants
    report["executes_model"] = True
    assert "executes_model must be false or NOT_AUTHORIZED" in validate_execution_candidate_manifest_validation_report(report)


def test_artifact_chain_references() -> None:
    manifest = _mock_valid_manifest()
    refs = extract_references(manifest)
    fields = {r["field"] for r in refs}
    assert "approval_boundary_ref" in fields
    assert "promotion_decision_ref" in fields
    assert "promotion_review_ref" in fields
    assert "promotion_request_ref" in fields
    assert "target_profile_ref" in fields
    assert "command_authority_ref" not in fields
    assert "verification_profile_ref" in fields
    assert "source_proposal_refs[0]" in fields


def test_artifact_index_validators() -> None:
    assert EXECUTION_CANDIDATE_MANIFEST_KIND in INDEX_VALIDATORS
    assert EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND in INDEX_VALIDATORS


def test_command_authority_tier_classification() -> None:
    registered = {r.name: r for r in COMMAND_AUTHORITY_REGISTRY}
    assert "builder-hitl candidate-manifest" in registered
    assert "builder-hitl validate-candidate-manifest" in registered

    # Tier 1 registration
    assert registered["builder-hitl candidate-manifest"].tier == TIER_1
    assert registered["builder-hitl validate-candidate-manifest"].tier == TIER_1

    # Non-executing
    assert registered["builder-hitl candidate-manifest"].allows_runtime_start is False
    assert registered["builder-hitl candidate-manifest"].allows_model_execution is False


def test_cli_commands(tmp_path: Path) -> None:
    boundary = tmp_path / "boundary.json"
    decision = tmp_path / "decision.json"
    review = tmp_path / "review.json"
    request = tmp_path / "request.json"
    proposal = tmp_path / "proposal.json"
    target = tmp_path / "target.json"
    cmd_auth = tmp_path / "cmd_auth.json"
    ver_profile = tmp_path / "ver_profile.json"
    output = tmp_path / "manifest.json"

    boundary.write_text(json.dumps(_boundary_data()), encoding="utf-8")
    decision.write_text(json.dumps(_decision_data()), encoding="utf-8")
    review.write_text(json.dumps(_review_data()), encoding="utf-8")
    request.write_text(json.dumps(_request_data()), encoding="utf-8")
    proposal.write_text(json.dumps(_proposal_data()), encoding="utf-8")
    target.write_text(json.dumps(_target_profile_data()), encoding="utf-8")
    cmd_auth.write_text(json.dumps(_cmd_auth_data()), encoding="utf-8")
    ver_profile.write_text(json.dumps(_ver_profile_data()), encoding="utf-8")

    # CLI Happy Path
    res = runner.invoke(
        hitl_app,
        [
            "candidate-manifest",
            "--approval-boundary-path",
            str(boundary),
            "--decision-path",
            str(decision),
            "--review-path",
            str(review),
            "--request-path",
            str(request),
            "--source-proposal-path",
            str(proposal),
            "--target-profile-path",
            str(target),
            "--command-authority-path",
            str(cmd_auth),
            "--verification-profile-path",
            str(ver_profile),
            "--output",
            str(output),
            "--no-mutation-assertion",
        ],
    )
    assert res.exit_code == 0, f"CLI error: {res.output}"
    assert output.exists()

    # CLI Validation Happy Path
    res_val = runner.invoke(hitl_app, ["validate-candidate-manifest", str(output)])
    assert res_val.exit_code == 0, f"CLI validation error: {res_val.output}"

    # CLI Validation Failure Path
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text(
        json.dumps(
            {
                "kind": EXECUTION_CANDIDATE_MANIFEST_KIND,
                "schema_version": 1,
                "record_state": "CANDIDATE_RECORDED_ONLY",
            }
        ),
        encoding="utf-8",
    )
    res_fail = runner.invoke(hitl_app, ["validate-candidate-manifest", str(corrupt)])
    assert res_fail.exit_code != 0


def test_hitl_verification_candidate_sibling() -> None:
    from builder_ii.hitl_verification_candidate import (
        HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND,
        validate_hitl_verification_execution_candidate,
    )

    assert HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND == "builder_ii.hitl_verification_execution_candidate"
    assert validate_hitl_verification_execution_candidate is not None


def test_unapproved_source_boundary_fails() -> None:
    manifest = _mock_valid_manifest()
    manifest["source_approval_boundary_record_state"] = "INVALID"
    assert (
        "source_approval_boundary_record_state must be BOUNDARY_RECORDED_ONLY"
        in validate_execution_candidate_manifest(manifest)
    )

    manifest = _mock_valid_manifest()
    manifest["source_approval_boundary_decision_result"] = "INVALID"
    assert (
        "source_approval_boundary_decision_result must be approved_for_candidate_design"
        in validate_execution_candidate_manifest(manifest)
    )

    manifest = _mock_valid_manifest()
    manifest["source_approval_boundary_decision_record_state"] = "INVALID"
    assert (
        "source_approval_boundary_decision_record_state must be DECISION_RECORDED_ONLY"
        in validate_execution_candidate_manifest(manifest)
    )

    manifest = _mock_valid_manifest()
    manifest["source_approval_boundary_requires_separate_execution_candidate"] = False
    assert (
        "source_approval_boundary_requires_separate_execution_candidate must be true"
        in validate_execution_candidate_manifest(manifest)
    )


def test_unclassified_command_preview_fails() -> None:
    manifest = _mock_valid_manifest()
    manifest["candidate_scope"]["command_previews"] = ["invalid-unregistered-command-xyz"]
    errors = validate_execution_candidate_manifest(manifest)
    assert any("has no matching command authority record" in err for err in errors)


def test_hidden_boolean_claims_rejected() -> None:
    for key in (
        "records_execution",
        "activation_requested",
        "runtime_activation",
        "commands_executed",
        "target_repo_mutated",
        "memory_mutated",
    ):
        manifest = _mock_valid_manifest()
        manifest["candidate_scope"][key] = True
        errors = validate_execution_candidate_manifest(manifest)
        assert any("claims forbidden active capability" in err for err in errors)


def test_core_as_platform_identity_rejected() -> None:
    manifest = _mock_valid_manifest()
    manifest["platform_identity"] = "CORE"
    errors = validate_execution_candidate_manifest(manifest)
    assert any("Forbidden CORE platform identity claim" in err for err in errors)

    manifest = _mock_valid_manifest()
    manifest["candidate_scope"]["notes"] = "builder-ii is core platform."
    errors = validate_execution_candidate_manifest(manifest)
    assert any("Forbidden text implying builder-II is CORE" in err for err in errors)


def test_cli_candidate_manifest_rejects_malformed_approval_boundary(
    tmp_path: Path,
) -> None:
    boundary = tmp_path / "boundary.json"
    decision = tmp_path / "decision.json"
    review = tmp_path / "review.json"
    request = tmp_path / "request.json"
    proposal = tmp_path / "proposal.json"
    target = tmp_path / "target.json"
    cmd_auth = tmp_path / "cmd_auth.json"
    ver_profile = tmp_path / "ver_profile.json"
    output = tmp_path / "manifest.json"

    # Malformed: missing source_decision_result
    boundary_data = _boundary_data()
    del boundary_data["source_decision_result"]

    boundary.write_text(json.dumps(boundary_data), encoding="utf-8")
    decision.write_text(json.dumps(_decision_data()), encoding="utf-8")
    review.write_text(json.dumps(_review_data()), encoding="utf-8")
    request.write_text(json.dumps(_request_data()), encoding="utf-8")
    proposal.write_text(json.dumps(_proposal_data()), encoding="utf-8")
    target.write_text(json.dumps(_target_profile_data()), encoding="utf-8")
    cmd_auth.write_text(json.dumps(_cmd_auth_data()), encoding="utf-8")
    ver_profile.write_text(json.dumps(_ver_profile_data()), encoding="utf-8")

    res = runner.invoke(
        hitl_app,
        [
            "candidate-manifest",
            "--approval-boundary-path",
            str(boundary),
            "--decision-path",
            str(decision),
            "--review-path",
            str(review),
            "--request-path",
            str(request),
            "--source-proposal-path",
            str(proposal),
            "--target-profile-path",
            str(target),
            "--command-authority-path",
            str(cmd_auth),
            "--verification-profile-path",
            str(ver_profile),
            "--output",
            str(output),
            "--no-mutation-assertion",
        ],
    )
    assert res.exit_code != 0
    assert "Approval boundary validation error" in res.output


def test_cli_candidate_manifest_rejects_unapproved_decision_result(
    tmp_path: Path,
) -> None:
    boundary = tmp_path / "boundary.json"
    decision = tmp_path / "decision.json"
    review = tmp_path / "review.json"
    request = tmp_path / "request.json"
    proposal = tmp_path / "proposal.json"
    target = tmp_path / "target.json"
    cmd_auth = tmp_path / "cmd_auth.json"
    ver_profile = tmp_path / "ver_profile.json"
    output = tmp_path / "manifest.json"

    # Not approved: rejected_only
    boundary_data = _boundary_data()
    boundary_data["source_decision_result"] = "rejected_only"

    boundary.write_text(json.dumps(boundary_data), encoding="utf-8")
    decision.write_text(json.dumps(_decision_data()), encoding="utf-8")
    review.write_text(json.dumps(_review_data()), encoding="utf-8")
    request.write_text(json.dumps(_request_data()), encoding="utf-8")
    proposal.write_text(json.dumps(_proposal_data()), encoding="utf-8")
    target.write_text(json.dumps(_target_profile_data()), encoding="utf-8")
    cmd_auth.write_text(json.dumps(_cmd_auth_data()), encoding="utf-8")
    ver_profile.write_text(json.dumps(_ver_profile_data()), encoding="utf-8")

    res = runner.invoke(
        hitl_app,
        [
            "candidate-manifest",
            "--approval-boundary-path",
            str(boundary),
            "--decision-path",
            str(decision),
            "--review-path",
            str(review),
            "--request-path",
            str(request),
            "--source-proposal-path",
            str(proposal),
            "--target-profile-path",
            str(target),
            "--command-authority-path",
            str(cmd_auth),
            "--verification-profile-path",
            str(ver_profile),
            "--output",
            str(output),
            "--no-mutation-assertion",
        ],
    )
    assert res.exit_code != 0
    assert "Approval boundary validation error" in res.output


def test_deephaven_key_name_rejected() -> None:
    manifest = _mock_valid_manifest()
    manifest["candidate_scope"]["deephaven_field"] = "some_value"
    errors = validate_execution_candidate_manifest(manifest)
    assert any("Deephaven work is forbidden in key" in err for err in errors)


def test_active_ish_words_in_source_proposal_refs_path() -> None:
    manifest = _mock_valid_manifest()
    # Path has active-ish words like "execute" and "run"
    manifest["source_proposal_refs"][0]["path"] = "execute_run_proposal.json"
    errors = validate_execution_candidate_manifest(manifest)
    assert not errors, f"Expected active-ish words in source_proposal_refs path to be skipped, got errors: {errors}"


def test_forbidden_command_detection_no_false_positives() -> None:
    manifest = _mock_valid_manifest()
    # Harmless substrings "datacurl" or "show_chmod" should NOT trigger forbidden command rejection
    manifest["candidate_scope"]["command_previews"] = [
        "builder-hitl validate-candidate-manifest --arg datacurl --arg show_chmod"
    ]
    errors = validate_execution_candidate_manifest(manifest)
    assert not errors, f"Expected no error for harmless substrings, got: {errors}"


def test_chain_extraction_command_authority_snapshot_ref() -> None:
    manifest = _mock_valid_manifest()
    manifest["command_authority_snapshot_ref"] = _ref("builder_ii.snapshot_record", "snapshot.json")

    # command_authority_snapshot_ref should be extracted pointing to builder_ii.snapshot_record
    # command_authority_ref is metadata-only and should not be extracted
    refs = extract_references(manifest)
    fields = {r["field"]: r for r in refs}

    assert "command_authority_snapshot_ref" in fields
    assert fields["command_authority_snapshot_ref"]["expected_kind"] == "builder_ii.snapshot_record"
    assert "command_authority_ref" not in fields
