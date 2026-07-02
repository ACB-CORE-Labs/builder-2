from __future__ import annotations

import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.performance_cli import performance_app
from builder_ii.validation_benchmark import (
    VALIDATION_BENCHMARK_KIND,
    VALIDATION_PARITY_REPORT_KIND,
    benchmark_validator,
    generate_parity_report,
    validate_validation_benchmark,
    validate_validation_parity_report,
)


def test_benchmark_validator_and_validate() -> None:
    # Test validator benchmarking logic directly
    res = benchmark_validator("builder_ii.goose_session_manifest", 10)
    assert res["kind"] == VALIDATION_BENCHMARK_KIND
    assert res["schema_version"] == 1
    assert res["validator_backend"] == "python"
    assert res["artifact_kind"] == "builder_ii.goose_session_manifest"
    assert res["artifact_count"] == 10
    assert res["valid_count"] == 9
    assert res["invalid_count"] == 1
    assert res["bytes_total"] > 0
    assert res["duration_ms"] >= 0.0
    assert res["p50_ms"] >= 0.0
    assert res["p95_ms"] >= 0.0
    assert res["p99_ms"] >= 0.0
    assert res["artifact_is_authority"] is False

    assert validate_validation_benchmark(res) == []

def test_validate_validation_benchmark_rejects_bad_data() -> None:
    # Missing required keys or wrong types
    bad_data: dict = {
        "kind": VALIDATION_BENCHMARK_KIND,
        "schema_version": 1,
        "validator_backend": "python",
        "artifact_kind": "",
        "artifact_count": -1,
        "bytes_total": 0,
        "valid_count": 0,
        "invalid_count": 0,
        "duration_ms": 0.0,
        "p50_ms": 0.0,
        "p95_ms": 0.0,
        "p99_ms": 0.0,
        "artifact_is_authority": False,
    }

    errors = validate_validation_benchmark(bad_data)
    assert "artifact_kind is required" in errors
    assert "artifact_count must be a non-negative integer" in errors

    not_dict = "not a dict"
    errors = validate_validation_benchmark(not_dict)
    assert "validation benchmark record must be a JSON object" in errors

def test_benchmark_all_supported_kinds() -> None:
    supported_kinds = [
        "builder_ii.goose_session_manifest",
        "builder_ii.goose_readonly_runtime_audit",
        "builder_ii.goose_readonly_inspection_audit",
        "builder_ii.performance_measurement",
        "builder_ii.hitl_execution_request",
        "builder_ii.hitl_execution_receipt",
        "builder_ii.approval_record",
    ]
    for kind in supported_kinds:
        res = benchmark_validator(kind, 10)
        assert res["artifact_kind"] == kind
        assert validate_validation_benchmark(res) == []

def test_cli_benchmark_validation(tmp_path: Path) -> None:
    runner = CliRunner()

    # Check stdout print
    result = runner.invoke(
        performance_app,
        [
            "benchmark-validation",
            "--kind",
            "builder_ii.goose_session_manifest",
            "--count",
            "5",
        ]
    )
    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == VALIDATION_BENCHMARK_KIND
    assert data["artifact_count"] == 5

    # Check writing to output file
    out_file = tmp_path / "benchmark-res.json"
    result_file = runner.invoke(
        performance_app,
        [
            "benchmark-validation",
            "--kind",
            "builder_ii.goose_session_manifest",
            "--count",
            "5",
            "--output",
            str(out_file),
        ]
    )
    assert result_file.exit_code == 0
    assert out_file.exists()

    file_data = json_lib.loads(out_file.read_text(encoding="utf-8"))
    assert file_data["kind"] == VALIDATION_BENCHMARK_KIND
    assert file_data["artifact_count"] == 5


def test_benchmark_rust_backend() -> None:
    res = benchmark_validator("builder_ii.goose_session_manifest", 5, backend="rust")
    assert res["kind"] == VALIDATION_BENCHMARK_KIND
    assert res["validator_backend"] == "rust"
    assert res["artifact_count"] == 5
    assert validate_validation_benchmark(res) == []


def test_generate_parity_report_and_validate() -> None:
    res = generate_parity_report("builder_ii.goose_session_manifest", 10)
    assert res["kind"] == VALIDATION_PARITY_REPORT_KIND
    assert res["cases_total"] == 10
    assert res["matches"] == 10
    assert res["mismatches"] == []
    assert validate_validation_parity_report(res) == []


def test_cli_parity_report(tmp_path: Path) -> None:
    runner = CliRunner()

    # Check stdout print
    result = runner.invoke(
        performance_app,
        [
            "parity-report",
            "--kind",
            "builder_ii.goose_session_manifest",
            "--count",
            "5",
        ]
    )
    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == VALIDATION_PARITY_REPORT_KIND
    assert data["cases_total"] == 5

    # Check writing to file
    out_file = tmp_path / "parity-res.json"
    result_file = runner.invoke(
        performance_app,
        [
            "parity-report",
            "--kind",
            "builder_ii.goose_session_manifest",
            "--count",
            "5",
            "--output",
            str(out_file),
        ]
    )
    assert result_file.exit_code == 0
    assert out_file.exists()

    file_data = json_lib.loads(out_file.read_text(encoding="utf-8"))
    assert file_data["kind"] == VALIDATION_PARITY_REPORT_KIND
    assert file_data["cases_total"] == 5

