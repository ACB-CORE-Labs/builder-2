from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.model_client_registry import (
    KNOWN_CLIENT_IDS,
    KNOWN_MODEL_IDS,
    KNOWN_PROVIDER_IDS,
    validate_model_client_registry,
)
from builder_ii.model_routing_policy import (
    validate_model_execution_policy,
)
from builder_ii.direct_chat import run_direct_chat, DirectChatResult

MODEL_CALL_ENVELOPE_KIND = "builder_ii.model_call_envelope"
MODEL_CALL_ENVELOPE_SCHEMA_VERSION = 1

MODEL_CALL_RECEIPT_KIND = "builder_ii.model_call_receipt"
MODEL_CALL_RECEIPT_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Secret scanning regexes
SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_]{32,}", re.IGNORECASE),
    re.compile(r"gsk_[a-zA-Z0-9_]{32,}", re.IGNORECASE),
    re.compile(r"AIza[a-zA-Z0-9_\-]{35}", re.IGNORECASE),
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.\~]{10,}", re.IGNORECASE),
    re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
    re.compile(r"(?:api_key|apikey|secret|token)\s*[:=]\s*[\"'][a-zA-Z0-9_\-]{8,}[\"']", re.IGNORECASE)
]

def scan_for_secrets(text: str) -> list[str]:
    errors: list[str] = []
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            errors.append(f"Potential secret/credential pattern detected: {pattern.pattern}")
    return errors

def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _default_authority_boundary(
    capability_state: str,
    *,
    performs_network_calls: bool = False,
) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "executes_model": True,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "constructs_subagents": False,
        "invokes_mcp": False,
        "performs_network_calls": performs_network_calls,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
    }

def _default_governance(
    capability_state: str,
    *,
    network_calls_enabled: bool = False,
) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runtime_execution": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime_start": "DISABLED",
        "agent_construction": "DISABLED",
        "subagent_construction": "DISABLED",
        "model_execution": "ENABLED_UNDER_ENVELOPE",
        "tool_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "network_calls": "ENABLED_UNDER_ENVELOPE" if network_calls_enabled else "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "mcp_tool_calls": "DISABLED",
        "verification_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
        "core_workbench_coupling": "NONE",
    }

def validate_model_call_envelope(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["model call envelope must be a JSON object"]

    if data.get("kind") != MODEL_CALL_ENVELOPE_KIND:
        errors.append(f"kind must be {MODEL_CALL_ENVELOPE_KIND}")
    if data.get("schema_version") != MODEL_CALL_ENVELOPE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_CALL_ENVELOPE_SCHEMA_VERSION}")

    for str_field in ("session_id", "model_id", "client_id", "provider_id", "prompt_digest"):
        val = data.get(str_field)
        if not isinstance(val, str) or not val:
            errors.append(f"{str_field} must be a non-empty string")

    pd = data.get("prompt_digest", "")
    if pd and not _SHA256_RE.match(pd):
        errors.append("prompt_digest must be a valid SHA-256 digest")

    if not isinstance(data.get("max_tokens"), int) or data["max_tokens"] <= 0:
        errors.append("max_tokens must be a positive integer")

    temp = data.get("temperature")
    if temp is not None and not isinstance(temp, (int, float)):
        errors.append("temperature must be a number or null")

    for f_false in (
        "executes_tools",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "constructs_subagents",
        "invokes_mcp",
        "mutates_target_repo",
        "mutates_memory",
        "grants_authority",
        "artifact_is_authority",
    ):
        if data.get(f_false) is not False:
            errors.append(f"{f_false} must be false")

    if data.get("executes_model") is not True:
        errors.append("executes_model must be true")

    if not isinstance(data.get("performs_network_calls"), bool):
        errors.append("performs_network_calls must be a boolean")

    if data.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    boundary = data.get("authority_boundary")
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
    else:
        if boundary.get("capability_state") != "model_call":
            errors.append("authority_boundary.capability_state must be model_call")
        if boundary.get("executes_model") is not True:
            errors.append("authority_boundary.executes_model must be true")
        for f_false in (
            "executes_tools",
            "executes_shell",
            "invokes_goose",
            "constructs_deepagents",
            "constructs_subagents",
            "invokes_mcp",
            "mutates_target_repo",
            "mutates_memory",
            "grants_authority",
            "artifact_is_authority",
        ):
            if boundary.get(f_false) is not False:
                errors.append(f"authority_boundary.{f_false} must be false")
        # performs_network_calls in authority_boundary must match top-level
        top_network = data.get("performs_network_calls")
        if isinstance(top_network, bool) and boundary.get("performs_network_calls") != top_network:
            errors.append(
                "authority_boundary.performs_network_calls must match top-level performs_network_calls"
            )

    gov = data.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        if gov.get("model_execution") != "ENABLED_UNDER_ENVELOPE":
            errors.append("governance.model_execution must be ENABLED_UNDER_ENVELOPE")
        # network_calls must match whether network is involved
        top_network = data.get("performs_network_calls")
        expected_network_gov = "ENABLED_UNDER_ENVELOPE" if top_network else "DISABLED"
        if gov.get("network_calls") != expected_network_gov:
            errors.append(f"governance.network_calls must be {expected_network_gov} (based on performs_network_calls={top_network})")
        for key in (
            "runtime_execution",
            "goose_runtime_start",
            "deepagents_runtime_start",
            "agent_construction",
            "subagent_construction",
            "tool_execution",
            "shell_execution",
            "target_repo_writes",
            "memory_mutation",
            "mcp_tool_calls",
            "verification_execution",
        ):
            if gov.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")

    return errors

def validate_model_call_receipt(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["model call receipt must be a JSON object"]

    if data.get("kind") != MODEL_CALL_RECEIPT_KIND:
        errors.append(f"kind must be {MODEL_CALL_RECEIPT_KIND}")
    if data.get("schema_version") != MODEL_CALL_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MODEL_CALL_RECEIPT_SCHEMA_VERSION}")

    envelope_ref = data.get("envelope_ref")
    if not isinstance(envelope_ref, dict):
        errors.append("envelope_ref must be an object")
    else:
        if envelope_ref.get("kind") != MODEL_CALL_ENVELOPE_KIND:
            errors.append(f"envelope_ref.kind must be {MODEL_CALL_ENVELOPE_KIND}")
        if not isinstance(envelope_ref.get("sha256"), str) or not _SHA256_RE.match(envelope_ref["sha256"]):
            errors.append("envelope_ref.sha256 must be a valid SHA-256 digest")
        if envelope_ref.get("role") != "model_call_envelope":
            errors.append("envelope_ref.role must be model_call_envelope")

    if not isinstance(data.get("response_text"), str):
        errors.append("response_text must be a string")

    cost = data.get("cost_report")
    if not isinstance(cost, dict):
        errors.append("cost_report must be an object")
    else:
        for f in ("input_tokens", "output_tokens", "total_tokens"):
            if not isinstance(cost.get(f), int) or cost[f] < 0:
                errors.append(f"cost_report.{f} must be a non-negative integer")

    if data.get("replay_declaration") != "non-deterministic-llm-completion":
        errors.append("replay_declaration must be non-deterministic-llm-completion")

    for f_false in (
        "executes_tools",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "constructs_subagents",
        "invokes_mcp",
        "mutates_target_repo",
        "mutates_memory",
        "grants_authority",
        "artifact_is_authority",
    ):
        if data.get(f_false) is not False:
            errors.append(f"{f_false} must be false")

    if data.get("executes_model") is not True:
        errors.append("executes_model must be true")

    if data.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    return errors

def validate_model_call_receipt_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"file not found or not a file: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_model_call_receipt(data)

class ModelExecutionGateway:
    def __init__(self, settings: Settings, registry: dict[str, Any], execution_policy: dict[str, Any]):
        reg_errs = validate_model_client_registry(registry)
        if reg_errs:
            raise ValueError(f"invalid model client registry: {'; '.join(reg_errs)}")
        pol_errs = validate_model_execution_policy(execution_policy)
        if pol_errs:
            raise ValueError(f"invalid model execution policy: {'; '.join(pol_errs)}")
        self.settings = settings
        self.registry = registry
        self.execution_policy = execution_policy

    def run_model_call(
        self,
        *,
        model_id: str,
        prompt: str,
        system_prompt: str = None,
        max_tokens: int = 256,
        temperature: float | None = None,
        envelope_path: Path,
        receipt_path: Path,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        # Fail closed on empty prompt or invalid outputs
        if not prompt.strip():
            raise ValueError("Prompt must not be empty")

        # Secret scanning
        secret_errors = scan_for_secrets(prompt)
        if secret_errors:
            raise ValueError(f"Credential/secret leak detected in prompt: {'; '.join(secret_errors)}")

        # Retrieve client record
        client_record = None
        for client in self.registry.get("clients", []):
            if client.get("model_id") == model_id:
                client_record = client
                break

        if not client_record:
            raise ValueError(f"Model ID '{model_id}' not found in registry")

        if not client_record.get("enabled"):
            raise ValueError(f"Model '{model_id}' is disabled in client registry")

        if model_id not in self.execution_policy.get("allowed_models", []):
            raise ValueError(f"Model ID '{model_id}' is not authorized by the execution policy")

        if max_tokens > client_record.get("max_output_tokens", 0):
            raise ValueError(f"Requested max_tokens {max_tokens} exceeds client registry limit {client_record.get('max_output_tokens')}")

        if max_tokens > self.execution_policy.get("max_tokens", 0):
            raise ValueError(f"Requested max_tokens {max_tokens} exceeds execution policy limit {self.execution_policy.get('max_tokens')}")

        # Check policy risk classification constraints
        risk_level = client_record.get("risk_classification")
        if risk_level == "cloud_external":
            # Check policy / settings for permissions
            if not self.settings.allow_cloud_models:
                raise ValueError("Cloud/external model calls are disabled by environment configuration")
        elif risk_level == "local_offline":
            raise ValueError("local_offline risk classification cannot perform network calls to execution backends")

        # Create envelope
        session_id = f"session-{_digest({'prompt': prompt})[:12]}"
        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        performs_network = risk_level in ("local_network", "cloud_external")

        envelope = {
            "kind": MODEL_CALL_ENVELOPE_KIND,
            "schema_version": MODEL_CALL_ENVELOPE_SCHEMA_VERSION,
            "session_id": session_id,
            "model_id": model_id,
            "client_id": client_record.get("client_id"),
            "provider_id": client_record.get("provider_id"),
            "prompt_digest": prompt_digest,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "executes_model": True,
            "executes_tools": False,
            "executes_shell": False,
            "invokes_goose": False,
            "constructs_deepagents": False,
            "constructs_subagents": False,
            "invokes_mcp": False,
            "performs_network_calls": performs_network,
            "mutates_target_repo": False,
            "mutates_memory": False,
            "grants_authority": False,
            "artifact_is_authority": False,
            "requires_human_promotion_for_execution": True,
            "authority_boundary": _default_authority_boundary(
                "model_call", performs_network_calls=performs_network
            ),
            "governance": _default_governance(
                "model_call", network_calls_enabled=performs_network
            ),
        }
        envelope["digest"] = _digest(envelope)

        env_errors = validate_model_call_envelope(envelope)
        if env_errors:
            raise ValueError(f"Generated envelope failed validation: {'; '.join(env_errors)}")

        envelope_path.parent.mkdir(parents=True, exist_ok=True)
        envelope_path.write_text(json_lib.dumps(envelope, indent=2, sort_keys=True), encoding="utf-8")

        # Execute call
        # If stub provider, return stub response
        if client_record.get("provider_id") in ("openai_stub_provider", "anthropic_stub_provider"):
            result_text = f"Mocked stub response for model '{model_id}' to: {prompt[:30]}..."
            input_tokens = len(prompt.split())
            output_tokens = len(result_text.split())
        else:
            # Run local offline/network call
            chat_res: DirectChatResult = run_direct_chat(
                self.settings,
                prompt=prompt,
                system_prompt=system_prompt if system_prompt else "Answer helpfully.",
                max_tokens=max_tokens,
                temperature=temperature,
                override_model_id=model_id,
            )
            if not chat_res.ok:
                raise RuntimeError(f"Model execution failed: {chat_res.error}")
            result_text = chat_res.content
            input_tokens = len(prompt.split()) + 10 # approximate estimate
            output_tokens = len(result_text.split())

        # Create receipt
        envelope_ref = {
            "kind": MODEL_CALL_ENVELOPE_KIND,
            "path": str(envelope_path),
            "sha256": envelope["digest"],
            "role": "model_call_envelope",
            "name": f"Model call envelope for {model_id}",
            "required": True
        }

        receipt = {
            "kind": MODEL_CALL_RECEIPT_KIND,
            "schema_version": MODEL_CALL_RECEIPT_SCHEMA_VERSION,
            "envelope_ref": envelope_ref,
            "response_text": result_text,
            "cost_report": {
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_tokens": input_tokens + output_tokens,
            },
            "replay_declaration": "non-deterministic-llm-completion",
            "executes_model": True,
            "executes_tools": False,
            "executes_shell": False,
            "invokes_goose": False,
            "constructs_deepagents": False,
            "constructs_subagents": False,
            "invokes_mcp": False,
            "mutates_target_repo": False,
            "mutates_memory": False,
            "grants_authority": False,
            "artifact_is_authority": False,
            "requires_human_promotion_for_execution": True,
            "authority_boundary": _default_authority_boundary(
                "model_call", performs_network_calls=performs_network
            ),
            "governance": _default_governance(
                "model_call", network_calls_enabled=performs_network
            ),
        }
        receipt["digest"] = _digest(receipt)

        rec_errors = validate_model_call_receipt(receipt)
        if rec_errors:
            raise ValueError(f"Generated receipt failed validation: {'; '.join(rec_errors)}")

        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json_lib.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")

        return envelope, receipt
