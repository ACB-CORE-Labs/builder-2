import json as json_lib
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from builder_ii.artifact_index_cli import index_app
from builder_ii.goose_command_proposal import create_goose_command_proposal

_MANIFEST: dict[str, Any] = {
    "kind": "builder_ii.goose_session_manifest",
    "schema_version": 1,
    "target": {"name": "test-target", "repo": "/tmp/repo", "description": "test"},
    "agent_profile": {"name": "test-agent", "description": "test", "authority": "user"},
    "task": "artifact index cli test",
    "requested_runtime_mode": "disabled",
}


def test_artifact_index_app_help() -> None:
    result = CliRunner().invoke(index_app, ["--help"])
    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout


def test_artifact_index_cli_record_and_validate(tmp_path: Path) -> None:
    # Write a valid json file to index using native factory
    proposal = create_goose_command_proposal(
        _MANIFEST,
        manifest_path="manifest.json",
        command="echo test",
        risk_level="low",
    )
    dummy_file = tmp_path / "dummy.json"
    dummy_file.write_text(json_lib.dumps(proposal), encoding="utf-8")

    output = tmp_path / "index.json"
    runner = CliRunner()

    # 1. Record command
    record_result = runner.invoke(index_app, ["record", str(tmp_path), "--output", str(output)])
    assert record_result.exit_code == 0
    assert "Artifact index record written to" in record_result.stdout
    assert output.exists()

    # Verify content
    data = json_lib.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.artifact_index_record"
    assert data["complete"] is True

    # 2. Validate command
    validate_result = runner.invoke(index_app, ["validate", str(output)])
    assert validate_result.exit_code == 0
    assert "Artifact index record is valid" in validate_result.stdout


def test_artifact_index_cli_validate_failure(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json_lib.dumps({"kind": "wrong_kind"}))

    runner = CliRunner()
    validate_result = runner.invoke(index_app, ["validate", str(bad_file)])
    assert validate_result.exit_code == 1
    assert "Validation error" in validate_result.stdout
