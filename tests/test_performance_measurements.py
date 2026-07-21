import json as json_lib
from pathlib import Path

from builder_ii.performance_cli import performance_app
from typer.testing import CliRunner

from builder_ii.governance.ledger.artifact_index_records import (
    create_artifact_index_record,
    validate_artifact_index_record,
)
from builder_ii.validation.performance_measurements import (
    PERFORMANCE_MEASUREMENT_KIND,
    PERFORMANCE_MEASUREMENT_SCHEMA_VERSION,
    create_performance_measurement_record,
    dumps_performance_measurement_record,
    validate_performance_measurement_record,
    validate_performance_measurement_record_file,
    write_performance_measurement_record,
)


def _record() -> dict:
    return create_performance_measurement_record(
        target="builder",
        candidate_name="readonly_inspection_candidate",
        metric_name="planning_latency_ms",
        metric_value=12.5,
        unit="ms",
        method="operator supplied dry-run note",
        source_ref="notes/perf.md",
        baseline_value=20.0,
        evidence_refs=["notes/perf.md"],
        notes=["explicit input only"],
    )


def test_create_performance_measurement_record_shape() -> None:
    record = _record()

    assert record["kind"] == PERFORMANCE_MEASUREMENT_KIND
    assert record["schema_version"] == PERFORMANCE_MEASUREMENT_SCHEMA_VERSION
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["target"] == "builder"
    assert record["metric"] == {"name": "planning_latency_ms", "value": 12.5, "unit": "ms"}
    assert record["baseline"] == {"value": 20.0, "unit": "ms"}
    assert record["performed_actions"] == []
    assert record["governance"]["benchmark_execution"] == "DISABLED"
    assert record["governance"]["hardware_probe"] == "DISABLED"
    assert record["governance"]["artifact_is_authority"] is False
    assert validate_performance_measurement_record(record) == []


def test_performance_measurement_json_and_file_round_trip(tmp_path: Path) -> None:
    data = json_lib.loads(dumps_performance_measurement_record(_record()))
    assert validate_performance_measurement_record(data) == []

    output = tmp_path / "perf.json"
    write_performance_measurement_record(data, output)
    assert validate_performance_measurement_record_file(output) == []


def test_validate_performance_measurement_rejects_authority_and_execution_drift() -> None:
    record = _record()
    record["performed_actions"] = ["benchmark"]
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["governance"]["runtime_execution"] = "ENABLED"
    record["governance"]["benchmark_execution"] = "ENABLED"
    record["governance"]["hardware_probe"] = "ENABLED"
    record["governance"]["artifact_is_authority"] = True
    record["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_performance_measurement_record(record)

    assert "performed_actions must be empty" in errors
    assert "grants_runtime_authority must be false or NOT_AUTHORIZED" in errors
    assert "grants_action_authority must be false or NOT_AUTHORIZED" in errors
    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.benchmark_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.hardware_probe must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors
    assert "governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in errors


def test_validate_performance_measurement_rejects_bad_metric() -> None:
    record = _record()
    record["metric"] = {"name": "", "value": "fast", "unit": ""}
    record["status"] = "promoted"
    record["evidence_refs"] = [""]

    errors = validate_performance_measurement_record(record)

    assert "metric.name must be a non-empty string" in errors
    assert "metric.value must be numeric" in errors
    assert "metric.unit must be a non-empty string" in errors
    assert "status must be candidate, accepted, or rejected" in errors
    assert "evidence_refs must be a list of non-empty strings" in errors


def test_performance_cli_stdout_and_validate(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        performance_app,
        [
            "record",
            "--target",
            "builder",
            "--candidate-name",
            "readonly_inspection_candidate",
            "--metric-name",
            "planning_latency_ms",
            "--metric-value",
            "12.5",
            "--unit",
            "ms",
            "--method",
            "operator supplied dry-run note",
            "--source-ref",
            "notes/perf.md",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == PERFORMANCE_MEASUREMENT_KIND
    assert data["governance"]["benchmark_execution"] == "DISABLED"

    output = tmp_path / "perf.json"
    file_result = runner.invoke(
        performance_app,
        [
            "record",
            "--target",
            "builder",
            "--candidate-name",
            "readonly_inspection_candidate",
            "--metric-name",
            "planning_latency_ms",
            "--metric-value",
            "12.5",
            "--unit",
            "ms",
            "--method",
            "operator supplied dry-run note",
            "--source-ref",
            "notes/perf.md",
            "--output",
            str(output),
        ],
    )
    assert file_result.exit_code == 0
    assert output.exists()

    validate_result = runner.invoke(performance_app, ["validate", str(output)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_artifact_index_recognizes_performance_measurement(tmp_path: Path) -> None:
    write_performance_measurement_record(_record(), tmp_path / "perf.json")
    index = create_artifact_index_record(tmp_path)

    assert index["counts"] == {"total": 1, "known": 1, "unknown": 0, "valid": 1, "invalid": 0}
    assert index["artifacts"][0]["kind"] == PERFORMANCE_MEASUREMENT_KIND
    assert validate_artifact_index_record(index) == []
