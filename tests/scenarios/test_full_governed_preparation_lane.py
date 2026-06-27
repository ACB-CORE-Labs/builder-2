from __future__ import annotations

import json as json_lib
from pathlib import Path

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.config import load_settings
from builder_ii.goose_projection import create_goose_projection, validate_goose_projection
from builder_ii.goose_readonly_session import create_goose_readonly_session_plan, validate_goose_readonly_session_plan
from builder_ii.goose_wrapper_plan import create_goose_wrapper_plan, validate_goose_wrapper_plan
from builder_ii.handoff_artifacts import create_handoff_artifact, validate_handoff_artifact
from builder_ii.orchestration_plan import create_orchestration_plan, validate_orchestration_plan
from builder_ii.session_config import create_session_configuration, validate_session_configuration
from builder_ii.verification_profile_reports import create_verification_profile_report, validate_verification_profile_report


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert_disabled(record: dict) -> None:
    governance = record["governance"]
    assert governance["runtime_execution"] == "DISABLED"
    assert governance["model_execution"] == "DISABLED"
    if "shell_execution" in governance:
        assert governance["shell_execution"] == "DISABLED"
    if "source_writes" in governance:
        assert governance["source_writes"] == "DISABLED"
    if "memory_mutation" in governance:
        assert governance["memory_mutation"] == "DISABLED"
    if "goose_runtime_start" in governance:
        assert governance["goose_runtime_start"] == "DISABLED"
    assert governance["artifact_is_authority"] is False
    assert governance["core_workbench_coupling"] == "NONE"


def test_full_governed_preparation_lane_for_generic_target(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    task = "prepare a full governed lane"

    session_config = create_session_configuration(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
        task=task,
        model_alias="qwen-coder",
        context_pack=".builder/artifacts/context-pack.json",
        generic_repo=repo,
    )
    goose_projection = create_goose_projection(settings, session_config)
    wrapper_plan = create_goose_wrapper_plan(goose_projection)
    orchestration_plan = create_orchestration_plan(
        target="generic",
        task=task,
        roles=("repo_mapper", "context_planner", "patch_planner", "verification_planner", "handoff_scribe"),
    )
    goose_readonly_plan = create_goose_readonly_session_plan(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
        task=task,
        generic_repo=repo,
    )
    verification_report = create_verification_profile_report(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
        task=task,
        goose_readonly_session_plan=goose_readonly_plan,
        generic_repo=repo,
    )
    handoff = create_handoff_artifact(
        target="generic",
        agent_profile="handoff_scribe",
        task=task,
        summary="Prepared the governed lane artifacts.",
        next_steps=("Operator reviews artifacts and records verification evidence separately.",),
        blockers=("No execution evidence has been recorded.",),
        verification=("Verification is planned only; all checks remain NOT_RUN.",),
        created_at="2026-01-01T00:00:00Z",
    )

    assert validate_session_configuration(session_config) == []
    assert validate_goose_projection(goose_projection) == []
    assert validate_goose_wrapper_plan(wrapper_plan) == []
    assert validate_orchestration_plan(orchestration_plan) == []
    assert validate_goose_readonly_session_plan(goose_readonly_plan) == []
    assert validate_verification_profile_report(verification_report) == []
    assert validate_handoff_artifact(handoff) == []

    assert session_config["target_profile"]["name"] == "generic"
    assert "CORE" not in session_config["selected_prompt_profile"]["system_prompt"]
    assert goose_projection["goose_native_surface"]["working_directory"] == str(repo.resolve())
    assert wrapper_plan["operator_launch"]["executes_now"] is False
    assert wrapper_plan["operator_launch"]["requires_operator_execution"] is True
    assert verification_report["report_state"] == "PLANNED_ONLY"
    assert verification_report["completed_verification"] is False
    assert all(check["execution_state"] == "NOT_RUN" for check in verification_report["planned_checks"])

    for record in (
        session_config,
        goose_projection,
        wrapper_plan,
        orchestration_plan,
        goose_readonly_plan,
        verification_report,
        handoff,
    ):
        _assert_disabled(record)

    artifact_values = {
        "session-config.json": session_config,
        "goose-projection.json": goose_projection,
        "goose-wrapper-plan.json": wrapper_plan,
        "orchestration-plan.json": orchestration_plan,
        "goose-readonly-plan.json": goose_readonly_plan,
        "verification-report.json": verification_report,
        "handoff.json": handoff,
    }
    paths: list[Path] = []
    for filename, artifact in artifact_values.items():
        path = tmp_path / "artifacts" / filename
        _write_json(path, artifact)
        paths.append(path)

    chain_report = verify_artifact_chain(paths)

    assert chain_report["valid"] is True
    assert chain_report["status"] == "valid"
    assert chain_report["counts"]["files"] == 7
    assert chain_report["counts"]["native_valid"] == 7
    assert chain_report["counts"]["native_invalid"] == 0
    assert chain_report["counts"]["broken_links"] == 0
    assert chain_report["governance"]["runtime_execution"] == "DISABLED"
    assert chain_report["governance"]["model_execution"] == "DISABLED"
    assert chain_report["governance"]["artifact_is_authority"] is False


def test_builder_target_preparation_lane_remains_separate_from_core_workbench(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    session_config = create_session_configuration(
        settings,
        "builder",
        agent_profile_name="patch_planner",
        verification_profile_name="builder_fast",
        repo_path=str(settings.project_root),
        task="prepare builder target lane",
    )
    goose_projection = create_goose_projection(settings, session_config)
    wrapper_plan = create_goose_wrapper_plan(goose_projection)

    assert validate_session_configuration(session_config) == []
    assert validate_goose_projection(goose_projection) == []
    assert validate_goose_wrapper_plan(wrapper_plan) == []
    assert session_config["target_profile"]["name"] == "builder"
    assert "no CORE Workbench identity" in session_config["target_profile"]["principles"]
    assert session_config["governance"]["core_workbench_coupling"] == "NONE"
    assert goose_projection["governance"]["core_workbench_coupling"] == "NONE"
    assert wrapper_plan["governance"]["core_workbench_coupling"] == "NONE"
    assert wrapper_plan["operator_launch"]["executes_now"] is False
