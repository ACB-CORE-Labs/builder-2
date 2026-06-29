from __future__ import annotations

import json as json_lib
from pathlib import Path

import pytest
from typer.testing import CliRunner

from builder_ii.event_ledger import replay_events
from builder_ii.ledger_cli import ledger_app
from builder_ii.workflow_cli import workflow_app
from builder_ii.workflow_orchestrator import (
    WorkflowError,
    candidate_workflow,
    handoff_workflow,
    plan_workflow,
    promote_workflow,
    verify_chain_workflow,
    workflow_status,
)


ROOT = Path(__file__).resolve().parents[1]


def _read(path: Path) -> dict:
    return json_lib.loads(path.read_text(encoding="utf-8"))


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target"
    (repo / "src").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "README.md").write_text("# target\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = \"target\"\n", encoding="utf-8")
    (repo / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
    (repo / "tests" / "test_app.py").write_text("def test_value():\n    assert True\n", encoding="utf-8")
    return repo


def test_workflow_golden_path_replays_and_audits(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(ROOT)
    workflows_dir = tmp_path / "workflows"
    output_dir = workflows_dir / "session-1"
    repo = _generic_repo(tmp_path)

    status = plan_workflow(
        target="generic",
        task="Inspect target and prepare passive handoff.",
        output_dir=output_dir,
        session_id="session-1",
        repo_path=repo,
    )
    assert status["current_stage"] == "planned"
    assert status["event_count"] == 1

    with pytest.raises(WorkflowError):
        candidate_workflow(output_dir=output_dir)

    assert promote_workflow(output_dir=output_dir)["current_stage"] == "promoted"
    assert candidate_workflow(output_dir=output_dir)["current_stage"] == "candidate"
    assert verify_chain_workflow(output_dir=output_dir)["current_stage"] == "chain_verified"
    final_status = handoff_workflow(output_dir=output_dir)
    assert final_status["current_stage"] == "handoff_ready"
    assert final_status["valid_replay"] is True
    assert final_status["event_count"] == 5

    golden = _read(output_dir / "GOLDEN_PATH_CHAIN_v1.json")
    assert golden["runtime_authority"] == "DISABLED"
    assert golden["model_execution"] == "DISABLED"
    assert (output_dir / "GOLDEN_PATH_DEMO_README.md").exists()

    chain = _read(output_dir / "artifacts" / "chain-verification-report.json")
    assert chain["valid"] is True

    events = sorted((output_dir / "events").glob("*.json"))
    assert len(events) == 5
    first_event = _read(events[0])
    assert first_event["command_surface"] == "builder workflow plan"
    assert first_event["payload_sha256"]
    assert first_event["policy_snapshot_ref"]["path"].endswith("docs/COMMAND_AUTHORITY.md")
    assert first_event["next_allowed_transitions"] == ["builder workflow promote"]

    replay = replay_events([(_read(path), path) for path in events], session_id="session-1")
    assert replay["valid"] is True
    assert replay["current_stage"] == "handoff_ready"

    refreshed = workflow_status(output_dir=output_dir)
    assert refreshed["current_stage"] == "handoff_ready"

    subject_sha = final_status["artifact_refs"][0]["sha256"]
    runner = CliRunner()
    audit = runner.invoke(
        ledger_app,
        [
            "audit",
            subject_sha,
            "--session-id",
            "session-1",
            "--workflows-dir",
            str(workflows_dir),
        ],
    )
    assert audit.exit_code == 0, audit.output
    audit_data = json_lib.loads(audit.stdout)
    assert audit_data["matches"][0]["who"]
    assert audit_data["matches"][0]["policy_snapshot_ref"]["path"].endswith("docs/COMMAND_AUTHORITY.md")

    cli_status = runner.invoke(workflow_app, ["status", "--output-dir", str(output_dir)])
    assert cli_status.exit_code == 0, cli_status.output
    assert json_lib.loads(cli_status.stdout)["current_stage"] == "handoff_ready"
