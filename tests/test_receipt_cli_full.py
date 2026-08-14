import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.receipt_records_cli import receipt_app
from typer.testing import CliRunner

from builder_ii.adapters.goose.goose_command_proposal import create_goose_command_proposal
from builder_ii.lifecycle.candidate.approval_records import create_approval_record
from builder_ii.lifecycle.candidate.preflight_records import create_preflight_record

_MANIFEST: dict[str, Any] = {
    "kind": "builder_ii.goose_session_manifest",
    "schema_version": 1,
    "target": {"name": "test-target", "repo": "/tmp/repo", "description": "test"},
    "agent_profile": {"name": "test-agent", "description": "test", "authority": "user"},
    "task": "receipt cli test",
    "requested_runtime_mode": "disabled",
}


def _preflight(tmp_path: Path) -> Path:
    p = create_goose_command_proposal(_MANIFEST, manifest_path="manifest.json", command="echo 1", risk_level="low")
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    a = create_approval_record(p, proposal_path="proposal.json", decision="approved", decided_by="operator")
    a_path = tmp_path / "approval.json"
    a_path.write_text(json_lib.dumps(a))

    pf = create_preflight_record(
        p, a, proposal_path="proposal.json", approval_path="approval.json", verification_refs=["ref"]
    )
    pf_path = tmp_path / "preflight.json"
    pf_path.write_text(json_lib.dumps(pf))
    return pf_path


def test_receipt_cli_help() -> None:
    result = CliRunner().invoke(receipt_app, ["--help"])
    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout


def test_receipt_cli_record_and_validate(tmp_path: Path) -> None:
    pf_path = _preflight(tmp_path)
    output = tmp_path / "receipt.json"
    runner = CliRunner()

    # 1. Record command
    record_result = runner.invoke(
        receipt_app,
        [
            "record",
            str(pf_path),
            "--status",
            "passed",
            "--recorded-by",
            "operator",
            "--evidence-ref",
            "evidence-item",
            "--summary",
            "test summary",
            "--output",
            str(output),
        ],
    )
    assert record_result.exit_code == 0, record_result.stdout
    assert "Receipt record written to" in record_result.stdout
    assert output.exists()

    # Verify content
    data = json_lib.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.receipt_record"
    assert data["status"] == "passed"
    assert data["accepted"] is True

    # 2. Validate command
    validate_result = runner.invoke(receipt_app, ["validate", str(output)])
    assert validate_result.exit_code == 0
    assert "Receipt record is valid" in validate_result.stdout


def test_receipt_cli_validate_failure(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json_lib.dumps({"kind": "wrong_kind"}))

    runner = CliRunner()
    validate_result = runner.invoke(receipt_app, ["validate", str(bad_file)])
    assert validate_result.exit_code == 1
    assert "Validation error" in validate_result.stdout
