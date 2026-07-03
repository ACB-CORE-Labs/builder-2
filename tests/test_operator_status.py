from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.operator_status import (
    OPERATOR_STATUS_REPORT_KIND,
    SCHEMA_VERSION,
    create_operator_status_report,
    validate_operator_status_report,
)
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

    # Must have all required fields
    required_fields = (
        "created_at_utc",
        "platform_state_summary",
        "capability_counts_by_state",
        "promoted_capabilities",
        "passive_capabilities",
        "blocked_or_missing_capabilities",
        "command_surfaces_available",
        "warnings",
        "memory_status",
        "disabled_authority_summary",
        "artifact_is_authority",
        "grants_authority",
        "governance",
    )
    for field in required_fields:
        assert field in report

    # Check capability counts by state
    counts = report["capability_counts_by_state"]
    assert isinstance(counts, dict)
    assert len(counts) > 0
    assert sum(counts.values()) == len(REQUIRED_CAPABILITY_ROWS)

    # Must validate cleanly
    errors = validate_operator_status_report(report)
    assert not errors, f"Validation errors: {errors}"


def test_validate_operator_status_report_missing_fields():
    report = create_operator_status_report()
    del report["platform_state_summary"]
    errors = validate_operator_status_report(report)
    assert any("missing required field: platform_state_summary" in e for e in errors)


def test_validate_operator_status_report_invalid_digest():
    report = create_operator_status_report()
    report["report_digest"] = "bad"
    errors = validate_operator_status_report(report)
    assert "report_digest does not match canonical content" in errors


def test_validate_operator_status_report_invalid_governance():
    report = create_operator_status_report()
    report["governance"]["artifact_is_authority"] = True
    errors = validate_operator_status_report(report)
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_authority_overclaim_fails_validation():
    # Top-level authority flag overclaim
    report = create_operator_status_report()
    report["artifact_is_authority"] = True
    errors = validate_operator_status_report(report)
    assert any("artifact_is_authority must be false or NOT_AUTHORIZED" in e for e in errors)

    # Governance authority flag overclaim
    report2 = create_operator_status_report()
    report2["governance"]["grants_authority"] = True
    errors2 = validate_operator_status_report(report2)
    assert any("governance.grants_authority must be false or NOT_AUTHORIZED" in e for e in errors2)
