import json as json_lib
from pathlib import Path

from builder_ii.promotion_decision_records import create_promotion_decision_record
from builder_ii.promotion_readiness_records import create_promotion_readiness_record
from builder_ii.state_ledger_records import create_state_ledger_record, dumps_state_ledger_record, validate_state_ledger_record, validate_state_ledger_record_file


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


def _decision() -> dict:
    return create_promotion_decision_record(_ready(), readiness_path="promotion-readiness.json", decision="approved", decided_by="operator")


def test_create_complete_state_ledger_shape() -> None:
    record = create_state_ledger_record([(_decision(), "promotion-decision.json")], ledger_name="main-ledger")

    assert record["kind"] == "builder_ii.state_ledger_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["counts"] == {"total": 1, "approved": 1, "blocked": 0}
    assert record["entries"][0]["capability_name"] == "artifact_index"
    assert validate_state_ledger_record(record) == []


def test_state_ledger_json_round_trip() -> None:
    data = json_lib.loads(dumps_state_ledger_record(create_state_ledger_record([(_decision(), "promotion-decision.json")], ledger_name="main-ledger")))

    assert data["complete"] is True
    assert validate_state_ledger_record(data) == []


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_state_ledger_record_file(tmp_path / "missing.json"))
