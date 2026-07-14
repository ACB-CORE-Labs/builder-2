"""V.2 agent/deepagents RO runner candidate."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.agent_readonly_runner import (
    AgentReadonlyError,
    run_readonly_agent,
    validate_agent_readonly_receipt,
)
from builder_ii.cli.agent_cli import agent_app
from builder_ii.cli.deepagents_cli import deepagents_app

runner = CliRunner()


def test_run_code_reviewer_readonly() -> None:
    receipt = run_readonly_agent(
        profile_name="code_reviewer",
        task="inspect wrp boundaries",
        repo_path=Path.cwd(),
        target_name="builder",
        max_files=40,
    )
    assert receipt["status"] == "succeeded"
    assert receipt["capability_state"] == "read_only_runtime_candidate"
    assert receipt["runtime_mode"] == "read_only"
    assert receipt["constructs_deepagents"] is False
    assert receipt["invokes_delegate"] is False
    assert receipt["executes_shell"] is False
    assert receipt["executes_model"] is False
    assert receipt["mutates_target_repo"] is False
    assert validate_agent_readonly_receipt(receipt) == []


def test_refuse_patch_planner_live_ro() -> None:
    try:
        run_readonly_agent(
            profile_name="patch_planner",
            task="should fail",
            repo_path=Path.cwd(),
        )
        raise AssertionError("expected AgentReadonlyError")
    except AgentReadonlyError as exc:
        assert "read_only" in str(exc)


def test_cli_agent_run_readonly(tmp_path: Path) -> None:
    out = tmp_path / "ro.json"
    r = runner.invoke(
        agent_app,
        [
            "run",
            "--profile",
            "code_reviewer",
            "--task",
            "ro inspect",
            "--read-only",
            "--repo",
            str(Path.cwd()),
            "-o",
            str(out),
        ],
    )
    assert r.exit_code == 0, r.output
    assert out.is_file()


def test_cli_agent_run_requires_read_only() -> None:
    r = runner.invoke(
        agent_app,
        ["run", "--profile", "code_reviewer", "--task", "x", "--no-read-only"],
    )
    assert r.exit_code == 1


def test_cli_deepagents_run_readonly(tmp_path: Path) -> None:
    out = tmp_path / "da.json"
    r = runner.invoke(
        deepagents_app,
        [
            "run-readonly",
            "--profile",
            "repo_mapper",
            "--task",
            "map only",
            "--repo",
            str(Path.cwd()),
            "-o",
            str(out),
        ],
    )
    assert r.exit_code == 0, r.output
