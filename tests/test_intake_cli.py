import json as json_lib
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from builder_ii.approval_records import create_approval_record
from builder_ii.chain_summary_records import create_chain_summary_record
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.handoff_bundle_records import create_handoff_bundle_record
from builder_ii.intake_cli import intake_app
from builder_ii.preflight_records import create_preflight_record
from builder_ii.receipt_records import create_receipt_record

_MANIFEST: dict[str, Any] = {
    "kind": "builder_ii.goose_session_manifest",
    "schema_version": 1,
    "target": {"name": "test-target", "repo": "/tmp/repo", "description": "test"},
    "agent_profile": {"name": "test-agent", "description": "test", "authority": "user"},
    "task": "intake cli test",
    "requested_runtime_mode": "disabled",
}


def _bundle(tmp_path: Path) -> Path:
    p = create_goose_command_proposal(_MANIFEST, manifest_path="manifest.json", command="echo 1", risk_level="low")
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    a = create_approval_record(p, proposal_path="proposal.json", decision="approved", decided_by="operator")
    a_path = tmp_path / "approval.json"
    a_path.write_text(json_lib.dumps(a))

    pf = create_preflight_record(p, a, proposal_path="proposal.json", approval_path="approval.json", verification_refs=["ref"])
    pf_path = tmp_path / "preflight.json"
    pf_path.write_text(json_lib.dumps(pf))

    r = create_receipt_record(pf, preflight_path="preflight.json", status="passed", recorded_by="operator", evidence_refs=["evidence"])
    r_path = tmp_path / "receipt.json"
    r_path.write_text(json_lib.dumps(r))

    s = create_chain_summary_record(
        p, a, pf, r,
        proposal_path="proposal.json",
        approval_path="approval.json",
        preflight_path="preflight.json",
        receipt_path="receipt.json"
    )
    s_path = tmp_path / "summary.json"
    s_path.write_text(json_lib.dumps(s))

    h = create_handoff_bundle_record(s, summary_path="summary.json", bundle_name="test-bundle")
    h_path = tmp_path / "bundle.json"
    h_path.write_text(json_lib.dumps(h))
    return h_path


def test_intake_app_help() -> None:
    result = CliRunner().invoke(intake_app, ["--help"])
    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout


def test_intake_cli_record_and_validate(tmp_path: Path) -> None:
    h_path = _bundle(tmp_path)
    output = tmp_path / "intake.json"
    runner = CliRunner()

    # 1. Record command
    record_result = runner.invoke(
        intake_app,
        [
            "record",
            str(h_path),
            "--decision", "accepted",
            "--received-by", "operator",
            "--notes", "looks good",
            "--output", str(output)
        ]
    )
    assert record_result.exit_code == 0, record_result.stdout
    assert "Intake record written to" in record_result.stdout
    assert output.exists()

    # Verify content
    data = json_lib.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.receive_record"
    assert data["decision"] == "accepted"
    assert data["accepted"] is True

    # 2. Validate command
    validate_result = runner.invoke(intake_app, ["validate", str(output)])
    assert validate_result.exit_code == 0
    assert "Intake record is valid" in validate_result.stdout


def test_intake_cli_validate_failure(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json_lib.dumps({"kind": "wrong_kind"}))

    runner = CliRunner()
    validate_result = runner.invoke(intake_app, ["validate", str(bad_file)])
    assert validate_result.exit_code == 1
    assert "Validation error" in validate_result.stdout
