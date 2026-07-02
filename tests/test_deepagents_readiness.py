import json as json_lib
from pathlib import Path

from builder_ii.deepagents_cli import deepagents_app
from typer.testing import CliRunner

import builder_ii.deepagents_readiness as readiness_mod
from builder_ii.deepagents_readiness import (
    create_deepagents_readiness_artifact,
    dumps_deepagents_readiness_artifact,
    validate_deepagents_readiness_artifact,
    validate_deepagents_readiness_artifact_file,
)


def test_create_metadata_only_readiness_artifact_shape() -> None:
    artifact = create_deepagents_readiness_artifact(mode="metadata_only")

    assert artifact["kind"] == "builder_ii.deepagents_dependency_readiness"
    assert artifact["schema_version"] == 1
    assert artifact["mode"] == "metadata_only"
    assert artifact["package"]["name"] == "deepagents"
    assert artifact["package"]["expected_factory"] == "create_governed_deep_agent"
    assert artifact["observed"]["dependency_state"] == "unknown"
    assert artifact["observed"]["module_available"] is False
    assert artifact["readiness_constructs_deepagents"] is False
    assert artifact["readiness_imports_deepagents"] is False
    assert "construct_deepagents_agent" in artifact["denied_actions"]
    assert "call_create_governed_deep_agent" in artifact["denied_actions"]
    assert artifact["governance"]["deepagents_runtime_start"] == "DISABLED"
    assert artifact["governance"]["agent_construction"] == "DISABLED"
    assert artifact["governance"]["artifact_is_authority"] is False
    assert validate_deepagents_readiness_artifact(artifact) == []


def test_import_check_readiness_artifact_available(monkeypatch) -> None:
    monkeypatch.setattr(readiness_mod, "_module_available", lambda module_name: True)
    monkeypatch.setattr(readiness_mod, "_package_version", lambda package_name: "0.1.0")
    monkeypatch.setattr(
        readiness_mod, "_export_available", lambda module_name, export_name: export_name == "create_governed_deep_agent"
    )

    artifact = create_deepagents_readiness_artifact(mode="import_check")

    assert artifact["observed"]["dependency_state"] == "available"
    assert artifact["observed"]["module_available"] is True
    assert artifact["observed"]["version"] == "0.1.0"
    assert artifact["observed"]["exports"]["create_governed_deep_agent"] is True
    assert artifact["observed"]["exports"]["DEFAULT_GOVERNED_ALLOW_TOOLS"] is False
    assert artifact["readiness_imports_deepagents"] is True
    assert validate_deepagents_readiness_artifact(artifact) == []


def test_import_check_readiness_artifact_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(readiness_mod, "_module_available", lambda module_name: False)
    monkeypatch.setattr(readiness_mod, "_package_version", lambda package_name: "")
    monkeypatch.setattr(readiness_mod, "_export_available", lambda module_name, export_name: False)

    artifact = create_deepagents_readiness_artifact(mode="import_check")

    assert artifact["observed"]["dependency_state"] == "unavailable"
    assert artifact["observed"]["module_available"] is False
    assert artifact["observed"]["version"] == ""
    assert all(value is False for value in artifact["observed"]["exports"].values())
    assert validate_deepagents_readiness_artifact(artifact) == []


def test_readiness_json_round_trip() -> None:
    artifact = create_deepagents_readiness_artifact(mode="metadata_only")
    data = json_lib.loads(dumps_deepagents_readiness_artifact(artifact))

    assert data["kind"] == "builder_ii.deepagents_dependency_readiness"
    assert data["mode"] == "metadata_only"
    assert validate_deepagents_readiness_artifact(data) == []


def test_validate_rejects_runtime_authority() -> None:
    artifact = create_deepagents_readiness_artifact(mode="metadata_only")
    artifact["mode"] = "runtime"
    artifact["package"]["name"] = "other"
    artifact["package"]["expected_factory"] = "create_deep_agent"
    artifact["observed"]["dependency_state"] = "running"
    artifact["current_runtime_state"] = "RUNNING"
    artifact["readiness_constructs_deepagents"] = True
    artifact["readiness_imports_deepagents"] = "yes"
    artifact["denied_actions"].remove("call_models")
    artifact["governance"]["runtime_execution"] = "ENABLED"
    artifact["governance"]["agent_construction"] = "ENABLED"
    artifact["governance"]["artifact_is_authority"] = True

    errors = validate_deepagents_readiness_artifact(artifact)

    assert "mode must be metadata_only or import_check" in errors
    assert "package.name must be deepagents" in errors
    assert "package.expected_factory must be create_governed_deep_agent" in errors
    assert "observed.dependency_state must be unknown, available, or unavailable" in errors
    assert "current_runtime_state must be DISABLED" in errors
    assert "readiness_constructs_deepagents must be false" in errors
    assert "readiness_imports_deepagents must be boolean" in errors
    assert "denied_actions must include call_models" in errors
    assert "governance.runtime_execution must be DISABLED" in errors
    assert "governance.agent_construction must be DISABLED" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any(
        "file not found" in error for error in validate_deepagents_readiness_artifact_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_deepagents_readiness_artifact_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "deepagents readiness artifact must be a JSON object" in validate_deepagents_readiness_artifact_file(
        not_object
    )


def test_cli_readiness_stdout() -> None:
    runner = CliRunner()
    result = runner.invoke(deepagents_app, ["readiness", "--mode", "metadata_only"])

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.deepagents_dependency_readiness"
    assert data["mode"] == "metadata_only"
    assert data["readiness_constructs_deepagents"] is False


def test_cli_readiness_output_and_validate(tmp_path: Path) -> None:
    out_file = tmp_path / "artifacts" / "deepagents-readiness.json"
    runner = CliRunner()
    create_result = runner.invoke(deepagents_app, ["readiness", "--mode", "metadata_only", "--output", str(out_file)])

    assert create_result.exit_code == 0
    assert out_file.exists()
    assert "Deepagents readiness artifact written" in create_result.stdout

    validate_result = runner.invoke(deepagents_app, ["validate-readiness", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_readiness_default_does_not_write() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(deepagents_app, ["readiness"])
        assert result.exit_code == 0
        assert list(Path(".").iterdir()) == []


def test_cli_rejects_bad_readiness_mode() -> None:
    runner = CliRunner()
    result = runner.invoke(deepagents_app, ["readiness", "--mode", "runtime"])

    assert result.exit_code == 1
    assert "readiness mode must be metadata_only or import_check" in result.stdout
