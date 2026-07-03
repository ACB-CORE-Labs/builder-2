from __future__ import annotations

import json as json_lib
from pathlib import Path

from builder_ii.session_cli import session_app
from typer.testing import CliRunner

from builder_ii.config import load_settings
from builder_ii.session_config import (
    SESSION_CONFIG_KIND,
    create_session_configuration,
    dumps_session_configuration,
    validate_session_configuration,
    validate_session_configuration_file,
)

runner = CliRunner()


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def test_create_generic_session_configuration_spine(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)

    config = create_session_configuration(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
        task="prepare a governed Goose session",
        authority_mode="read_only",
        model_alias="qwen-coder",
        context_pack=".builder/artifacts/context-pack.json",
        generic_repo=repo,
    )

    assert config["kind"] == SESSION_CONFIG_KIND
    assert config["target_profile"]["name"] == "generic"
    assert config["repo_path"] == str(repo.resolve())
    assert config["selected_agent_profile"]["name"] == "patch_planner"
    assert config["selected_prompt_profile"]["name"] == "generic_default"
    assert config["selected_verification_profile"]["name"] == "generic_basic"
    assert config["authority_mode"] == "read_only"
    assert config["context"]["context_pack_ref"] == ".builder/artifacts/context-pack.json"
    assert "README.md" in config["context"]["context_defaults"]
    assert config["model_policy"]["provider_backend"] == "mlx-lm"
    assert config["model_policy"]["model_alias"] == "qwen-coder"
    assert config["model_policy"]["governance"]["model_execution"] == "DISABLED"
    assert config["goose_projection_policy"]["projection_state"] == "PLANNED_ONLY"
    assert config["goose_projection_policy"]["governance"]["goose_runtime_start"] == "DISABLED"
    assert config["governance"]["runtime_execution"] == "DISABLED"
    assert config["governance"]["goose_runtime_start"] == "DISABLED"
    assert config["governance"]["subagent_construction"] == "DISABLED"
    assert config["governance"]["artifact_is_authority"] is False
    assert "CORE" not in config["selected_prompt_profile"]["system_prompt"]

    assert validate_session_configuration(config) == []


def test_session_configuration_rejects_authority_escalation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(settings, "generic", repo_path=str(repo), generic_repo=repo)

    config["governance"]["runtime_execution"] = "ENABLED"
    config["goose_projection_policy"]["projection_state"] = "EXECUTED"
    config["goose_projection_policy"]["governance"]["goose_runtime_start"] = "ENABLED"
    config["model_policy"]["governance"]["model_execution"] = "ENABLED"

    errors = validate_session_configuration(config)

    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "goose_projection_policy.projection_state must be PLANNED_ONLY" in errors
    assert "goose_projection_policy.governance.goose_runtime_start must be DISABLED or NOT_AUTHORIZED" in errors
    assert "model_policy.governance.model_execution must be DISABLED or NOT_AUTHORIZED" in errors


def test_session_configuration_file_validation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(settings, "generic", repo_path=str(repo), generic_repo=repo)

    output = tmp_path / "session-configuration.json"
    output.write_text(dumps_session_configuration(config), encoding="utf-8")

    assert json_lib.loads(output.read_text(encoding="utf-8"))["kind"] == SESSION_CONFIG_KIND
    assert validate_session_configuration_file(output) == []
    assert any("file not found" in error for error in validate_session_configuration_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_session_configuration_file(bad_json))


def test_session_config_cli_stdout(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    result = runner.invoke(
        session_app,
        [
            "config",
            "generic",
            "--repo-path",
            str(repo),
            "--agent",
            "patch_planner",
            "--verification",
            "generic_basic",
            "--task",
            "prepare governed session config",
            "--model",
            "qwen-coder",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.output)
    assert data["kind"] == SESSION_CONFIG_KIND
    assert data["target_profile"]["name"] == "generic"
    assert data["selected_agent_profile"]["name"] == "patch_planner"
    assert data["model_policy"]["model_alias"] == "qwen-coder"
    assert data["goose_projection_policy"]["projection_state"] == "PLANNED_ONLY"


def test_session_config_cli_output_and_validate(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output = tmp_path / "artifacts" / "session-configuration.json"
    create_result = runner.invoke(
        session_app,
        [
            "config",
            "generic",
            "--repo-path",
            str(repo),
            "--output",
            str(output),
        ],
    )

    assert create_result.exit_code == 0
    assert output.exists()
    assert "Session configuration written" in create_result.stdout

    validate_result = runner.invoke(session_app, ["validate-config", str(output)])
    assert validate_result.exit_code == 0
    assert "valid" in validate_result.stdout.replace("\\n", " ")
