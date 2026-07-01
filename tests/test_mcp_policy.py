from builder_ii.mcp_policy import (
    validate_mcp_policy,
    validate_mcp_envelope,
    validate_mcp_receipt,
    validate_mcp_inventory,
    TOOL_POLICY_KIND,
    MCP_POLICY_KIND,
    TOOL_ENVELOPE_KIND,
    MCP_ENVELOPE_KIND,
    TOOL_RECEIPT_KIND,
    MCP_RECEIPT_KIND,
    TOOL_INVENTORY_KIND,
    MCP_INVENTORY_KIND,
    POLICY_SCHEMA_VERSION,
    ENVELOPE_SCHEMA_VERSION,
    RECEIPT_SCHEMA_VERSION,
    INVENTORY_SCHEMA_VERSION,
)

def test_validate_mcp_policy_valid_tool():
    policy = {
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
    errors = validate_mcp_policy(policy)
    assert not errors

def test_validate_mcp_policy_invalid():
    policy = {
        "kind": TOOL_POLICY_KIND,
        "schema_version": 999,
        "denied_by_default": False,
        "artifact_is_authority": True,
        "governance": {}
    }
    errors = validate_mcp_policy(policy)
    assert any("schema_version" in e for e in errors)
    assert any("denied_by_default" in e for e in errors)

def test_validate_mcp_envelope_valid_tool():
    envelope = {
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
    errors = validate_mcp_envelope(envelope)
    assert not errors

def test_validate_mcp_receipt_valid():
    receipt = {
        "kind": TOOL_RECEIPT_KIND,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "envelope_ref": {"role": "env", "kind": "env", "path": "p", "sha256": "0" * 64},
        "policy_ref": {"role": "pol", "kind": "pol", "path": "p", "sha256": "0" * 64},
        "started_at": "now",
        "completed_at": "later",
        "status": "succeeded",
        "bounded_stdout": "hello",
        "output_digest": "0" * 64,
        "output_truncated": False,
        "timeout_hit": False,
        "credential_redaction_report": True,
        "effect_classification": "pure",
        "rollback_classification": "none",
        "replay_declaration": "safe",
        "no_mutation_proof": "read_only",
        "governance": {
            "artifact_is_authority": False
        }
    }
    errors = validate_mcp_receipt(receipt)
    assert not errors

def test_validate_mcp_inventory_valid():
    inventory = {
        "kind": TOOL_INVENTORY_KIND,
        "schema_version": INVENTORY_SCHEMA_VERSION,
        "tools": ["echo", "date"],
        "governance": {
            "artifact_is_authority": False
        }
    }
    errors = validate_mcp_inventory(inventory)
    assert not errors
