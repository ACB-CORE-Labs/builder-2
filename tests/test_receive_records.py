import json as json_lib
from pathlib import Path

from builder_ii.approval_records import create_approval_record
from builder_ii.chain_summary_records import create_chain_summary_record
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest
from builder_ii.handoff_bundle_records import create_handoff_bundle_record
from builder_ii.preflight_records import create_preflight_record
from builder_ii.receipt_records import create_receipt_record
from builder_ii.receive_records import (
    create_receive_record,
    dumps_receive_record,
    validate_receive_record,
    validate_receive_record_file,
)


def _bundle(tmp_path: Path) -> dict:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="receive record check",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    proposal = create_goose_command_proposal(manifest, manifest_path=tmp_path / "goose-session.json", command="verify", risk_level="low")
    approval = create_approval_record(proposal, proposal_path=tmp_path / "proposal.json", decision="approved", decided_by="operator")
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
    summary = create_chain_summary_record(
        proposal,
        approval,
        preflight,
        receipt,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        preflight_path=tmp_path / "preflight.json",
        receipt_path=tmp_path / "receipt.json",
    )
    return create_handoff_bundle_record(summary, summary_path=tmp_path / "summary.json", bundle_name="handoff-one")


def test_create_accepted_receive_record_shape(tmp_path: Path) -> None:
    record = create_receive_record(
        _bundle(tmp_path),
        bundle_path=tmp_path / "bundle.json",
        decision="accepted",
        received_by="receiver",
        notes="received cleanly",
    )

    assert record["kind"] == "builder_ii.receive_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["decision"] == "accepted"
    assert record["accepted"] is True
    assert record["blockers"] == []
    assert record["received_by"] == "receiver"
    assert record["bundle"]["sha256"]
    assert set(record["artifact_digests"]) == {"proposal", "approval", "preflight", "receipt"}
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert validate_receive_record(record) == []


def test_blocked_receive_record_carries_blocker(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path)
    bundle["complete"] = False
    bundle["status"] = "incomplete"
    record = create_receive_record(
        bundle,
        bundle_path=tmp_path / "bundle.json",
        decision="accepted",
        received_by="receiver",
    )

    assert record["decision"] == "blocked"
    assert record["accepted"] is False
    assert "handoff bundle is not complete" in record["blockers"]
    assert validate_receive_record(record) == []


def test_receive_record_json_round_trip(tmp_path: Path) -> None:
    record = create_receive_record(_bundle(tmp_path), bundle_path=tmp_path / "bundle.json", decision="accepted", received_by="receiver")
    data = json_lib.loads(dumps_receive_record(record))

    assert data["accepted"] is True
    assert validate_receive_record(data) == []


def test_validate_rejects_authority_changes(tmp_path: Path) -> None:
    record = create_receive_record(_bundle(tmp_path), bundle_path=tmp_path / "bundle.json", decision="accepted", received_by="receiver")
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["verify"]
    record["governance"]["artifact_is_authority"] = True

    errors = validate_receive_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false" in errors
    assert "grants_action_authority must be false" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_receive_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_receive_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "receive record must be a JSON object" in validate_receive_record_file(not_object)
