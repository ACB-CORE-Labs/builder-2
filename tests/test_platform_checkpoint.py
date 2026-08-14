import json as json_lib
from pathlib import Path

from builder_ii.governance.ledger.artifact_index_records import (
    create_artifact_index_record,
    write_artifact_index_record,
)
from builder_ii.governance.ledger.snapshot_records import (
    SNAPSHOT_RECORD_KIND,
    create_snapshot_record,
    dumps_snapshot_record,
    validate_snapshot_record,
    validate_snapshot_record_file,
    write_snapshot_record,
)
from builder_ii.governance.ledger.state_ledger_records import create_state_ledger_record, write_state_ledger_record
from builder_ii.lifecycle.candidate.promotion_decision_records import (
    create_promotion_decision_record,
    write_promotion_decision_record,
)
from builder_ii.lifecycle.candidate.promotion_readiness_records import (
    create_promotion_readiness_record,
    write_promotion_readiness_record,
)


def _write_snapshot_inputs(tmp_path: Path) -> tuple[dict, dict, Path, Path]:
    readiness_path = tmp_path / "readiness.json"
    decision_path = tmp_path / "decision.json"
    ledger_path = tmp_path / "ledger.json"
    index_path = tmp_path / "artifact-index.json"

    readiness = create_promotion_readiness_record(
        capability_name="snapshot-validation",
        docs_refs=("docs/PLATFORM_SNAPSHOT.md",),
        tests_refs=("tests/test_platform_checkpoint.py",),
        cli_refs=("builder-snapshot",),
        failure_mode_refs=("invalid inputs produce incomplete snapshots",),
        approval_boundary_refs=("manual review remains required",),
        output_artifact_refs=("platform-snapshot.json",),
        rollback_refs=("revert snapshot validation patch",),
        verification_refs=("uv run pytest tests/test_platform_checkpoint.py tests/test_platform_checkpoint_cli.py -q",),
    )
    write_promotion_readiness_record(readiness, readiness_path)

    decision = create_promotion_decision_record(
        readiness,
        readiness_path=readiness_path,
        decision="approved",
        decided_by="operator",
        reason="test fixture",
    )
    write_promotion_decision_record(decision, decision_path)

    ledger = create_state_ledger_record([(decision, decision_path)], ledger_name="snapshot-test")
    write_state_ledger_record(ledger, ledger_path)

    artifact_index = create_artifact_index_record(tmp_path)
    write_artifact_index_record(artifact_index, index_path)
    return artifact_index, ledger, index_path, ledger_path


def test_platform_checkpoint_record_shape(tmp_path: Path) -> None:
    artifact_index, ledger, index_path, ledger_path = _write_snapshot_inputs(tmp_path)
    record = create_snapshot_record(
        artifact_index,
        ledger,
        artifact_index_path=index_path,
        state_ledger_path=ledger_path,
        snapshot_name="snapshot-test",
        notes="checkpoint",
    )

    assert record["kind"] == SNAPSHOT_RECORD_KIND
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["issues"] == []
    assert record["performed_actions"] == []
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["governance"]["capability_state"] == "snapshot_record"
    assert validate_snapshot_record(record) == []


def test_platform_checkpoint_json_round_trip(tmp_path: Path) -> None:
    artifact_index, ledger, index_path, ledger_path = _write_snapshot_inputs(tmp_path)
    record = create_snapshot_record(
        artifact_index,
        ledger,
        artifact_index_path=index_path,
        state_ledger_path=ledger_path,
        snapshot_name="snapshot-test",
    )
    data = json_lib.loads(dumps_snapshot_record(record))

    assert data["complete"] is True
    assert validate_snapshot_record(data) == []


def test_platform_checkpoint_file_validation(tmp_path: Path) -> None:
    artifact_index, ledger, index_path, ledger_path = _write_snapshot_inputs(tmp_path)
    record = create_snapshot_record(
        artifact_index,
        ledger,
        artifact_index_path=index_path,
        state_ledger_path=ledger_path,
        snapshot_name="snapshot-test",
    )
    snapshot_path = tmp_path / "snapshot.json"
    write_snapshot_record(record, snapshot_path)

    assert validate_snapshot_record_file(snapshot_path) == []


def test_platform_checkpoint_rejects_authority_changes(tmp_path: Path) -> None:
    artifact_index, ledger, index_path, ledger_path = _write_snapshot_inputs(tmp_path)
    record = create_snapshot_record(
        artifact_index,
        ledger,
        artifact_index_path=index_path,
        state_ledger_path=ledger_path,
        snapshot_name="snapshot-test",
    )
    record["record_state"] = "ACTIVE"
    record["performed_actions"] = ["record_snapshot"]
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["governance"]["runtime_execution"] = "ENABLED"
    record["governance"]["model_execution"] = "ENABLED"
    record["governance"]["source_writes"] = "ENABLED"
    record["governance"]["memory_mutation"] = "ENABLED"
    record["governance"]["artifact_is_authority"] = True
    record["governance"]["core_workbench_coupling"] = "COUPLED"

    errors = validate_snapshot_record(record)

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


def test_platform_checkpoint_requires_snapshot_name(tmp_path: Path) -> None:
    artifact_index, ledger, index_path, ledger_path = _write_snapshot_inputs(tmp_path)
    record = create_snapshot_record(
        artifact_index, ledger, artifact_index_path=index_path, state_ledger_path=ledger_path, snapshot_name=""
    )

    assert record["status"] == "incomplete"
    assert record["complete"] is False
    assert "snapshot_name is required" in validate_snapshot_record(record)
