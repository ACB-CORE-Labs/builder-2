import json as json_lib
from pathlib import Path

from builder_ii.approval_records_cli import approval_app
from typer.testing import CliRunner

from builder_ii.approval_records import dumps_approval_record
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal, write_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest


def _proposal(tmp_path: Path) -> dict:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="approval record CLI",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    return create_goose_command_proposal(
        manifest,
        manifest_path=tmp_path / "goose-session.json",
        command="verify",
        reason="record a proposed operator action",
        risk_level="low",
    )


def test_cli_record_stdout(tmp_path: Path) -> None:
    proposal_path = tmp_path / "proposal.json"
    write_goose_command_proposal(_proposal(tmp_path), proposal_path)

    result = CliRunner().invoke(
        approval_app,
        [
            "record",
            str(proposal_path),
            "--decision",
            "approved",
            "--decided-by",
            "operator",
            "--reason",
            "ready for later gated handling",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.approval_record"
    assert data["record_state"] == "RECORDED_ONLY"
    assert data["decision"]["value"] == "approved"
    assert data["decision"]["decided_by"] == "operator"
    assert data["grants_runtime_authority"] is False
    assert data["grants_action_authority"] is False


def test_cli_record_output_and_validate(tmp_path: Path) -> None:
    proposal_path = tmp_path / "proposal.json"
    output_path = tmp_path / "approval-record.json"
    write_goose_command_proposal(_proposal(tmp_path), proposal_path)

    create_result = CliRunner().invoke(
        approval_app,
        [
            "record",
            str(proposal_path),
            "--decision",
            "rejected",
            "--decided-by",
            "operator",
            "--output",
            str(output_path),
        ],
    )

    assert create_result.exit_code == 0
    assert output_path.exists()
    assert "Approval record written" in create_result.stdout

    validate_result = CliRunner().invoke(approval_app, ["validate", str(output_path)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_rejects_bad_decision(tmp_path: Path) -> None:
    proposal_path = tmp_path / "proposal.json"
    write_goose_command_proposal(_proposal(tmp_path), proposal_path)

    result = CliRunner().invoke(
        approval_app,
        ["record", str(proposal_path), "--decision", "maybe", "--decided-by", "operator"],
    )

    assert result.exit_code == 1
    assert "decision must be approved or rejected" in result.stdout


def test_cli_validate_rejects_invalid_record(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text(dumps_approval_record({"kind": "wrong"}), encoding="utf-8")

    result = CliRunner().invoke(approval_app, ["validate", str(invalid)])

    assert result.exit_code == 1
    assert "Validation error" in result.stdout
