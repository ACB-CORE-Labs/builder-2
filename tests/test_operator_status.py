import json
from builder_ii.operator_status import (
    create_operator_status_report,
    validate_operator_status_report,
    dumps_operator_status_report,
    OPERATOR_STATUS_REPORT_KIND,
    SCHEMA_VERSION
)
from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.platform_completion_audit import REQUIRED_CAPABILITY_ROWS

def test_create_operator_status_report():
    report = create_operator_status_report(operator_name="test-op", target="generic")
    assert report["kind"] == OPERATOR_STATUS_REPORT_KIND
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["status_state"] == "STATUS_REPORT_ONLY"
    assert report["operator_name"] == "test-op"
    assert report["target"] == "generic"
    assert len(report["capabilities"]) == len(REQUIRED_CAPABILITY_ROWS)
    assert len(report["commands"]) == len(COMMAND_AUTHORITY_REGISTRY)
    assert "report_digest" in report
    
    # Must validate cleanly
    errors = validate_operator_status_report(report)
    assert not errors, f"Validation errors: {errors}"

def test_validate_operator_status_report_invalid_digest():
    report = create_operator_status_report()
    report["report_digest"] = "bad"
    errors = validate_operator_status_report(report)
    assert "report_digest does not match canonical content" in errors

def test_validate_operator_status_report_invalid_governance():
    report = create_operator_status_report()
    report["governance"]["artifact_is_authority"] = True
    errors = validate_operator_status_report(report)
    assert "governance.artifact_is_authority must be false" in errors
