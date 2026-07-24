from pathlib import Path

import pytest

from builder_ii.core.mcp_policy import (
    ENVELOPE_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    TOOL_ENVELOPE_KIND,
    TOOL_POLICY_KIND,
    validate_mcp_receipt,
)
from builder_ii.core.tool_invocation_gateway import execute_tool_envelope
from builder_ii.governance.ledger.workflow_records import canonical_digest


def _create_valid_policy():
    return {
        "kind": TOOL_POLICY_KIND,
        "schema_version": POLICY_SCHEMA_VERSION,
        "denied_by_default": True,
        "artifact_is_authority": False,
        "grants_authority": False,
        "allowed_operations": ["invoke"],
        "allowed_risk_classes": [
            "low",
            "low_risk",
            "mutation",
            "external_network",
            "credential_sensitive",
            "cost_bearing",
        ],
        "allowed_tools": ["builtin.echo", "builtin.utc_static"],
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


def _create_valid_envelope(policy):
    digest = canonical_digest(policy)
    return {
        "kind": TOOL_ENVELOPE_KIND,
        "schema_version": ENVELOPE_SCHEMA_VERSION,
        "operation_name": "invoke",
        "tool_id": "builtin.echo",
        "executes_tool": True,
        "input_digest": "0" * 64,
        "policy_ref": {"role": "policy", "kind": "policy", "path": "path", "sha256": digest},
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
        "arguments": {"text": "hello test"},
    }


def test_execute_tool_success():
    policy = _create_valid_policy()
    envelope = _create_valid_envelope(policy)

    receipt = execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))

    assert receipt["status"] == "succeeded"
    assert receipt["bounded_stdout"] == "hello test"
    assert not receipt["output_truncated"]
    assert not receipt["timeout_hit"]
    assert validate_mcp_receipt(receipt) == []


def test_execute_tool_denied_unknown_tool():
    policy = _create_valid_policy()
    envelope = _create_valid_envelope(policy)
    envelope["tool_id"] = "unknown_tool"
    # We must recalculate digest because envelope changed? Wait, no, envelope tool_id doesn't affect policy digest.

    with pytest.raises(ValueError, match="Tool unknown_tool not permitted by policy"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_policy_digest_mismatch():
    policy = _create_valid_policy()
    envelope = _create_valid_envelope(policy)
    envelope["policy_ref"]["sha256"] = "a" * 64

    with pytest.raises(ValueError, match="Policy digest mismatch"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_missing_requires_human_promotion():
    policy = _create_valid_policy()
    envelope = _create_valid_envelope(policy)
    envelope["requires_human_promotion_for_execution"] = False

    with pytest.raises(ValueError, match="requires_human_promotion_for_execution=True"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_mutation_without_approval():
    policy = _create_valid_policy()
    policy["mutation_allowed"] = True
    envelope = _create_valid_envelope(policy)
    envelope["risk_classification"] = "mutation"

    with pytest.raises(ValueError, match="requires an approval_ref"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_mutation_denied_by_policy():
    policy = _create_valid_policy()
    policy["mutation_allowed"] = False
    envelope = _create_valid_envelope(policy)
    envelope["risk_classification"] = "mutation"
    envelope["approval_ref"] = {"role": "approval", "kind": "approval", "path": "path", "sha256": "0" * 64}

    with pytest.raises(ValueError, match="Mutation is not allowed by policy"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_external_network_denied_by_policy():
    policy = _create_valid_policy()
    policy["network_allowed"] = False
    envelope = _create_valid_envelope(policy)
    envelope["risk_classification"] = "external_network"
    envelope["approval_ref"] = {"role": "approval", "kind": "approval", "path": "path", "sha256": "0" * 64}

    with pytest.raises(ValueError, match="External network is not allowed by policy"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_credential_sensitive_denied_by_policy():
    policy = _create_valid_policy()
    policy["credential_access_allowed"] = False
    envelope = _create_valid_envelope(policy)
    envelope["risk_classification"] = "credential_sensitive"
    envelope["approval_ref"] = {"role": "approval", "kind": "approval", "path": "path", "sha256": "0" * 64}

    with pytest.raises(ValueError, match="Credential access is not allowed by policy"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_cost_bearing_denied_by_policy():
    policy = _create_valid_policy()
    policy["cost_allowed"] = False
    envelope = _create_valid_envelope(policy)
    envelope["risk_classification"] = "cost_bearing"
    envelope["approval_ref"] = {"role": "approval", "kind": "approval", "path": "path", "sha256": "0" * 64}

    with pytest.raises(ValueError, match="Cost-bearing operations are not allowed by policy"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_low_risk_path_invariants_envelope_mismatch():
    policy = _create_valid_policy()
    envelope = _create_valid_envelope(policy)
    envelope["mutates_target_repo"] = True

    with pytest.raises(ValueError, match="Invalid envelope:.*mutates_target_repo must be false or NOT_AUTHORIZED"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_low_risk_path_invariants_policy_mismatch():
    policy = _create_valid_policy()
    policy["mutation_allowed"] = True
    envelope = _create_valid_envelope(policy)

    with pytest.raises(ValueError, match="Low-risk policy must have mutation_allowed=False"):
        execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))


def test_output_truncation():
    policy = _create_valid_policy()
    envelope = _create_valid_envelope(policy)
    envelope["output_cap"] = 5

    receipt = execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))
    assert receipt["status"] == "succeeded"
    assert receipt["bounded_stdout"] == "hello"
    assert receipt["output_truncated"] is True
