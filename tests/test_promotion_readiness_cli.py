import json as json_lib
from pathlib import Path

from builder_ii.promotion_readiness_cli import promotion_app
from typer.testing import CliRunner

from builder_ii.lifecycle.candidate.promotion_readiness_records import validate_promotion_readiness_record


def test_promotion_readiness_app_help() -> None:
    result = CliRunner().invoke(promotion_app, ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout


def test_cli_record_stdout() -> None:
    """Record command prints valid JSON to stdout when no --output given."""
    result = CliRunner().invoke(
        promotion_app,
        [
            "record",
            "--capability-name",
            "test-cap",
            "--docs-ref",
            "docs/README.md",
            "--tests-ref",
            "tests/test_foo.py",
            "--cli-ref",
            "builder-test",
            "--failure-mode-ref",
            "reports error",
            "--approval-boundary-ref",
            "no-authority",
            "--output-artifact-ref",
            "output.json",
            "--rollback-ref",
            "delete output.json",
            "--verification-ref",
            "uv run pytest -q",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.output)
    assert data["kind"] == "builder_ii.promotion_readiness_record"
    assert data["status"] == "ready"
    assert data["ready"] is True
    assert data["capability_name"] == "test-cap"
    assert len(data["checks"]) == 8
    assert data["governance"]["source_writes"] == "DISABLED"
    assert data["governance"]["memory_mutation"] == "DISABLED"
    assert validate_promotion_readiness_record(data) == []


def test_cli_record_and_validate_roundtrip(tmp_path: Path) -> None:
    """Record command writes file, validate command accepts it."""
    output = tmp_path / "promotion-readiness.json"
    record_result = CliRunner().invoke(
        promotion_app,
        [
            "record",
            "--capability-name",
            "test-cap",
            "--docs-ref",
            "docs/README.md",
            "--tests-ref",
            "tests/test_foo.py",
            "--cli-ref",
            "builder-test",
            "--failure-mode-ref",
            "reports error",
            "--approval-boundary-ref",
            "no-authority",
            "--output-artifact-ref",
            "output.json",
            "--rollback-ref",
            "delete output.json",
            "--verification-ref",
            "uv run pytest -q",
            "--output",
            str(output),
        ],
    )

    assert record_result.exit_code == 0
    assert output.exists()
    data = json_lib.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.promotion_readiness_record"
    assert data["status"] == "ready"
    assert data["governance"]["artifact_is_authority"] is False
    assert validate_promotion_readiness_record(data) == []

    validate_result = CliRunner().invoke(promotion_app, ["validate", str(output)])

    assert validate_result.exit_code == 0
    assert "valid" in validate_result.stdout.lower()


def test_cli_record_blocked_output(tmp_path: Path) -> None:
    """Blocked record (missing refs) still validates — it's metadata-only."""
    output = tmp_path / "blocked.json"
    record_result = CliRunner().invoke(
        promotion_app,
        [
            "record",
            "--capability-name",
            "partial-cap",
            "--docs-ref",
            "docs/README.md",
            "--output",
            str(output),
        ],
    )

    assert record_result.exit_code == 0
    assert output.exists()
    data = json_lib.loads(output.read_text(encoding="utf-8"))
    assert data["status"] == "blocked"
    assert data["ready"] is False
    assert validate_promotion_readiness_record(data) == []

    validate_result = CliRunner().invoke(promotion_app, ["validate", str(output)])

    assert validate_result.exit_code == 0


def test_cli_validate_rejects_invalid_file(tmp_path: Path) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text('{"kind": "wrong"}', encoding="utf-8")

    result = CliRunner().invoke(promotion_app, ["validate", str(bad)])

    assert result.exit_code == 1
    assert "Validation error" in result.stdout


def test_cli_validate_missing_file(tmp_path: Path) -> None:
    result = CliRunner().invoke(promotion_app, ["validate", str(tmp_path / "missing.json")])

    assert result.exit_code == 1
    assert "file not found" in result.stdout.lower() or "Validation error" in result.stdout
