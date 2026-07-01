from pathlib import Path
from builder_ii.tool_invocation_gateway import execute_tool_envelope
from builder_ii.mcp_policy import (
    TOOL_ENVELOPE_KIND,
    TOOL_POLICY_KIND,
    ENVELOPE_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
)

def _create_valid_policy():
    return {
        "kind": TOOL_POLICY_KIND,
        "schema_version": POLICY_SCHEMA_VERSION,
        "denied_by_default": True,
        "artifact_is_authority": False,
        "grants_authority": False,
        "allowed_operations": ["invoke"],
        "allowed_risk_classes": ["low"],
        "allowed_tools": ["echo", "date"],
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
        "governance": {
            "artifact_is_authority": False
        }
    }

def _create_valid_envelope():
    return {
        "kind": TOOL_ENVELOPE_KIND,
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "operation_name": "invoke",
        "tool_id": "echo",
        "executes_tool": True,
        "input_digest": "0" * 64,
        "policy_ref": {"role": "policy", "kind": "policy", "path": "path", "sha256": "0" * 64},
        "effect_classification": "pure",
        "risk_classification": "low",
        "rollback_requirement": "none",
        "timeout": 30,
        "output_cap": 1024,
        "credential_redaction_declaration": True,
        "requires_human_promotion_for_execution": False,
        "executes_shell": False,
        "mutates_target_repo": False,
        "grants_authority": False,
        "artifact_is_authority": False,
    }

def test_execute_tool_success():
    envelope = _create_valid_envelope()
    policy = _create_valid_policy()
    
    receipt = execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))
    
    assert receipt["status"] == "succeeded"
    assert "output_digest" in receipt
    assert receipt["kind"] == "builder_ii.tool_call_receipt"

def test_execute_tool_denied():
    envelope = _create_valid_envelope()
    envelope["tool_id"] = "unknown_tool"
    policy = _create_valid_policy()
    
    import pytest
    with pytest.raises(ValueError, match="not permitted by policy"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))
