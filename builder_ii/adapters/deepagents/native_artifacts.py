"""Governance-only contracts for optional native Deep Agents evidence.

This module deliberately has no Deep Agents, LangChain, or LangGraph imports so
artifact indexing and chain verification remain available in the lightweight
base installation.
"""

from __future__ import annotations

from typing import Any

from builder_ii.core.config_schema import digest_jsonable

NATIVE_CHECKPOINT_STORE_KIND = "builder_ii.deepagents_native_checkpoint_store"
NATIVE_EVIDENCE_KIND = "builder_ii.deepagents_native_evidence_bundle"
NATIVE_EVENT_KIND = "builder_ii.deepagents_native_event"
NATIVE_RUNTIME_SCHEMA_VERSION = 1

DEFAULT_ACTIVE_WORKERS = 2
MAX_ACTIVE_WORKERS = 4


def _digest(data: dict[str, Any], key: str) -> str:
    return digest_jsonable(data, digest_key=key)


def validate_native_evidence_bundle(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["native Deep Agents evidence must be a JSON object"]
    if data.get("kind") != NATIVE_EVIDENCE_KIND:
        errors.append(f"kind must be {NATIVE_EVIDENCE_KIND}")
    if data.get("schema_version") != NATIVE_RUNTIME_SCHEMA_VERSION:
        errors.append(f"schema_version must be {NATIVE_RUNTIME_SCHEMA_VERSION}")
    if data.get("official_factory") != "deepagents.create_deep_agent":
        errors.append("official_factory must be deepagents.create_deep_agent")
    if data.get("model_adapter") != "builder_ii.ModelExecutionGateway":
        errors.append("model_adapter must be builder_ii.ModelExecutionGateway")
    if data.get("single_model_instance") is not True:
        errors.append("single_model_instance must be true")
    if not isinstance(data.get("active_workers"), int) or not 1 <= data["active_workers"] <= MAX_ACTIVE_WORKERS:
        errors.append(f"active_workers must be between 1 and {MAX_ACTIVE_WORKERS}")
    obligations = data.get("obligations")
    if not isinstance(obligations, list) or len(obligations) < 2:
        errors.append("at least two obligations must be evidenced")
    delegated = data.get("delegated_subagents")
    if not isinstance(delegated, list) or len({item for item in delegated if isinstance(item, str)}) < 2:
        errors.append("at least two distinct bounded subagents must be delegated")
    chain = data.get("parent_child_chain")
    if not isinstance(chain, list) or not isinstance(obligations, list) or len(chain) != len(obligations):
        errors.append("parent_child_chain must cover every obligation")
    else:
        for index, child in enumerate(chain):
            if not isinstance(child, dict):
                errors.append(f"parent_child_chain[{index}] must be an object")
                continue
            parent_ref = child.get("parent_ref")
            if not isinstance(parent_ref, dict) or len(parent_ref) != 1:
                errors.append(f"parent_child_chain[{index}].parent_ref must identify one parent")
            else:
                parent_digest = next(iter(parent_ref.values()))
                if not isinstance(parent_digest, str) or len(parent_digest) != 64:
                    errors.append(f"parent_child_chain[{index}] parent digest must be SHA-256")
            if child.get("delegated") is not True:
                errors.append(f"parent_child_chain[{index}] must be delegated")
            if data.get("status") == "COMPLETED" and child.get("completed") is not True:
                errors.append(f"parent_child_chain[{index}] must be completed")
    if not isinstance(data.get("model_receipt_refs"), list) or not data["model_receipt_refs"]:
        errors.append("at least one governed model receipt is required")
    if not isinstance(data.get("tool_receipt_refs"), list) or not data["tool_receipt_refs"]:
        errors.append("at least one governed tool receipt is required")
    if not isinstance(data.get("event_refs"), list) or len(data["event_refs"]) != data.get("event_count"):
        errors.append("event_refs must cover the complete event chain")
    event_types = data.get("event_types", [])
    if data.get("status") == "COMPLETED":
        for required in ("hitl_interrupted", "hitl_resumed", "native_run_completed"):
            if required not in event_types:
                errors.append(f"completed evidence requires {required}")
        if not data.get("approved_checkpoint_digest"):
            errors.append("completed evidence requires approved_checkpoint_digest")
        if not isinstance(data.get("completed_task_count"), int) or data["completed_task_count"] < 2:
            errors.append("completed evidence requires at least two completed task calls")
    for flag in ("target_repo_mutation", "shell_execution", "git_mutation", "direct_provider_bypass"):
        if data.get(flag) is not False:
            errors.append(f"{flag} must be false")
    for flag in ("artifact_is_authority", "grants_authority"):
        if data.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if data.get("evidence_digest") != _digest(data, "evidence_digest"):
        errors.append("evidence_digest mismatch")
    return errors


def validate_native_checkpoint_store(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["native Deep Agents checkpoint store must be a JSON object"]
    if data.get("kind") != NATIVE_CHECKPOINT_STORE_KIND:
        errors.append(f"kind must be {NATIVE_CHECKPOINT_STORE_KIND}")
    if data.get("schema_version") != NATIVE_RUNTIME_SCHEMA_VERSION:
        errors.append(f"schema_version must be {NATIVE_RUNTIME_SCHEMA_VERSION}")
    for field in ("storage", "writes", "blobs"):
        if not isinstance(data.get(field), list):
            errors.append(f"{field} must be a list")
    for flag in ("artifact_is_authority", "grants_authority"):
        if data.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if data.get("checkpoint_store_digest") != _digest(data, "checkpoint_store_digest"):
        errors.append("checkpoint_store_digest mismatch")
    return errors


def validate_native_event(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["native Deep Agents event must be a JSON object"]
    if data.get("kind") != NATIVE_EVENT_KIND:
        errors.append(f"kind must be {NATIVE_EVENT_KIND}")
    if data.get("schema_version") != NATIVE_RUNTIME_SCHEMA_VERSION:
        errors.append(f"schema_version must be {NATIVE_RUNTIME_SCHEMA_VERSION}")
    if not isinstance(data.get("sequence"), int) or data["sequence"] <= 0:
        errors.append("sequence must be a positive integer")
    if not isinstance(data.get("event_type"), str) or not data["event_type"]:
        errors.append("event_type must be a non-empty string")
    if not isinstance(data.get("previous_event_digest"), str):
        errors.append("previous_event_digest must be a string")
    if not isinstance(data.get("payload"), dict):
        errors.append("payload must be an object")
    for flag in ("artifact_is_authority", "grants_authority"):
        if data.get(flag) is not False:
            errors.append(f"{flag} must be false")
    if data.get("event_digest") != _digest(data, "event_digest"):
        errors.append("event_digest mismatch")
    return errors
