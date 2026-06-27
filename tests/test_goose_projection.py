from __future__ import annotations

import copy
from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.goose_projection import (
    GOOSE_PROJECTION_KIND,
    create_goose_projection,
    dumps_goose_projection,
    validate_goose_projection,
    validate_goose_projection_file,
)
from builder_ii.session_config import create_session_configuration


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def test_create_goose_projection_from_session_config(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
        task="project a governed Goose session",
        model_alias="qwen-coder",
        context_pack=".builder/artifacts/context-pack.json",
        generic_repo=repo,
    )

    projection = create_goose_projection(settings, config)

    assert projection["kind"] == GOOSE_PROJECTION_KIND
    assert projection["projection_state"] == "PLANNED_ONLY"
    assert projection["target"] == "generic"
    assert projection["agent_profile"] == "patch_planner"
    assert projection["authority_mode"] == "read_only"
    assert projection["repo_path"] == str(repo.resolve())

    surface = projection["goose_native_surface"]
    env = surface["env"]
    assert env["GOOSE_PROVIDER"] == "openai"
    assert env["GOOSE_MODEL"] == settings.mlx_model_qwen
    assert env["GOOSE_TEMPERATURE"] == "0.0"
    assert env["GOOSE_PLANNER_PROVIDER"] == "openai"
    assert env["GOOSE_PLANNER_MODEL"] == settings.mlx_model_qwen
    assert env["BUILDER_MODEL_ALIAS"] == "qwen-coder"
    assert env["BUILDER_SESSION_MODE"] == "read_only"
    assert surface["recipe_name"] == "core-plan.yaml"
    assert surface["working_directory"] == str(repo.resolve())
    assert surface["context_pack_ref"] == ".builder/artifacts/context-pack.json"
    assert surface["resume"] is False
    assert surface["builtins"] == []
    assert surface["extensions"] == []

    assert projection["governance"]["runtime_execution"] == "DISABLED"
    assert projection["governance"]["goose_runtime_start"] == "DISABLED"
    assert projection["governance"]["model_execution"] == "DISABLED"
    assert projection["governance"]["artifact_is_authority"] is False
    assert validate_goose_projection(projection) == []


def test_goose_projection_rejects_runtime_escalation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(settings, "generic", repo_path=str(repo), generic_repo=repo)
    projection = create_goose_projection(settings, config)

    bad = copy.deepcopy(projection)
    bad["projection_state"] = "EXECUTED"
    bad["governance"]["runtime_execution"] = "ENABLED"
    bad["governance"]["goose_runtime_start"] = "ENABLED"
    bad["governance"]["model_execution"] = "ENABLED"

    errors = validate_goose_projection(bad)

    assert "projection_state must be PLANNED_ONLY" in errors
    assert "governance.runtime_execution must be DISABLED" in errors
    assert "governance.goose_runtime_start must be DISABLED" in errors
    assert "governance.model_execution must be DISABLED" in errors


def test_goose_projection_file_validation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(settings, "generic", repo_path=str(repo), generic_repo=repo)
    projection = create_goose_projection(settings, config)

    output = tmp_path / "goose-projection.json"
    output.write_text(dumps_goose_projection(projection), encoding="utf-8")

    assert validate_goose_projection_file(output) == []
    assert any("file not found" in error for error in validate_goose_projection_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_goose_projection_file(bad_json))
