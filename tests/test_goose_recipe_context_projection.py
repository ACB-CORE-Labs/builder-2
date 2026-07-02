from __future__ import annotations

import copy
from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.goose_recipe_context_projection import (
    GOOSE_RECIPE_CONTEXT_PROJECTION_KIND,
    create_goose_recipe_context_projection,
    dumps_goose_recipe_context_projection,
    validate_goose_recipe_context_projection,
    validate_goose_recipe_context_projection_file,
)
from builder_ii.session_config import create_session_configuration


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def test_create_goose_recipe_context_projection(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
        task="project recipe and context",
        context_pack=".builder/artifacts/context-pack.json",
        generic_repo=repo,
    )

    projection = create_goose_recipe_context_projection(config)

    assert projection["kind"] == GOOSE_RECIPE_CONTEXT_PROJECTION_KIND
    assert projection["projection_state"] == "PLANNED_ONLY"
    assert projection["target"] == "generic"
    assert projection["agent_profile"] == "patch_planner"
    assert projection["recipe_projection"]["name"] == "core-plan.yaml"
    assert "execute_shell" in projection["recipe_projection"]["forbidden_tools"]
    assert projection["recipe_projection"]["verification_profile"] == "generic_basic"
    assert projection["context_projection"]["repo_path"] == str(repo.resolve())
    assert projection["context_projection"]["context_pack_ref"] == ".builder/artifacts/context-pack.json"
    assert "README.md" in projection["context_projection"]["context_defaults"]
    assert projection["governance"]["runtime_execution"] == "DISABLED"
    assert projection["governance"]["goose_runtime_start"] == "DISABLED"
    assert projection["governance"]["model_execution"] == "DISABLED"
    assert projection["governance"]["artifact_is_authority"] is False
    assert validate_goose_recipe_context_projection(projection) == []


def test_goose_recipe_context_projection_rejects_authority_escalation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(settings, "generic", repo_path=str(repo), generic_repo=repo)
    projection = create_goose_recipe_context_projection(config)
    bad = copy.deepcopy(projection)
    bad["projection_state"] = "EXECUTED"
    bad["recipe_projection"]["forbidden_tools"] = ["write_file"]
    bad["governance"]["model_execution"] = "ENABLED"

    errors = validate_goose_recipe_context_projection(bad)

    assert "projection_state must be PLANNED_ONLY" in errors
    assert "recipe_projection.forbidden_tools must include execute_shell" in errors
    assert "governance.model_execution must be DISABLED" in errors


def test_goose_recipe_context_projection_file_validation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(settings, "generic", repo_path=str(repo), generic_repo=repo)
    projection = create_goose_recipe_context_projection(config)

    output = tmp_path / "goose-recipe-context-projection.json"
    output.write_text(dumps_goose_recipe_context_projection(projection), encoding="utf-8")

    assert validate_goose_recipe_context_projection_file(output) == []
    assert any(
        "file not found" in error for error in validate_goose_recipe_context_projection_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_goose_recipe_context_projection_file(bad_json))
