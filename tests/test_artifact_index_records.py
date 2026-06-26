import json as json_lib
from pathlib import Path

from builder_ii.approval_records import create_approval_record, write_approval_record
from builder_ii.artifact_index_records import create_artifact_index_record, dumps_artifact_index_record, validate_artifact_index_record, validate_artifact_index_record_file
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal, write_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest


def _write_known_artifacts(tmp_path: Path) -> None:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="artifact index check",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    proposal = create_goose_command_proposal(manifest, manifest_path=tmp_path / "goose-session.json", command="verify", risk_level="low")
    approval = create_approval_record(proposal, proposal_path=tmp_path / "proposal.json", decision="approved", decided_by="operator")
    write_goose_command_proposal(proposal, tmp_path / "proposal.json")
    write_approval_record(approval, tmp_path / "approval.json")


def test_create_complete_artifact_index_shape(tmp_path: Path) -> None:
    _write_known_artifacts(tmp_path)
    record = create_artifact_index_record(tmp_path)

    assert record["kind"] == "builder_ii.artifact_index_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["counts"]["total"] == 2
    assert record["counts"]["known"] == 2
    assert record["counts"]["invalid"] == 0
    assert {entry["kind"] for entry in record["artifacts"]} == {"builder_ii.goose_command_proposal", "builder_ii.approval_record"}
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"]["artifact_is_authority"] is False
    assert record["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_artifact_index_record(record) == []


def test_index_marks_unknown_artifact_incomplete(tmp_path: Path) -> None:
    (tmp_path / "unknown.json").write_text(json_lib.dumps({"kind": "unknown", "schema_version": 1}), encoding="utf-8")
    record = create_artifact_index_record(tmp_path)

    assert record["status"] == "incomplete"
    assert record["complete"] is False
    assert record["counts"]["unknown"] == 1
    assert record["counts"]["invalid"] == 1
    assert record["artifacts"][0]["errors"] == ["unknown artifact kind"]
    assert validate_artifact_index_record(record) == []


def test_index_recursive_option(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    _write_known_artifacts(nested)

    shallow = create_artifact_index_record(tmp_path)
    recursive = create_artifact_index_record(tmp_path, recursive=True)

    assert shallow["counts"]["total"] == 0
    assert recursive["counts"]["total"] == 2


def test_artifact_index_json_round_trip(tmp_path: Path) -> None:
    _write_known_artifacts(tmp_path)
    record = create_artifact_index_record(tmp_path)
    data = json_lib.loads(dumps_artifact_index_record(record))

    assert data["complete"] is True
    assert validate_artifact_index_record(data) == []


def test_validate_rejects_authority_changes(tmp_path: Path) -> None:
    _write_known_artifacts(tmp_path)
    record = create_artifact_index_record(tmp_path)
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["verify"]
    record["governance"]["artifact_is_authority"] = True

    errors = validate_artifact_index_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false" in errors
    assert "grants_action_authority must be false" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_artifact_index_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_artifact_index_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "artifact index record must be a JSON object" in validate_artifact_index_record_file(not_object)
