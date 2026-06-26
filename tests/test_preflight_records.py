import json as json_lib
from pathlib import Path

from builder_ii.approval_records import create_approval_record
from builder_ii.config import load_settings
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.goose_session import create_goose_session_manifest
from builder_ii.preflight_records import (
    create_preflight_record,
    dumps_preflight_record,
    validate_preflight_record,
    validate_preflight_record_file,
)


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


def test_create_ready_preflight_record_shape(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    approval = _approval(tmp_path, proposal)
    record = create_preflight_record(
        proposal,
        approval,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        verification_refs=["uv run pytest -q"],
    )

    assert record["kind"] == "builder_ii.preflight_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_runtime_state"] == "DISABLED"
    assert record["status"] == "ready"
    assert record["ready"] is True
    assert record["blockers"] == []
    assert record["verification_refs"] == ["uv run pytest -q"]
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["result"] == {"status": None, "stdout": "", "stderr": ""}
    assert record["governance"]["artifact_is_authority"] is False
    assert record["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_preflight_record(record) == []


def test_create_blocked_preflight_without_verification_refs(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    approval = _approval(tmp_path, proposal)
    record = create_preflight_record(
        proposal,
        approval,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
    )

    assert record["status"] == "blocked"
    assert record["ready"] is False
    assert "verification refs are required" in record["blockers"]
    assert validate_preflight_record(record) == []


def test_create_blocked_preflight_for_rejected_approval(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    approval = _approval(tmp_path, proposal, decision="rejected")
    record = create_preflight_record(
        proposal,
        approval,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        verification_refs=["uv run pytest -q"],
    )

    assert record["status"] == "blocked"
    assert record["ready"] is False
    assert "approval decision is not approved" in record["blockers"]
    assert validate_preflight_record(record) == []


def test_preflight_record_json_round_trip(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    approval = _approval(tmp_path, proposal)
    record = create_preflight_record(
        proposal,
        approval,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        verification_refs=["verification artifact"],
    )
    data = json_lib.loads(dumps_preflight_record(record))

    assert data["status"] == "ready"
    assert validate_preflight_record(data) == []


def test_validate_rejects_authority_changes(tmp_path: Path) -> None:
    proposal = _proposal(tmp_path)
    approval = _approval(tmp_path, proposal)
    record = create_preflight_record(
        proposal,
        approval,
        proposal_path=tmp_path / "proposal.json",
        approval_path=tmp_path / "approval.json",
        verification_refs=["verification artifact"],
    )
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["verify"]
    record["result"]["status"] = 0
    record["governance"]["artifact_is_authority"] = True

    errors = validate_preflight_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false" in errors
    assert "grants_action_authority must be false" in errors
    assert "performed_actions must be empty" in errors
    assert "result must be empty" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_preflight_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_preflight_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "preflight record must be a JSON object" in validate_preflight_record_file(not_object)
