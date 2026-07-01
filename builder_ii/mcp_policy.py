from __future__ import annotations

import json
from pathlib import Path
from typing import Any

TOOL_INVENTORY_KIND = "builder_ii.tool_inventory"
MCP_INVENTORY_KIND = "builder_ii.mcp_inventory"
TOOL_POLICY_KIND = "builder_ii.tool_invocation_policy"
MCP_POLICY_KIND = "builder_ii.mcp_tool_policy"
TOOL_ENVELOPE_KIND = "builder_ii.tool_call_envelope"
MCP_ENVELOPE_KIND = "builder_ii.mcp_call_envelope"
TOOL_RECEIPT_KIND = "builder_ii.tool_call_receipt"
MCP_RECEIPT_KIND = "builder_ii.mcp_call_receipt"

POLICY_SCHEMA_VERSION = 1
ENVELOPE_SCHEMA_VERSION = 1
RECEIPT_SCHEMA_VERSION = 1
INVENTORY_SCHEMA_VERSION = 1


def _validate_ref(value: Any, *, field: str, required: bool = True) -> list[str]:
    if value is None:
        return [f"{field} is required"] if required else []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    errors: list[str] = []
    for key in ("role", "kind", "path", "sha256"):
        if not isinstance(value.get(key), str) or not value[key]:
            errors.append(f"{field}.{key} must be a non-empty string")
    if isinstance(value.get("sha256"), str) and len(value["sha256"]) != 64:
        errors.append(f"{field}.sha256 must be a SHA-256 hex digest")
    if not isinstance(value.get("required", True), bool):
        errors.append(f"{field}.required must be a boolean")
    return errors


def _validate_governance(record: dict[str, Any], prefix: str = "governance.") -> list[str]:
    errors: list[str] = []
    governance = record.get("governance")
    if not isinstance(governance, dict):
        return [f"{prefix} must be an object"]
    
    if governance.get("artifact_is_authority") is not False:
        errors.append(f"{prefix}artifact_is_authority must be false")
    
    return errors


def validate_mcp_policy(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["policy must be a JSON object"]
    
    kind = record.get("kind")
    if kind not in (TOOL_POLICY_KIND, MCP_POLICY_KIND):
        errors.append(f"kind must be {TOOL_POLICY_KIND} or {MCP_POLICY_KIND}")
    
    if record.get("schema_version") != POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {POLICY_SCHEMA_VERSION}")
        
    if record.get("denied_by_default") is not True:
        errors.append("denied_by_default must be true")
        
    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
        
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")

    for field in ("allowed_operations", "allowed_risk_classes"):
        if not isinstance(record.get(field), list):
            errors.append(f"{field} must be a list")
            
    if kind == TOOL_POLICY_KIND and not isinstance(record.get("allowed_tools"), list):
        errors.append("allowed_tools must be a list")
    elif kind == MCP_POLICY_KIND and not isinstance(record.get("allowed_servers"), list):
        errors.append("allowed_servers must be a list")

    for field in ("max_input_bytes", "max_output_bytes", "timeout_seconds"):
        if not isinstance(record.get(field), (int, float)):
            errors.append(f"{field} must be a number")
            
    for field in (
        "network_allowed", 
        "mutation_allowed", 
        "credential_access_allowed", 
        "cost_allowed",
        "requires_approval_for_mutation",
        "requires_approval_for_external_network",
        "requires_approval_for_credentials"
    ):
        if not isinstance(record.get(field), bool):
            errors.append(f"{field} must be a boolean")

    errors.extend(_validate_governance(record))
    return errors


def validate_mcp_envelope(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["envelope must be a JSON object"]
        
    kind = record.get("kind")
    if kind not in (TOOL_ENVELOPE_KIND, MCP_ENVELOPE_KIND):
        errors.append(f"kind must be {TOOL_ENVELOPE_KIND} or {MCP_ENVELOPE_KIND}")
        
    if record.get("schema_version") != ENVELOPE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ENVELOPE_SCHEMA_VERSION}")

    if not isinstance(record.get("operation_name"), str):
        errors.append("operation_name must be a string")
        
    if kind == TOOL_ENVELOPE_KIND:
        if not isinstance(record.get("tool_id"), str):
            errors.append("tool_id must be a string")
        if record.get("executes_tool") is not True:
            errors.append("executes_tool must be true")
    else:
        if not isinstance(record.get("server_id"), str):
            errors.append("server_id must be a string")
        if record.get("invokes_mcp") is not True:
            errors.append("invokes_mcp must be true")

    if not isinstance(record.get("input_digest"), str) or len(record.get("input_digest", "")) != 64:
        errors.append("input_digest must be a 64-character hex string")

    errors.extend(_validate_ref(record.get("policy_ref"), field="policy_ref"))
    errors.extend(_validate_ref(record.get("approval_ref"), field="approval_ref", required=False))

    for field in ("effect_classification", "risk_classification", "rollback_requirement"):
        if not isinstance(record.get(field), str):
            errors.append(f"{field} must be a string")

    for field in ("timeout", "output_cap"):
        if not isinstance(record.get(field), (int, float)):
            errors.append(f"{field} must be a number")

    for field in ("credential_redaction_declaration", "requires_human_promotion_for_execution"):
        if not isinstance(record.get(field), bool):
            errors.append(f"{field} must be a boolean")

    if record.get("executes_shell") is not False:
        errors.append("executes_shell must be false")
        
    if record.get("mutates_target_repo") is not False:
        errors.append("mutates_target_repo must be false")
        
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
        
    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")

    return errors


def validate_mcp_receipt(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["receipt must be a JSON object"]
        
    kind = record.get("kind")
    if kind not in (TOOL_RECEIPT_KIND, MCP_RECEIPT_KIND):
        errors.append(f"kind must be {TOOL_RECEIPT_KIND} or {MCP_RECEIPT_KIND}")
        
    if record.get("schema_version") != RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RECEIPT_SCHEMA_VERSION}")

    errors.extend(_validate_ref(record.get("envelope_ref"), field="envelope_ref"))
    errors.extend(_validate_ref(record.get("policy_ref"), field="policy_ref"))
    errors.extend(_validate_ref(record.get("approval_ref"), field="approval_ref", required=False))

    for field in ("started_at", "completed_at", "status"):
        if not isinstance(record.get(field), str):
            errors.append(f"{field} must be a string")
            
    if record.get("status") not in ("succeeded", "failed", "denied"):
        errors.append("status must be succeeded, failed, or denied")

    if "bounded_stdout" not in record and "output_artifact_ref" not in record:
        errors.append("must provide either bounded_stdout or output_artifact_ref")
        
    if not isinstance(record.get("output_digest"), str) or len(record.get("output_digest", "")) != 64:
        errors.append("output_digest must be a 64-character hex string")

    for field in ("output_truncated", "timeout_hit", "credential_redaction_report"):
        if not isinstance(record.get(field), bool):
            errors.append(f"{field} must be a boolean")

    for field in ("effect_classification", "rollback_classification", "replay_declaration"):
        if not isinstance(record.get(field), str):
            errors.append(f"{field} must be a string")

    if not isinstance(record.get("no_mutation_proof"), str):
        errors.append("no_mutation_proof must be a string")

    errors.extend(_validate_governance(record))
    return errors


def validate_mcp_inventory(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["inventory must be a JSON object"]
        
    kind = record.get("kind")
    if kind not in (TOOL_INVENTORY_KIND, MCP_INVENTORY_KIND):
        errors.append(f"kind must be {TOOL_INVENTORY_KIND} or {MCP_INVENTORY_KIND}")
        
    if record.get("schema_version") != INVENTORY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {INVENTORY_SCHEMA_VERSION}")

    if not isinstance(record.get("tools"), list):
        errors.append("tools must be a list")

    errors.extend(_validate_governance(record))
    return errors
