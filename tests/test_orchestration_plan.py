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
from builder_ii.orchestration_assignment import (
    AGENT_ASSIGNMENT_PLAN_KIND,
    ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
    create_orchestration_assignment_plan,
    validate_agent_assignment_plan,
    validate_orchestration_assignment_plan,
)
from orchestration_assignment_fixtures import build_goal2_assignment_fixture


def test_create_default_orchestration_plan() -> None:
    plan = create_orchestration_plan(
        target="generic", task="coordinate a governed patch planning flow"
    )

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
    assert [step["role"] for step in plan["roles"]] == [
        "code_reviewer",
        "verification_planner",
        "handoff_scribe",
    ]
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
    plan = create_orchestration_plan(
        target="generic", task="validate orchestration file"
    )
    output = tmp_path / "orchestration-plan.json"
    output.write_text(dumps_orchestration_plan(plan), encoding="utf-8")

    assert validate_orchestration_plan_file(output) == []
    assert any(
        "file not found" in error
        for error in validate_orchestration_plan_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any(
        "invalid JSON" in error for error in validate_orchestration_plan_file(bad_json)
    )


def test_goal2_assignment_and_orchestration_plan_happy_path(tmp_path: Path) -> None:
    fixture = build_goal2_assignment_fixture(tmp_path)
    assignment = fixture["artifacts"]["assignment"]
    orchestration = fixture["artifacts"]["orchestration"]

    assert assignment["kind"] == AGENT_ASSIGNMENT_PLAN_KIND
    assert assignment["assignment_state"] == "BOUND_ONLY"
    assert assignment["target"] == "generic"
    assert assignment["bindings"]["agent"]["name"] == "patch_planner"
    assert (
        assignment["bindings"]["task"]["profile_entry_id"]
        == "task-profile-planning-contract"
    )
    assert assignment["bindings"]["tools"]["default_policy"] == "denied"
    assert assignment["bindings"]["hitl"]["approval_state"] == "NOT_GRANTED"
    assert assignment["bindings"]["verification"]["verification_status"] == "NOT_RUN"
    assert assignment["executes_model"] is False
    assert assignment["executes_tools"] is False
    assert assignment["executes_shell"] is False
    assert assignment["invokes_goose"] is False
    assert assignment["constructs_deepagents"] is False
    assert assignment["invokes_mcp"] is False
    assert assignment["performs_network_calls"] is False
    assert assignment["mutates_target_repo"] is False
    assert assignment["grants_authority"] is False
    assert assignment["artifact_is_authority"] is False
    assert assignment["requires_human_promotion_for_execution"] is True
    assert validate_agent_assignment_plan(assignment) == []

    assert orchestration["kind"] == ORCHESTRATION_ASSIGNMENT_PLAN_KIND
    assert orchestration["orchestration_mode"] == "passive_assignment_v2"
    assert orchestration["planned_bindings"]["model"]["executes_model"] is False
    assert "model execution" in orchestration["denied_capabilities"]
    assert any("HITL approval" in item for item in orchestration["required_promotions"])
    assert validate_orchestration_assignment_plan(orchestration) == []


def test_goal2_assignment_missing_required_refs_fail_closed(tmp_path: Path) -> None:
    assignment = build_goal2_assignment_fixture(tmp_path)["artifacts"]["assignment"]

    missing_cases = {
        "target_profile": "missing target_profile ref",
        "agent_profile": "missing agent_profile ref",
        "task_profile": "missing task_profile ref",
        "verification_profile": "missing verification_profile ref",
        "model_recommendation": "missing model_recommendation ref",
    }
    for role, expected_error in missing_cases.items():
        bad = copy.deepcopy(assignment)
        bad["source_refs"] = [ref for ref in bad["source_refs"] if ref["role"] != role]

        assert expected_error in validate_agent_assignment_plan(bad)


def test_goal2_assignment_unknown_profiles_and_policy_refs_fail_closed(
    tmp_path: Path,
) -> None:
    assignment = build_goal2_assignment_fixture(tmp_path)["artifacts"]["assignment"]

    bad_target = copy.deepcopy(assignment)
    bad_target["bindings"]["target"]["name"] = "unknown"
    assert (
        "bindings.target.name must be a known target profile"
        in validate_agent_assignment_plan(bad_target)
    )

    bad_agent = copy.deepcopy(assignment)
    bad_agent["bindings"]["agent"]["name"] = "runtime_agent"
    assert (
        "bindings.agent.name must be a known agent profile"
        in validate_agent_assignment_plan(bad_agent)
    )

    bad_task = copy.deepcopy(assignment)
    for ref in bad_task["source_refs"]:
        if ref["role"] == "task_profile":
            ref["entry_id"] = "unknown-task-profile"
    assert (
        "source_refs.task_profile.entry_id must be task-profile-planning-contract"
        in validate_agent_assignment_plan(bad_task)
    )

    bad_verification = copy.deepcopy(assignment)
    bad_verification["bindings"]["verification"]["name"] = "unknown_verifier"
    assert (
        "bindings.verification.name must be a known verification profile"
        in validate_agent_assignment_plan(bad_verification)
    )

    bad_tool_policy = copy.deepcopy(assignment)
    for ref in bad_tool_policy["source_refs"]:
        if ref["role"] == "tool_policy":
            ref["profile_kind"] = "runtime_tool_policy"
    assert (
        "source_refs.tool_policy.profile_kind must be tool_profile"
        in validate_agent_assignment_plan(bad_tool_policy)
    )


def test_goal2_assignment_digest_mismatch_and_lifecycle_mismatch_fail_closed(
    tmp_path: Path,
) -> None:
    assignment = build_goal2_assignment_fixture(tmp_path)["artifacts"]["assignment"]

    bad_digest = copy.deepcopy(assignment)
    bad_digest["source_digests"]["model_recommendation"] = "a" * 64
    assert (
        "source_digests.model_recommendation must match model_recommendation ref sha256"
        in validate_agent_assignment_plan(bad_digest)
    )

    bad_pack = copy.deepcopy(assignment)
    bad_pack["profile_pack_lifecycle"]["lifecycle_bindings"]["dry_run_sha256"] = (
        bad_pack["profile_pack_lifecycle"]["manifest_sha256"]
    )
    assert (
        "profile_pack_lifecycle.lifecycle_bindings.dry_run_sha256 must match dry_run_sha256"
        in validate_agent_assignment_plan(bad_pack)
    )


def test_goal2_assignment_model_recommendation_binding_fails_closed(
    tmp_path: Path,
) -> None:
    assignment = build_goal2_assignment_fixture(tmp_path)["artifacts"]["assignment"]

    bad_recommendation = copy.deepcopy(assignment)
    bad_recommendation["model_routing"]["recommendation"]["recommended_candidates"][0][
        "model_id"
    ] = "unknown-model"
    errors = validate_agent_assignment_plan(bad_recommendation)
    assert any("model_routing.recommendation invalid" in error for error in errors)

    unbound_recommendation = copy.deepcopy(assignment)
    unbound_recommendation["model_routing"]["recommendation"]["source_policy_ref"][
        "sha256"
    ] = "b" * 64
    assert (
        "model routing recommendation must be bound to the model_policy source ref"
        in validate_agent_assignment_plan(unbound_recommendation)
    )


def test_goal2_assignment_rejects_unknown_kind_and_active_authority_states(
    tmp_path: Path,
) -> None:
    assignment = build_goal2_assignment_fixture(tmp_path)["artifacts"]["assignment"]

    bad_kind = copy.deepcopy(assignment)
    bad_kind["source_refs"][0]["kind"] = "builder_ii.unknown_artifact"
    assert (
        "source_refs.target_profile.kind is an unknown artifact kind"
        in validate_agent_assignment_plan(bad_kind)
    )

    bad_active = copy.deepcopy(assignment)
    bad_active["bindings"]["hitl"]["approval_state"] = "AUTHORIZED"
    bad_active["governance"]["tool_execution"] = "ENABLED"
    errors = validate_agent_assignment_plan(bad_active)

    assert (
        "field 'assignment.bindings.hitl.approval_state' claims active authority state 'AUTHORIZED'"
        in errors
    )
    assert (
        "field 'assignment.governance.tool_execution' claims active authority state 'ENABLED'"
        in errors
    )
    assert "governance.tool_execution must be DISABLED" in errors


def test_goal2_orchestration_assignment_plan_rejects_authority_escalation(
    tmp_path: Path,
) -> None:
    assignment = build_goal2_assignment_fixture(tmp_path)["artifacts"]["assignment"]
    plan = create_orchestration_assignment_plan(assignment)
    bad = copy.deepcopy(plan)
    bad["plan_state"] = "EXECUTED"
    bad["executes_tools"] = True
    bad["planned_bindings"]["verification"]["verification_status"] = "PASSED"
    bad["governance"]["network_calls"] = "ENABLED"

    errors = validate_orchestration_assignment_plan(bad)

    assert "plan_state must be BOUND_ONLY" in errors
    assert "executes_tools must be false" in errors
    assert "planned_bindings.verification.verification_status must be NOT_RUN" in errors
    assert "governance.network_calls must be DISABLED" in errors
    assert (
        "field 'orchestration_assignment_plan.plan_state' claims active authority state 'EXECUTED'"
        in errors
    )
