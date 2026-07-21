from __future__ import annotations

import json as json_lib
from pathlib import Path

from builder_ii.adapters.deepagents.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.adapters.deepagents.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND,
    DEEPAGENTS_HUMAN_GATE_REQUEST_KIND,
    DEEPAGENTS_PROPOSAL_RESULT_KIND,
    DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
    DEEPAGENTS_SUBAGENT_RESULT_KIND,
    DEEPAGENTS_SUBAGENT_REVIEW_KIND,
    DEEPAGENTS_WORK_PLAN_KIND,
    DEEPAGENTS_WORK_VALIDATION_REPORT_KIND,
    create_deepagents_blocked_action_record,
    create_deepagents_human_gate_request,
    create_deepagents_proposal_result,
    create_deepagents_subagent_assignment,
    create_deepagents_subagent_result,
    create_deepagents_subagent_review,
    create_deepagents_work_plan,
    create_deepagents_work_validation_report,
    validate_deepagents_blocked_action_record,
    validate_deepagents_human_gate_request,
    validate_deepagents_proposal_result,
    validate_deepagents_subagent_assignment,
    validate_deepagents_subagent_result,
    validate_deepagents_subagent_review,
    validate_deepagents_work_plan,
    validate_deepagents_work_plan_file,
    validate_deepagents_work_validation_report,
    write_deepagents_work_plan,
)
from builder_ii.core.config import load_settings
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture


def test_deepagents_work_plan_lifecycle(tmp_path: Path) -> None:
    # 1. Setup prerequisite fixtures
    goal2_fixture = build_goal2_assignment_fixture(tmp_path, task="Goal 3 passive work artifacts testing")

    orchestration_assignment_plan = goal2_fixture["artifacts"]["orchestration"]
    orchestration_assignment_dry_run = goal2_fixture["artifacts"]["dry_run"]

    deepagents_policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    deepagents_readiness = create_deepagents_readiness_artifact(mode="metadata_only")

    policy_path = tmp_path / "deepagents-policy.json"
    readiness_path = tmp_path / "deepagents-readiness.json"

    policy_path.write_text(json_lib.dumps(deepagents_policy), encoding="utf-8")
    readiness_path.write_text(json_lib.dumps(deepagents_readiness), encoding="utf-8")

    # 2. Construct Work Plan
    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Goal 3 passive work plan execution test",
        orchestration_assignment_plan=orchestration_assignment_plan,
        orchestration_assignment_dry_run=orchestration_assignment_dry_run,
        deepagents_policy=deepagents_policy,
        deepagents_readiness=deepagents_readiness,
        orchestration_assignment_plan_path=goal2_fixture["paths"]["orchestration"],
        orchestration_assignment_dry_run_path=goal2_fixture["paths"]["dry_run"],
        deepagents_policy_path=policy_path,
        deepagents_readiness_path=readiness_path,
        proposed_subagents=["repo_mapper", "code_reviewer"],
        expected_outputs=["deepagents_work_plan", "subagent_assignment"],
        review_gates=["operator_review"],
        blocked_capabilities=["model execution", "shell execution"],
    )

    assert work_plan["kind"] == DEEPAGENTS_WORK_PLAN_KIND
    assert work_plan["schema_version"] == 1
    assert work_plan["plan_state"] == "PLANNED_ONLY"
    assert work_plan["mode"] == "proposal_only"
    assert work_plan["target"] == "builder"
    assert work_plan["proposed_subagents"] == ["repo_mapper", "code_reviewer"]
    assert work_plan["executes_model"] is False
    assert work_plan["governance"]["subagent_construction"] == "DISABLED"
    assert validate_deepagents_work_plan(work_plan) == []

    # 3. Test validation errors on work plan
    bad_plan = dict(work_plan)
    bad_plan["orchestration_assignment_plan_ref"] = {"invalid": "ref"}
    assert len(validate_deepagents_work_plan(bad_plan)) > 0

    bad_plan_digests = dict(work_plan)
    bad_plan_digests["source_digests"] = {"orchestration_assignment_plan": "badsha"}
    assert len(validate_deepagents_work_plan(bad_plan_digests)) > 0

    bad_plan_wrong_kind = dict(work_plan)
    bad_plan_wrong_kind["orchestration_assignment_plan_ref"] = dict(work_plan["orchestration_assignment_plan_ref"])
    bad_plan_wrong_kind["orchestration_assignment_plan_ref"]["kind"] = "wrong.kind"
    assert len(validate_deepagents_work_plan(bad_plan_wrong_kind)) > 0

    bad_plan_missing_source = dict(work_plan)
    bad_plan_missing_source["source_refs"] = [
        ref for ref in work_plan["source_refs"] if ref["role"] != "orchestration_assignment_plan"
    ]
    errors = validate_deepagents_work_plan(bad_plan_missing_source)
    assert any("missing orchestration_assignment_plan source ref" in err for err in errors)

    bad_plan_unknown_blocked = dict(work_plan)
    bad_plan_unknown_blocked["blocked_capabilities"] = ["telepathy"]
    errors = validate_deepagents_work_plan(bad_plan_unknown_blocked)
    assert any("unknown denied capability" in err for err in errors)

    invalid_source = dict(orchestration_assignment_plan)
    invalid_source["executes_model"] = True
    try:
        create_deepagents_work_plan(
            target="builder",
            task="reject invalid source",
            orchestration_assignment_plan=invalid_source,
            orchestration_assignment_dry_run=orchestration_assignment_dry_run,
            deepagents_policy=deepagents_policy,
            deepagents_readiness=deepagents_readiness,
        )
        assert False, "invalid source artifact should fail before binding"
    except ValueError as exc:
        assert "orchestration assignment plan" in str(exc)


def test_subagent_assignment_and_result(tmp_path: Path) -> None:
    # 1. Setup prerequisite fixtures
    goal2_fixture = build_goal2_assignment_fixture(tmp_path)
    plan_data = goal2_fixture["artifacts"]["orchestration"]
    dry_run_data = goal2_fixture["artifacts"]["dry_run"]
    policy_data = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness_data = create_deepagents_readiness_artifact(mode="metadata_only")

    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Test task",
        orchestration_assignment_plan=plan_data,
        orchestration_assignment_dry_run=dry_run_data,
        deepagents_policy=policy_data,
        deepagents_readiness=readiness_data,
    )

    # 2. Assignment
    assignment = create_deepagents_subagent_assignment(
        target="builder",
        task="Map relevant repository files",
        subagent_profile="repo_mapper",
        work_plan=work_plan,
        work_plan_path=tmp_path / "work-plan.json",
    )
    assert assignment["kind"] == DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND
    assert assignment["assignment_state"] == "ASSIGNED_ONLY"
    assert assignment["result_mode"] == "PROPOSAL_ONLY"
    assert assignment["constructs_subagents"] is False
    assert validate_deepagents_subagent_assignment(assignment) == []

    # 3. Result
    result = create_deepagents_subagent_result(
        target="builder",
        subagent_profile="repo_mapper",
        summary="Repository mapped successfully",
        subagent_assignment=assignment,
        subagent_assignment_path=tmp_path / "subagent-assignment.json",
    )
    assert result["kind"] == DEEPAGENTS_SUBAGENT_RESULT_KIND
    assert result["result_state"] == "RECORDED_ONLY"
    assert validate_deepagents_subagent_result(result) == []

    bad_assignment = dict(assignment)
    bad_assignment["constructs_subagents"] = True
    assert len(validate_deepagents_subagent_assignment(bad_assignment)) > 0

    # Result active escalation checks
    for claim in (
        "EXECUTED",
        "authorized by operator",
        "verified truth",
        "applied patch",
        "merged result",
        "promoted capability",
        "enabled runtime",
        "APPROVED",
    ):
        bad_result = dict(result)
        bad_result["custom_claim"] = claim
        errors = validate_deepagents_subagent_result(bad_result)
        assert any("claims active authority state" in err for err in errors)

    denied_result = dict(result)
    denied_result["custom_claim"] = "not authorized and blocked by policy"
    assert validate_deepagents_subagent_result(denied_result) == []


def test_subagent_review_and_proposal_result(tmp_path: Path) -> None:
    goal2_fixture = build_goal2_assignment_fixture(tmp_path)
    plan_data = goal2_fixture["artifacts"]["orchestration"]
    dry_run_data = goal2_fixture["artifacts"]["dry_run"]
    policy_data = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness_data = create_deepagents_readiness_artifact(mode="metadata_only")

    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Test task",
        orchestration_assignment_plan=plan_data,
        orchestration_assignment_dry_run=dry_run_data,
        deepagents_policy=policy_data,
        deepagents_readiness=readiness_data,
    )

    assignment = create_deepagents_subagent_assignment(
        target="builder",
        task="Map files",
        subagent_profile="repo_mapper",
        work_plan=work_plan,
        work_plan_path=tmp_path / "work-plan.json",
    )

    result = create_deepagents_subagent_result(
        target="builder",
        subagent_profile="repo_mapper",
        summary="Done",
        subagent_assignment=assignment,
        subagent_assignment_path=tmp_path / "assignment.json",
    )

    # 1. Review
    review = create_deepagents_subagent_review(
        target="builder",
        disposition="accepted_as_proposal",
        subagent_result=result,
        subagent_assignment=assignment,
        subagent_result_path=tmp_path / "result.json",
        subagent_assignment_path=tmp_path / "assignment.json",
    )
    assert review["kind"] == DEEPAGENTS_SUBAGENT_REVIEW_KIND
    assert review["review_state"] == "REVIEW_ONLY"
    assert review["disposition"] == "accepted_as_proposal"
    assert validate_deepagents_subagent_review(review) == []

    bad_review = dict(review)
    bad_review["grants_authority"] = True
    assert len(validate_deepagents_subagent_review(bad_review)) > 0

    # Review disposition validation check
    try:
        create_deepagents_subagent_review(
            target="builder",
            disposition="APPROVED",
            subagent_result=result,
            subagent_assignment=assignment,
        )
        assert False, "Should raise ValueError on invalid disposition option"
    except ValueError:
        pass

    # 2. Proposal Result
    proposal = create_deepagents_proposal_result(
        target="builder",
        work_plan=work_plan,
        reviewed_results=[result],
        work_plan_path=tmp_path / "work-plan.json",
        reviewed_result_paths=[tmp_path / "result.json"],
    )
    assert proposal["kind"] == DEEPAGENTS_PROPOSAL_RESULT_KIND
    assert proposal["proposal_state"] == "PROPOSAL_ONLY"
    assert validate_deepagents_proposal_result(proposal) == []

    # Escalation check on proposal
    bad_proposal = dict(proposal)
    bad_proposal["governance"] = dict(proposal["governance"])
    bad_proposal["governance"]["runtime_execution"] = "ENABLED"
    assert len(validate_deepagents_proposal_result(bad_proposal)) > 0

    for claim in ("applied", "merged", "promoted", "enabled"):
        bad_claim = dict(proposal)
        bad_claim["custom_claim"] = claim
        errors = validate_deepagents_proposal_result(bad_claim)
        assert any("claims active authority state" in err for err in errors)

    try:
        create_deepagents_proposal_result(
            target="builder",
            work_plan=work_plan,
            reviewed_results=[],
        )
        assert False, "proposal result must require at least one reviewed result"
    except ValueError as exc:
        assert "reviewed_results" in str(exc)


def test_human_gate_request_and_blocked_action(tmp_path: Path) -> None:
    goal2_fixture = build_goal2_assignment_fixture(tmp_path)
    plan_data = goal2_fixture["artifacts"]["orchestration"]
    dry_run_data = goal2_fixture["artifacts"]["dry_run"]
    policy_data = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness_data = create_deepagents_readiness_artifact(mode="metadata_only")

    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Test task",
        orchestration_assignment_plan=plan_data,
        orchestration_assignment_dry_run=dry_run_data,
        deepagents_policy=policy_data,
        deepagents_readiness=readiness_data,
    )

    # 1. Human Gate Request
    req = create_deepagents_human_gate_request(
        target="builder",
        reviewed_artifact=work_plan,
        reviewed_artifact_path=tmp_path / "work-plan.json",
    )
    assert req["kind"] == DEEPAGENTS_HUMAN_GATE_REQUEST_KIND
    assert req["gate_state"] == "REQUESTED_ONLY"
    assert req["approval_state"] == "NOT_GRANTED"
    assert req["grants_authority"] is False
    assert validate_deepagents_human_gate_request(req) == []

    # Escalation check
    bad_req = dict(req)
    bad_req["approval_state"] = "GRANTED"
    assert len(validate_deepagents_human_gate_request(bad_req)) > 0

    bad_req_authority = dict(req)
    bad_req_authority["grants_authority"] = True
    assert len(validate_deepagents_human_gate_request(bad_req_authority)) > 0

    # 2. Blocked Action Record
    blocked = create_deepagents_blocked_action_record(
        target="builder",
        denied_capability="shell execution",
        triggering_artifact=work_plan,
        triggering_artifact_path=tmp_path / "work-plan.json",
    )
    assert blocked["kind"] == DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND
    assert blocked["record_state"] == "BLOCKED_ONLY"
    assert blocked["denied_capability"] == "shell execution"
    assert validate_deepagents_blocked_action_record(blocked) == []

    blocked_without_trigger = create_deepagents_blocked_action_record(
        target="builder",
        denied_capability="model execution",
    )
    assert blocked_without_trigger["source_refs"] == []
    assert blocked_without_trigger["source_digests"] == {}
    assert validate_deepagents_blocked_action_record(blocked_without_trigger) == []

    bad_blocked = dict(blocked)
    bad_blocked["denied_capability"] = "unknown capability"
    assert len(validate_deepagents_blocked_action_record(bad_blocked)) > 0


def test_work_validation_report(tmp_path: Path) -> None:
    goal2_fixture = build_goal2_assignment_fixture(tmp_path)
    plan_data = goal2_fixture["artifacts"]["orchestration"]
    dry_run_data = goal2_fixture["artifacts"]["dry_run"]
    policy_data = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness_data = create_deepagents_readiness_artifact(mode="metadata_only")

    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Test task",
        orchestration_assignment_plan=plan_data,
        orchestration_assignment_dry_run=dry_run_data,
        deepagents_policy=policy_data,
        deepagents_readiness=readiness_data,
    )

    report = create_deepagents_work_validation_report(
        subject=work_plan,
        subject_path=tmp_path / "work-plan.json",
    )

    assert report["kind"] == DEEPAGENTS_WORK_VALIDATION_REPORT_KIND
    assert report["validation_state"] == "VALIDATION_ONLY"
    assert report["status"] == "valid"
    assert report["valid"] is True, report["errors"]
    assert report["errors"] == []
    assert validate_deepagents_work_validation_report(report) == []

    # Validate file loaders
    plan_file = tmp_path / "plan.json"
    write_deepagents_work_plan(work_plan, plan_file)
    assert validate_deepagents_work_plan_file(plan_file) == []


def test_deepagents_work_cli(tmp_path: Path) -> None:
    from builder_ii.deepagents_cli import deepagents_app
    from typer.testing import CliRunner

    runner = CliRunner()
    command_names = {command.name for command in deepagents_app.registered_commands}
    assert {
        "policy",
        "validate",
        "readiness",
        "validate-readiness",
        "delegate",
        "work-plan",
        "assign-subagent",
        "record-result",
        "review-result",
        "request-human-gate",
        "record-blocked-action",
        "proposal-result",
        "validate-work-artifact",
    }.issubset(command_names)

    forbidden = runner.invoke(deepagents_app, ["delegate"])
    assert forbidden.exit_code == 1
    assert "forbidden/unpromoted" in forbidden.output

    goal2_fixture = build_goal2_assignment_fixture(tmp_path)

    plan_path = goal2_fixture["paths"]["orchestration"]
    dry_run_path = goal2_fixture["paths"]["dry_run"]

    deepagents_policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    deepagents_readiness = create_deepagents_readiness_artifact(mode="metadata_only")

    policy_path = tmp_path / "deepagents-policy.json"
    readiness_path = tmp_path / "deepagents-readiness.json"

    policy_path.write_text(json_lib.dumps(deepagents_policy), encoding="utf-8")
    readiness_path.write_text(json_lib.dumps(deepagents_readiness), encoding="utf-8")

    output_plan = tmp_path / "deepagents-work-plan.json"

    # Test work-plan CLI
    result = runner.invoke(
        deepagents_app,
        [
            "work-plan",
            "--target",
            "builder",
            "--task",
            "CLI test task",
            "--assignment-plan",
            str(plan_path),
            "--assignment-dry-run",
            str(dry_run_path),
            "--policy",
            str(policy_path),
            "--readiness",
            str(readiness_path),
            "--output",
            str(output_plan),
        ],
    )
    assert result.exit_code == 0
    assert output_plan.exists()

    # Test assign-subagent CLI
    output_assign = tmp_path / "subagent-assignment.json"
    result = runner.invoke(
        deepagents_app,
        [
            "assign-subagent",
            "--target",
            "builder",
            "--task",
            "subagent task",
            "--subagent-profile",
            "repo_mapper",
            "--work-plan",
            str(output_plan),
            "--output",
            str(output_assign),
        ],
    )
    assert result.exit_code == 0
    assert output_assign.exists()

    # Test record-result CLI
    output_result = tmp_path / "subagent-result.json"
    result = runner.invoke(
        deepagents_app,
        [
            "record-result",
            "--target",
            "builder",
            "--subagent-profile",
            "repo_mapper",
            "--summary",
            "cli result summary",
            "--subagent-assignment",
            str(output_assign),
            "--output",
            str(output_result),
        ],
    )
    assert result.exit_code == 0
    assert output_result.exists()

    # Test review-result CLI
    output_review = tmp_path / "subagent-review.json"
    result = runner.invoke(
        deepagents_app,
        [
            "review-result",
            "--target",
            "builder",
            "--disposition",
            "accepted_as_proposal",
            "--subagent-result",
            str(output_result),
            "--subagent-assignment",
            str(output_assign),
            "--output",
            str(output_review),
        ],
    )
    assert result.exit_code == 0
    assert output_review.exists()

    # Test request-human-gate CLI
    output_gate = tmp_path / "human-gate-request.json"
    result = runner.invoke(
        deepagents_app,
        [
            "request-human-gate",
            "--target",
            "builder",
            "--reviewed-artifact",
            str(output_plan),
            "--output",
            str(output_gate),
        ],
    )
    assert result.exit_code == 0
    assert output_gate.exists()

    # Test record-blocked-action CLI
    output_blocked = tmp_path / "blocked-action.json"
    result = runner.invoke(
        deepagents_app,
        [
            "record-blocked-action",
            "--target",
            "builder",
            "--denied-capability",
            "shell execution",
            "--triggering-artifact",
            str(output_plan),
            "--output",
            str(output_blocked),
        ],
    )
    assert result.exit_code == 0
    assert output_blocked.exists()

    # Test proposal-result CLI
    output_prop = tmp_path / "proposal-result.json"
    result = runner.invoke(
        deepagents_app,
        [
            "proposal-result",
            "--target",
            "builder",
            "--work-plan",
            str(output_plan),
            "--reviewed-result",
            str(output_result),
            "--output",
            str(output_prop),
        ],
    )
    assert result.exit_code == 0
    assert output_prop.exists()

    # Test validate-work-artifact CLI
    result = runner.invoke(
        deepagents_app,
        [
            "validate-work-artifact",
            str(output_plan),
        ],
    )
    assert result.exit_code == 0
    assert "Deepagents work artifact is valid" in result.output


def test_deepagents_chain_verification(tmp_path: Path) -> None:
    from builder_ii.core.artifact_chain_verification import extract_references

    goal2_fixture = build_goal2_assignment_fixture(tmp_path)
    plan_data = goal2_fixture["artifacts"]["orchestration"]
    dry_run_data = goal2_fixture["artifacts"]["dry_run"]
    policy_data = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness_data = create_deepagents_readiness_artifact(mode="metadata_only")

    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Test task",
        orchestration_assignment_plan=plan_data,
        orchestration_assignment_dry_run=dry_run_data,
        deepagents_policy=policy_data,
        deepagents_readiness=readiness_data,
        orchestration_assignment_plan_path=Path("plan.json"),
        orchestration_assignment_dry_run_path=Path("dry_run.json"),
        deepagents_policy_path=Path("policy.json"),
        deepagents_readiness_path=Path("readiness.json"),
    )

    refs = extract_references(work_plan)
    assert len(refs) == 4
    roles = {r["field"] for r in refs}
    assert roles == {
        "orchestration_assignment_plan_ref",
        "orchestration_assignment_dry_run_ref",
        "deepagents_policy_ref",
        "deepagents_readiness_ref",
    }

    assignment = create_deepagents_subagent_assignment(
        target="builder",
        task="Test subtask",
        subagent_profile="repo_mapper",
        work_plan=work_plan,
        work_plan_path=Path("work-plan.json"),
    )
    refs_assign = extract_references(assignment)
    assert len(refs_assign) == 1
    assert refs_assign[0]["field"] == "work_plan_ref"

    result = create_deepagents_subagent_result(
        target="builder",
        subagent_profile="repo_mapper",
        summary="Done",
        subagent_assignment=assignment,
        subagent_assignment_path=Path("assignment.json"),
    )
    refs_result = extract_references(result)
    assert len(refs_result) == 1
    assert refs_result[0]["field"] == "subagent_assignment_ref"

    review = create_deepagents_subagent_review(
        target="builder",
        disposition="accepted_as_proposal",
        subagent_result=result,
        subagent_assignment=assignment,
        subagent_result_path=Path("result.json"),
        subagent_assignment_path=Path("assignment.json"),
    )
    refs_review = extract_references(review)
    assert len(refs_review) == 2
    assert {r["field"] for r in refs_review} == {
        "subagent_result_ref",
        "subagent_assignment_ref",
    }

    gate = create_deepagents_human_gate_request(
        target="builder",
        reviewed_artifact=review,
        reviewed_artifact_path=Path("review.json"),
    )
    refs_gate = extract_references(gate)
    assert len(refs_gate) == 1
    assert refs_gate[0]["field"] == "reviewed_artifact_ref"

    blocked = create_deepagents_blocked_action_record(
        target="builder",
        denied_capability="shell execution",
        triggering_artifact=result,
        triggering_artifact_path=Path("result.json"),
    )
    refs_blocked = extract_references(blocked)
    assert len(refs_blocked) == 1
    assert refs_blocked[0]["field"] == "triggering_artifact_ref"

    proposal = create_deepagents_proposal_result(
        target="builder",
        work_plan=work_plan,
        reviewed_results=[review],
        work_plan_path=Path("work-plan.json"),
        reviewed_result_paths=[Path("review.json")],
    )
    refs_proposal = extract_references(proposal)
    assert {r["field"] for r in refs_proposal} == {
        "work_plan_ref",
        "reviewed_result_refs[0]",
    }

    report = create_deepagents_work_validation_report(
        subject=proposal,
        subject_path=Path("proposal.json"),
    )
    refs_report = extract_references(report)
    assert len(refs_report) == 1
    assert refs_report[0]["field"] == "subject_ref"


def test_deepagents_artifact_index_and_chain_resolution(tmp_path: Path) -> None:
    from builder_ii.core.artifact_chain_verification import (
        VALIDATORS as CHAIN_VALIDATORS,
    )
    from builder_ii.core.artifact_chain_verification import (
        verify_artifact_chain,
    )
    from builder_ii.governance.ledger.artifact_index_records import (
        _VALIDATORS as INDEX_VALIDATORS,
    )
    from builder_ii.governance.ledger.artifact_index_records import (
        create_artifact_index_record,
    )

    goal2_fixture = build_goal2_assignment_fixture(tmp_path)
    plan_data = goal2_fixture["artifacts"]["orchestration"]
    dry_run_data = goal2_fixture["artifacts"]["dry_run"]
    policy_data = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    readiness_data = create_deepagents_readiness_artifact(mode="metadata_only")

    source_dir = tmp_path / "sources"
    artifact_dir = tmp_path / "goal3"
    source_dir.mkdir()
    artifact_dir.mkdir()

    policy_path = source_dir / "deepagents-policy.json"
    readiness_path = source_dir / "deepagents-readiness.json"
    work_plan_path = artifact_dir / "deepagents-work-plan.json"
    assignment_path = artifact_dir / "subagent-assignment.json"
    result_path = artifact_dir / "subagent-result.json"
    review_path = artifact_dir / "subagent-review.json"
    gate_path = artifact_dir / "human-gate-request.json"
    blocked_path = artifact_dir / "blocked-action.json"
    proposal_path = artifact_dir / "proposal-result.json"
    validation_path = artifact_dir / "work-validation-report.json"

    policy_path.write_text(json_lib.dumps(policy_data), encoding="utf-8")
    readiness_path.write_text(json_lib.dumps(readiness_data), encoding="utf-8")

    work_plan = create_deepagents_work_plan(
        target="builder",
        task="Index and chain passive deepagents work artifacts",
        orchestration_assignment_plan=plan_data,
        orchestration_assignment_dry_run=dry_run_data,
        deepagents_policy=policy_data,
        deepagents_readiness=readiness_data,
        orchestration_assignment_plan_path=goal2_fixture["paths"]["orchestration"],
        orchestration_assignment_dry_run_path=goal2_fixture["paths"]["dry_run"],
        deepagents_policy_path=policy_path,
        deepagents_readiness_path=readiness_path,
    )
    assignment = create_deepagents_subagent_assignment(
        target="builder",
        task="Map passive artifacts",
        subagent_profile="repo_mapper",
        work_plan=work_plan,
        work_plan_path=work_plan_path,
    )
    result = create_deepagents_subagent_result(
        target="builder",
        subagent_profile="repo_mapper",
        summary="Proposal-only result",
        subagent_assignment=assignment,
        subagent_assignment_path=assignment_path,
    )
    review = create_deepagents_subagent_review(
        target="builder",
        disposition="accepted_as_proposal",
        subagent_result=result,
        subagent_assignment=assignment,
        subagent_result_path=result_path,
        subagent_assignment_path=assignment_path,
    )
    gate = create_deepagents_human_gate_request(
        target="builder",
        reviewed_artifact=review,
        reviewed_artifact_path=review_path,
    )
    blocked = create_deepagents_blocked_action_record(
        target="builder",
        denied_capability="shell execution",
        triggering_artifact=result,
        triggering_artifact_path=result_path,
    )
    proposal = create_deepagents_proposal_result(
        target="builder",
        work_plan=work_plan,
        reviewed_results=[review],
        work_plan_path=work_plan_path,
        reviewed_result_paths=[review_path],
    )
    validation = create_deepagents_work_validation_report(
        subject=proposal,
        subject_path=proposal_path,
    )

    artifacts = {
        work_plan_path: work_plan,
        assignment_path: assignment,
        result_path: result,
        review_path: review,
        gate_path: gate,
        blocked_path: blocked,
        proposal_path: proposal,
        validation_path: validation,
    }
    for path, artifact in artifacts.items():
        path.write_text(json_lib.dumps(artifact), encoding="utf-8")

    new_kinds = {
        DEEPAGENTS_WORK_PLAN_KIND,
        DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
        DEEPAGENTS_SUBAGENT_RESULT_KIND,
        DEEPAGENTS_SUBAGENT_REVIEW_KIND,
        DEEPAGENTS_HUMAN_GATE_REQUEST_KIND,
        DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND,
        DEEPAGENTS_PROPOSAL_RESULT_KIND,
        DEEPAGENTS_WORK_VALIDATION_REPORT_KIND,
    }
    assert new_kinds.issubset(INDEX_VALIDATORS)
    assert new_kinds.issubset(CHAIN_VALIDATORS)

    index = create_artifact_index_record(artifact_dir)
    indexed_kinds = {entry["kind"] for entry in index["artifacts"]}
    assert new_kinds.issubset(indexed_kinds)
    assert index["counts"]["unknown"] == 0
    assert index["counts"]["invalid"] == 0

    report = verify_artifact_chain(
        [
            goal2_fixture["paths"]["orchestration"],
            goal2_fixture["paths"]["dry_run"],
            policy_path,
            readiness_path,
            *artifacts.keys(),
        ]
    )
    assert report["valid"] is True, report["errors"]
    assert report["counts"]["broken_links"] == 0


def test_deepagents_command_authority() -> None:
    from builder_ii.governance.authority import (
        COMMAND_AUTHORITY_REGISTRY,
        STATE_ARTIFACT_ONLY,
        STATE_FORBIDDEN_UNPROMOTED,
        STATE_HITL_RUNTIME_CANDIDATE,
        STATE_VALIDATION_ONLY,
        TIER_1,
        TIER_3,
        TIER_4,
    )

    expected_cmds = {
        "builder-deepagents policy",
        "builder-deepagents validate",
        "builder-deepagents readiness",
        "builder-deepagents validate-readiness",
        "builder-deepagents forge",
        "builder-deepagents delegate",
        "builder-deepagents work-plan",
        "builder-deepagents assign-subagent",
        "builder-deepagents record-result",
        "builder-deepagents review-result",
        "builder-deepagents request-human-gate",
        "builder-deepagents record-blocked-action",
        "builder-deepagents proposal-result",
        "builder-deepagents validate-work-artifact",
        "builder-deepagents backend-readiness",
        "builder-deepagents execution-candidate",
        "builder-deepagents approve-candidate",
        "builder-deepagents run-approved",
        "builder-deepagents replay-run",
        "builder-deepagents evidence-bundle",
        "builder-deepagents resume-approved",
    }
    found_cmds = set()
    for record in COMMAND_AUTHORITY_REGISTRY:
        if record.name in expected_cmds:
            found_cmds.add(record.name)
            if record.name == "builder-deepagents delegate":
                assert record.tier == TIER_4
                assert record.promotion_state == STATE_FORBIDDEN_UNPROMOTED
                continue
            if record.name in {
                "builder-deepagents run-approved",
                "builder-deepagents resume-approved",
            }:
                assert record.tier == TIER_3
                assert record.promotion_state == STATE_HITL_RUNTIME_CANDIDATE
                assert record.allows_artifact_writes is True
                continue
            assert record.tier == TIER_1
            if record.name in {
                "builder-deepagents validate",
                "builder-deepagents validate-readiness",
                "builder-deepagents validate-work-artifact",
                "builder-deepagents replay-run",
            }:
                assert record.promotion_state == STATE_VALIDATION_ONLY
            else:
                assert record.promotion_state == STATE_ARTIFACT_ONLY
                assert record.allows_artifact_writes is True
    assert found_cmds == expected_cmds
