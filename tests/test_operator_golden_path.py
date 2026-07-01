import json
from pathlib import Path
from builder_ii.operator_golden_path import (
    create_operator_golden_path_report,
    validate_operator_golden_path_report,
    dumps_operator_golden_path_report,
    OPERATOR_GOLDEN_PATH_REPORT_KIND,
    SCHEMA_VERSION
)

def test_create_operator_golden_path_report():
    report = create_operator_golden_path_report("builder", Path("/tmp/golden-path"))
    assert report["kind"] == OPERATOR_GOLDEN_PATH_REPORT_KIND
    assert report["schema_version"] == SCHEMA_VERSION
    assert report["target_profile"] == "builder"
    assert "output_dir" in report
    assert "run_id" in report
    assert isinstance(report["exercised_capabilities"], list)
    assert isinstance(report["skipped_capabilities"], list)
    assert "report_digest" in report
    assert "no_mutation_proof" in report
    assert "disabled_authority_summary" in report
    
    # Must validate cleanly
    errors = validate_operator_golden_path_report(report)
    assert not errors, f"Validation errors: {errors}"

def test_validate_operator_golden_path_report_invalid_digest():
    report = create_operator_golden_path_report("builder", Path("/tmp/golden-path"))
    report["report_digest"] = "bad"
    errors = validate_operator_golden_path_report(report)
    assert "report_digest does not match canonical content" in errors

def test_validate_operator_golden_path_report_invalid_governance():
    report = create_operator_golden_path_report("builder", Path("/tmp/golden-path"))
    report["governance"]["artifact_is_authority"] = True
    errors = validate_operator_golden_path_report(report)
    assert "governance.artifact_is_authority must be false" in errors
