import json as json_lib
from pathlib import Path

from builder_ii.deepagents_cli import deepagents_app
from typer.testing import CliRunner

from builder_ii.adapters.deepagents.deepagents_policy import (
    create_deepagents_policy_artifact,
    dumps_deepagents_policy_artifact,
    validate_deepagents_policy_artifact,
    validate_deepagents_policy_artifact_file,
)
from builder_ii.core.config import load_settings


def test_create_deepagents_policy_artifact_shape() -> None:
    artifact = create_deepagents_policy_artifact(
        load_settings(),
        target_name="builder",
        task="render governed deepagents config",
    )

    assert artifact["kind"] == "builder_ii.deepagents_governed_policy"
    assert artifact["schema_version"] == 1
    assert artifact["target"]["name"] == "builder"
    assert artifact["policy_mode"] == "artifact_only"
    assert artifact["current_runtime_state"] == "DISABLED"
    assert artifact["policy_constructs_deepagents"] is False
    assert artifact["governed_factory"]["factory"] == "create_deep_agent"
    assert artifact["governed_factory"]["root_binding"] == "target.repo"
    assert artifact["governed_factory"]["memory_mode"] == "proposal_only"
    assert artifact["governed_factory"]["subagent_result_mode"] == "proposal_only"
    assert "construct_deepagents_agent" in artifact["denied_actions"]
    assert "call_create_deep_agent_without_builder_runtime" in artifact["denied_actions"]
    assert artifact["governance"]["deepagents_runtime_start"] == "DISABLED"
    assert artifact["governance"]["agent_construction"] == "DISABLED"
    assert artifact["governance"]["artifact_is_authority"] is False
    assert validate_deepagents_policy_artifact(artifact) == []


def test_deepagents_policy_json_round_trip() -> None:
    artifact = create_deepagents_policy_artifact(
        load_settings(),
        target_name="generic",
        task="map repo through governed deepagents policy",
        generic_repo=Path("."),
        allow_tools=["read_file", "grep"],
        deny_tools=["execute"],
        memory_mode="disabled",
        subagent_result_mode="trusted",
    )
    data = json_lib.loads(dumps_deepagents_policy_artifact(artifact))

    assert data["kind"] == "builder_ii.deepagents_governed_policy"
    assert data["target"]["name"] == "generic"
    assert data["governed_factory"]["allow_tools"] == ["read_file", "grep"]
    assert data["governed_factory"]["deny_tools"] == ["execute"]
    assert data["governed_factory"]["memory_mode"] == "disabled"
    assert data["governed_factory"]["subagent_result_mode"] == "trusted"
    assert validate_deepagents_policy_artifact(data) == []


def test_validate_rejects_runtime_authority() -> None:
    artifact = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    artifact["policy_mode"] = "runtime"
    artifact["current_runtime_state"] = "RUNNING"
    artifact["policy_constructs_deepagents"] = True
    artifact["governed_factory"]["factory"] = "custom_factory"
    artifact["governed_factory"]["allow_tools"] = []
    artifact["governed_factory"]["memory_mode"] = "write"
    artifact["governed_factory"]["subagent_result_mode"] = "trusted_runtime"
    artifact["denied_actions"].remove("call_models")
    artifact["governance"]["runtime_execution"] = "ENABLED"
    artifact["governance"]["deepagents_runtime_start"] = "ENABLED"
    artifact["governance"]["agent_construction"] = "ENABLED"
    artifact["governance"]["artifact_is_authority"] = True

    errors = validate_deepagents_policy_artifact(artifact)

    assert "policy_mode must be artifact_only" in errors
    assert "current_runtime_state must be DISABLED or NOT_AUTHORIZED" in errors
    assert "policy_constructs_deepagents must be false or NOT_AUTHORIZED" in errors
    assert "governed_factory.factory must be create_deep_agent" in errors
    assert "governed_factory.allow_tools must be a non-empty list" in errors
    assert "governed_factory.memory_mode must be disabled, proposal_only, or approved" in errors
    assert "governed_factory.subagent_result_mode must be trusted or proposal_only" in errors
    assert "denied_actions must include call_models" in errors
    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.deepagents_runtime_start must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.agent_construction must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any(
        "file not found" in error for error in validate_deepagents_policy_artifact_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_deepagents_policy_artifact_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "deepagents policy artifact must be a JSON object" in validate_deepagents_policy_artifact_file(not_object)


def test_cli_policy_stdout() -> None:
    runner = CliRunner()
    result = runner.invoke(
        deepagents_app,
        [
            "policy",
            "--target",
            "builder",
            "--task",
            "render governed deepagents config",
            "--memory-mode",
            "proposal_only",
            "--subagent-result-mode",
            "proposal_only",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.deepagents_governed_policy"
    assert data["policy_constructs_deepagents"] is False
    assert data["governed_factory"]["memory_mode"] == "proposal_only"


def test_cli_policy_output_and_validate(tmp_path: Path) -> None:
    out_file = tmp_path / "artifacts" / "deepagents-policy.json"
    runner = CliRunner()
    create_result = runner.invoke(
        deepagents_app,
        [
            "policy",
            "--target",
            "builder",
            "--task",
            "render governed deepagents config",
            "--output",
            str(out_file),
        ],
    )

    assert create_result.exit_code == 0
    assert out_file.exists()
    assert "Deepagents policy artifact written" in create_result.stdout

    validate_result = runner.invoke(deepagents_app, ["validate", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_policy_default_does_not_write() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(deepagents_app, ["policy", "--target", "builder", "--task", "render config"])
        assert result.exit_code == 0
        assert list(Path(".").iterdir()) == []


def test_cli_rejects_bad_memory_mode() -> None:
    runner = CliRunner()
    result = runner.invoke(deepagents_app, ["policy", "--memory-mode", "runtime_write"])

    assert result.exit_code == 1
    assert "memory mode must be disabled, proposal_only, or approved" in result.stdout
