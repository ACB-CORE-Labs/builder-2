import json as json_lib
from pathlib import Path

from builder_ii.snap_cli import snap_app
from typer.testing import CliRunner

from builder_ii.artifact_index_records import create_artifact_index_record, write_artifact_index_record
from builder_ii.promotion_decision_records import create_promotion_decision_record, write_promotion_decision_record
from builder_ii.promotion_readiness_records import create_promotion_readiness_record, write_promotion_readiness_record
from builder_ii.state_ledger_records import create_state_ledger_record, write_state_ledger_record


def _write_snapshot_cli_inputs(tmp_path: Path) -> tuple[Path, Path]:
    readiness_path = tmp_path / "readiness.json"
    decision_path = tmp_path / "decision.json"
    ledger_path = tmp_path / "ledger.json"
    index_path = tmp_path / "artifact-index.json"

    readiness = create_promotion_readiness_record(
        capability_name="snapshot-cli",
        docs_refs=("docs/PLATFORM_SNAPSHOT.md",),
        tests_refs=("tests/test_platform_checkpoint_cli.py",),
        cli_refs=("builder-snapshot",),
        failure_mode_refs=("invalid files exit nonzero",),
        approval_boundary_refs=("operator review",),
        output_artifact_refs=("snapshot.json",),
        rollback_refs=("revert cli test",),
        verification_refs=("uv run pytest tests/test_platform_checkpoint_cli.py -q",),
    )
    write_promotion_readiness_record(readiness, readiness_path)

    decision = create_promotion_decision_record(
        readiness, readiness_path=readiness_path, decision="approved", decided_by="operator"
    )
    write_promotion_decision_record(decision, decision_path)

    ledger = create_state_ledger_record([(decision, decision_path)], ledger_name="snapshot-cli")
    write_state_ledger_record(ledger, ledger_path)

    artifact_index = create_artifact_index_record(tmp_path)
    write_artifact_index_record(artifact_index, index_path)
    return index_path, ledger_path


def test_checkpoint_cli_record_and_validate(tmp_path: Path) -> None:
    index_path, ledger_path = _write_snapshot_cli_inputs(tmp_path)
    output = tmp_path / "snapshot.json"

    record_result = CliRunner().invoke(
        snap_app,
        ["record", str(index_path), str(ledger_path), "--snapshot-name", "snapshot-cli", "--output", str(output)],
    )

    assert record_result.exit_code == 0
    assert output.exists()
    data = json_lib.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.snapshot_record"
    assert data["complete"] is True
    assert data["governance"]["source_writes"] == "DISABLED"
    assert data["governance"]["memory_mutation"] == "DISABLED"

    validate_result = CliRunner().invoke(snap_app, ["validate", str(output)])

    assert validate_result.exit_code == 0
    assert "Snapshot record is valid" in validate_result.stdout


def test_checkpoint_cli_rejects_invalid_input(tmp_path: Path) -> None:
    index_path = tmp_path / "bad-index.json"
    ledger_path = tmp_path / "missing-ledger.json"
    index_path.write_text("[]", encoding="utf-8")

    result = CliRunner().invoke(snap_app, ["record", str(index_path), str(ledger_path), "--snapshot-name", "bad"])

    assert result.exit_code == 1
    assert "Validation error" in result.stdout
