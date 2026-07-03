import json as json_lib
from pathlib import Path

from builder_ii.goose_readonly_session import GOOSE_READONLY_SESSION_PLAN_KIND
from builder_ii.handoff_notes import (
    HANDOFF_NOTE_KIND,
    create_artifact_ref,
    create_handoff_note,
    validate_handoff_note,
    validate_handoff_note_file,
)
from builder_ii.session_workflow import SESSION_WORKFLOW_PLAN_KIND
from builder_ii.verification_profile_reports import VERIFICATION_PROFILE_REPORT_KIND


def test_create_handoff_note_without_evidence_refs() -> None:
    note = create_handoff_note(
        target_name="builder",
        summary="Implemented a bounded platform slice.",
        changed_files_summary=["builder_ii/example.py"],
        verification_summary="Verification planned but not completed by this note.",
        open_risks=["operator must run full suite"],
        next_recommended_action="Run focused and full verification locally.",
    )

    assert note["kind"] == HANDOFF_NOTE_KIND
    assert note["target_name"] == "builder"
    assert note["verification_claim"] == "NOT_CLAIMED"
    assert note["verification_evidence_refs"] == []
    assert note["human_review_required"] is True
    assert note["governance"]["claims_verification_passed"] is False
    assert validate_handoff_note(note) == []


def test_handoff_note_with_lifecycle_refs_and_evidence() -> None:
    note = create_handoff_note(
        target_name="generic",
        summary="Prepared a governed handoff.",
        next_recommended_action="Review evidence and merge if clean.",
        session_ref=create_artifact_ref(kind=SESSION_WORKFLOW_PLAN_KIND, path=".builder/session.json"),
        goose_readonly_session_ref=create_artifact_ref(
            kind=GOOSE_READONLY_SESSION_PLAN_KIND, path=".builder/goose.json"
        ),
        verification_report_ref=create_artifact_ref(
            kind=VERIFICATION_PROFILE_REPORT_KIND, path=".builder/verification.json"
        ),
        verification_evidence_refs=[
            create_artifact_ref(kind="builder_ii.operator_evidence", path=".builder/evidence.txt")
        ],
        status="READY_FOR_REVIEW",
    )

    assert note["verification_claim"] == "EVIDENCE_REFERENCED"
    assert note["governance"]["claims_verification_passed"] is True
    assert validate_handoff_note(note) == []


def test_validation_rejects_unsupported_claims() -> None:
    note = create_handoff_note(
        target_name="builder",
        summary="Prepared a governed handoff.",
        next_recommended_action="Review locally.",
    )

    bad_claim = dict(note)
    bad_claim["verification_claim"] = "EVIDENCE_REFERENCED"
    assert any("verification_claim must be NOT_CLAIMED" in error for error in validate_handoff_note(bad_claim))

    bad_review = dict(note)
    bad_review["human_review_required"] = False
    assert any("human_review_required must be true" in error for error in validate_handoff_note(bad_review))

    bad_governance = dict(note)
    bad_governance["governance"] = dict(note["governance"])
    bad_governance["governance"]["runtime_execution"] = "ENABLED"
    assert any("governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in error for error in validate_handoff_note(bad_governance))


def test_validation_rejects_wrong_reference_kind() -> None:
    note = create_handoff_note(
        target_name="builder",
        summary="Prepared a governed handoff.",
        next_recommended_action="Review locally.",
        session_ref=create_artifact_ref(kind=GOOSE_READONLY_SESSION_PLAN_KIND, path=".builder/wrong.json"),
    )

    assert any(
        "session_ref.kind must be an allowed handoff reference kind" in error for error in validate_handoff_note(note)
    )


def test_validate_handoff_note_file(tmp_path: Path) -> None:
    note = create_handoff_note(
        target_name="builder",
        summary="Prepared a governed handoff.",
        next_recommended_action="Run verification locally.",
    )

    note_file = tmp_path / "handoff-note.json"
    note_file.write_text(json_lib.dumps(note), encoding="utf-8")
    assert validate_handoff_note_file(note_file) == []

    assert any("file not found" in error for error in validate_handoff_note_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_handoff_note_file(bad_json))


def test_handoff_note_references_are_extracted_for_chain_verification():
    from builder_ii.artifact_chain_verification import extract_references
    from builder_ii.goose_readonly_session import GOOSE_READONLY_SESSION_PLAN_KIND
    from builder_ii.handoff_notes import create_artifact_ref, create_handoff_note
    from builder_ii.session_workflow import SESSION_WORKFLOW_PLAN_KIND
    from builder_ii.verification_profile_reports import VERIFICATION_PROFILE_REPORT_KIND

    note = create_handoff_note(
        target_name="builder",
        summary="Session handoff.",
        next_recommended_action="Review and continue.",
        session_ref=create_artifact_ref(
            kind=SESSION_WORKFLOW_PLAN_KIND,
            path="artifacts/session.json",
            sha256="session-sha",
        ),
        goose_readonly_session_ref=create_artifact_ref(
            kind=GOOSE_READONLY_SESSION_PLAN_KIND,
            path="artifacts/goose-readonly.json",
            sha256="goose-sha",
        ),
        verification_report_ref=create_artifact_ref(
            kind=VERIFICATION_PROFILE_REPORT_KIND,
            path="artifacts/verification.json",
            sha256="verification-sha",
        ),
        verification_evidence_refs=[
            create_artifact_ref(
                kind="builder_ii.execution_verification_record",
                path="artifacts/execution-verification.json",
                sha256="evidence-sha",
            )
        ],
    )

    refs = extract_references(note)
    refs_by_field = {ref["field"]: ref for ref in refs}

    assert refs_by_field["session_ref"] == {
        "field": "session_ref",
        "sha256": "session-sha",
        "path": "artifacts/session.json",
        "expected_kind": SESSION_WORKFLOW_PLAN_KIND,
    }
    assert refs_by_field["goose_readonly_session_ref"]["expected_kind"] == GOOSE_READONLY_SESSION_PLAN_KIND
    assert refs_by_field["verification_report_ref"]["expected_kind"] == VERIFICATION_PROFILE_REPORT_KIND
    assert refs_by_field["verification_evidence_refs[0]"] == {
        "field": "verification_evidence_refs[0]",
        "sha256": "evidence-sha",
        "path": "artifacts/execution-verification.json",
        "expected_kind": "builder_ii.execution_verification_record",
    }
