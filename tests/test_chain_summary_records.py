import json as json_lib
from pathlib import Path

from builder_ii.approval_records import create_approval_record
from builder_ii.chain_summary_records import (
    create_chain_summary_record,
    dumps_chain_summary_record,
    validate_chain_summary_record,
)
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest
from builder_ii.preflight_records import create_preflight_record
from builder_ii.receipt_records import create_receipt_record


def _chain(tmp_path: Path) -> tuple[dict, dict, dict, dict]:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="chain summary check",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    proposal = create_goose_command_proposal(
        manifest, manifest_path=tmp_path / "goose-session.json", command="verify", risk_level="low"
    )
    approval = create_approval_record(
        proposal, proposal_path=tmp_path / "proposal.json", decision="approved", decided_by="operator"
    )
    preflight = create_preflight_record(
        proposal,
        approval,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        verification_refs=["verification artifact"],
    )
    receipt = create_receipt_record(
        preflight,
        preflight_path=tmp_path / "preflight.json",
        status="passed",
        recorded_by="operator",
        evidence_refs=["receipt artifact"],
    )
    return proposal, approval, preflight, receipt


def test_create_complete_chain_summary_shape(tmp_path: Path) -> None:
    proposal, approval, preflight, receipt = _chain(tmp_path)
    record = create_chain_summary_record(
        proposal,
        approval,
        preflight,
        receipt,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        preflight_path=tmp_path / "preflight.json",
        receipt_path=tmp_path / "receipt.json",
        summary="ready handoff",
    )

    assert record["kind"] == "builder_ii.chain_summary_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_runtime_state"] == "DISABLED"
    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["issues"] == []
    assert record["artifacts"]["proposal"]["sha256"]
    assert record["artifacts"]["approval"]["sha256"]
    assert record["artifacts"]["preflight"]["sha256"]
    assert record["artifacts"]["receipt"]["sha256"]
    assert record["receipt_accepted"] is True
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert validate_chain_summary_record(record) == []


def test_incomplete_chain_summary_carries_issue(tmp_path: Path) -> None:
    proposal, approval, preflight, receipt = _chain(tmp_path)
    receipt["preflight"]["sha256"] = "wrong"
    record = create_chain_summary_record(
        proposal,
        approval,
        preflight,
        receipt,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        preflight_path=tmp_path / "preflight.json",
        receipt_path=tmp_path / "receipt.json",
    )

    assert record["status"] == "incomplete"
    assert record["complete"] is False
    assert "receipt does not reference the preflight digest" in record["issues"]
    assert validate_chain_summary_record(record) == []


def test_chain_summary_json_round_trip(tmp_path: Path) -> None:
    proposal, approval, preflight, receipt = _chain(tmp_path)
    record = create_chain_summary_record(
        proposal,
        approval,
        preflight,
        receipt,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        preflight_path=tmp_path / "preflight.json",
        receipt_path=tmp_path / "receipt.json",
    )
    data = json_lib.loads(dumps_chain_summary_record(record))

    assert data["complete"] is True
    assert validate_chain_summary_record(data) == []
