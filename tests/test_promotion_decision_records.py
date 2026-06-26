import json as json_lib
from pathlib import Path

from builder_ii.promotion_decision_records import (
    create_promotion_decision_record,
    dumps_promotion_decision_record,
    validate_promotion_decision_record,
    validate_promotion_decision_record_file,
)
from builder_ii.promotion_readiness_records import create_promotion_readiness_record


def _ready() -> dict:
    return create_promotion_readiness_record(
        capability_name="artifact_index",
        docs_refs=["docs/ARTIFACT_INDEX.md"],
        tests_refs=["tests/test_artifact_index_records.py"],
        cli_refs=["builder-index"],
        failure_mode_refs=["incomplete index"],
        approval_boundary_refs=["artifact_is_authority=false"],
        output_artifact_refs=["artifact-index.json"],
        rollback_refs=["delete artifact-index.json"],
        verification_refs=["uv run pytest -q"],
    )


def test_create_approved_promotion_decision_shape() -> None:
    record = create_promotion_decision_record(
        _ready(),
        readiness_path="promotion-readiness.json",
        decision="approved",
        decided_by="operator",
        reason="all evidence present",
    )

    assert record["kind"] == "builder_ii.promotion_decision_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["decision"] == "approved"
    assert record["approved"] is True
    assert record["blockers"] == []
    assert record["decided_by"] == "operator"
    assert record["readiness"]["sha256"]
    assert record["readiness"]["capability_name"] == "artifact_index"
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"]["artifact_is_authority"] is False
    assert record["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_promotion_decision_record(record) == []


def test_blocked_when_readiness_is_blocked() -> None:
    readiness = create_promotion_readiness_record(capability_name="artifact_index", docs_refs=["docs/ARTIFACT_INDEX.md"])
    record = create_promotion_decision_record(
        readiness,
        readiness_path="promotion-readiness.json",
        decision="approved",
        decided_by="operator",
    )

    assert record["decision"] == "blocked"
    assert record["approved"] is False
    assert "promotion readiness record is not ready" in record["blockers"]
    assert validate_promotion_decision_record(record) == []


def test_promotion_decision_json_round_trip() -> None:
    data = json_lib.loads(dumps_promotion_decision_record(create_promotion_decision_record(_ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator")))

    assert data["approved"] is True
    assert validate_promotion_decision_record(data) == []


def test_validate_rejects_authority_changes() -> None:
    record = create_promotion_decision_record(_ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator")
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["promote"]
    record["governance"]["artifact_is_authority"] = True

    errors = validate_promotion_decision_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false" in errors
    assert "grants_action_authority must be false" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_promotion_decision_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_promotion_decision_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "promotion decision record must be a JSON object" in validate_promotion_decision_record_file(not_object)
