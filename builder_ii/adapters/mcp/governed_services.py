"""Thin MCP adapters for existing governed Builder-II services."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from builder_ii.core.config import load_settings
from builder_ii.core.governed_prepare_package import (
    create_governed_prepare_package,
    validate_governed_prepare_package_directory,
)
from builder_ii.core.repo_map import create_repo_map
from builder_ii.governance.authority.readonly_authority import (
    create_read_policy,
    execute_content_read,
    validate_content_read_receipt,
)
from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    create_event_record,
    load_event_records,
    validate_event_record,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest

MAX_MAP_FILES = 500
MAX_MAP_FILE_BYTES = 1_000_000
MAX_SEARCH_RESULTS = 100
MAX_READ_BYTES = 256 * 1024
MAX_READ_FILES = 1


def _json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _service_receipt(
    *, builder_root: Path, session_id: str, tool_name: str, arguments: dict[str, Any], result: Any, status: str
) -> tuple[dict[str, Any], Path, Path]:
    session_dir = builder_root / "sessions" / session_id
    mcp_dir = session_dir / "mcp"
    events_dir = session_dir / "events"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)
    existing = load_event_records(events_dir)
    sequence = len(existing) + 1
    receipt = {
        "kind": "builder_ii.mcp_service_receipt",
        "schema_version": 1,
        "service": tool_name,
        "status": status,
        "arguments": arguments,
        "result": result,
        "governance": {
            "artifact_is_authority": False,
            "shell_execution": "DISABLED",
            "network_access": "DISABLED",
            "credential_access": "DISABLED",
            "model_execution": "DISABLED",
        },
    }
    receipt_path = mcp_dir / f"{sequence:03d}_{tool_name}_receipt.json"
    _json(receipt_path, receipt)
    previous = None
    if existing:
        previous_data, previous_path = existing[-1]
        previous = {"role": "event", "kind": EVENT_RECORD_KIND, "path": str(previous_path), "sha256": canonical_digest(previous_data), "required": True}
    event = create_event_record(
        event_id=f"evt_mcp_service_{session_id}_{sequence}", session_id=session_id, sequence=sequence,
        event_type="mcp_call_executed" if status == "succeeded" else "mcp_call_denied",
        stage="initialized", subject_refs=[{"kind": receipt["kind"], "path": str(receipt_path), "sha256": canonical_digest(receipt), "role": "mcp_service_receipt", "required": True}],
        command_surface="builder-mcp serve",
        policy_snapshot_ref={"kind": "builder_ii.mcp_service_policy", "path": "transport-deny-by-default", "sha256": canonical_digest({"tool": tool_name, "denied_by_default": True}), "role": "mcp_tool_policy", "required": True},
        previous_event_ref=previous,
        message=f"governed MCP service call: {tool_name}",
    )
    errors = validate_event_record(event)
    if errors:
        raise ValueError("event validation failed: " + "; ".join(errors))
    event_path = events_dir / f"{sequence:03d}_mcp_service.json"
    write_event_record(event, event_path)
    return receipt, receipt_path, event_path


def run_service(*, tool_name: str, arguments: dict[str, Any], session_id: str, builder_root: Path, target_root: Path) -> tuple[dict[str, Any], Path, Path]:
    """Dispatch only to existing governed services; no CLI or subprocess boundary."""
    target_root = target_root.resolve()
    if not _within(target_root, target_root) or not target_root.is_dir():
        raise ValueError("target root must be an existing directory")
    if tool_name == "repo_map":
        max_files = min(int(arguments.get("max_files", MAX_MAP_FILES)), MAX_MAP_FILES)
        max_bytes = min(int(arguments.get("max_file_bytes", MAX_MAP_FILE_BYTES)), MAX_MAP_FILE_BYTES)
        result = create_repo_map(target_root, target_name="builder", max_files=max_files, max_file_bytes=max_bytes)
    elif tool_name == "repo_search":
        repo_map = create_repo_map(target_root, target_name="builder", max_files=MAX_MAP_FILES, max_file_bytes=MAX_MAP_FILE_BYTES)
        query = str(arguments.get("query", ""))[:256].lower()
        result = {"matches": [item for item in repo_map.get("files", []) if query in str(item.get("path", "")).lower() or query in str(item.get("role", "")).lower()][:MAX_SEARCH_RESULTS], "bounded": True}
    elif tool_name == "content_read":
        rel = str(arguments.get("path", ""))
        path = target_root / rel
        if not _within(path, target_root) or path.is_symlink():
            result = {"kind": "builder_ii.denied_read", "reason": "path traversal or symlink refused", "target_file": str(path)}
        else:
            policy = create_read_policy(target_name="builder", target_repo=target_root, allowed_paths=[rel], max_bytes_budget=MAX_READ_BYTES, content_capture_allowed=True)
            result = execute_content_read(policy, path, max_bytes_per_file=MAX_READ_BYTES, current_read_bytes=0)
            validate_content_read_receipt(result) if result.get("kind") == "builder_ii.content_read_receipt" else None
    elif tool_name == "prepare_package":
        call_id = uuid.uuid4().hex
        output = builder_root.resolve() / "sessions" / session_id / "mcp" / "prepare-package" / call_id
        result = create_governed_prepare_package(load_settings(target_root), "builder", output_dir=output, repo_path=str(target_root), task=str(arguments.get("task", "")), include_deepagents_readiness=False)
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
    status = "succeeded" if not (isinstance(result, dict) and result.get("kind") == "builder_ii.denied_read") and not (isinstance(result, dict) and result.get("valid") is False) else "denied"
    return _service_receipt(builder_root=builder_root, session_id=session_id, tool_name=tool_name, arguments=arguments, result=result, status=status)
