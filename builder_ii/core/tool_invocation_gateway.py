from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.core.mcp_policy import (
    MCP_RECEIPT_KIND,
    RECEIPT_SCHEMA_VERSION,
    TOOL_ENVELOPE_KIND,
    TOOL_RECEIPT_KIND,
    validate_mcp_envelope,
    validate_mcp_policy,
)
from builder_ii.governance.ledger.workflow_records import artifact_ref, canonical_digest

# This is the strict allowlist of deterministic, non-mutating "stub" tools that we allow
# for proving the B7 capability before broader rollout.
ALLOWED_STUB_TOOLS = {
    "builtin.echo",
    "builtin.utc_static",
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def execute_tool_envelope(
    envelope: dict[str, Any], envelope_path: Path, policy: dict[str, Any], policy_path: Path
) -> dict[str, Any]:

    env_errors = validate_mcp_envelope(envelope)
    if env_errors:
        raise ValueError(f"Invalid envelope: {env_errors}")

    pol_errors = validate_mcp_policy(policy)
    if pol_errors:
        raise ValueError(f"Invalid policy: {pol_errors}")

    kind = envelope.get("kind")
    is_tool = kind == TOOL_ENVELOPE_KIND
    receipt_kind = TOOL_RECEIPT_KIND if is_tool else MCP_RECEIPT_KIND

    # Optional WRP MSDA preflight (off by default; BUILDER_II_WRP_MSDA_PREFLIGHT=1).
    # Option A: annotate skip/enforced on receipt — never soft-enable global default-on.
    from builder_ii.wrp.msda_preflight import annotate_msda_preflight_result, assert_msda_preflight

    tool_name = str(envelope.get("tool_id") or envelope.get("operation_name") or "unknown_tool")
    data_domain = str(envelope.get("data_domain") or "local_workspace")
    risk = str(envelope.get("risk_classification") or "local_offline")
    # Map gateway risk labels into MSDA risk axis when needed.
    msda_risk = risk if risk in {"local_offline", "local_network", "cloud_external"} else "local_network"
    _msda_decision = assert_msda_preflight(tool=tool_name, data_domain=data_domain, risk=msda_risk)
    _msda_preflight_annotation = annotate_msda_preflight_result(_msda_decision)

    # 1. Enforce Policy Restrictions and Drift Checks
    policy_digest = canonical_digest(policy)
    expected_digest = envelope.get("policy_ref", {}).get("sha256")
    if policy_digest != expected_digest:
        raise ValueError(
            f"Policy digest mismatch: active policy is {policy_digest}, envelope expected {expected_digest}"
        )

    if envelope.get("requires_human_promotion_for_execution") is not True:
        raise ValueError("Envelope must have requires_human_promotion_for_execution=True for execution")

    if policy.get("denied_by_default") is not True:
        raise ValueError("Policy must be deny-by-default")

    op_name = envelope.get("operation_name", "")
    if op_name not in policy.get("allowed_operations", []):
        raise ValueError(f"Operation {op_name} not permitted by policy")

    if is_tool:
        tool_id = envelope.get("tool_id")
        if tool_id not in policy.get("allowed_tools", []):
            raise ValueError(f"Tool {tool_id} not permitted by policy")
    else:
        server_id = envelope.get("server_id")
        if server_id not in policy.get("allowed_servers", []):
            raise ValueError(f"Server {server_id} not permitted by policy")

    risk_class = envelope.get("risk_classification")
    if risk_class not in policy.get("allowed_risk_classes", []):
        raise ValueError(f"Risk class {risk_class} not permitted by policy")

    # Enforce risk and approval requirements
    if risk_class in ("mutation", "external_network", "credential_sensitive", "cost_bearing"):
        if "approval_ref" not in envelope or not envelope["approval_ref"]:
            raise ValueError(f"Risk classification '{risk_class}' requires an approval_ref")

        # Check corresponding policy allowance
        if risk_class == "mutation" and not policy.get("mutation_allowed"):
            raise ValueError("Mutation is not allowed by policy")
        if risk_class == "external_network" and not policy.get("network_allowed"):
            raise ValueError("External network is not allowed by policy")
        if risk_class == "credential_sensitive" and not policy.get("credential_access_allowed"):
            raise ValueError("Credential access is not allowed by policy")
        if risk_class == "cost_bearing" and not policy.get("cost_allowed"):
            raise ValueError("Cost-bearing operations are not allowed by policy")

    # Enforce low-risk read-only path invariants
    if risk_class in ("low", "low_risk"):
        if envelope.get("mutates_target_repo") is not False:
            raise ValueError("Low-risk path requires mutates_target_repo to be False")
        if envelope.get("grants_authority") is not False:
            raise ValueError("Low-risk path requires grants_authority to be False")
        if envelope.get("artifact_is_authority") is not False:
            raise ValueError("Low-risk path requires artifact_is_authority to be False")
        if envelope.get("executes_shell") is not False:
            raise ValueError("Low-risk path requires executes_shell to be False")

        if policy.get("mutation_allowed") is not False:
            raise ValueError("Low-risk policy must have mutation_allowed=False")
        if policy.get("credential_access_allowed") is not False:
            raise ValueError("Low-risk policy must have credential_access_allowed=False")
        if policy.get("cost_allowed") is not False:
            raise ValueError("Low-risk policy must have cost_allowed=False")
        if policy.get("network_allowed") is not False:
            raise ValueError("Low-risk policy must have network_allowed=False")

    min(policy.get("timeout_seconds", 30), envelope.get("timeout", 30))
    output_cap = min(policy.get("max_output_bytes", 1024), envelope.get("output_cap", 1024))

    started_at = _get_utc_now()
    status = "failed"
    stdout = ""
    truncated = False
    timeout_hit = False
    no_mutation_proof = "no_mutation_because_read_only"

    # 2. Execution Logic (Pure in-process deterministic stubs)
    if is_tool:
        tool_id = envelope.get("tool_id")
        if tool_id in ALLOWED_STUB_TOOLS:
            if op_name != "invoke":
                status = "denied"
                stdout = f"Operation {op_name} not supported for stub"
            else:
                status = "succeeded"
                if tool_id == "builtin.echo":
                    text = envelope.get("arguments", {}).get("text", "")
                    stdout = str(text)
                elif tool_id == "builtin.utc_static":
                    stdout = "2026-07-01T10:00:00Z"
        else:
            status = "denied"
            stdout = f"Tool '{tool_id}' not available or denied by B7 safe allowlist."
    else:
        server_id = envelope.get("server_id")
        tool_id = envelope.get("tool_id")
        if server_id == "builtin.mcp_server" and tool_id in ALLOWED_STUB_TOOLS:
            if op_name != "invoke":
                status = "denied"
                stdout = f"Operation {op_name} not supported for stub"
            else:
                status = "succeeded"
                if tool_id == "builtin.echo":
                    text = envelope.get("arguments", {}).get("text", "")
                    stdout = str(text)
                elif tool_id == "builtin.utc_static":
                    stdout = "2026-07-01T10:00:00Z"
        else:
            status = "denied"
            stdout = f"MCP server '{server_id}' or tool '{tool_id}' not available or denied by B7 safe allowlist."

    if status == "succeeded":
        raw_bytes = stdout.encode("utf-8")
        if len(raw_bytes) > output_cap:
            stdout = raw_bytes[: int(output_cap)].decode("utf-8", errors="replace")
            truncated = True

    completed_at = _get_utc_now()
    output_digest = _digest(stdout.encode("utf-8"))

    governance = {
        "capability_state": "receipt",
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime": "DISABLED",
        "mcp_execution": "DISABLED",
        "tool_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "core_workbench_coupling": "NONE",
    }

    if is_tool:
        if status == "succeeded":
            governance["tool_execution"] = "ENABLED UNDER ENVELOPE"
    else:
        # Since B7 is passive for live MCP calls, mcp_execution remains DISABLED
        governance["mcp_execution"] = "DISABLED"

    receipt = {
        "kind": receipt_kind,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "envelope_ref": artifact_ref(envelope, path=envelope_path, role="envelope", name=op_name),
        "policy_ref": artifact_ref(policy, path=policy_path, role="policy", name="active_policy"),
        "started_at": started_at,
        "completed_at": completed_at,
        "status": status,
        "bounded_stdout": stdout,
        "output_digest": output_digest,
        "output_truncated": truncated,
        "timeout_hit": timeout_hit,
        "effect_classification": envelope.get("effect_classification", "unknown"),
        "rollback_classification": "no_rollback_required_for_read_only",
        "no_mutation_proof": no_mutation_proof,
        "credential_redaction_report": True,
        "replay_declaration": "deterministic_execution_recorded",
        "msda_preflight": _msda_preflight_annotation,
        "governance": governance,
    }

    # If approval was required and present in envelope, copy to receipt
    if "approval_ref" in envelope:
        receipt["approval_ref"] = envelope["approval_ref"]

    return receipt
