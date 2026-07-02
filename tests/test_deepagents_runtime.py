import json as json_lib
from pathlib import Path
from unittest.mock import patch

import pytest
from builder_ii.deepagents_cli import deepagents_app
from typer.testing import CliRunner

from builder_ii.config import load_settings
from builder_ii.deepagents_bridge import DeepAgentsAvailability
from builder_ii.deepagents_policy import create_deepagents_policy_artifact
from builder_ii.deepagents_readiness import create_deepagents_readiness_artifact
from builder_ii.deepagents_runtime import DeepAgentsRuntimeHarness
from builder_ii.deepagents_work_artifacts import (
    create_deepagents_work_plan,
    validate_deepagents_blocked_action_record,
    validate_deepagents_proposal_result,
    validate_deepagents_runtime_envelope,
    validate_deepagents_subagent_execution_receipt,
)
from tests.orchestration_assignment_fixtures import build_goal2_assignment_fixture


def _available() -> DeepAgentsAvailability:
    return DeepAgentsAvailability(
        available=True,
        source="/mock/lib/deepagents",
        detail="available",
        import_status="PASS",
    )


@pytest.fixture
def test_env_setup(tmp_path: Path):
    goal2_fixture = build_goal2_assignment_fixture(tmp_path, task="Deepagents runtime testing")
    orchestration_assignment_plan = goal2_fixture["artifacts"]["orchestration"]
    orchestration_assignment_dry_run = goal2_fixture["artifacts"]["dry_run"]

    deepagents_policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    deepagents_readiness = create_deepagents_readiness_artifact(mode="metadata_only")

    policy_path = tmp_path / "deepagents-policy.json"
    readiness_path = tmp_path / "deepagents-readiness.json"

    policy_path.write_text(json_lib.dumps(deepagents_policy), encoding="utf-8")
    readiness_path.write_text(json_lib.dumps(deepagents_readiness), encoding="utf-8")

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

    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json_lib.dumps(work_plan), encoding="utf-8")

    return {
        "plan_path": plan_path,
        "policy_path": policy_path,
        "readiness_path": readiness_path,
        "dry_run": orchestration_assignment_dry_run,
        "orchestration": orchestration_assignment_plan,
        "goal2_fixture": goal2_fixture,
    }


def test_deepagents_runtime_fails_when_dependency_unavailable(test_env_setup, tmp_path: Path) -> None:
    avail = DeepAgentsAvailability(
        available=False,
        source=None,
        detail="missing dependency",
        import_status="MISS",
    )
    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=avail):
        harness = DeepAgentsRuntimeHarness(load_settings(), test_env_setup["plan_path"])
        with pytest.raises(ImportError) as exc_info:
            harness.run(tmp_path / "envelope.json", tmp_path / "receipts")
        assert "deepagents dependency is not available" in str(exc_info.value)


def test_deepagents_runtime_executes_successfully_proposal_only(test_env_setup, tmp_path: Path) -> None:
    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=_available()):
        harness = DeepAgentsRuntimeHarness(load_settings(), test_env_setup["plan_path"])
        env_path = tmp_path / "envelope.json"
        receipts_dir = tmp_path / "receipts"
        envelope = harness.run(env_path, receipts_dir)

        assert env_path.exists()
        assert validate_deepagents_runtime_envelope(envelope) == []
        assert envelope["envelope_state"] == "COMPLETED"

        # Check subagent assignments and receipts
        receipt_paths = list(receipts_dir.glob("receipt-*.json"))
        assert len(receipt_paths) == 2
        for path in receipt_paths:
            receipt = json_lib.loads(path.read_text(encoding="utf-8"))
            assert validate_deepagents_subagent_execution_receipt(receipt) == []


def test_deepagents_runtime_fails_on_denied_tools(test_env_setup, tmp_path: Path) -> None:
    # Set up policy with violations
    bad_policy = create_deepagents_policy_artifact(load_settings(), target_name="builder")
    # Modify allow_tools to include a denied tool (write_file is denied by default)
    bad_policy["governed_factory"]["allow_tools"] = ["write_file"]
    bad_policy_path = tmp_path / "bad-policy.json"
    bad_policy_path.write_text(json_lib.dumps(bad_policy), encoding="utf-8")

    bad_work_plan = create_deepagents_work_plan(
        target="builder",
        task="Goal 3 passive work plan execution test",
        orchestration_assignment_plan=test_env_setup["orchestration"],
        orchestration_assignment_dry_run=test_env_setup["dry_run"],
        deepagents_policy=bad_policy,
        deepagents_readiness=create_deepagents_readiness_artifact(mode="metadata_only"),
        orchestration_assignment_plan_path=test_env_setup["goal2_fixture"]["paths"]["orchestration"],
        orchestration_assignment_dry_run_path=test_env_setup["goal2_fixture"]["paths"]["dry_run"],
        deepagents_policy_path=bad_policy_path,
        deepagents_readiness_path=test_env_setup["readiness_path"],
        proposed_subagents=["repo_mapper"],
        expected_outputs=["deepagents_work_plan"],
        review_gates=[],
        blocked_capabilities=["tool execution"],
    )
    bad_plan_path = tmp_path / "bad_plan.json"
    bad_plan_path.write_text(json_lib.dumps(bad_work_plan), encoding="utf-8")

    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=_available()):
        harness = DeepAgentsRuntimeHarness(load_settings(), bad_plan_path)
        receipts_dir = tmp_path / "receipts"
        with pytest.raises(ValueError) as exc_info:
            harness.run(tmp_path / "envelope.json", receipts_dir)
        assert "Plan allows denied tool: write_file" in str(exc_info.value)

        # Verify blocked action record was emitted
        blocked_path = receipts_dir / "blocked-action.json"
        assert blocked_path.exists()
        blocked_record = json_lib.loads(blocked_path.read_text(encoding="utf-8"))
        assert validate_deepagents_blocked_action_record(blocked_record) == []


def test_deepagents_runtime_fails_on_unapproved_capabilities(test_env_setup, tmp_path: Path) -> None:
    # Force the work plan to claim executes_model=True but have model execution blocked
    plan_data = json_lib.loads(test_env_setup["plan_path"].read_text(encoding="utf-8"))
    plan_data["executes_model"] = True
    plan_data["blocked_capabilities"] = ["model execution"]
    plan_data["authority_boundary"]["executes_model"] = True

    # Write directly (bypassing normal schema creation) to simulate a malformed/adversarial plan
    bad_plan_path = tmp_path / "adversarial_plan.json"
    bad_plan_path.write_text(json_lib.dumps(plan_data), encoding="utf-8")

    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=_available()):
        harness = DeepAgentsRuntimeHarness(load_settings(), bad_plan_path)
        with pytest.raises(ValueError) as exc_info:
            harness.run(tmp_path / "envelope.json", tmp_path / "receipts")
        assert "Plan contains blocked capability: model execution" in str(exc_info.value)


def test_deepagents_runtime_rejects_non_object_work_plan(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("[]", encoding="utf-8")

    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=_available()):
        harness = DeepAgentsRuntimeHarness(load_settings(), plan_path)
        with pytest.raises(ValueError) as exc_info:
            harness.run(tmp_path / "envelope.json", tmp_path / "receipts")

    assert "Work plan must be a JSON object" in str(exc_info.value)


def test_deepagents_runtime_rejects_missing_policy_ref_path(test_env_setup, tmp_path: Path) -> None:
    plan_data = json_lib.loads(test_env_setup["plan_path"].read_text(encoding="utf-8"))
    plan_data["deepagents_policy_ref"]["path"] = ""
    bad_plan_path = tmp_path / "bad-policy-ref.json"
    bad_plan_path.write_text(json_lib.dumps(plan_data), encoding="utf-8")

    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=_available()):
        harness = DeepAgentsRuntimeHarness(load_settings(), bad_plan_path)
        with pytest.raises(ValueError) as exc_info:
            harness.run(tmp_path / "envelope.json", tmp_path / "receipts")

    assert "deepagents_policy_ref.path must be a non-empty string" in str(exc_info.value)


def test_deepagents_collect_results(test_env_setup, tmp_path: Path) -> None:
    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=_available()):
        harness = DeepAgentsRuntimeHarness(load_settings(), test_env_setup["plan_path"])
        env_path = tmp_path / "envelope.json"
        proposal_path = tmp_path / "proposal.json"
        harness.run(env_path, tmp_path / "receipts")

        proposal = harness.collect_results(env_path, proposal_path)
        assert proposal_path.exists()
        assert validate_deepagents_proposal_result(proposal) == []


def test_deepagents_collect_results_rejects_mismatched_work_plan(test_env_setup, tmp_path: Path) -> None:
    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=_available()):
        original_harness = DeepAgentsRuntimeHarness(load_settings(), test_env_setup["plan_path"])
        env_path = tmp_path / "envelope.json"
        original_harness.run(env_path, tmp_path / "receipts")

    other_plan = json_lib.loads(test_env_setup["plan_path"].read_text(encoding="utf-8"))
    other_plan["task"] = "Different task must not inherit stale receipts"
    other_plan_path = tmp_path / "other-plan.json"
    other_plan_path.write_text(json_lib.dumps(other_plan), encoding="utf-8")

    mismatched_harness = DeepAgentsRuntimeHarness(load_settings(), other_plan_path)
    with pytest.raises(ValueError) as exc_info:
        mismatched_harness.collect_results(env_path, tmp_path / "proposal.json")

    assert "Envelope work_plan_ref does not match requested work plan" in str(exc_info.value)


def test_deepagents_collect_results_rejects_non_object_envelope(test_env_setup, tmp_path: Path) -> None:
    env_path = tmp_path / "envelope.json"
    env_path.write_text("[]", encoding="utf-8")
    harness = DeepAgentsRuntimeHarness(load_settings(), test_env_setup["plan_path"])

    with pytest.raises(ValueError) as exc_info:
        harness.collect_results(env_path, tmp_path / "proposal.json")

    assert "Envelope must be a JSON object" in str(exc_info.value)


def test_deepagents_collect_results_rejects_directory_receipt_ref(test_env_setup, tmp_path: Path) -> None:
    env_path = tmp_path / "envelope.json"
    env_path.write_text(
        json_lib.dumps(
            {
                "work_plan_ref": {
                    "role": "work_plan",
                    "kind": "builder_ii.deepagents_work_plan",
                    "path": str(test_env_setup["plan_path"]),
                    "sha256": "invalid-for-this-test",
                },
                "execution_receipt_refs": [{"path": str(tmp_path)}],
            }
        ),
        encoding="utf-8",
    )
    harness = DeepAgentsRuntimeHarness(load_settings(), test_env_setup["plan_path"])

    with pytest.raises(ValueError) as exc_info:
        harness.collect_results(env_path, tmp_path / "proposal.json")

    assert "Envelope work_plan_ref does not match requested work plan" in str(exc_info.value)


def test_cli_integration(test_env_setup, tmp_path: Path) -> None:
    runner = CliRunner()
    with patch("builder_ii.deepagents_runtime.deepagents_availability", return_value=_available()):
        env_path = tmp_path / "envelope_cli.json"
        receipts_dir = tmp_path / "receipts_cli"

        # Test run-plan
        result_run = runner.invoke(
            deepagents_app,
            [
                "run-plan",
                "--work-plan",
                str(test_env_setup["plan_path"]),
                "--output",
                str(env_path),
                "--receipts-dir",
                str(receipts_dir),
            ],
        )
        assert result_run.exit_code == 0
        assert env_path.exists()

        # Test collect-results
        proposal_path = tmp_path / "proposal_cli.json"
        result_collect = runner.invoke(
            deepagents_app,
            [
                "collect-results",
                "--work-plan",
                str(test_env_setup["plan_path"]),
                "--envelope",
                str(env_path),
                "--output",
                str(proposal_path),
            ],
        )
        assert result_collect.exit_code == 0
        assert proposal_path.exists()
