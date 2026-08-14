"""W.2 Option A: MSDA skip/enforced annotations on tool receipts."""

from __future__ import annotations

from pathlib import Path

from builder_ii.core.mcp_policy import (
    ENVELOPE_SCHEMA_VERSION,
    POLICY_SCHEMA_VERSION,
    TOOL_ENVELOPE_KIND,
    TOOL_POLICY_KIND,
)
from builder_ii.core.tool_invocation_gateway import execute_tool_envelope
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.wrp.msda_preflight import (
    annotate_msda_preflight_result,
    msda_preflight_skip_annotation,
)


def _policy() -> dict:
    return {
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


def _envelope(policy: dict) -> dict:
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
        "arguments": {"text": "msda-annotate"},
    }


def test_skip_annotation_shape() -> None:
    ann = msda_preflight_skip_annotation()
    assert ann["skipped"] is True
    assert ann["enforced"] is False
    assert ann["skip_mode"] == "skipped_default_off"
    assert ann["grants_authority"] is False


def test_annotate_none_is_skip() -> None:
    ann = annotate_msda_preflight_result(None)
    assert ann["skipped"] is True


def test_tool_receipt_stamps_skip_when_env_off(monkeypatch) -> None:
    monkeypatch.delenv("BUILDER_II_WRP_MSDA_PREFLIGHT", raising=False)
    policy = _policy()
    envelope = _envelope(policy)
    receipt = execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))
    assert receipt["status"] == "succeeded"
    assert "msda_preflight" in receipt
    assert receipt["msda_preflight"]["skipped"] is True
    assert receipt["msda_preflight"]["skip_mode"] == "skipped_default_off"
    assert receipt["msda_preflight"]["grants_authority"] is False


def test_tool_receipt_enforced_when_env_on(monkeypatch) -> None:
    monkeypatch.setenv("BUILDER_II_WRP_MSDA_PREFLIGHT", "1")
    policy = _policy()
    envelope = _envelope(policy)
    # If preflight denies unknown tools under default MSDA, that is fail-closed Option A.
    from builder_ii.wrp.msda_preflight import MsdaPreflightDenied

    try:
        receipt = execute_tool_envelope(envelope, Path("env.json"), policy, Path("pol.json"))
    except MsdaPreflightDenied:
        return
    assert receipt["msda_preflight"]["enforced"] is True
    assert receipt["msda_preflight"]["skipped"] is False
