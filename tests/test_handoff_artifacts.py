import json as json_lib
from pathlib import Path

from builder_ii.notes_cli import notes_app
from typer.testing import CliRunner

from builder_ii.handoff_artifacts import (
    create_handoff_artifact,
    dumps_handoff_artifact,
    validate_handoff_artifact,
    validate_handoff_artifact_file,
)


def test_create_handoff_artifact_shape() -> None:
    artifact = create_handoff_artifact(
        target="builder",
        agent_profile="handoff_scribe",
        task="finish notes artifacts",
        summary="Added governed handoff artifacts.",
        next_steps=("run focused tests",),
        blockers=("none",),
        verification=("pytest pending",),
        created_at="2026-01-01T00:00:00Z",
    )

    assert artifact["kind"] == "builder_ii.handoff_artifact"
    assert artifact["schema_version"] == 1
    assert artifact["created_at"] == "2026-01-01T00:00:00Z"
    assert artifact["target"] == "builder"
    assert artifact["agent_profile"] == "handoff_scribe"
    assert artifact["task"] == "finish notes artifacts"
    assert artifact["summary"] == "Added governed handoff artifacts."
    assert artifact["next_steps"] == ["run focused tests"]
    assert artifact["blockers"] == ["none"]
    assert artifact["verification"] == ["pytest pending"]
    assert artifact["governance"]["runtime_execution"] == "DISABLED"
    assert artifact["governance"]["model_execution"] == "DISABLED"
    assert artifact["governance"]["agent_construction"] == "DISABLED"
    assert artifact["governance"]["notes_vault_mutation"] == "DISABLED"
    assert artifact["governance"]["shell_execution"] == "DISABLED"
    assert artifact["governance"]["artifact_is_authority"] is False
    assert validate_handoff_artifact(artifact) == []


def test_handoff_json_round_trip() -> None:
    artifact = create_handoff_artifact(
        target="generic",
        agent_profile="repo_mapper",
        task="map repo",
        summary="Mapped the repository.",
        created_at="2026-01-01T00:00:00Z",
    )
    data = json_lib.loads(dumps_handoff_artifact(artifact))

    assert data["kind"] == "builder_ii.handoff_artifact"
    assert validate_handoff_artifact(data) == []


def test_validate_handoff_artifact_rejects_runtime_authority() -> None:
    artifact = create_handoff_artifact(
        target="builder",
        agent_profile="handoff_scribe",
        task="finish notes artifacts",
        summary="Added governed handoff artifacts.",
    )
    artifact["governance"]["runtime_execution"] = "ENABLED"
    artifact["governance"]["model_execution"] = "ENABLED"
    artifact["governance"]["agent_construction"] = "ENABLED"
    artifact["governance"]["notes_vault_mutation"] = "ENABLED"
    artifact["governance"]["shell_execution"] = "ENABLED"
    artifact["governance"]["artifact_is_authority"] = True

    errors = validate_handoff_artifact(artifact)

    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.model_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.agent_construction must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.notes_vault_mutation must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.shell_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_validate_handoff_artifact_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_handoff_artifact_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_handoff_artifact_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "handoff artifact must be a JSON object" in validate_handoff_artifact_file(not_object)


def test_cli_handoff_stdout() -> None:
    runner = CliRunner()
    result = runner.invoke(
        notes_app,
        [
            "handoff",
            "--target",
            "builder",
            "--agent",
            "handoff_scribe",
            "--task",
            "finish notes artifacts",
            "--summary",
            "Added governed handoff artifacts.",
            "--next",
            "run tests",
            "--blocker",
            "none",
            "--verification",
            "pytest pending",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.handoff_artifact"
    assert data["target"] == "builder"
    assert data["next_steps"] == ["run tests"]
    assert data["governance"]["notes_vault_mutation"] == "DISABLED"


def test_cli_handoff_output_and_validate(tmp_path: Path) -> None:
    out_file = tmp_path / "artifacts" / "handoff.json"
    runner = CliRunner()
    create_result = runner.invoke(
        notes_app,
        [
            "handoff",
            "--target",
            "builder",
            "--agent",
            "handoff_scribe",
            "--task",
            "finish notes artifacts",
            "--summary",
            "Added governed handoff artifacts.",
            "--output",
            str(out_file),
        ],
    )

    assert create_result.exit_code == 0
    assert out_file.exists()
    assert "Handoff artifact written" in create_result.stdout

    validate_result = runner.invoke(notes_app, ["validate", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_handoff_default_does_not_write() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            notes_app,
            [
                "handoff",
                "--target",
                "builder",
                "--agent",
                "handoff_scribe",
                "--task",
                "finish notes artifacts",
                "--summary",
                "Added governed handoff artifacts.",
            ],
        )
        assert result.exit_code == 0
        assert list(Path(".").iterdir()) == []
