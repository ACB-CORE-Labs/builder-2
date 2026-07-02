import json as json_lib
from pathlib import Path

from builder_ii.promotion_decision_records import (
    create_promotion_decision_record,
    dumps_promotion_decision_record,
    validate_promotion_decision_record,
    validate_promotion_decision_record_file,
    write_promotion_decision_record,
)
from builder_ii.promotion_readiness_records import create_promotion_readiness_record, write_promotion_readiness_record


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
    assert record["readiness"]["expected_kind"] == "builder_ii.promotion_readiness_record"
    assert record["readiness"]["kind"] == "builder_ii.promotion_readiness_record"
    assert record["readiness"]["sha256"]
    assert record["readiness"]["status"] == "ready"
    assert record["readiness"]["ready"] is True
    assert record["readiness"]["capability_name"] == "artifact_index"
    assert record["checks"]
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"] == {
        "capability_state": "promotion_decision_record",
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "source_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "artifact_is_authority": False,
        "core_workbench_coupling": "NONE",
    }
    assert validate_promotion_decision_record(record) == []


def test_blocked_when_readiness_is_blocked() -> None:
    readiness = create_promotion_readiness_record(
        capability_name="artifact_index", docs_refs=["docs/ARTIFACT_INDEX.md"]
    )
    record = create_promotion_decision_record(
        readiness,
        readiness_path="promotion-readiness.json",
        decision="approved",
        decided_by="operator",
    )

    assert record["decision"] == "blocked"
    assert record["approved"] is False
    assert "promotion readiness record is not ready" in record["blockers"]
    assert record["readiness"]["status"] == "blocked"
    assert record["readiness"]["ready"] is False
    assert validate_promotion_decision_record(record) == []


def test_manual_blocked_decision_is_valid() -> None:
    record = create_promotion_decision_record(
        _ready(),
        readiness_path="promotion-readiness.json",
        decision="blocked",
        decided_by="operator",
        reason="manual hold",
    )

    assert record["decision"] == "blocked"
    assert record["approved"] is False
    assert record["blockers"] == []
    assert validate_promotion_decision_record(record) == []


def test_promotion_decision_json_round_trip() -> None:
    data = json_lib.loads(
        dumps_promotion_decision_record(
            create_promotion_decision_record(
                _ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator"
            )
        )
    )

    assert data["approved"] is True
    assert validate_promotion_decision_record(data) == []


def test_promotion_decision_file_validation(tmp_path: Path) -> None:
    path = tmp_path / "promotion-decision.json"
    record = create_promotion_decision_record(
        _ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator"
    )
    write_promotion_decision_record(record, path)

    assert validate_promotion_decision_record_file(path) == []


def test_write_readiness_fixture_remains_compatible(tmp_path: Path) -> None:
    path = tmp_path / "readiness.json"
    write_promotion_readiness_record(_ready(), path)
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    record = create_promotion_decision_record(data, readiness_path=path, decision="approved", decided_by="operator")

    assert record["approved"] is True
    assert validate_promotion_decision_record(record) == []


def test_validate_rejects_authority_changes() -> None:
    record = create_promotion_decision_record(
        _ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator"
    )
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["promote"]
    record["governance"]["runtime_execution"] = "ENABLED"
    record["governance"]["model_execution"] = "ENABLED"
    record["governance"]["source_writes"] = "ENABLED"
    record["governance"]["memory_mutation"] = "ENABLED"
    record["governance"]["artifact_is_authority"] = True
    record["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_promotion_decision_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false" in errors
    assert "grants_action_authority must be false" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.runtime_execution must be DISABLED" in errors
    assert "governance.model_execution must be DISABLED" in errors
    assert "governance.source_writes must be DISABLED" in errors
    assert "governance.memory_mutation must be DISABLED" in errors
    assert "governance.artifact_is_authority must be false" in errors
    assert "governance.core_workbench_coupling must be NONE" in errors


def test_validate_rejects_readiness_shape_drift() -> None:
    record = create_promotion_decision_record(
        _ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator"
    )
    record["readiness"]["expected_kind"] = "wrong"
    record["readiness"]["kind"] = "wrong"
    record["readiness"]["path"] = ""
    record["readiness"]["sha256"] = ""
    record["readiness"]["status"] = "bad"
    record["readiness"]["ready"] = "yes"
    record["readiness"]["capability_name"] = ""
    record["checks"] = "not-list"

    errors = validate_promotion_decision_record(record)

    assert "readiness.expected_kind must be builder_ii.promotion_readiness_record" in errors
    assert "readiness.kind must be builder_ii.promotion_readiness_record" in errors
    assert "readiness.path is required" in errors
    assert "readiness.sha256 is required" in errors
    assert "readiness.status must be ready or blocked" in errors
    assert "readiness.ready must be a boolean" in errors
    assert "readiness.capability_name is required" in errors
    assert "checks must be a list" in errors


def test_validate_rejects_non_object_readiness() -> None:
    record = create_promotion_decision_record(
        _ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator"
    )
    record["readiness"] = []

    assert "readiness must be an object" in validate_promotion_decision_record(record)


def test_validate_rejects_approved_with_blockers() -> None:
    record = create_promotion_decision_record(
        _ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator"
    )
    record["blockers"] = ["manual inconsistency"]
    record["approved"] = False

    assert "approved decision must not have blockers" in validate_promotion_decision_record(record)


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any(
        "file not found" in error for error in validate_promotion_decision_record_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_promotion_decision_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "promotion decision record must be a JSON object" in validate_promotion_decision_record_file(not_object)
