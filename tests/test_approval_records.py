import json as json_lib
from pathlib import Path

from builder_ii.approval_records import (
    create_approval_record,
    dumps_approval_record,
    validate_approval_record,
    validate_approval_record_file,
)
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest


def _proposal(tmp_path: Path) -> dict:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="approval record check",
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


def test_create_approval_record_shape(tmp_path: Path) -> None:
    record = create_approval_record(
        _proposal(tmp_path),
        proposal_path=tmp_path / "proposal.json",
        decision="approved",
        decided_by="operator",
        reason="ready for later gated handling",
    )

    assert record["kind"] == "builder_ii.approval_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_runtime_state"] == "DISABLED"
    assert record["decision"]["value"] == "approved"
    assert record["decision"]["approved"] is True
    assert record["decision"]["decided_by"] == "operator"
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["result"]["status"] is None
    assert record["governance"]["artifact_is_authority"] is False
    assert record["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_approval_record(record) == []


def test_rejected_approval_record_shape(tmp_path: Path) -> None:
    record = create_approval_record(
        _proposal(tmp_path),
        proposal_path=tmp_path / "proposal.json",
        decision="rejected",
        decided_by="operator",
        reason="needs narrower scope",
    )

    assert record["decision"]["value"] == "rejected"
    assert record["decision"]["approved"] is False
    assert validate_approval_record(record) == []


def test_approval_record_json_round_trip(tmp_path: Path) -> None:
    record = create_approval_record(
        _proposal(tmp_path),
        proposal_path=tmp_path / "proposal.json",
        decision="approved",
        decided_by="operator",
    )
    data = json_lib.loads(dumps_approval_record(record))

    assert data["decision"]["value"] == "approved"
    assert validate_approval_record(data) == []


def test_validate_rejects_authority_changes(tmp_path: Path) -> None:
    record = create_approval_record(
        _proposal(tmp_path),
        proposal_path=tmp_path / "proposal.json",
        decision="approved",
        decided_by="operator",
    )
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["verify"]
    record["result"]["status"] = 0
    record["governance"]["artifact_is_authority"] = True

    errors = validate_approval_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false or NOT_AUTHORIZED" in errors
    assert "grants_action_authority must be false or NOT_AUTHORIZED" in errors
    assert "performed_actions must be empty" in errors
    assert "result must be empty" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_approval_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_approval_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "approval record must be a JSON object" in validate_approval_record_file(not_object)
