import json

from builder_ii.mcp_cli import mcp_app
from typer.testing import CliRunner

from builder_ii.mcp_policy import (
    ENVELOPE_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    TOOL_ENVELOPE_KIND,
    TOOL_POLICY_KIND,
)
from builder_ii.workflow_records import canonical_digest

runner = CliRunner()


def test_mcp_inventory():
    result = runner.invoke(mcp_app, ["inventory"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "servers" in data


def test_mcp_policy():
    result = runner.invoke(mcp_app, ["policy"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert "allowed_servers" in data


def test_mcp_standalone_call_success(tmp_path):
    policy = {
        "kind": TOOL_POLICY_KIND,
        "schema_version": POLICY_SCHEMA_VERSION,
        "denied_by_default": True,
        "artifact_is_authority": False,
        "grants_authority": False,
        "allowed_operations": ["invoke"],
        "allowed_risk_classes": ["low", "low_risk"],
        "allowed_tools": ["builtin.echo"],
        "max_input_bytes": 1024,
        "max_output_bytes": 1024,
        "timeout_seconds": 30,
        "network_allowed": False,
        "mutation_allowed": False,
        "credential_access_allowed": False,
        "cost_allowed": False,
        "requires_approval_for_mutation": True,
        "requires_approval_for_external_network": True,
        "requires_approval_for_credentials": True,
        "governance": {"artifact_is_authority": False},
    }
    envelope = {
        "kind": TOOL_ENVELOPE_KIND,
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "operation_name": "invoke",
        "tool_id": "builtin.echo",
        "executes_tool": True,
        "input_digest": "0" * 64,
        "policy_ref": {"role": "policy", "kind": "policy", "path": "path", "sha256": canonical_digest(policy)},
        "effect_classification": "pure",
        "risk_classification": "low",
        "rollback_requirement": "none",
        "timeout": 30,
        "output_cap": 1024,
        "credential_redaction_declaration": True,
        "requires_human_promotion_for_execution": True,
        "executes_shell": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "arguments": {"text": "hello mcp standalone"},
    }

    pol_path = tmp_path / "policy.json"
    env_path = tmp_path / "envelope.json"
    rec_path = tmp_path / "receipt.json"

    pol_path.write_text(json.dumps(policy))
    env_path.write_text(json.dumps(envelope))

    result = runner.invoke(
        mcp_app,
        [
            "standalone-call",
            str(env_path),
            str(pol_path),
            "--receipt-output",
            str(rec_path),
        ],
    )

    assert result.exit_code == 0
    assert rec_path.is_file()
    receipt_data = json.loads(rec_path.read_text())
    assert receipt_data["status"] == "succeeded"
    assert receipt_data["bounded_stdout"] == "hello mcp standalone"
