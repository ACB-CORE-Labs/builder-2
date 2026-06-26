import json as json_lib
from pathlib import Path

from builder_ii.promotion_readiness_records import (
    create_promotion_readiness_record,
    dumps_promotion_readiness_record,
    validate_promotion_readiness_record,
    validate_promotion_readiness_record_file,
)


def _ready_record() -> dict:
    return create_promotion_readiness_record(
        capability_name="artifact_index",
        docs_refs=["docs/ARTIFACT_INDEX.md"],
        tests_refs=["tests/test_artifact_index_records.py"],
        cli_refs=["builder-index"],
        failure_mode_refs=["invalid artifacts are reported as incomplete"],
        approval_boundary_refs=["artifact_is_authority=false"],
        output_artifact_refs=["artifact-index.json"],
        rollback_refs=["delete artifact-index.json"],
        verification_refs=["uv run pytest -q"],
        notes="ready for promotion review",
    )


def test_create_ready_promotion_readiness_shape() -> None:
    record = _ready_record()

    assert record["kind"] == "builder_ii.promotion_readiness_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["capability_name"] == "artifact_index"
    assert record["status"] == "ready"
    assert record["ready"] is True
    assert record["missing"] == []
    assert len(record["checks"]) == 8
    assert all(check["ready"] is True for check in record["checks"])
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"]["artifact_is_authority"] is False
    assert record["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_promotion_readiness_record(record) == []


def test_create_blocked_promotion_readiness_shape() -> None:
    record = create_promotion_readiness_record(capability_name="artifact_index", docs_refs=["docs/ARTIFACT_INDEX.md"])

    assert record["status"] == "blocked"
    assert record["ready"] is False
    assert "tests refs are required" in record["missing"]
    assert "cli_surface refs are required" in record["missing"]
    assert validate_promotion_readiness_record(record) == []


def test_promotion_readiness_json_round_trip() -> None:
    data = json_lib.loads(dumps_promotion_readiness_record(_ready_record()))

    assert data["ready"] is True
    assert validate_promotion_readiness_record(data) == []


def test_validate_rejects_authority_changes() -> None:
    record = _ready_record()
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["promote"]
    record["governance"]["artifact_is_authority"] = True

    errors = validate_promotion_readiness_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false" in errors
    assert "grants_action_authority must be false" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_promotion_readiness_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_promotion_readiness_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "promotion readiness record must be a JSON object" in validate_promotion_readiness_record_file(not_object)
