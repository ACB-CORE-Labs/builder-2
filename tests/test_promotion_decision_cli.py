import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.promotion_decision_cli import promotion_decision_app
from builder_ii.promotion_readiness_records import create_promotion_readiness_record


def _readiness(tmp_path: Path) -> Path:
    readiness = create_promotion_readiness_record(
        capability_name="test_capability",
        docs_refs=["docs/README.md"],
        tests_refs=["tests/test.py"],
        cli_refs=["builder-test"],
        failure_mode_refs=["reports error"],
        approval_boundary_refs=["no-authority"],
        output_artifact_refs=["output.json"],
        rollback_refs=["delete output"],
        verification_refs=["uv run pytest -q"],
    )
    readiness_path = tmp_path / "readiness.json"
    readiness_path.write_text(json_lib.dumps(readiness), encoding="utf-8")
    return readiness_path


def test_promotion_decision_app_help() -> None:
    result = CliRunner().invoke(promotion_decision_app, ["--help"])
    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout


def test_promotion_decision_cli_record_and_validate(tmp_path: Path) -> None:
    readiness_path = _readiness(tmp_path)
    output = tmp_path / "decision.json"
    runner = CliRunner()

    # 1. Record command
    record_result = runner.invoke(
        promotion_decision_app,
        [
            "record",
            str(readiness_path),
            "--decision", "approved",
            "--decided-by", "operator",
            "--reason", "ready",
            "--output", str(output)
        ]
    )
    assert record_result.exit_code == 0
    assert "Promotion decision record written to" in record_result.stdout
    assert output.exists()

    # Verify content
    data = json_lib.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.promotion_decision_record"
    assert data["decision"] == "approved"
    assert data["approved"] is True

    # 2. Validate command
    validate_result = runner.invoke(promotion_decision_app, ["validate", str(output)])
    assert validate_result.exit_code == 0
    assert "Promotion decision record is valid" in validate_result.stdout


def test_promotion_decision_cli_validate_failure(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json_lib.dumps({"kind": "wrong_kind"}))

    runner = CliRunner()
    validate_result = runner.invoke(promotion_decision_app, ["validate", str(bad_file)])
    assert validate_result.exit_code == 1
    assert "Validation error" in validate_result.stdout


def test_promotion_decision_cli_rejects_bad_decision(tmp_path: Path) -> None:
    readiness_path = _readiness(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        promotion_decision_app,
        ["record", str(readiness_path), "--decision", "invalid-val", "--decided-by", "operator"]
    )
    assert result.exit_code == 1
    assert "decision must be approved or blocked" in result.stdout
