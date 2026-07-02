import inspect
import json
from pathlib import Path

from builder_ii.hitl_promotion_cli import hitl_promotion_app
from typer.testing import CliRunner

import builder_ii.hitl_promotion_artifacts as hitl_promo_mod
from builder_ii.artifact_chain_verification import extract_references
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
    create_hitl_promotion_validation_report,
    create_hitl_rejection_record,
    validate_hitl_approval_boundary,
    validate_hitl_promotion_decision,
    validate_hitl_promotion_request,
    validate_hitl_promotion_review,
    validate_hitl_promotion_validation_report,
    validate_hitl_rejection_record,
)

runner = CliRunner()


def test_module_safety_checks() -> None:
    src = inspect.getsource(hitl_promo_mod)
    assert "import subprocess" not in src
    assert "os.system" not in src
    assert "exec(" not in src


def _assert_fail_closed_governance(data: dict) -> None:
    gov = data.get("governance", {})
    assert gov.get("artifact_is_authority") is False
    assert gov.get("grants_runtime_authority") is False
    assert gov.get("runtime_execution") is False
    assert gov.get("source_writes") is False
    assert gov.get("memory_mutation") is False


def test_create_and_validate_promotion_request(tmp_path: Path) -> None:
    prop_path = tmp_path / "proposal.json"
    prop_data = {
        "kind": "builder_ii.orchestration_assignment_plan",
        "schema_version": 1,
        "status": "planned",
    }
    prop_path.write_text(json.dumps(prop_data), encoding="utf-8")

    prop_ref = _create_ref(prop_data, path=prop_path, role="proposal")
    req = create_hitl_promotion_request(
        proposal=prop_data,
        proposal_path=prop_path,
        proposal_ref=prop_ref,
        requested_by="test_agent",
        reason="Test promotion",
    )

    assert req["kind"] == HITL_PROMOTION_REQUEST_KIND
    _assert_fail_closed_governance(req)
    assert not validate_hitl_promotion_request(req)

    # Chain extraction check
    refs = extract_references(req)
    assert any(r["field"] == "proposal_ref" for r in refs)


def test_create_and_validate_promotion_review(tmp_path: Path) -> None:
    req_path = tmp_path / "req.json"
    req_data = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "schema_version": 1,
        "promotion_status": "requested",
    }
    req_path.write_text(json.dumps(req_data), encoding="utf-8")
    req_ref = _create_ref(req_data, path=req_path, role="promotion_request")

    rev = create_hitl_promotion_review(
        promotion_request=req_data,
        promotion_request_path=req_path,
        promotion_request_ref=req_ref,
        disposition="acceptable_for_decision",
        findings=["All checks passed"],
    )

    assert rev["kind"] == HITL_PROMOTION_REVIEW_KIND
    _assert_fail_closed_governance(rev)
    assert not validate_hitl_promotion_review(rev)

    refs = extract_references(rev)
    assert any(r["field"] == "promotion_request_ref" for r in refs)


def test_create_and_validate_promotion_decision(tmp_path: Path) -> None:
    req_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "promotion_request",
    }
    rev_ref = {
        "kind": HITL_PROMOTION_REVIEW_KIND,
        "sha256": "b" * 64,
        "path": "rev.json",
        "role": "promotion_review",
    }

    dec = create_hitl_promotion_decision(
        promotion_request_ref=req_ref,
        promotion_review_ref=rev_ref,
        decision_result="approved_for_candidate_design",
        decided_by="operator",
        reason="Candidate design decision recorded",
        source_review_disposition="acceptable_for_decision",
        source_review_blocking_issues=[],
    )

    assert dec["kind"] == HITL_PROMOTION_DECISION_KIND
    _assert_fail_closed_governance(dec)
    assert not validate_hitl_promotion_decision(dec)

    refs = extract_references(dec)
    assert any(r["field"] == "promotion_request_ref" for r in refs)
    assert any(r["field"] == "promotion_review_ref" for r in refs)


def test_create_and_validate_approval_boundary() -> None:
    dec_ref = {
        "kind": HITL_PROMOTION_DECISION_KIND,
        "sha256": "c" * 64,
        "path": "dec.json",
        "role": "promotion_decision",
    }
    req_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "promotion_request",
    }

    bnd = create_hitl_approval_boundary(
        promotion_decision_ref=dec_ref,
        promotion_request_ref=req_ref,
        permitted_candidate_scope={"allowed_profiles": ["generic"]},
        denied_boundaries=["runtime execution"],
        source_decision_result="approved_for_candidate_design",
        source_decision_record_state="DECISION_RECORDED_ONLY",
    )

    assert bnd["kind"] == HITL_APPROVAL_BOUNDARY_KIND
    _assert_fail_closed_governance(bnd)
    assert not validate_hitl_approval_boundary(bnd)

    refs = extract_references(bnd)
    assert any(r["field"] == "promotion_decision_ref" for r in refs)


def test_create_and_validate_rejection_record() -> None:
    req_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "promotion_request",
    }

    rej = create_hitl_rejection_record(
        promotion_request_ref=req_ref,
        rationale="Policy failure",
    )

    assert rej["kind"] == HITL_REJECTION_RECORD_KIND
    _assert_fail_closed_governance(rej)
    assert not validate_hitl_rejection_record(rej)

    refs = extract_references(rej)
    assert any(r["field"] == "promotion_request_ref" for r in refs)


def test_create_and_validate_validation_report() -> None:
    sub_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "subject",
    }

    rep = create_hitl_promotion_validation_report(
        subject_refs=[sub_ref],
        valid=True,
    )

    assert rep["kind"] == HITL_PROMOTION_VALIDATION_REPORT_KIND
    _assert_fail_closed_governance(rep)
    assert not validate_hitl_promotion_validation_report(rep)

    refs = extract_references(rep)
    assert any(r["field"] == "subject_refs[0]" for r in refs)


def test_validation_failure_cases() -> None:
    assert validate_hitl_promotion_request({"kind": "wrong_kind"})
    assert validate_hitl_promotion_review({"kind": HITL_PROMOTION_REVIEW_KIND, "disposition": "invalid_disposition"})
    assert validate_hitl_promotion_decision({"kind": HITL_PROMOTION_DECISION_KIND, "decision_result": "invalid"})


def test_cli_promotion_request_flow(tmp_path: Path) -> None:
    prop_path = tmp_path / "proposal.json"
    prop_data = {
        "kind": "builder_ii.orchestration_assignment_plan",
        "schema_version": 1,
        "status": "planned",
    }
    prop_path.write_text(json.dumps(prop_data), encoding="utf-8")

    out_path = tmp_path / "req_out.json"

    res = runner.invoke(
        hitl_promotion_app,
        [
            "promotion-request",
            "--proposal-path",
            str(prop_path),
            "--output",
            str(out_path),
            "--reason",
            "CLI test",
        ],
    )

    assert res.exit_code == 0, res.output
    assert out_path.exists()
    out_data = json.loads(out_path.read_text("utf-8"))
    assert out_data["kind"] == HITL_PROMOTION_REQUEST_KIND
    _assert_fail_closed_governance(out_data)


def test_cli_validate_promotion(tmp_path: Path) -> None:
    prop_path = tmp_path / "proposal.json"
    prop_data = {
        "kind": "builder_ii.orchestration_assignment_plan",
        "schema_version": 1,
        "status": "planned",
    }
    prop_path.write_text(json.dumps(prop_data), encoding="utf-8")

    req_data = create_hitl_promotion_request(
        proposal=prop_data,
        proposal_path=prop_path,
        reason="Test",
    )
    req_path = tmp_path / "req.json"
    req_path.write_text(json.dumps(req_data), encoding="utf-8")

    res = runner.invoke(hitl_promotion_app, ["validate-promotion", str(req_path)])
    assert res.exit_code == 0, res.output
    assert "All promotion bridge artifacts valid." in res.output


def test_promotion_decision_cannot_approve_blocked_review() -> None:
    req_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "promotion_request",
    }
    rev_ref = {
        "kind": HITL_PROMOTION_REVIEW_KIND,
        "sha256": "b" * 64,
        "path": "rev.json",
        "role": "promotion_review",
    }

    dec = create_hitl_promotion_decision(
        promotion_request_ref=req_ref,
        promotion_review_ref=rev_ref,
        decision_result="approved_for_candidate_design",
        source_review_disposition="blocked",
        source_review_blocking_issues=[],
    )

    errors = validate_hitl_promotion_decision(dec)
    assert any("source_review_disposition acceptable_for_decision" in e for e in errors)


def test_promotion_decision_cannot_approve_review_with_blocking_issues() -> None:
    req_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "promotion_request",
    }
    rev_ref = {
        "kind": HITL_PROMOTION_REVIEW_KIND,
        "sha256": "b" * 64,
        "path": "rev.json",
        "role": "promotion_review",
    }

    dec = create_hitl_promotion_decision(
        promotion_request_ref=req_ref,
        promotion_review_ref=rev_ref,
        decision_result="approved_for_candidate_design",
        source_review_disposition="acceptable_for_decision",
        source_review_blocking_issues=["policy blocker"],
    )

    errors = validate_hitl_promotion_decision(dec)
    assert any("empty source_review_blocking_issues" in e for e in errors)


def test_approval_boundary_rejects_non_approved_decision_results() -> None:
    dec_ref = {
        "kind": HITL_PROMOTION_DECISION_KIND,
        "sha256": "c" * 64,
        "path": "dec.json",
        "role": "promotion_decision",
    }
    req_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "promotion_request",
    }

    for result in ("rejected", "needs_revision", ""):
        bnd = create_hitl_approval_boundary(
            promotion_decision_ref=dec_ref,
            promotion_request_ref=req_ref,
            source_decision_result=result,
            source_decision_record_state="DECISION_RECORDED_ONLY",
        )
        errors = validate_hitl_approval_boundary(bnd)
        assert any("source_decision_result approved_for_candidate_design" in e for e in errors)


def test_active_state_guard_rejects_broad_authority_language() -> None:
    req_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "promotion_request",
    }
    rev_ref = {
        "kind": HITL_PROMOTION_REVIEW_KIND,
        "sha256": "b" * 64,
        "path": "rev.json",
        "role": "promotion_review",
    }

    bad_strings = (
        "review approved",
        "candidate executable",
        "boundary authorized",
        "approved_for_candidate_design and executed",
    )
    for bad in bad_strings:
        dec = create_hitl_promotion_decision(
            promotion_request_ref=req_ref,
            promotion_review_ref=rev_ref,
            decision_result="approved_for_candidate_design",
            source_review_disposition="acceptable_for_decision",
            source_review_blocking_issues=[],
            reason=bad,
        )
        errors = validate_hitl_promotion_decision(dec)
        assert any("claims active authority state" in e for e in errors), bad


def test_active_state_guard_allows_tight_passive_and_denial_contexts() -> None:
    req_ref = {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "sha256": "a" * 64,
        "path": "req.json",
        "role": "promotion_request",
    }
    rev_ref = {
        "kind": HITL_PROMOTION_REVIEW_KIND,
        "sha256": "b" * 64,
        "path": "rev.json",
        "role": "promotion_review",
    }

    dec = create_hitl_promotion_decision(
        promotion_request_ref=req_ref,
        promotion_review_ref=rev_ref,
        decision_result="approved_for_candidate_design",
        source_review_disposition="acceptable_for_decision",
        source_review_blocking_issues=[],
        reason="active execution forbidden",
    )
    assert not validate_hitl_promotion_decision(dec)


def test_active_state_guard_skips_reference_metadata_paths(tmp_path: Path) -> None:
    active_dir = tmp_path / "active"
    active_dir.mkdir()
    proposal_path = active_dir / "enabled-plan.json"

    proposal_ref = {
        "kind": "builder_ii.orchestration_assignment_plan",
        "sha256": "a" * 64,
        "path": str(proposal_path),
        "role": "proposal",
        "name": "enabled-plan",
    }

    req = create_hitl_promotion_request(
        proposal_ref=proposal_ref,
        requested_by="operator",
        reason="passive request",
    )

    assert not validate_hitl_promotion_request(req)
