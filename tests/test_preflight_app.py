import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.approval_records import create_approval_record, write_approval_record
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal, write_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest
from builder_ii.preflight_cli import preflight_app


def _proposal(tmp_path: Path) -> dict:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="preflight record check",
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


def _approval(tmp_path: Path, proposal: dict, decision: str = "approved") -> dict:
    return create_approval_record(
        proposal,
        proposal_path=tmp_path / "proposal.json",
        decision=decision,  # type: ignore[arg-type]
        decided_by="operator",
        reason="ready for later gated handling",
    )


def test_preflight_app_imports() -> None:
    assert preflight_app is not None


def test_cli_record_ready_stdout(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    approval = _approval(tmp_path, proposal)

    proposal_path = tmp_path / "proposal.json"
    approval_path = tmp_path / "approval.json"

    write_goose_command_proposal(proposal, proposal_path)
    write_approval_record(approval, approval_path)

    result = CliRunner().invoke(
        preflight_app,
        [
            "record",
            str(proposal_path),
            str(approval_path),
            "--verification-ref",
            "verification artifact",
        ],
    )

    assert result.exit_code == 0, result.stdout
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.preflight_record"
    assert data["status"] == "ready"
    assert data["ready"] is True
    assert data["blockers"] == []
    assert data["grants_runtime_authority"] is False
    assert data["grants_action_authority"] is False


def test_cli_record_output_file_and_validate(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    approval = _approval(tmp_path, proposal)

    proposal_path = tmp_path / "proposal.json"
    approval_path = tmp_path / "approval.json"
    output_path = tmp_path / "preflight.json"

    write_goose_command_proposal(proposal, proposal_path)
    write_approval_record(approval, approval_path)

    result = CliRunner().invoke(
        preflight_app,
        [
            "record",
            str(proposal_path),
            str(approval_path),
            "--verification-ref",
            "verification artifact",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert output_path.exists()
    assert "Preflight record written" in result.stdout

    # Now validate it
    validate_result = CliRunner().invoke(
        preflight_app,
        [
            "validate",
            str(output_path),
        ],
    )
    assert validate_result.exit_code == 0, validate_result.stdout
    assert "Preflight record is valid" in validate_result.stdout


def test_cli_record_blocked_no_verification_ref(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    approval = _approval(tmp_path, proposal)

    proposal_path = tmp_path / "proposal.json"
    approval_path = tmp_path / "approval.json"

    write_goose_command_proposal(proposal, proposal_path)
    write_approval_record(approval, approval_path)

    result = CliRunner().invoke(
        preflight_app,
        [
            "record",
            str(proposal_path),
            str(approval_path),
        ],
    )

    assert result.exit_code == 0, result.stdout
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.preflight_record"
    assert data["status"] == "blocked"
    assert data["ready"] is False
    assert "verification refs are required" in data["blockers"]


def test_cli_validate_invalid_record(tmp_path: Path) -> None:
    invalid_path = tmp_path / "invalid.json"
    invalid_path.write_text(json_lib.dumps({"kind": "wrong"}), encoding="utf-8")

    result = CliRunner().invoke(
        preflight_app,
        [
            "validate",
            str(invalid_path),
        ],
    )

    assert result.exit_code == 1, result.stdout
    assert "Validation error" in result.stdout
