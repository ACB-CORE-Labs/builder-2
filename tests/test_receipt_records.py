import json as json_lib
from pathlib import Path

from builder_ii.approval_records import create_approval_record
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest
from builder_ii.preflight_records import create_preflight_record
from builder_ii.receipt_records import (
    create_receipt_record,
    dumps_receipt_record,
    validate_receipt_record,
    validate_receipt_record_file,
)


def _preflight(tmp_path: Path, ready: bool = True) -> dict:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="receipt record check",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    proposal = create_goose_command_proposal(
        manifest,
        manifest_path=tmp_path / "goose-session.json",
        command="verify",
        risk_level="low",
    )
    approval = create_approval_record(
        proposal,
        proposal_path=tmp_path / "proposal.json",
        decision="approved",
        decided_by="operator",
    )
    refs = ["verification artifact"] if ready else []
    return create_preflight_record(
        proposal,
        approval,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        verification_refs=refs,
    )


def test_create_accepted_receipt_record_shape(tmp_path: Path) -> None:
    record = create_receipt_record(
        _preflight(tmp_path),
        preflight_path=tmp_path / "preflight.json",
        status="passed",
        recorded_by="operator",
        evidence_refs=["receipt artifact"],
        summary="observed pass",
    )

    assert record["kind"] == "builder_ii.receipt_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_runtime_state"] == "DISABLED"
    assert record["status"] == "passed"
    assert record["accepted"] is True
    assert record["blockers"] == []
    assert record["recorded_by"] == "operator"
    assert record["evidence_refs"] == ["receipt artifact"]
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"]["artifact_is_authority"] is False
    assert record["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_receipt_record(record) == []


def test_failed_receipt_is_valid_but_not_accepted(tmp_path: Path) -> None:
    record = create_receipt_record(
        _preflight(tmp_path),
        preflight_path=tmp_path / "preflight.json",
        status="failed",
        recorded_by="operator",
        evidence_refs=["receipt artifact"],
    )

    assert record["status"] == "failed"
    assert record["accepted"] is False
    assert validate_receipt_record(record) == []


def test_receipt_from_blocked_preflight_carries_blocker(tmp_path: Path) -> None:
    record = create_receipt_record(
        _preflight(tmp_path, ready=False),
        preflight_path=tmp_path / "preflight.json",
        status="blocked",
        recorded_by="operator",
        evidence_refs=["receipt artifact"],
    )

    assert record["status"] == "blocked"
    assert record["accepted"] is False
    assert "preflight record is not ready" in record["blockers"]
    assert validate_receipt_record(record) == []


def test_receipt_record_json_round_trip(tmp_path: Path) -> None:
    record = create_receipt_record(
        _preflight(tmp_path),
        preflight_path=tmp_path / "preflight.json",
        status="passed",
        recorded_by="operator",
        evidence_refs=["receipt artifact"],
    )
    data = json_lib.loads(dumps_receipt_record(record))

    assert data["accepted"] is True
    assert validate_receipt_record(data) == []


def test_validate_rejects_authority_changes(tmp_path: Path) -> None:
    record = create_receipt_record(
        _preflight(tmp_path),
        preflight_path=tmp_path / "preflight.json",
        status="passed",
        recorded_by="operator",
        evidence_refs=["receipt artifact"],
    )
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["verify"]
    record["governance"]["artifact_is_authority"] = True

    errors = validate_receipt_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false" in errors
    assert "grants_action_authority must be false" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_receipt_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_receipt_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "receipt record must be a JSON object" in validate_receipt_record_file(not_object)
