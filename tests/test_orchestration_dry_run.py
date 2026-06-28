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
from builder_ii.orchestration_assignment import (
    ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
    create_orchestration_assignment_dry_run,
    validate_orchestration_assignment_dry_run,
    validate_orchestration_assignment_validation_report,
)
from orchestration_assignment_fixtures import build_goal2_assignment_fixture


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text(
        "[project]\nname = 'generic-repo'\n", encoding="utf-8"
    )
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
    assert [step["role"] for step in dry_run["steps"]] == [
        "repo_mapper",
        "context_planner",
        "patch_planner",
    ]
    assert all(
        step["session_configuration_kind"] == "builder_ii.session_configuration"
        for step in dry_run["steps"]
    )
    assert all(
        step["goose_projection_kind"] == "builder_ii.goose_projection"
        for step in dry_run["steps"]
    )
    assert all(
        step["goose_wrapper_plan_kind"] == "builder_ii.goose_wrapper_plan"
        for step in dry_run["steps"]
    )
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
    dry_run = create_orchestration_dry_run(
        settings, plan, repo_path=str(repo), generic_repo=repo
    )
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
    dry_run = create_orchestration_dry_run(
        settings, plan, repo_path=str(repo), generic_repo=repo
    )
    output = tmp_path / "orchestration-dry-run.json"
    output.write_text(dumps_orchestration_dry_run(dry_run), encoding="utf-8")

    assert validate_orchestration_dry_run_file(output) == []
    assert any(
        "file not found" in error
        for error in validate_orchestration_dry_run_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any(
        "invalid JSON" in error
        for error in validate_orchestration_dry_run_file(bad_json)
    )


def test_goal2_orchestration_assignment_dry_run_passes(tmp_path: Path) -> None:
    fixture = build_goal2_assignment_fixture(tmp_path)
    dry_run = fixture["artifacts"]["dry_run"]
    validation_report = fixture["artifacts"]["validation_report"]

    assert dry_run["kind"] == ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND
    assert dry_run["dry_run_state"] == "DRY_RUN_ONLY"
    assert dry_run["target"] == "generic"
    assert dry_run["planned_bindings"]["agent"]["name"] == "patch_planner"
    assert "model execution" in dry_run["denied_capabilities"]
    assert any("HITL approval" in item for item in dry_run["required_promotions"])
    assert dry_run["expected_evidence"]
    assert dry_run["handoff_expectations"]
    assert dry_run["executes_model"] is False
    assert dry_run["executes_tools"] is False
    assert dry_run["executes_shell"] is False
    assert dry_run["invokes_goose"] is False
    assert dry_run["constructs_deepagents"] is False
    assert dry_run["invokes_mcp"] is False
    assert dry_run["performs_network_calls"] is False
    assert dry_run["mutates_target_repo"] is False
    assert dry_run["grants_authority"] is False
    assert dry_run["artifact_is_authority"] is False
    assert dry_run["requires_human_promotion_for_execution"] is True
    assert dry_run["execution_summary"] == {
        "models_called": 0,
        "tools_called": 0,
        "shell_commands_run": 0,
        "goose_invocations": 0,
        "deepagents_constructed": 0,
        "mcp_calls": 0,
        "network_calls": 0,
        "target_repo_mutations": 0,
        "verification_status": "NOT_RUN",
        "authority_granted": False,
    }
    assert validate_orchestration_assignment_dry_run(dry_run) == []
    assert validate_orchestration_assignment_validation_report(validation_report) == []


def test_goal2_orchestration_assignment_dry_run_rejects_execution_claims(
    tmp_path: Path,
) -> None:
    dry_run = build_goal2_assignment_fixture(tmp_path)["artifacts"]["dry_run"]
    bad = copy.deepcopy(dry_run)
    bad["dry_run_state"] = "EXECUTED"
    bad["executes_model"] = True
    bad["invokes_goose"] = True
    bad["constructs_deepagents"] = True
    bad["invokes_mcp"] = True
    bad["performs_network_calls"] = True
    bad["mutates_target_repo"] = True
    bad["grants_authority"] = True
    bad["execution_summary"]["models_called"] = 1
    bad["execution_summary"]["tools_called"] = 1
    bad["execution_summary"]["shell_commands_run"] = 1
    bad["execution_summary"]["goose_invocations"] = 1
    bad["execution_summary"]["deepagents_constructed"] = 1
    bad["execution_summary"]["mcp_calls"] = 1
    bad["execution_summary"]["network_calls"] = 1
    bad["execution_summary"]["target_repo_mutations"] = 1
    bad["execution_summary"]["verification_status"] = "PASSED"
    bad["execution_summary"]["authority_granted"] = True
    bad["governance"]["runtime_execution"] = "ENABLED"

    errors = validate_orchestration_assignment_dry_run(bad)

    assert "dry_run_state must be DRY_RUN_ONLY" in errors
    assert "executes_model must be false" in errors
    assert "invokes_goose must be false" in errors
    assert "constructs_deepagents must be false" in errors
    assert "invokes_mcp must be false" in errors
    assert "performs_network_calls must be false" in errors
    assert "mutates_target_repo must be false" in errors
    assert "grants_authority must be false" in errors
    assert "execution_summary.models_called must be 0" in errors
    assert "execution_summary.tools_called must be 0" in errors
    assert "execution_summary.shell_commands_run must be 0" in errors
    assert "execution_summary.goose_invocations must be 0" in errors
    assert "execution_summary.deepagents_constructed must be 0" in errors
    assert "execution_summary.mcp_calls must be 0" in errors
    assert "execution_summary.network_calls must be 0" in errors
    assert "execution_summary.target_repo_mutations must be 0" in errors
    assert "execution_summary.verification_status must be NOT_RUN" in errors
    assert "execution_summary.authority_granted must be false" in errors
    assert "governance.runtime_execution must be DISABLED" in errors
    assert (
        "field 'orchestration_assignment_dry_run.dry_run_state' claims active authority state 'EXECUTED'"
        in errors
    )


def test_goal2_orchestration_assignment_dry_run_requires_valid_plan(
    tmp_path: Path,
) -> None:
    orchestration = build_goal2_assignment_fixture(tmp_path)["artifacts"][
        "orchestration"
    ]
    bad_plan = copy.deepcopy(orchestration)
    bad_plan["planned_bindings"]["tools"]["executes_tools"] = True

    try:
        create_orchestration_assignment_dry_run(bad_plan)
    except ValueError as exc:
        assert "planned_bindings.tools.executes_tools must be false" in str(exc)
    else:
        raise AssertionError("invalid orchestration assignment plan should not dry-run")
