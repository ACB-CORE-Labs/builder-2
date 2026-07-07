import json as json_lib
import sys
from pathlib import Path

import pytest

from builder_ii.approval_records import ApprovalDecision, create_approval_record, write_approval_record
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal, write_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest
from builder_ii.hitl_command_runner import execute_hitl_command
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_RECEIPT_KIND,
    create_hitl_execution_request,
    write_hitl_execution_request,
)


def _write_chain(
    tmp_path: Path, *, command: str, decision: ApprovalDecision = "approved"
) -> tuple[Path, Path, Path]:
    """Build a fully bound request/proposal/approval chain rooted at tmp_path."""
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="hitl command runner test",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    proposal_path = tmp_path / "proposal.json"
    proposal = create_goose_command_proposal(
        manifest,
        manifest_path=tmp_path / "goose-session.json",
        command=command,
        reason="hitl command runner test",
        risk_level="low",
    )
    write_goose_command_proposal(proposal, proposal_path)

    approval_path = tmp_path / "approval.json"
    approval = create_approval_record(
        proposal,
        proposal_path=proposal_path,
        decision=decision,
        decided_by="operator",
        reason="hitl command runner test",
    )
    write_approval_record(approval, approval_path)

    request_path = tmp_path / "request.json"
    request = create_hitl_execution_request(
        target_name="generic",
        command_proposal_ref=str(proposal_path),
        approval_record_ref=str(approval_path),
        preflight_record_ref="preflight-001",
        requested_by="operator",
        requested_at="2026-07-07T00:00:00Z",
        explicit_operator_intent="hitl command runner test",
        command_preview=command,
        generic_repo=tmp_path,
    )
    write_hitl_execution_request(request, request_path)

    return request_path, proposal_path, approval_path


def test_execute_hitl_command_success(tmp_path: Path) -> None:
    request_path, proposal_path, approval_path = _write_chain(tmp_path, command="echo hello-from-hitl")
    output_dir = tmp_path / "out"

    execute_hitl_command(request_path, proposal_path, approval_path, output_dir)

    receipt_path = output_dir / "hitl_execution_receipt.json"
    assert receipt_path.exists()
    receipt = json_lib.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == HITL_EXECUTION_RECEIPT_KIND
    assert receipt["execution_state"] == "EXECUTED"
    assert receipt["exit_code"] == 0
    assert receipt["current_state"] == "EXECUTION_COMPLETE"

    stdout_text = (output_dir / "stdout.log").read_text(encoding="utf-8")
    assert "hello-from-hitl" in stdout_text


def test_execute_hitl_command_records_nonzero_exit(tmp_path: Path) -> None:
    command = f'{sys.executable} -c "import sys; sys.exit(3)"'
    request_path, proposal_path, approval_path = _write_chain(tmp_path, command=command)
    output_dir = tmp_path / "out"

    execute_hitl_command(request_path, proposal_path, approval_path, output_dir)

    receipt = json_lib.loads((output_dir / "hitl_execution_receipt.json").read_text(encoding="utf-8"))
    # A nonzero exit is still a completed execution attempt, not a denial.
    assert receipt["execution_state"] == "EXECUTED"
    assert receipt["exit_code"] == 3


def test_execute_hitl_command_denies_forbidden_command(tmp_path: Path) -> None:
    request_path, proposal_path, approval_path = _write_chain(tmp_path, command="git push origin main")
    output_dir = tmp_path / "out"

    with pytest.raises(ValueError, match="forbidden"):
        execute_hitl_command(request_path, proposal_path, approval_path, output_dir)

    assert not output_dir.exists(), "forbidden command must be denied before any output is written"


def test_execute_hitl_command_denies_rejected_approval(tmp_path: Path) -> None:
    request_path, proposal_path, approval_path = _write_chain(
        tmp_path, command="echo hello", decision="rejected"
    )
    output_dir = tmp_path / "out"

    with pytest.raises(ValueError, match="approved"):
        execute_hitl_command(request_path, proposal_path, approval_path, output_dir)

    assert not output_dir.exists()


def test_execute_hitl_command_denies_tampered_proposal(tmp_path: Path) -> None:
    request_path, proposal_path, approval_path = _write_chain(tmp_path, command="echo hello")

    # Tamper with the proposal after the approval's digest binding was computed.
    # Keep it internally consistent (still schema-valid) so the digest check itself
    # is what catches the tamper, rather than an earlier proposal-schema rejection.
    proposal = json_lib.loads(proposal_path.read_text(encoding="utf-8"))
    proposal["command"] = "echo tampered"
    proposal["commands_proposed"] = ["echo tampered"]
    proposal_path.write_text(json_lib.dumps(proposal), encoding="utf-8")

    output_dir = tmp_path / "out"

    with pytest.raises(ValueError, match="does not match command proposal digest"):
        execute_hitl_command(request_path, proposal_path, approval_path, output_dir)

    assert not output_dir.exists()


def test_execute_hitl_command_rejects_invalid_request_artifact(tmp_path: Path) -> None:
    request_path = tmp_path / "request.json"
    request_path.write_text(json_lib.dumps({"kind": "not_a_real_kind"}), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid execution request"):
        execute_hitl_command(request_path, tmp_path / "proposal.json", tmp_path / "approval.json", tmp_path / "out")


def test_execute_hitl_command_rejects_missing_target_repo(tmp_path: Path) -> None:
    missing_repo = tmp_path / "does-not-exist"
    request_path, proposal_path, approval_path = _write_chain(tmp_path, command="echo hello")

    request = json_lib.loads(request_path.read_text(encoding="utf-8"))
    request["target"]["repo"] = str(missing_repo)
    request_path.write_text(json_lib.dumps(request), encoding="utf-8")

    with pytest.raises(ValueError, match="does not exist or is not a directory"):
        execute_hitl_command(request_path, proposal_path, approval_path, tmp_path / "out")
