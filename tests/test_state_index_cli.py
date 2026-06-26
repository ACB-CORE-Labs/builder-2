import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.promotion_decision_records import create_promotion_decision_record, write_promotion_decision_record
from builder_ii.promotion_readiness_records import create_promotion_readiness_record
from builder_ii.state_index_cli import state_index_app


def _write_decision(tmp_path: Path) -> Path:
    readiness = create_promotion_readiness_record(
        capability_name="state-ledger-cli",
        docs_refs=("docs/STATE_LEDGER.md",),
        tests_refs=("tests/test_state_index_cli.py",),
        cli_refs=("builder-state-index",),
        failure_mode_refs=("invalid decision files fail validation",),
        approval_boundary_refs=("manual followup only",),
        output_artifact_refs=("state-ledger.json",),
        rollback_refs=("delete state-ledger.json",),
        verification_refs=("uv run pytest tests/test_state_index_cli.py -q",),
    )
    decision = create_promotion_decision_record(readiness, readiness_path="readiness.json", decision="approved", decided_by="operator")
    decision_path = tmp_path / "decision.json"
    write_promotion_decision_record(decision, decision_path)
    return decision_path


def test_state_index_cli_record_and_validate(tmp_path: Path) -> None:
    decision_path = _write_decision(tmp_path)
    output = tmp_path / "state-ledger.json"

    record_result = CliRunner().invoke(
        state_index_app,
        ["record", str(decision_path), "--ledger-name", "state-cli", "--output", str(output)],
    )

    assert record_result.exit_code == 0
    assert output.exists()
    data = json_lib.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.state_ledger_record"
    assert data["complete"] is True
    assert data["counts"] == {"total": 1, "approved": 1, "blocked": 0}
    assert data["governance"]["source_writes"] == "DISABLED"
    assert data["governance"]["memory_mutation"] == "DISABLED"

    validate_result = CliRunner().invoke(state_index_app, ["validate", str(output)])

    assert validate_result.exit_code == 0
    assert "State index record is valid" in validate_result.stdout


def test_state_index_cli_rejects_invalid_input(tmp_path: Path) -> None:
    decision_path = tmp_path / "bad-decision.json"
    decision_path.write_text("[]", encoding="utf-8")

    result = CliRunner().invoke(state_index_app, ["record", str(decision_path), "--ledger-name", "bad"])

    assert result.exit_code == 1
    assert "Validation error" in result.stdout
