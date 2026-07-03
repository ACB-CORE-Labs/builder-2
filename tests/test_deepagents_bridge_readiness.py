from __future__ import annotations

from unittest.mock import patch

from builder_ii.deepagents_bridge_readiness import (
    create_deepagents_bridge_readiness_report,
    validate_deepagents_bridge_readiness_report,
)


def test_create_valid_report_when_absent():
    with patch("importlib.util.find_spec", return_value=None):
        report = create_deepagents_bridge_readiness_report(
            target_profile="core",
            agent_profile_compatibility_summary="Compatible but optional",
            readiness_verdict="NOT_READY",
        )
        assert report["optional_dependency_state"] == "ABSENT"
        errors = validate_deepagents_bridge_readiness_report(report)
        assert not errors


def test_create_valid_report_when_present():
    class DummySpec:
        pass

    with patch("importlib.util.find_spec", return_value=DummySpec()):
        report = create_deepagents_bridge_readiness_report(
            target_profile="core",
            agent_profile_compatibility_summary="Compatible and ready",
            readiness_verdict="READY_FOR_DRY_RUN_SPEC",
        )
        assert report["optional_dependency_state"] == "PRESENT"
        errors = validate_deepagents_bridge_readiness_report(report)
        assert not errors


def test_no_shell_execution_during_creation():
    with patch("subprocess.run") as mock_run, patch("os.system") as mock_system:
        create_deepagents_bridge_readiness_report(
            target_profile="core",
            agent_profile_compatibility_summary="Test",
        )
        mock_run.assert_not_called()
        mock_system.assert_not_called()


def test_validation_rejects_missing_fields():
    report = create_deepagents_bridge_readiness_report(
        target_profile="core",
        agent_profile_compatibility_summary="Test",
    )
    report.pop("target_profile")
    errors = validate_deepagents_bridge_readiness_report(report)
    assert len(errors) > 0
    assert any("target_profile must be a non-empty string" in e for e in errors)


def test_validation_rejects_wrong_mode():
    report = create_deepagents_bridge_readiness_report(
        target_profile="core",
        agent_profile_compatibility_summary="Test",
    )
    report["bridge_mode"] = "EXECUTABLE"
    errors = validate_deepagents_bridge_readiness_report(report)
    assert len(errors) > 0
    assert any("bridge_mode must be READINESS_ONLY" in e for e in errors)


def test_validation_enforces_strict_disabled_capabilities():
    report = create_deepagents_bridge_readiness_report(
        target_profile="core",
        agent_profile_compatibility_summary="Test",
    )
    report["disabled_capabilities"].pop()
    errors = validate_deepagents_bridge_readiness_report(report)
    assert len(errors) > 0

    report = create_deepagents_bridge_readiness_report(
        target_profile="core",
        agent_profile_compatibility_summary="Test",
    )
    report["disabled_capabilities"].append("extra_capability")
    errors = validate_deepagents_bridge_readiness_report(report)
    assert len(errors) > 0


def test_validation_enforces_governance_no_authority():
    report = create_deepagents_bridge_readiness_report(
        target_profile="core",
        agent_profile_compatibility_summary="Test",
    )
    report["governance"]["artifact_is_authority"] = True
    errors = validate_deepagents_bridge_readiness_report(report)
    assert any("artifact_is_authority must be false or NOT_AUTHORIZED" in e for e in errors)

    report["governance"]["artifact_is_authority"] = False
    report["governance"]["shell_execution"] = "ENABLED"
    errors = validate_deepagents_bridge_readiness_report(report)
    assert any("shell_execution must be DISABLED or NOT_AUTHORIZED" in e for e in errors)
