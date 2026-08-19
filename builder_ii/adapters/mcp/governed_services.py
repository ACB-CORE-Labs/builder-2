"""Thin MCP adapters for existing governed Builder-II services."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from builder_ii.adapters.mcp.governed_call import build_read_only_policy
from builder_ii.core.config import load_settings
from builder_ii.core.governed_prepare_package import (
    create_governed_prepare_package,
    validate_governed_prepare_package_directory,
)
from builder_ii.core.repo_map import create_repo_map
from builder_ii.core.repo_search import search_repo_map
from builder_ii.governance.authority.readonly_authority import (
    create_read_policy,
    execute_content_read,
    validate_content_read_receipt,
)
from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    create_event_record,
    load_event_records,
    replay_events,
    validate_event_record,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest

MAX_MAP_FILES = 500
MAX_MAP_FILE_BYTES = 1_000_000
MAX_SEARCH_RESULTS = 100
MAX_READ_BYTES = 256 * 1024
MAX_READ_FILES = 1
MAX_TASK_BYTES = 4096
SERVICE_TOOLS = {"repo_map", "repo_search", "content_read", "prepare_package", "validate_prepare_package"}


def _json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_mcp_service_receipt(record: Any) -> list[str]:
    if not isinstance(record, dict):
        return ["receipt must be an object"]
    errors = [
        key + " is required"
        for key in (
            "kind",
            "schema_version",
            "target_profile",
            "session_id",
            "service",
            "status",
            "digest",
            "finalized_by",
            "policy_ref",
            "result_digest",
        )
        if key not in record
    ]
    if record.get("kind") != "builder_ii.mcp_service_receipt":
        errors.append("kind is invalid")
    if record.get("schema_version") != 2:
        errors.append("schema_version must be 2")
    if record.get("status") not in {"succeeded", "denied", "failed"}:
        errors.append("status is invalid")
    if record.get("finalized_by") != "builder_ii.adapters.mcp.governed_services":
        errors.append("finalized_by is invalid")
    for key in ("digest", "result_digest"):
        if not isinstance(record.get(key), str) or len(record[key]) != 64:
            errors.append(f"{key} must be a SHA-256 digest")
    if not isinstance(record.get("policy_ref"), dict):
        errors.append("policy_ref must be an object")
    return errors


def _service_receipt(
    *,
    builder_root: Path,
    session_id: str,
    target_name: str,
    tool_name: str,
    arguments: dict[str, Any],
    result: Any,
    status: str,
) -> tuple[dict[str, Any], Path, Path]:
    session_dir = builder_root / "sessions" / session_id
    mcp_dir = session_dir / "mcp"
    events_dir = session_dir / "events"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)
    existing = load_event_records(events_dir)
    sequence = len(existing) + 1
    policy = build_read_only_policy()
    policy_path = mcp_dir / "mcp-deny-by-default-policy.json"
    _json(policy_path, policy)
    policy_ref = {
        "role": "mcp_tool_policy",
        "kind": policy["kind"],
        "path": str(policy_path),
        "sha256": canonical_digest(policy),
        "required": True,
    }
    receipt = {
        "kind": "builder_ii.mcp_service_receipt",
        "schema_version": 2,
        "target_profile": target_name,
        "session_id": session_id,
        "service": tool_name,
        "status": status,
        "arguments": arguments,
        "result": result,
        "policy_ref": policy_ref,
        "result_digest": canonical_digest(result),
        "finalized_by": "builder_ii.adapters.mcp.governed_services",
        "governance": {
            "artifact_is_authority": False,
            "target_repo_writes": "DISABLED",
            "shell_execution": "DISABLED",
            "network_access": "DISABLED",
            "credential_access": "DISABLED",
            "model_execution": "DISABLED",
        },
    }
    receipt["digest"] = canonical_digest({k: v for k, v in receipt.items() if k != "digest"})
    errors = validate_mcp_service_receipt(receipt)
    if errors:
        raise ValueError("MCP service receipt validation failed: " + "; ".join(errors))
    receipt_path = mcp_dir / f"{sequence:03d}_{tool_name}_receipt.json"
    _json(receipt_path, receipt)
    previous = None
    if existing:
        previous_data, previous_path = existing[-1]
        previous = {
            "role": "event",
            "kind": EVENT_RECORD_KIND,
            "path": str(previous_path),
            "sha256": canonical_digest(previous_data),
            "required": True,
        }
    event = create_event_record(
        event_id=f"evt_mcp_service_{session_id}_{sequence}",
        session_id=session_id,
        sequence=sequence,
        event_type="mcp_call_executed" if status == "succeeded" else "mcp_call_denied",
        stage=(
            replay_events(existing, session_id=session_id).get("current_stage", "initialized")
            if existing
            else "initialized"
        ),
        subject_refs=[
            {
                "kind": receipt["kind"],
                "path": str(receipt_path),
                "sha256": canonical_digest(receipt),
                "role": "mcp_service_receipt",
                "required": True,
            }
        ],
        command_surface="builder-mcp serve",
        policy_snapshot_ref=policy_ref,
        previous_event_ref=previous,
        message=f"governed MCP service call: {tool_name}",
    )
    errors = validate_event_record(event)
    if errors:
        raise ValueError("event validation failed: " + "; ".join(errors))
    event_path = events_dir / f"{sequence:03d}_mcp_service.json"
    write_event_record(event, event_path)
    return receipt, receipt_path, event_path


def run_service(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    session_id: str,
    builder_root: Path,
    target_root: Path,
    target_name: str,
) -> tuple[dict[str, Any], Path, Path]:
    """Dispatch only to existing governed services; no CLI or subprocess boundary."""
    target_root = target_root.resolve()
    if not _within(target_root, target_root) or not target_root.is_dir():
        raise ValueError("target root must be an existing directory")
    if target_name not in {"generic", "builder", "core"} or tool_name not in SERVICE_TOOLS:
        raise ValueError("invalid governed MCP service admission")
    if tool_name == "repo_map":
        max_files = int(arguments.get("max_files", MAX_MAP_FILES))
        max_bytes = int(arguments.get("max_file_bytes", MAX_MAP_FILE_BYTES))
        if not 1 <= max_files <= MAX_MAP_FILES or not 1 <= max_bytes <= MAX_MAP_FILE_BYTES:
            raise ValueError("repo map bounds must be positive and within limits")
        result = create_repo_map(target_root, target_name=target_name, max_files=max_files, max_file_bytes=max_bytes)
    elif tool_name == "repo_search":
        repo_map = create_repo_map(
            target_root, target_name=target_name, max_files=MAX_MAP_FILES, max_file_bytes=MAX_MAP_FILE_BYTES
        )
        result = search_repo_map(repo_map, arguments.get("query"), max_results=MAX_SEARCH_RESULTS)
    elif tool_name == "content_read":
        rel = str(arguments.get("path", ""))
        path = target_root / rel
        if not _within(path, target_root) or path.is_symlink():
            result = {
                "kind": "builder_ii.denied_read",
                "reason": "path traversal or symlink refused",
                "target_file": str(path),
            }
        else:
            policy = create_read_policy(
                target_name=target_name,
                target_repo=target_root,
                allowed_paths=[rel],
                max_bytes_budget=MAX_READ_BYTES,
                content_capture_allowed=True,
            )
            result = execute_content_read(policy, path, max_bytes_per_file=MAX_READ_BYTES, current_read_bytes=0)
            errors = validate_content_read_receipt(result)
            if errors:
                raise ValueError("content-read receipt validation failed: " + "; ".join(errors))
    elif tool_name == "prepare_package":
        call_id = uuid.uuid4().hex
        output = builder_root.resolve() / "sessions" / session_id / "mcp" / "prepare-package" / call_id
        task = str(arguments.get("task", ""))
        if not task.strip() or len(task.encode("utf-8")) > MAX_TASK_BYTES:
            raise ValueError("task must be non-empty and within the byte limit")
        result = create_governed_prepare_package(
            load_settings(target_root),
            target_name,
            output_dir=output,
            repo_path=str(target_root),
            task=task,
            include_deepagents_readiness=False,
        )
    elif tool_name == "validate_prepare_package":
        package_root = (builder_root / "sessions" / session_id / "mcp" / "prepare-package").resolve()
        supplied = Path(str(arguments.get("path", "")))
        raw = supplied if supplied.is_absolute() else package_root / supplied
        if not _within(raw, package_root):
            result = {"valid": False, "errors": ["package path is outside server-controlled artifact root"]}
        else:
            errors = validate_governed_prepare_package_directory(raw)
            result = {"valid": not errors, "errors": errors}
    else:
        raise KeyError(tool_name)
    status = (
        "succeeded"
        if not (isinstance(result, dict) and result.get("kind") == "builder_ii.denied_read")
        and not (isinstance(result, dict) and result.get("valid") is False)
        else "denied"
    )
    return _service_receipt(
        builder_root=builder_root,
        session_id=session_id,
        target_name=target_name,
        tool_name=tool_name,
        arguments=arguments,
        result=result,
        status=status,
    )
