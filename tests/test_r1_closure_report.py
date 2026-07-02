import json
from pathlib import Path

from builder_ii.onboarding_intent import DISABLED_AUTHORITY
from builder_ii.r1_closure_report import (
    R1_CLOSURE_REPORT_KIND,
    R1_CLOSURE_REPORT_SCHEMA_VERSION,
    finalize_r1_closure_report,
    validate_r1_closure_report_artifact,
)


def _sample_status(valid: bool = True) -> dict[str, object]:
    return {
        "valid": valid,
        "path": "/tmp/sample.json",
        "digest": "a" * 64,
        "errors": [] if valid else ["some error"],
    }


def test_finalize_and_validate_r1_closure_report():
    report = finalize_r1_closure_report(
        artifact_root="/tmp/artifacts",
        output_dir="/tmp/artifacts",
        config_schema_status=_sample_status(),
        config_resolution_status=_sample_status(),
        setup_plan_status=_sample_status(),
        overlay_plan_status=_sample_status(),
        rollback_snapshot_status=_sample_status(),
        onboarding_intent_status=_sample_status(),
        command_authority_status={"valid": True, "errors": []},
        platform_matrix_status={"valid": True, "errors": []},
        docs_truth_status={"valid": True, "violations": []},
        deferred_apply_command="builder-setup apply /tmp/ov.json --rollback-snapshot /tmp/snp.json --approve-digest " + ("b" * 64) + " --output /tmp/rec.json",
        deferred_rollback_command="builder-setup rollback /tmp/rec.json --rollback-snapshot /tmp/snp.json --approve-digest " + ("c" * 64) + " --output /tmp/rb_rec.json",
    )

    assert report["kind"] == R1_CLOSURE_REPORT_KIND
    assert report["schema_version"] == R1_CLOSURE_REPORT_SCHEMA_VERSION
    assert report["valid"] is True
    assert report["errors"] == []
    assert report["disabled_authority"] == DISABLED_AUTHORITY

    errors = validate_r1_closure_report_artifact(report)
    assert not errors, f"Unexpected validation errors: {errors}"


def test_invalid_r1_closure_report_when_subsystem_fails():
    report = finalize_r1_closure_report(
        artifact_root="/tmp/artifacts",
        output_dir="/tmp/artifacts",
        config_schema_status=_sample_status(valid=False),
        config_resolution_status=_sample_status(),
        setup_plan_status=_sample_status(),
        overlay_plan_status=_sample_status(),
        rollback_snapshot_status=_sample_status(),
        onboarding_intent_status=_sample_status(),
        command_authority_status={"valid": True, "errors": []},
        platform_matrix_status={"valid": True, "errors": []},
        docs_truth_status={"valid": True, "violations": []},
        deferred_apply_command="builder-setup apply /tmp/ov.json --approve-digest " + ("b" * 64),
        deferred_rollback_command="builder-setup rollback /tmp/rec.json --approve-digest " + ("c" * 64),
    )

    assert report["valid"] is False
    assert len(report["errors"]) > 0

    errors = validate_r1_closure_report_artifact(report)
    assert not errors, f"Unexpected validation errors on invalid report artifact: {errors}"


def test_report_digest_drift_fails():
    report = finalize_r1_closure_report(
        artifact_root="/tmp/artifacts",
        output_dir="/tmp/artifacts",
        config_schema_status=_sample_status(),
        config_resolution_status=_sample_status(),
        setup_plan_status=_sample_status(),
        overlay_plan_status=_sample_status(),
        rollback_snapshot_status=_sample_status(),
        onboarding_intent_status=_sample_status(),
        command_authority_status={"valid": True, "errors": []},
        platform_matrix_status={"valid": True, "errors": []},
        docs_truth_status={"valid": True, "violations": []},
        deferred_apply_command="builder-setup apply /tmp/ov.json --approve-digest " + ("b" * 64),
        deferred_rollback_command="builder-setup rollback /tmp/rec.json --approve-digest " + ("c" * 64),
    )
    errors = validate_r1_closure_report_artifact(report)
    assert not errors

    report["artifact_root"] = "/tmp/other"
    errors_drift = validate_r1_closure_report_artifact(report)
    assert any("drift" in e for e in errors_drift)


def test_missing_disabled_authority_fails():
    report = finalize_r1_closure_report(
        artifact_root="/tmp/artifacts",
        output_dir="/tmp/artifacts",
        config_schema_status=_sample_status(),
        config_resolution_status=_sample_status(),
        setup_plan_status=_sample_status(),
        overlay_plan_status=_sample_status(),
        rollback_snapshot_status=_sample_status(),
        onboarding_intent_status=_sample_status(),
        command_authority_status={"valid": True, "errors": []},
        platform_matrix_status={"valid": True, "errors": []},
        docs_truth_status={"valid": True, "violations": []},
        deferred_apply_command="builder-setup apply /tmp/ov.json --approve-digest " + ("b" * 64),
        deferred_rollback_command="builder-setup rollback /tmp/rec.json --approve-digest " + ("c" * 64),
    )
    del report["disabled_authority"]
    errors = validate_r1_closure_report_artifact(report)
    assert any("disabled_authority" in e for e in errors)


def test_disabled_authority_overclaim_fails():
    report = finalize_r1_closure_report(
        artifact_root="/tmp/artifacts",
        output_dir="/tmp/artifacts",
        config_schema_status=_sample_status(),
        config_resolution_status=_sample_status(),
        setup_plan_status=_sample_status(),
        overlay_plan_status=_sample_status(),
        rollback_snapshot_status=_sample_status(),
        onboarding_intent_status=_sample_status(),
        command_authority_status={"valid": True, "errors": []},
        platform_matrix_status={"valid": True, "errors": []},
        docs_truth_status={"valid": True, "violations": []},
        deferred_apply_command="builder-setup apply /tmp/ov.json --approve-digest " + ("b" * 64),
        deferred_rollback_command="builder-setup rollback /tmp/rec.json --approve-digest " + ("c" * 64),
    )
    report["disabled_authority"]["autonomous_writes"] = "enabled"
    errors = validate_r1_closure_report_artifact(report)
    assert any("disabled_authority" in e for e in errors)


def test_missing_evidence_status_digest_fails():
    report = finalize_r1_closure_report(
        artifact_root="/tmp/artifacts",
        output_dir="/tmp/artifacts",
        config_schema_status=_sample_status(),
        config_resolution_status=_sample_status(),
        setup_plan_status=_sample_status(),
        overlay_plan_status=_sample_status(),
        rollback_snapshot_status=_sample_status(),
        onboarding_intent_status=_sample_status(),
        command_authority_status={"valid": True, "errors": []},
        platform_matrix_status={"valid": True, "errors": []},
        docs_truth_status={"valid": True, "violations": []},
        deferred_apply_command="builder-setup apply /tmp/ov.json --approve-digest " + ("b" * 64),
        deferred_rollback_command="builder-setup rollback /tmp/rec.json --approve-digest " + ("c" * 64),
    )
    del report["config_schema_status"]["digest"]
    errors = validate_r1_closure_report_artifact(report)
    assert any("config_schema_status.digest" in e for e in errors)


def _generate_valid_closure(tmp_path: Path):
    from typer.testing import CliRunner

    from builder_ii.platform_status_cli import platform_app
    runner = CliRunner()
    output_dir = tmp_path / "r1-closure"
    res = runner.invoke(platform_app, ["r1-closure", "--output-dir", str(output_dir)])
    assert res.exit_code == 0
    report_path = output_dir / "r1-closure-report.json"
    return json.loads(report_path.read_text(encoding="utf-8")), output_dir


def test_evidence_status_digest_mismatch_fails(tmp_path):
    from builder_ii.r1_closure_report import validate_r1_closure_evidence_chain
    report, output_dir = _generate_valid_closure(tmp_path)

    # Let's verify that the base evidence chain first validates cleanly
    errors_ok = validate_r1_closure_evidence_chain(report, base_dir=output_dir)
    assert not errors_ok, f"Expected clean validation, got: {errors_ok}"

    # Mutate a status digest to something wrong
    report["config_schema_status"]["digest"] = "b" * 64
    from builder_ii.config_schema import attach_digest
    report = attach_digest(report, digest_key="r1_closure_digest")
    errors = validate_r1_closure_evidence_chain(report, base_dir=output_dir)
    assert any("digest mismatch" in e for e in errors)


def test_missing_evidence_file_fails(tmp_path):
    from builder_ii.r1_closure_report import validate_r1_closure_evidence_chain
    report, output_dir = _generate_valid_closure(tmp_path)

    # Move/delete one of the evidence files
    config_schema_path = Path(report["config_schema_status"]["path"])
    # Resolve relative or actual path in output_dir
    actual_file = output_dir / config_schema_path.name
    assert actual_file.exists()
    actual_file.unlink()

    errors = validate_r1_closure_evidence_chain(report, base_dir=output_dir)
    assert any("evidence file missing on disk" in e for e in errors)


def test_deferred_command_validation():
    def get_report(deferred_apply, deferred_rollback):
        return finalize_r1_closure_report(
            artifact_root="/tmp/artifacts",
            output_dir="/tmp/artifacts",
            config_schema_status=_sample_status(),
            config_resolution_status=_sample_status(),
            setup_plan_status=_sample_status(),
            overlay_plan_status=_sample_status(),
            rollback_snapshot_status=_sample_status(),
            onboarding_intent_status=_sample_status(),
            command_authority_status={"valid": True, "errors": []},
            platform_matrix_status={"valid": True, "errors": []},
            docs_truth_status={"valid": True, "violations": []},
            deferred_apply_command=deferred_apply,
            deferred_rollback_command=deferred_rollback,
        )

    # Valid
    report = get_report(
        deferred_apply="builder-setup apply /tmp/ov.json --approve-digest " + ("b" * 64),
        deferred_rollback="builder-setup rollback /tmp/rec.json --approve-digest <setup_receipt_digest>"
    )
    assert not validate_r1_closure_report_artifact(report)

    # Missing approve digest
    report = get_report(
        deferred_apply="builder-setup apply /tmp/ov.json",
        deferred_rollback="builder-setup rollback /tmp/rec.json --approve-digest <setup_receipt_digest>"
    )
    errors = validate_r1_closure_report_artifact(report)
    assert any("must contain '--approve-digest'" in e for e in errors)

    # Injection operators
    for op in ("&&", "||", ";", "|", "`", "$(", "\n", "\r"):
        report = get_report(
            deferred_apply=f"builder-setup apply /tmp/ov.json --approve-digest bbb {op} touch /tmp/hacked",
            deferred_rollback="builder-setup rollback /tmp/rec.json --approve-digest <setup_receipt_digest>"
        )
        errors = validate_r1_closure_report_artifact(report)
        assert any("forbidden chaining" in e for e in errors)
