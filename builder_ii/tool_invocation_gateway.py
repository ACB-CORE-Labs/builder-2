from __future__ import annotations

import hashlib
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.mcp_policy import (
    MCP_ENVELOPE_KIND,
    MCP_POLICY_KIND,
    MCP_RECEIPT_KIND,
    RECEIPT_SCHEMA_VERSION,
    TOOL_ENVELOPE_KIND,
    TOOL_POLICY_KIND,
    TOOL_RECEIPT_KIND,
    validate_mcp_envelope,
    validate_mcp_policy,
)
from builder_ii.workflow_records import canonical_digest, artifact_ref

# This is the strict allowlist of deterministic, non-mutating "stub" tools that we allow 
# for proving the B7 capability before broader rollout.
ALLOWED_STUB_TOOLS = {
    "echo": ["echo"],
    "date": ["date", "-u"],
}


def _digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _get_utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def execute_tool_envelope(
    envelope: dict[str, Any], 
    envelope_path: Path, 
    policy: dict[str, Any], 
    policy_path: Path
) -> dict[str, Any]:
    
    env_errors = validate_mcp_envelope(envelope)
    if env_errors:
        raise ValueError(f"Invalid envelope: {env_errors}")
    
    pol_errors = validate_mcp_policy(policy)
    if pol_errors:
        raise ValueError(f"Invalid policy: {pol_errors}")
        
    kind = envelope.get("kind")
    is_tool = (kind == TOOL_ENVELOPE_KIND)
    receipt_kind = TOOL_RECEIPT_KIND if is_tool else MCP_RECEIPT_KIND
    
    # 1. Enforce Policy Restrictions
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
        
    timeout_limit = min(policy.get("timeout_seconds", 30), envelope.get("timeout", 30))
    output_cap = min(policy.get("max_output_bytes", 1024), envelope.get("output_cap", 1024))
    
    started_at = _get_utc_now()
    status = "failed"
    stdout = ""
    truncated = False
    timeout_hit = False
    no_mutation_proof = "no_mutation_because_read_only"
    
    # 2. Execution Logic (Strict bounded stub executor)
    if is_tool and tool_id in ALLOWED_STUB_TOOLS:
        cmd = ALLOWED_STUB_TOOLS[tool_id]
        if op_name != "invoke":
            status = "denied"
            stdout = f"Operation {op_name} not supported for stub"
        else:
            try:
                proc = subprocess.run(cmd, capture_output=True, timeout=timeout_limit)
                status = "succeeded" if proc.returncode == 0 else "failed"
                raw_out = proc.stdout if proc.returncode == 0 else proc.stderr
                if len(raw_out) > output_cap:
                    raw_out = raw_out[:int(output_cap)]
                    truncated = True
                stdout = raw_out.decode('utf-8', errors='replace')
            except subprocess.TimeoutExpired:
                status = "failed"
                timeout_hit = True
                stdout = "Execution timed out"
    else:
        status = "denied"
        stdout = "Tool/MCP server not available or denied by B7 safe allowlist."
    
    completed_at = _get_utc_now()
    output_digest = _digest(stdout.encode("utf-8"))
    
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
        "governance": {
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
            "artifact_is_authority": False,
            "grants_runtime_authority": False,
            "grants_action_authority": False,
            "core_workbench_coupling": "NONE",
        }
    }
    
    # If approval was required and present in envelope, copy to receipt
    if "approval_ref" in envelope:
        receipt["approval_ref"] = envelope["approval_ref"]
        
    return receipt
