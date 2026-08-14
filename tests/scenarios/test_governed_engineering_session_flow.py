from __future__ import annotations

import copy
import json as json_lib
from pathlib import Path

from builder_ii.adapters.goose.goose_readonly_session import (
    create_goose_readonly_session_plan,
    validate_goose_readonly_session_plan,
)
from builder_ii.core.artifact_chain_verification import verify_artifact_chain
from builder_ii.core.config import load_settings
from builder_ii.core.handoff_artifacts import create_handoff_artifact, validate_handoff_artifact
from builder_ii.core.session_workflow import create_session_workflow_plan, validate_session_workflow_plan
from builder_ii.lifecycle.candidate.verification_profile_reports import (
    create_verification_profile_report,
    validate_verification_profile_report,
)


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def _write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _assert_disabled_governance(record: dict) -> None:
    governance = record["governance"]
    for key in (
        "runtime_execution",
        "model_execution",
        "shell_execution",
        "source_writes",
        "memory_mutation",
    ):
        if key in governance:
            assert governance[key] == "DISABLED"
    assert governance["artifact_is_authority"] is False
    assert governance["core_workbench_coupling"] == "NONE"


def test_generic_governed_engineering_session_flow_preserves_context_without_runtime_authority(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    task = "Add governed scenario coverage for a generic target repo."

    session_plan = create_session_workflow_plan(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
    )
    goose_plan = create_goose_readonly_session_plan(
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
        goose_readonly_session_plan=goose_plan,
        generic_repo=repo,
    )
    handoff = create_handoff_artifact(
        target="generic",
        agent_profile="handoff_scribe",
        task=task,
        summary="Prepared a governed generic engineering session without runtime activation.",
        next_steps=("Operator runs the planned verification commands and records evidence.",),
        blockers=("No runtime authority has been granted.",),
        verification=("Verification report is PLANNED_ONLY; all checks are NOT_RUN.",),
        created_at="2026-01-01T00:00:00Z",
    )

    assert validate_session_workflow_plan(session_plan) == []
    assert validate_goose_readonly_session_plan(goose_plan) == []
    assert validate_verification_profile_report(verification_report) == []
    assert validate_handoff_artifact(handoff) == []

    assert session_plan["target_profile"]["name"] == "generic"
    assert session_plan["selected_agent_profile"]["name"] == "patch_planner"
    assert session_plan["selected_prompt_profile"]["name"] == "generic_default"
    assert session_plan["selected_verification_profile"]["name"] == "generic_basic"
    assert "CORE" not in session_plan["selected_prompt_profile"]["system_prompt"]

    assert goose_plan["target_profile"]["name"] == "generic"
    assert goose_plan["selected_agent_profile"]["name"] == "patch_planner"
    assert goose_plan["runtime_mode"] == "read_only"
    assert goose_plan["shell_execution"] == "DISABLED"
    assert goose_plan["autonomous_writes"] == "DISABLED"
    assert "GOOSE GOVERNED READ-ONLY SESSION INSTRUCTIONS" in goose_plan["goose_instructions"]
    assert "No commands may be executed directly by Goose" in goose_plan["goose_instructions"]

    assert verification_report["report_state"] == "PLANNED_ONLY"
    assert verification_report["completed_verification"] is False
    assert verification_report["planned_checks"]
    assert all(check["execution_state"] == "NOT_RUN" for check in verification_report["planned_checks"])
    assert all(check["completed_evidence_ref"] is None for check in verification_report["planned_checks"])

    assert handoff["target"] == "generic"
    assert handoff["agent_profile"] == "handoff_scribe"
    assert handoff["verification"] == ["Verification report is PLANNED_ONLY; all checks are NOT_RUN."]

    for record in (session_plan, goose_plan, verification_report, handoff):
        _assert_disabled_governance(record)

    session_plan_path = tmp_path / "artifacts" / "session-plan.json"
    goose_plan_path = tmp_path / "artifacts" / "goose-readonly-session-plan.json"
    verification_report_path = tmp_path / "artifacts" / "verification-profile-report.json"
    handoff_path = tmp_path / "artifacts" / "handoff.json"
    _write_json(session_plan_path, session_plan)
    _write_json(goose_plan_path, goose_plan)
    _write_json(verification_report_path, verification_report)
    _write_json(handoff_path, handoff)

    chain_report = verify_artifact_chain([session_plan_path, goose_plan_path, verification_report_path, handoff_path])

    assert chain_report["valid"] is True
    assert chain_report["status"] == "valid"
    assert chain_report["counts"]["files"] == 4
    assert chain_report["counts"]["native_valid"] == 4
    assert chain_report["counts"]["native_invalid"] == 0
    assert chain_report["counts"]["broken_links"] == 0
    assert chain_report["governance"]["runtime_execution"] == "DISABLED"
    assert chain_report["governance"]["model_execution"] == "DISABLED"
    assert chain_report["governance"]["artifact_is_authority"] is False


def test_governed_engineering_session_rejects_false_verification_and_runtime_claims(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    task = "Reject false completion claims in a governed generic session."

    goose_plan = create_goose_readonly_session_plan(
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
        goose_readonly_session_plan=goose_plan,
        generic_repo=repo,
    )

    false_report = copy.deepcopy(verification_report)
    false_report["report_state"] = "PASSED"
    false_report["completed_verification"] = True
    false_report["governance"]["report_is_completed_evidence"] = True
    false_report["planned_checks"][0]["execution_state"] = "PASSED"
    false_report["planned_checks"][0]["completed_evidence_ref"] = "operator-evidence.txt"

    report_errors = validate_verification_profile_report(false_report)

    assert "report_state must be PLANNED_ONLY" in report_errors
    assert "completed_verification must be false or NOT_AUTHORIZED" in report_errors
    assert "governance.report_is_completed_evidence must be false or NOT_AUTHORIZED" in report_errors
    assert any("execution_state must be NOT_RUN" in error for error in report_errors)
    assert any("completed_evidence_ref must be null" in error for error in report_errors)

    false_goose_plan = copy.deepcopy(goose_plan)
    false_goose_plan["shell_execution"] = "ENABLED"
    false_goose_plan["governance"]["runtime_execution"] = "ENABLED"

    goose_plan_path = tmp_path / "artifacts" / "false-goose-readonly-session-plan.json"
    _write_json(goose_plan_path, false_goose_plan)

    chain_report = verify_artifact_chain([goose_plan_path])

    assert chain_report["valid"] is False
    assert chain_report["status"] == "invalid"
    assert chain_report["counts"]["native_invalid"] == 1
    assert any("shell_execution must be DISABLED or NOT_AUTHORIZED" in error for error in chain_report["errors"])
    assert any(
        "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in error for error in chain_report["errors"]
    )
