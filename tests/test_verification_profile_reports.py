import json as json_lib
from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.goose_readonly_session import create_goose_readonly_session_plan
from builder_ii.verification_profile_reports import (
    VERIFICATION_PROFILE_REPORT_KIND,
    create_verification_profile_report,
    validate_verification_profile_report,
    validate_verification_profile_report_file,
)


def test_create_verification_profile_report_defaults() -> None:
    settings = load_settings()
    report = create_verification_profile_report(settings, "builder")

    assert report["kind"] == VERIFICATION_PROFILE_REPORT_KIND
    assert report["target_profile"]["name"] == "builder"
    assert report["selected_verification_profile"]["name"] == "builder_fast"
    assert report["report_state"] == "PLANNED_ONLY"
    assert report["completed_verification"] is False
    assert report["planned_checks"]
    assert all(check["execution_state"] == "NOT_RUN" for check in report["planned_checks"])
    assert all(check["human_operator_required"] is True for check in report["planned_checks"])
    assert all(check["completed_evidence_ref"] is None for check in report["planned_checks"])
    assert validate_verification_profile_report(report) == []


def test_report_can_embed_goose_readonly_session_plan() -> None:
    settings = load_settings()
    goose_plan = create_goose_readonly_session_plan(settings, "generic")
    report = create_verification_profile_report(settings, "generic", goose_readonly_session_plan=goose_plan)

    assert report["goose_readonly_session_plan"] == goose_plan
    assert validate_verification_profile_report(report) == []


def test_validation_rejects_completed_claims() -> None:
    settings = load_settings()
    report = create_verification_profile_report(settings, "builder")

    bad_state = dict(report)
    bad_state["report_state"] = "COMPLETE"
    assert any(
        "report_state must be PLANNED_ONLY" in error for error in validate_verification_profile_report(bad_state)
    )

    bad_completed = dict(report)
    bad_completed["completed_verification"] = True
    assert any(
        "completed_verification must be false or NOT_AUTHORIZED" in error for error in validate_verification_profile_report(bad_completed)
    )

    bad_check = dict(report)
    bad_check["planned_checks"] = [dict(report["planned_checks"][0])]
    bad_check["planned_checks"][0]["execution_state"] = "RUN"
    assert any("execution_state must be NOT_RUN" in error for error in validate_verification_profile_report(bad_check))


def test_validate_file_helpers(tmp_path: Path) -> None:
    settings = load_settings()
    report = create_verification_profile_report(settings, "builder")

    report_file = tmp_path / "verification-report.json"
    report_file.write_text(json_lib.dumps(report), encoding="utf-8")
    assert validate_verification_profile_report_file(report_file) == []

    assert any(
        "file not found" in error for error in validate_verification_profile_report_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("not json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_verification_profile_report_file(bad_json))
