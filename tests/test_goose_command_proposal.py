import json as json_lib
from pathlib import Path

from builder_ii.goose_cli import goose_app
from typer.testing import CliRunner

from builder_ii.adapters.goose.goose_command_proposal import (
    create_goose_command_proposal,
    dumps_goose_command_proposal,
    validate_goose_command_proposal,
    validate_goose_command_proposal_file,
)
from builder_ii.adapters.goose.goose_session import create_goose_session_manifest, write_goose_session_manifest
from builder_ii.core.config import load_settings


def _manifest(tmp_path: Path) -> dict:
    return create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="propose command only",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )


def test_create_command_proposal_shape(tmp_path: Path) -> None:
    proposal = create_goose_command_proposal(
        _manifest(tmp_path),
        manifest_path=tmp_path / "goose-session.json",
        command="uv run pytest -q",
        reason="verify current tree",
        risk_level="low",
    )

    assert proposal["kind"] == "builder_ii.goose_command_proposal"
    assert proposal["schema_version"] == 1
    assert proposal["execution_state"] == "PROPOSED_ONLY"
    assert proposal["requires_human_approval"] is True
    assert proposal["executed"] is False
    assert proposal["runtime_started"] is False
    assert proposal["goose_process_started"] is False
    assert proposal["command"] == "uv run pytest -q"
    assert proposal["commands_proposed"] == ["uv run pytest -q"]
    assert proposal["commands_executed"] == []
    assert proposal["shell_commands_executed"] == []
    assert proposal["execution_result"]["stdout"] == ""
    assert proposal["execution_result"]["stderr"] == ""
    assert proposal["execution_result"]["exit_code"] is None
    assert proposal["approval"]["approved"] is False
    assert proposal["governance"]["command_execution"] == "DISABLED"
    assert proposal["governance"]["shell_execution"] == "DISABLED"
    assert proposal["governance"]["artifact_is_authority"] is False
    assert proposal["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_goose_command_proposal(proposal) == []


def test_command_proposal_json_round_trip(tmp_path: Path) -> None:
    proposal = create_goose_command_proposal(
        _manifest(tmp_path),
        manifest_path=tmp_path / "goose-session.json",
        command="git status --short",
        reason="inspect pending changes after human approval",
        risk_level="low",
    )
    data = json_lib.loads(dumps_goose_command_proposal(proposal))

    assert data["command"] == "git status --short"
    assert data["executed"] is False
    assert validate_goose_command_proposal(data) == []


def test_validate_rejects_execution_authority(tmp_path: Path) -> None:
    proposal = create_goose_command_proposal(
        _manifest(tmp_path),
        manifest_path=tmp_path / "goose-session.json",
        command="uv run pytest -q",
    )
    proposal["execution_state"] = "EXECUTED"
    proposal["executed"] = True
    proposal["requires_human_approval"] = False
    proposal["commands_executed"] = ["uv run pytest -q"]
    proposal["shell_commands_executed"] = ["uv run pytest -q"]
    proposal["execution_result"]["exit_code"] = 0
    proposal["execution_result"]["stdout"] = "passed"
    proposal["approval"]["approved"] = True
    proposal["governance"]["command_execution"] = "ENABLED"
    proposal["governance"]["shell_execution"] = "ENABLED"
    proposal["governance"]["artifact_is_authority"] = True

    errors = validate_goose_command_proposal(proposal)

    assert "execution_state must be PROPOSED_ONLY" in errors
    assert "executed must be false or NOT_AUTHORIZED" in errors
    assert "requires_human_approval must be true" in errors
    assert "commands_executed must be empty" in errors
    assert "shell_commands_executed must be empty" in errors
    assert "execution_result.exit_code must be null" in errors
    assert "execution_result.stdout must be empty" in errors
    assert "approval.approved must be false or NOT_AUTHORIZED" in errors
    assert "governance.command_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.shell_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_goose_command_proposal_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_goose_command_proposal_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "Goose command proposal must be a JSON object" in validate_goose_command_proposal_file(not_object)


def test_cli_propose_command_stdout(tmp_path: Path) -> None:
    manifest_path = tmp_path / "goose-session.json"
    write_goose_session_manifest(_manifest(tmp_path), manifest_path)

    result = CliRunner().invoke(
        goose_app,
        [
            "propose-command",
            str(manifest_path),
            "--command",
            "uv run pytest -q",
            "--reason",
            "verify current tree",
            "--risk-level",
            "low",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["command"] == "uv run pytest -q"
    assert data["executed"] is False
    assert data["commands_executed"] == []


def test_cli_propose_command_output_and_validate(tmp_path: Path) -> None:
    manifest_path = tmp_path / "goose-session.json"
    out_file = tmp_path / "artifacts" / "goose-command-proposal.json"
    write_goose_session_manifest(_manifest(tmp_path), manifest_path)

    create_result = CliRunner().invoke(
        goose_app,
        [
            "propose-command",
            str(manifest_path),
            "--command",
            "uv run pytest -q",
            "--output",
            str(out_file),
        ],
    )

    assert create_result.exit_code == 0
    assert out_file.exists()
    assert "Goose command proposal written" in create_result.stdout

    validate_result = CliRunner().invoke(goose_app, ["validate-command-proposal", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_rejects_empty_command(tmp_path: Path) -> None:
    manifest_path = tmp_path / "goose-session.json"
    write_goose_session_manifest(_manifest(tmp_path), manifest_path)

    result = CliRunner().invoke(goose_app, ["propose-command", str(manifest_path), "--command", "  "])

    assert result.exit_code == 1
    assert "command is required" in result.stdout
