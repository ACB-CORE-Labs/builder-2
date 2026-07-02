from __future__ import annotations

from pathlib import Path

from builder_ii.onboarding_intent import (
    ONBOARDING_INTENT_KIND,
    finalize_onboarding_intent_report,
    validate_onboarding_intent_report_artifact,
    validate_onboarding_intent_report_file,
    write_onboarding_intent_report,
)


def _sample_report() -> dict:
    return finalize_onboarding_intent_report(
        setup_plan_path="/tmp/test/setup-plan.json",
        setup_plan_digest="a" * 64,
        setup_overlay_path="/tmp/test/setup-overlay.json",
        overlay_plan_digest="b" * 64,
        rollback_snapshot_path="/tmp/test/setup-rollback-snapshot.json",
        rollback_snapshot_digest="c" * 64,
        onboarding_mode="init",
        apply_command="builder-setup apply /tmp/test/setup-overlay.json --rollback-snapshot /tmp/test/setup-rollback-snapshot.json --approve-digest "
        + ("b" * 64)
        + " --output /tmp/test/receipt.json",
        validate_receipt_command="builder-setup validate-receipt /tmp/test/receipt.json",
        rollback_command="builder-setup rollback /tmp/test/receipt.json --rollback-snapshot /tmp/test/setup-rollback-snapshot.json --approve-digest "
        + ("d" * 64)
        + " --output /tmp/test/rollback-receipt.json",
        validate_rollback_receipt_command="builder-setup validate-rollback-receipt /tmp/test/rollback-receipt.json",
        selected_summary={"target_profile": "generic"},
    )


def test_onboarding_intent_artifact_validates_and_canonical_digest():
    report = _sample_report()
    errors = validate_onboarding_intent_report_artifact(report)
    assert errors == [], f"expected valid report, got {errors}"
    assert report["kind"] == ONBOARDING_INTENT_KIND
    assert report["artifact_is_authority"] is False
    assert report["planned_only"] is True
    assert len(report["onboarding_intent_digest"]) == 64


def test_tampered_digest_fails():
    report = _sample_report()
    report["onboarding_intent_digest"] = "f" * 64
    errors = validate_onboarding_intent_report_artifact(report)
    assert any("does not match canonical schema payload" in err for err in errors)


def test_wrong_kind_fails():
    report = _sample_report()
    report["kind"] = "wrong.kind"
    errors = validate_onboarding_intent_report_artifact(report)
    assert any("kind must be" in err for err in errors)


def test_missing_disabled_authority_fails():
    report = _sample_report()
    report["disabled_authority"]["runtime_execution"] = "enabled"
    # Re-sign digest so failure is specifically from disabled authority check
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert any("disabled_authority.runtime_execution must remain disabled" in err for err in errors)


def test_command_string_with_unmanaged_language_fails():
    report = _sample_report()
    report["apply_command"] = "builder-setup apply && bash -c 'echo bad'"
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert any(
        "contains forbidden command pattern" in err or "must reference only governed builder-setup commands" in err
        for err in errors
    )


def test_file_validation_and_write(tmp_path: Path):
    report = _sample_report()
    p = tmp_path / "onboarding-intent.json"
    write_onboarding_intent_report(report, p)
    errors = validate_onboarding_intent_report_file(p)
    assert errors == []


def test_apply_command_missing_approve_digest_fails():
    report = _sample_report()
    report["apply_command"] = "builder-setup apply /tmp/test/setup-overlay.json"
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert any("apply_command must include --approve-digest" in err for err in errors)


def test_apply_command_wrong_digest_fails():
    report = _sample_report()
    report["apply_command"] = "builder-setup apply /tmp/test/setup-overlay.json --approve-digest " + ("1" * 64)
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert any("apply_command must include --approve-digest matching overlay_plan_digest" in err for err in errors)


def test_apply_command_wrong_subcommand_fails():
    report = _sample_report()
    report["apply_command"] = "builder-setup plan /tmp/test/setup-overlay.json --approve-digest " + ("b" * 64)
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert any("apply_command must begin with 'builder-setup apply '" in err for err in errors)


def test_validate_receipt_command_wrong_subcommand_fails():
    report = _sample_report()
    report["validate_receipt_command"] = "builder-setup validate-plan /tmp/test/receipt.json"
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert any("validate_receipt_command must begin with 'builder-setup validate-receipt '" in err for err in errors)


def test_rollback_command_missing_digest_placeholder_fails():
    report = _sample_report()
    report["rollback_command"] = "builder-setup rollback /tmp/test/receipt.json"
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert any(
        "rollback_command must include --approve-digest placeholder or setup receipt digest" in err for err in errors
    )


def test_shell_separator_still_fails():
    report = _sample_report()
    report["apply_command"] = "builder-setup apply /tmp/test/setup-overlay.json ; rm -rf /"
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert any("contains forbidden command pattern" in err for err in errors)


def test_command_allowing_model_lab_and_git_safe_dir_paths():
    report = _sample_report()
    overlay_digest = report["overlay_plan_digest"]
    report["apply_command"] = (
        f"builder-setup apply /tmp/model-lab/setup-overlay.json --rollback-snapshot /tmp/git-safe-dir/snap.json --approve-digest {overlay_digest}"
    )
    report["rollback_command"] = (
        "builder-setup rollback /tmp/git-safe-dir/setup-receipt.json --approve-digest <setup_receipt_digest>"
    )
    from builder_ii.config_schema import attach_digest

    report = attach_digest(report, digest_key="onboarding_intent_digest")
    errors = validate_onboarding_intent_report_artifact(report)
    assert errors == []
