import json
from pathlib import Path
import pytest
from typer.testing import CliRunner

from builder_ii.operator_golden_path import (
    create_operator_golden_path_report,
    validate_operator_golden_path_report,
    dumps_operator_golden_path_report,
    OPERATOR_GOLDEN_PATH_REPORT_KIND,
    SCHEMA_VERSION
)
from builder_ii.platform_status_cli import platform_app

def test_create_operator_golden_path_report(tmp_path):
    report = create_operator_golden_path_report("builder", tmp_path)
    assert report["kind"] == OPERATOR_GOLDEN_PATH_REPORT_KIND
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["target"] == "builder"
    assert report["target_profile"] == "builder"
    assert "output_dir" in report
    assert "run_id" in report
    assert isinstance(report["exercised_capabilities"], list)
    assert isinstance(report["skipped_capabilities"], list)
    assert "report_digest" in report
    assert "no_mutation_proof" in report
    assert "disabled_authority_summary" in report
    assert "memory_status" in report
    assert "ledger_status" in report
    
    # Check non-empty evidence_refs and generated_artifacts
    assert isinstance(report["evidence_refs"], list)
    assert len(report["evidence_refs"]) > 0
    assert isinstance(report["generated_artifacts"], list)
    assert len(report["generated_artifacts"]) > 0

    # Ensure status and next reports were written to the output dir
    assert (tmp_path / "operator-status.json").is_file()
    assert (tmp_path / "operator-next.json").is_file()

    # Must validate cleanly
    errors = validate_operator_golden_path_report(report)
    assert not errors, f"Validation errors: {errors}"

def test_validate_operator_golden_path_report_missing_fields(tmp_path):
    report = create_operator_golden_path_report("builder", tmp_path)
    del report["output_dir"]
    errors = validate_operator_golden_path_report(report)
    assert any("missing required field: output_dir" in e for e in errors)

def test_validate_operator_golden_path_report_empty_refs(tmp_path):
    report = create_operator_golden_path_report("builder", tmp_path)
    report["evidence_refs"] = []
    errors = validate_operator_golden_path_report(report)
    assert any("evidence_refs must be a non-empty list" in e for e in errors)

def test_validate_operator_golden_path_report_invalid_digest(tmp_path):
    report = create_operator_golden_path_report("builder", tmp_path)
    report["report_digest"] = "bad"
    errors = validate_operator_golden_path_report(report)
    assert "report_digest does not match canonical content" in errors

def test_validate_operator_golden_path_report_invalid_governance(tmp_path):
    report = create_operator_golden_path_report("builder", tmp_path)
    report["governance"]["artifact_is_authority"] = True
    errors = validate_operator_golden_path_report(report)
    assert "governance.artifact_is_authority must be false" in errors

def test_golden_path_authority_overclaim_fails(tmp_path):
    report = create_operator_golden_path_report("builder", tmp_path)
    report["grants_authority"] = True
    errors = validate_operator_golden_path_report(report)
    assert any("grants_authority must be false" in e for e in errors)

def test_tmp_table_md_does_not_exist():
    assert not Path("tmp_table.md").exists(), "Accidental tmp_table.md must not exist in workspace!"

def test_validate_golden_path_rejects_directory(tmp_path):
    runner = CliRunner()
    res = runner.invoke(platform_app, ["validate-golden-path", str(tmp_path)])
    assert res.exit_code != 0
    assert "report file is not a valid file" in res.output
