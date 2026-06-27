from __future__ import annotations

import copy
from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.orchestration_dry_run import (
    ORCHESTRATION_DRY_RUN_KIND,
    create_orchestration_dry_run,
    dumps_orchestration_dry_run,
    validate_orchestration_dry_run,
    validate_orchestration_dry_run_file,
)
from builder_ii.orchestration_plan import create_orchestration_plan


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def test_create_orchestration_dry_run(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    plan = create_orchestration_plan(
        target="generic",
        task="prepare governed dry run",
        roles=("repo_mapper", "context_planner", "patch_planner"),
    )

    dry_run = create_orchestration_dry_run(
        settings,
        plan,
        repo_path=str(repo),
        generic_repo=repo,
    )

    assert dry_run["kind"] == ORCHESTRATION_DRY_RUN_KIND
    assert dry_run["dry_run_state"] == "PLANNED_ONLY"
    assert dry_run["target"] == "generic"
    assert [step["role"] for step in dry_run["steps"]] == ["repo_mapper", "context_planner", "patch_planner"]
    assert all(step["session_configuration_kind"] == "builder_ii.session_configuration" for step in dry_run["steps"])
    assert all(step["goose_projection_kind"] == "builder_ii.goose_projection" for step in dry_run["steps"])
    assert all(step["goose_wrapper_plan_kind"] == "builder_ii.goose_wrapper_plan" for step in dry_run["steps"])
    assert all(step["operator_review_required"] is True for step in dry_run["steps"])
    assert all(step["executes_now"] is False for step in dry_run["steps"])
    assert all(step["validation_errors"] == [] for step in dry_run["steps"])
    assert dry_run["final_handoff"]["verification_status"] == "NOT_RUN"
    assert dry_run["governance"]["runtime_execution"] == "DISABLED"
    assert dry_run["governance"]["deepagents_runtime_start"] == "DISABLED"
    assert dry_run["governance"]["subagent_construction"] == "DISABLED"
    assert dry_run["governance"]["artifact_is_authority"] is False
    assert validate_orchestration_dry_run(dry_run) == []


def test_orchestration_dry_run_rejects_runtime_escalation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    plan = create_orchestration_plan(target="generic", task="reject dry run escalation")
    dry_run = create_orchestration_dry_run(settings, plan, repo_path=str(repo), generic_repo=repo)
    bad = copy.deepcopy(dry_run)
    bad["dry_run_state"] = "EXECUTED"
    bad["steps"][0]["executes_now"] = True
    bad["governance"]["deepagents_runtime_start"] = "ENABLED"
    bad["final_handoff"]["verification_status"] = "PASSED"

    errors = validate_orchestration_dry_run(bad)

    assert "dry_run_state must be PLANNED_ONLY" in errors
    assert "steps[0].executes_now must be false" in errors
    assert "governance.deepagents_runtime_start must be DISABLED" in errors
    assert "final_handoff.verification_status must be NOT_RUN" in errors


def test_orchestration_dry_run_file_validation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    plan = create_orchestration_plan(target="generic", task="validate dry run file")
    dry_run = create_orchestration_dry_run(settings, plan, repo_path=str(repo), generic_repo=repo)
    output = tmp_path / "orchestration-dry-run.json"
    output.write_text(dumps_orchestration_dry_run(dry_run), encoding="utf-8")

    assert validate_orchestration_dry_run_file(output) == []
    assert any("file not found" in error for error in validate_orchestration_dry_run_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_orchestration_dry_run_file(bad_json))
