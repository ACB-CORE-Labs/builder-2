import json
from builder_ii.operator_next import (
    create_operator_next_action_report,
    validate_operator_next_action_report,
    dumps_operator_next_action_report,
    OPERATOR_NEXT_ACTION_REPORT_KIND,
    SCHEMA_VERSION
)

def test_create_operator_next_action_report():
    report = create_operator_next_action_report()
    assert report["kind"] == OPERATOR_NEXT_ACTION_REPORT_KIND
    assert report["schema_version"] == SCHEMA_VERSION
    assert "next_action" in report
    assert "suggested_command" in report
    assert "report_digest" in report
    
    # Must validate cleanly
    errors = validate_operator_next_action_report(report)
    assert not errors, f"Validation errors: {errors}"

def test_validate_operator_next_action_report_invalid_digest():
    report = create_operator_next_action_report()
    report["report_digest"] = "bad"
    errors = validate_operator_next_action_report(report)
    assert "report_digest does not match canonical content" in errors

def test_validate_operator_next_action_report_invalid_governance():
    report = create_operator_next_action_report()
    report["governance"]["artifact_is_authority"] = True
    errors = validate_operator_next_action_report(report)
    assert "governance.artifact_is_authority must be false" in errors
