from __future__ import annotations

import json
from pathlib import Path

from builder_ii.verification_execution_plan_cli import verify_app
from typer.testing import CliRunner

from builder_ii.verification_execution_plan import validate_verification_execution_plan_artifact

runner = CliRunner()


def test_builder_verify_plan_writes_artifact_prints_json_and_validates(tmp_path: Path) -> None:
    output = tmp_path / "verification-execution-plan.json"
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
        ],
    )
    assert result.exit_code == 0, result.output
    printed = json.loads(result.output)
    written = json.loads(output.read_text(encoding="utf-8"))
    assert printed == written
    assert validate_verification_execution_plan_artifact(written) == []
    assert written["execution_enabled"] is False
    assert written["plan_mode"] == "planned_only"


def test_builder_verify_validate_plan_reports_valid(tmp_path: Path) -> None:
    output = tmp_path / "verification-execution-plan.json"
    plan_result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(output),
        ],
    )
    assert plan_result.exit_code == 0, plan_result.output

    validate_result = runner.invoke(verify_app, ["validate-plan", str(output)])
    assert validate_result.exit_code == 0, validate_result.output
    report = json.loads(validate_result.output)
    assert report == {"errors": [], "path": str(output), "valid": True}


def test_builder_verify_plan_output_directory_fails_cleanly(tmp_path: Path) -> None:
    result = runner.invoke(
        verify_app,
        [
            "plan",
            "--target-profile",
            "builder",
            "--verification-profile",
            "builder_full",
            "--output",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "Verification execution plan could not be written:" in result.output
    assert "Traceback" not in result.output
