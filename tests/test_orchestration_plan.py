from __future__ import annotations

import copy
from pathlib import Path

from builder_ii.orchestration_plan import (
    ORCHESTRATION_PLAN_KIND,
    create_orchestration_plan,
    dumps_orchestration_plan,
    validate_orchestration_plan,
    validate_orchestration_plan_file,
)


def test_create_default_orchestration_plan() -> None:
    plan = create_orchestration_plan(target="generic", task="coordinate a governed patch planning flow")

    assert plan["kind"] == ORCHESTRATION_PLAN_KIND
    assert plan["plan_state"] == "PLANNED_ONLY"
    assert plan["target"] == "generic"
    assert plan["orchestration_mode"] == "plan_only"
    assert [step["role"] for step in plan["roles"]] == [
        "repo_mapper",
        "context_planner",
        "patch_planner",
        "verification_planner",
        "handoff_scribe",
    ]
    assert plan["roles"][0]["depends_on"] == []
    assert plan["roles"][1]["depends_on"] == ["step_1_repo_mapper"]
    assert all(step["runtime_binding"] == "UNBOUND" for step in plan["roles"])
    assert all("execute_shell" in step["forbidden_tools"] for step in plan["roles"])
    assert plan["governance"]["runtime_execution"] == "DISABLED"
    assert plan["governance"]["deepagents_runtime_start"] == "DISABLED"
    assert plan["governance"]["subagent_construction"] == "DISABLED"
    assert plan["governance"]["artifact_is_authority"] is False
    assert validate_orchestration_plan(plan) == []


def test_create_custom_orchestration_plan() -> None:
    plan = create_orchestration_plan(
        target="builder",
        task="review a session configuration patch",
        roles=("code_reviewer", "verification_planner", "handoff_scribe"),
    )

    assert plan["target"] == "builder"
    assert plan["handoff"]["entry_role"] == "code_reviewer"
    assert plan["handoff"]["exit_role"] == "handoff_scribe"
    assert [step["role"] for step in plan["roles"]] == ["code_reviewer", "verification_planner", "handoff_scribe"]
    assert validate_orchestration_plan(plan) == []


def test_orchestration_plan_rejects_runtime_escalation() -> None:
    plan = create_orchestration_plan(target="generic", task="reject runtime escalation")
    bad = copy.deepcopy(plan)
    bad["plan_state"] = "EXECUTED"
    bad["roles"][0]["runtime_binding"] = "deepagents"
    bad["governance"]["deepagents_runtime_start"] = "ENABLED"
    bad["governance"]["subagent_construction"] = "ENABLED"

    errors = validate_orchestration_plan(bad)

    assert "plan_state must be PLANNED_ONLY" in errors
    assert "roles[0].runtime_binding must be UNBOUND" in errors
    assert "governance.deepagents_runtime_start must be DISABLED" in errors
    assert "governance.subagent_construction must be DISABLED" in errors


def test_orchestration_plan_file_validation(tmp_path: Path) -> None:
    plan = create_orchestration_plan(target="generic", task="validate orchestration file")
    output = tmp_path / "orchestration-plan.json"
    output.write_text(dumps_orchestration_plan(plan), encoding="utf-8")

    assert validate_orchestration_plan_file(output) == []
    assert any("file not found" in error for error in validate_orchestration_plan_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_orchestration_plan_file(bad_json))
