import json as json_lib
from pathlib import Path

from builder_ii.adapters.goose.goose_command_proposal import create_goose_command_proposal
from builder_ii.adapters.goose.goose_session import create_goose_session_manifest
from builder_ii.core.config import load_settings
from builder_ii.governance.ledger.chain_summary_records import create_chain_summary_record
from builder_ii.governance.ledger.handoff_bundle_records import (
    create_handoff_bundle_record,
    dumps_handoff_bundle_record,
    validate_handoff_bundle_record,
    validate_handoff_bundle_record_file,
)
from builder_ii.governance.ledger.receipt_records import create_receipt_record
from builder_ii.lifecycle.candidate.approval_records import create_approval_record
from builder_ii.lifecycle.candidate.preflight_records import create_preflight_record


def _summary(tmp_path: Path) -> dict:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="handoff bundle check",
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
    return create_chain_summary_record(
        proposal,
        approval,
        preflight,
        receipt,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        preflight_path=tmp_path / "preflight.json",
        receipt_path=tmp_path / "receipt.json",
        summary="handoff ready",
    )


def test_create_complete_handoff_bundle_shape(tmp_path: Path) -> None:
    record = create_handoff_bundle_record(
        _summary(tmp_path),
        summary_path=tmp_path / "summary.json",
        bundle_name="handoff-one",
        notes="portable metadata",
        include_refs=["README.md"],
    )

    assert record["kind"] == "builder_ii.handoff_bundle_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_runtime_state"] == "DISABLED"
    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["issues"] == []
    assert record["bundle_name"] == "handoff-one"
    assert record["summary"]["sha256"]
    assert set(record["artifact_digests"]) == {"proposal", "approval", "preflight", "receipt"}
    assert record["include_refs"] == ["README.md"]
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"]["artifact_is_authority"] is False
    assert record["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_handoff_bundle_record(record) == []


def test_incomplete_handoff_bundle_carries_issue(tmp_path: Path) -> None:
    summary = _summary(tmp_path)
    summary["kind"] = "wrong"
    record = create_handoff_bundle_record(
        summary,
        summary_path=tmp_path / "summary.json",
        bundle_name="handoff-one",
    )

    assert record["status"] == "incomplete"
    assert record["complete"] is False
    assert any("summary.kind" in issue for issue in record["issues"])
    assert validate_handoff_bundle_record(record) == []


def test_handoff_bundle_json_round_trip(tmp_path: Path) -> None:
    record = create_handoff_bundle_record(
        _summary(tmp_path),
        summary_path=tmp_path / "summary.json",
        bundle_name="handoff-one",
    )
    data = json_lib.loads(dumps_handoff_bundle_record(record))

    assert data["complete"] is True
    assert validate_handoff_bundle_record(data) == []


def test_validate_rejects_authority_changes(tmp_path: Path) -> None:
    record = create_handoff_bundle_record(
        _summary(tmp_path),
        summary_path=tmp_path / "summary.json",
        bundle_name="handoff-one",
    )
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["verify"]
    record["governance"]["artifact_is_authority"] = True

    errors = validate_handoff_bundle_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false or NOT_AUTHORIZED" in errors
    assert "grants_action_authority must be false or NOT_AUTHORIZED" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_handoff_bundle_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_handoff_bundle_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "handoff bundle record must be a JSON object" in validate_handoff_bundle_record_file(not_object)
