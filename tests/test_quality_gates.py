import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.quality_cli import quality_app
from builder_ii.quality_gates import (
    create_quality_gate_artifact,
    dumps_quality_gate_artifact,
    validate_quality_gate_artifact,
    validate_quality_gate_artifact_file,
)


def test_create_quality_gate_artifact_shape() -> None:
    artifact = create_quality_gate_artifact(
        target="builder",
        verification_profile="builder_full",
        task="implement quality gates",
    )

    assert artifact["kind"] == "builder_ii.quality_gate"
    assert artifact["schema_version"] == 1
    assert artifact["target"] == "builder"
    assert artifact["task"] == "implement quality gates"
    assert artifact["verification_profile"]["kind"] == "builder_ii.verification_profile"
    assert artifact["verification_profile"]["name"] == "builder_full"
    assert artifact["required_commands"]
    assert artifact["required_evidence"]
    assert artifact["merge_blockers"]
    assert artifact["rollback_requirements"]
    assert artifact["approval_required"] is True
    assert artifact["governance"]["runtime_execution"] == "DISABLED"
    assert artifact["governance"]["command_execution"] == "DISABLED"
    assert artifact["governance"]["quality_gate_executes_commands"] is False
    assert artifact["governance"]["artifact_is_authority"] is False
    assert validate_quality_gate_artifact(artifact) == []


def test_quality_gate_json_round_trip() -> None:
    artifact = create_quality_gate_artifact(
        target="generic",
        verification_profile="generic_basic",
        task="map generic repo quality path",
    )
    data = json_lib.loads(dumps_quality_gate_artifact(artifact))

    assert data["kind"] == "builder_ii.quality_gate"
    assert validate_quality_gate_artifact(data) == []


def test_quality_gate_accepts_custom_blockers_and_rollback() -> None:
    artifact = create_quality_gate_artifact(
        target="builder",
        verification_profile="builder_fast",
        task="verify docs only change",
        merge_blockers=("focused tests missing",),
        rollback_requirements=("record recovery path",),
    )

    assert artifact["merge_blockers"] == ["focused tests missing"]
    assert artifact["rollback_requirements"] == ["record recovery path"]
    assert validate_quality_gate_artifact(artifact) == []


def test_validate_quality_gate_rejects_execution_authority() -> None:
    artifact = create_quality_gate_artifact(
        target="builder",
        verification_profile="builder_full",
        task="implement quality gates",
    )
    artifact["governance"]["runtime_execution"] = "ENABLED"
    artifact["governance"]["command_execution"] = "ENABLED"
    artifact["governance"]["quality_gate_executes_commands"] = True
    artifact["governance"]["artifact_is_authority"] = True

    errors = validate_quality_gate_artifact(artifact)

    assert "governance.runtime_execution must be DISABLED" in errors
    assert "governance.command_execution must be DISABLED" in errors
    assert "governance.quality_gate_executes_commands must be false" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_quality_gate_rejects_incompatible_profile() -> None:
    artifact = create_quality_gate_artifact(
        target="builder",
        verification_profile="builder_full",
        task="implement quality gates",
    )
    artifact["target"] = "core"

    errors = validate_quality_gate_artifact(artifact)

    assert "verification_profile must be compatible with target" in errors


def test_validate_quality_gate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_quality_gate_artifact_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_quality_gate_artifact_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "quality gate artifact must be a JSON object" in validate_quality_gate_artifact_file(not_object)


def test_cli_plan_stdout() -> None:
    runner = CliRunner()
    result = runner.invoke(
        quality_app,
        [
            "plan",
            "--target",
            "builder",
            "--profile",
            "builder_full",
            "--task",
            "implement quality gates",
            "--blocker",
            "missing full suite",
            "--rollback",
            "record recovery path",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.quality_gate"
    assert data["target"] == "builder"
    assert data["merge_blockers"] == ["missing full suite"]
    assert data["rollback_requirements"] == ["record recovery path"]


def test_cli_plan_output_and_validate(tmp_path: Path) -> None:
    out_file = tmp_path / "artifacts" / "quality-gate.json"
    runner = CliRunner()
    create_result = runner.invoke(
        quality_app,
        [
            "plan",
            "--target",
            "builder",
            "--profile",
            "builder_full",
            "--task",
            "implement quality gates",
            "--output",
            str(out_file),
        ],
    )

    assert create_result.exit_code == 0
    assert out_file.exists()
    assert "Quality gate artifact written" in create_result.stdout

    validate_result = runner.invoke(quality_app, ["validate", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_plan_default_does_not_write() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            quality_app,
            [
                "plan",
                "--target",
                "builder",
                "--profile",
                "builder_fast",
                "--task",
                "verify docs only change",
            ],
        )
        assert result.exit_code == 0
        assert list(Path(".").iterdir()) == []


def test_cli_plan_rejects_incompatible_profile() -> None:
    runner = CliRunner()
    result = runner.invoke(
        quality_app,
        [
            "plan",
            "--target",
            "core",
            "--profile",
            "builder_full",
            "--task",
            "incompatible profile",
        ],
    )

    assert result.exit_code == 1
    assert "not compatible" in result.stdout
