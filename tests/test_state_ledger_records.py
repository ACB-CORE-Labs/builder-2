import json as json_lib
from pathlib import Path

from builder_ii.governance.ledger.state_ledger_records import (
    create_state_ledger_record,
    dumps_state_ledger_record,
    validate_state_ledger_record,
    validate_state_ledger_record_file,
    write_state_ledger_record,
)
from builder_ii.lifecycle.candidate.promotion_decision_records import (
    create_promotion_decision_record,
    write_promotion_decision_record,
)
from builder_ii.lifecycle.candidate.promotion_readiness_records import create_promotion_readiness_record


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


def _decision(decision: str = "approved") -> dict:
    return create_promotion_decision_record(
        _ready(), readiness_path="promotion-readiness.json", decision=decision, decided_by="operator"
    )


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
    assert record["entries"][0]["ledger_state"] == "approved_for_manual_followup"
    assert record["entries"][0]["decision"]["expected_kind"] == "builder_ii.promotion_decision_record"
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"]["capability_state"] == "state_ledger_record"
    assert validate_state_ledger_record(record) == []


def test_create_blocked_state_ledger_entry() -> None:
    record = create_state_ledger_record([(_decision("blocked"), "promotion-decision.json")], ledger_name="main-ledger")

    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["counts"] == {"total": 1, "approved": 0, "blocked": 1}
    assert record["entries"][0]["ledger_state"] == "blocked"
    assert record["entries"][0]["approved"] is False
    assert validate_state_ledger_record(record) == []


def test_state_ledger_json_round_trip() -> None:
    data = json_lib.loads(
        dumps_state_ledger_record(
            create_state_ledger_record([(_decision(), "promotion-decision.json")], ledger_name="main-ledger")
        )
    )

    assert data["complete"] is True
    assert validate_state_ledger_record(data) == []


def test_state_ledger_file_validation(tmp_path: Path) -> None:
    path = tmp_path / "state-ledger.json"
    record = create_state_ledger_record([(_decision(), "promotion-decision.json")], ledger_name="main-ledger")
    write_state_ledger_record(record, path)

    assert validate_state_ledger_record_file(path) == []


def test_validate_rejects_count_drift() -> None:
    record = create_state_ledger_record([(_decision(), "promotion-decision.json")], ledger_name="main-ledger")
    record["counts"] = {"total": 999, "approved": 999, "blocked": 999}

    errors = validate_state_ledger_record(record)

    assert any(error.startswith("counts must match entries") for error in errors)


def test_validate_rejects_entry_shape_drift() -> None:
    record = create_state_ledger_record([(_decision(), "promotion-decision.json")], ledger_name="main-ledger")
    record["entries"][0]["capability_name"] = ""
    record["entries"][0]["ledger_state"] = "approved_for_manual_followup"
    record["entries"][0]["approved"] = False
    record["entries"][0]["issues"] = "not-list"
    record["entries"][0]["decision"]["expected_kind"] = "wrong"

    errors = validate_state_ledger_record(record)

    assert "entries[0].capability_name is required" in errors
    assert "entries[0].approved must be true for approved_for_manual_followup" in errors
    assert "entries[0].issues must be a list" in errors
    assert "entries[0].decision.expected_kind must be builder_ii.promotion_decision_record" in errors


def test_validate_rejects_authority_changes() -> None:
    record = create_state_ledger_record([(_decision(), "promotion-decision.json")], ledger_name="main-ledger")
    record["record_state"] = "ACTIVE"
    record["performed_actions"] = ["record_state_ledger"]
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["governance"]["runtime_execution"] = "ENABLED"
    record["governance"]["model_execution"] = "ENABLED"
    record["governance"]["source_writes"] = "ENABLED"
    record["governance"]["memory_mutation"] = "ENABLED"
    record["governance"]["artifact_is_authority"] = True
    record["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_state_ledger_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "performed_actions must be empty" in errors
    assert "grants_runtime_authority must be false or NOT_AUTHORIZED" in errors
    assert "grants_action_authority must be false or NOT_AUTHORIZED" in errors
    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.model_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.source_writes must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.memory_mutation must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors
    assert "governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED" in errors


def test_validate_rejects_missing_ledger_name() -> None:
    record = create_state_ledger_record([(_decision(), "promotion-decision.json")], ledger_name="")

    assert record["status"] == "incomplete"
    assert record["complete"] is False
    assert "ledger_name is required" in validate_state_ledger_record(record)


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_state_ledger_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_state_ledger_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "state ledger record must be a JSON object" in validate_state_ledger_record_file(not_object)


def test_create_state_ledger_from_file_fixture(tmp_path: Path) -> None:
    decision_path = tmp_path / "decision.json"
    write_promotion_decision_record(_decision(), decision_path)

    record = create_state_ledger_record(
        [(json_lib.loads(decision_path.read_text(encoding="utf-8")), decision_path)], ledger_name="main-ledger"
    )

    assert record["status"] == "complete"
    assert validate_state_ledger_record(record) == []
