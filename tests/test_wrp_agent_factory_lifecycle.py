"""W.5 AgentFactory spawn/retire lifecycle records (validation_only)."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app
from builder_ii.wrp.agent_factory import (
    AgentFactory,
    plan_agent_lifecycle,
    prove_agent_lifecycle,
    retire_agent,
    spawn_agent,
    validate_agent_lifecycle_proof,
    validate_agent_lifecycle_record,
)
from builder_ii.wrp.experience_store import create_experience_store
from builder_ii.wrp.spaces import AgentPoint

runner = CliRunner()


def test_spawn_record_honesty_bounds() -> None:
    rec = spawn_agent(role="code_reviewer", task="review honesty bounds")
    assert rec["kind"] == "builder_ii.wrp.agent_lifecycle_record"
    assert rec["action"] == "spawn"
    assert rec["spawn_permitted"] is False
    assert rec["spawn_executed"] is False
    assert rec["runtime_binding"] == "UNBOUND"
    assert rec["grants_authority"] is False
    assert rec["s3_enabled"] is False
    assert rec["process_spawn"] is False
    assert rec["role"] == "code_reviewer"
    assert rec["role_binding"]["bound"] is True
    assert rec["experience_binding"]["bound"] is False
    assert validate_agent_lifecycle_record(rec) == []
    assert isinstance(rec["digest"], str) and len(rec["digest"]) == 64


def test_spawn_deterministic_replay() -> None:
    a = spawn_agent(role="code_reviewer", task="same task")
    b = spawn_agent(role="code_reviewer", task="same task")
    assert a["agent_id"] == b["agent_id"]
    assert a["digest"] == b["digest"]


def test_retire_bound_to_spawn_digest() -> None:
    spawn = spawn_agent(role="patch_planner", task="plan a patch")
    retire = retire_agent(spawn_record=spawn, reason="done")
    assert retire["action"] == "retire"
    assert retire["spawn_digest"] == spawn["digest"]
    assert retire["agent_id"] == spawn["agent_id"]
    assert retire["spawn_executed"] is False
    assert validate_agent_lifecycle_record(retire) == []


def test_experience_store_binding() -> None:
    store = create_experience_store(store_id="test-lifecycle")
    spawn = spawn_agent(role="code_reviewer", task="bind store", experience_store=store)
    binding = spawn["experience_binding"]
    assert binding["bound"] is True
    assert binding["exemplar_appended"] is True
    assert binding["updates_live_routing"] is False
    assert binding["grants_authority"] is False
    assert isinstance(binding["updated_store_digest"], str)
    assert len(binding["updated_store_digest"]) == 64
    assert validate_agent_lifecycle_record(spawn) == []


def test_agent_factory_class_surface() -> None:
    factory = AgentFactory()
    spawn = factory.spawn(role="governor_architecture", task="gate review")
    retire = factory.retire(spawn_record=spawn, reason="complete")
    assert spawn["spawn_executed"] is False
    assert retire["spawn_digest"] == spawn["digest"]


def test_prove_agent_lifecycle_ok() -> None:
    proof = prove_agent_lifecycle()
    assert proof["ok"] is True
    assert proof["kind"] == "builder_ii.wrp.agent_lifecycle_proof"
    assert proof["spawn_executed"] is False
    assert proof["spawn_permitted"] is False
    assert proof["s3_enabled"] is False
    assert proof["process_spawn"] is False
    assert proof["experience_store_bound"] is True
    assert proof["case_count"] >= 2
    assert all(c["ok"] and c["replay_ok"] for c in proof["cases"])
    assert validate_agent_lifecycle_proof(proof) == []
    # Deterministic proof digests.
    again = prove_agent_lifecycle()
    assert again["digest"] == proof["digest"]


def test_spawn_earned_seam_execution_path() -> None:
    rec = spawn_agent(
        role="code_reviewer",
        task="earned bind",
        seam_execution={
            "subagent_loop_digest": "1" * 64,
            "plan_digest": "2" * 64,
            "approved_by": "human",
            "gateway_mode": "invoke_local",
            "steps_executed": 1,
            "kill_switch_armed": True,
        },
    )
    assert rec["spawn_executed"] is True
    assert rec["spawn_permitted"] is True
    assert rec["runtime_binding"] == "SEAM_BOUND"
    assert rec["process_spawn"] is False
    assert validate_agent_lifecycle_record(rec) == []
    retire = retire_agent(spawn_record=rec, reason="done")
    assert retire["spawn_executed"] is True
    assert retire["runtime_binding"] == "SEAM_BOUND"
    assert validate_agent_lifecycle_record(retire) == []


def test_plan_agent_lifecycle_still_plan_only() -> None:
    agents = [
        AgentPoint(
            role="maker_structural",
            reasoning_coverage=0.9,
            tool_coverage=0.8,
            model_family="plan-only",
            platform="maker",
        )
    ]
    plan = plan_agent_lifecycle(agents=agents, action="register_plan")
    assert plan["spawn_permitted"] is False
    assert plan["spawn_executed"] is False


def test_cli_agent_factory_spawn_retire_prove(tmp_path: Path) -> None:
    spawn_path = tmp_path / "spawn.json"
    r = runner.invoke(
        wrp_app,
        [
            "agent-factory",
            "spawn",
            "--role",
            "code_reviewer",
            "--task",
            "cli spawn test",
            "-o",
            str(spawn_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert spawn_path.is_file()

    retire_path = tmp_path / "retire.json"
    r = runner.invoke(
        wrp_app,
        [
            "agent-factory",
            "retire",
            "--spawn-record",
            str(spawn_path),
            "-o",
            str(retire_path),
        ],
    )
    assert r.exit_code == 0, r.output
    assert retire_path.is_file()

    proof_path = tmp_path / "agent_lifecycle_proof.json"
    r = runner.invoke(wrp_app, ["agent-factory", "prove", "-o", str(proof_path)])
    assert r.exit_code == 0, r.output
    assert proof_path.is_file()

    assert runner.invoke(wrp_app, ["validate", str(spawn_path)]).exit_code == 0
    assert runner.invoke(wrp_app, ["validate", str(retire_path)]).exit_code == 0
    assert runner.invoke(wrp_app, ["validate", str(proof_path)]).exit_code == 0


def test_cli_rejects_unknown_role() -> None:
    r = runner.invoke(
        wrp_app,
        ["agent-factory", "spawn", "--role", "not_a_real_role", "--task", "x"],
    )
    assert r.exit_code != 0
