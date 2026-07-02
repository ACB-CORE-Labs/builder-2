from __future__ import annotations

import copy
from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.goose_projection import create_goose_projection
from builder_ii.goose_wrapper_plan import (
    GOOSE_WRAPPER_PLAN_KIND,
    create_goose_wrapper_plan,
    dumps_goose_wrapper_plan,
    validate_goose_wrapper_plan,
    validate_goose_wrapper_plan_file,
)
from builder_ii.session_config import create_session_configuration


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def _projection(tmp_path: Path) -> dict:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        repo_path=str(repo),
        task="prepare wrapper plan",
        generic_repo=repo,
    )
    return create_goose_projection(settings, config)


def test_create_goose_wrapper_plan(tmp_path: Path) -> None:
    projection = _projection(tmp_path)
    plan = create_goose_wrapper_plan(projection)

    assert plan["kind"] == GOOSE_WRAPPER_PLAN_KIND
    assert plan["plan_state"] == "PLANNED_ONLY"
    assert plan["target"] == "generic"
    assert plan["agent_profile"] == "patch_planner"
    assert plan["operator_launch"]["argv"][:3] == ["goose", "session", "--recipe"]
    assert plan["operator_launch"]["working_directory"] == projection["repo_path"]
    assert plan["operator_launch"]["requires_operator_execution"] is True
    assert plan["operator_launch"]["executes_now"] is False
    assert "GOOSE_MODEL" in plan["operator_launch"]["env_keys"]
    assert plan["governance"]["runtime_execution"] == "DISABLED"
    assert plan["governance"]["goose_runtime_start"] == "DISABLED"
    assert plan["governance"]["artifact_is_authority"] is False
    assert validate_goose_wrapper_plan(plan) == []


def test_goose_wrapper_plan_rejects_authority_escalation(tmp_path: Path) -> None:
    plan = create_goose_wrapper_plan(_projection(tmp_path))
    bad = copy.deepcopy(plan)
    bad["plan_state"] = "EXECUTED"
    bad["operator_launch"]["executes_now"] = True
    bad["operator_launch"]["requires_operator_execution"] = False
    bad["governance"]["goose_runtime_start"] = "ENABLED"

    errors = validate_goose_wrapper_plan(bad)

    assert "plan_state must be PLANNED_ONLY" in errors
    assert "operator_launch.executes_now must be false" in errors
    assert "operator_launch.requires_operator_execution must be true" in errors
    assert "governance.goose_runtime_start must be DISABLED" in errors


def test_goose_wrapper_plan_file_validation(tmp_path: Path) -> None:
    plan = create_goose_wrapper_plan(_projection(tmp_path))
    output = tmp_path / "goose-wrapper-plan.json"
    output.write_text(dumps_goose_wrapper_plan(plan), encoding="utf-8")

    assert validate_goose_wrapper_plan_file(output) == []
    assert any("file not found" in error for error in validate_goose_wrapper_plan_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_goose_wrapper_plan_file(bad_json))
