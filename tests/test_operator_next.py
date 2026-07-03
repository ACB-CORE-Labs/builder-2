from builder_ii.operator_next import (
    OPERATOR_NEXT_ACTION_REPORT_KIND,
    SCHEMA_VERSION,
    create_operator_next_action_report,
    validate_operator_next_action_report,
)


def test_create_operator_next_action_report():
    report = create_operator_next_action_report()
    assert report["kind"] == OPERATOR_NEXT_ACTION_REPORT_KIND
    assert report["schema_version"] == SCHEMA_VERSION
    assert "report_digest" in report

    required_fields = (
        "created_at_utc",
        "current_state_digest",
        "current_state_summary",
        "ordered_next_actions",
        "non_goals",
        "missing_evidence",
        "artifact_is_authority",
        "grants_authority",
        "governance",
    )
    for field in required_fields:
        assert field in report

    # Verify ordered next actions is a list and contains required fields
    actions = report["ordered_next_actions"]
    assert isinstance(actions, list)
    if actions:
        for action in actions:
            assert "capability" in action
            assert "state" in action
            assert "reason" in action
            assert "blocked_by" in action
            assert "safe_commands" in action

    # Verify non-goals is non-empty list of strings
    assert isinstance(report["non_goals"], list)
    assert len(report["non_goals"]) > 0
    assert all(isinstance(x, str) for x in report["non_goals"])

    # Verify missing_evidence list
    assert isinstance(report["missing_evidence"], list)

    # Must validate cleanly
    errors = validate_operator_next_action_report(report)
    assert not errors, f"Validation errors: {errors}"


def test_validate_operator_next_action_report_missing_fields():
    report = create_operator_next_action_report()
    del report["ordered_next_actions"]
    errors = validate_operator_next_action_report(report)
    assert any("missing required field: ordered_next_actions" in e for e in errors)


def test_validate_operator_next_action_report_invalid_digest():
    report = create_operator_next_action_report()
    report["report_digest"] = "bad"
    errors = validate_operator_next_action_report(report)
    assert "report_digest does not match canonical content" in errors


def test_validate_operator_next_action_report_invalid_governance():
    report = create_operator_next_action_report()
    report["governance"]["artifact_is_authority"] = True
    errors = validate_operator_next_action_report(report)
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_next_action_authority_overclaim_fails():
    report = create_operator_next_action_report()
    report["grants_authority"] = True
    errors = validate_operator_next_action_report(report)
    assert any("grants_authority must be false or NOT_AUTHORIZED" in e for e in errors)
