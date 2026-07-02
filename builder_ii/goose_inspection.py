from __future__ import annotations

import hashlib
import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.goose_session import validate_goose_session_manifest

GOOSE_READONLY_INSPECTION_KIND = "builder_ii.goose_readonly_inspection_audit"
GOOSE_READONLY_INSPECTION_SCHEMA_VERSION = 1
DEFAULT_MAX_READ_BYTES = 65536

_ALLOWED_ACTIONS = (
    "validate_goose_session_manifest",
    "read_explicit_operator_requested_repository_files",
    "emit_readonly_inspection_audit_artifact",
)

_DENIED_ACTIONS = (
    "start_goose_process",
    "start_goose_runtime",
    "inspect_git_status",
    "read_linked_target_artifacts",
    "execute_commands",
    "execute_shell",
    "write_source_files",
    "apply_patches",
    "mutate_memory",
    "create_commits",
    "push_refs",
    "open_pull_requests",
    "construct_deepagents",
    "call_models",
    "source_collection",
    "web_search",
    "mcp_execution",
)

_DISABLED_GOVERNANCE_KEYS = (
    "goose_runtime_start",
    "model_execution",
    "agent_construction",
    "deepagents_construction",
    "shell_execution",
    "command_execution",
    "source_writes",
    "memory_mutation",
    "commit_push",
    "pull_request_creation",
    "source_collection",
    "web_search",
    "mcp_execution",
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_reserved_git_path(path: Path) -> bool:
    return any(part == ".git" for part in path.parts)


def _validate_relative_repo_path(path: Path) -> list[str]:
    errors: list[str] = []
    if path.is_absolute():
        errors.append(f"read path must be relative: {path}")
    if str(path).strip() in ("", "."):
        errors.append("read path must name a file")
    if ".." in path.parts:
        errors.append(f"read path must not contain '..': {path}")
    if _is_reserved_git_path(path):
        errors.append(f"read path must not enter .git: {path}")
    return errors


def _read_file_metadata(
    repo_root: Path, relative_path: Path, *, max_bytes: int
) -> tuple[dict[str, Any] | None, list[str]]:
    errors = _validate_relative_repo_path(relative_path)
    if errors:
        return None, errors
    try:
        root = repo_root.expanduser().resolve()
        candidate = (root / relative_path).resolve()
        candidate.relative_to(root)
    except ValueError:
        return None, [f"read path escapes target repo: {relative_path}"]
    except Exception as exc:
        return None, [f"failed to resolve read path {relative_path}: {exc}"]

    if not candidate.exists():
        return None, [f"read path not found: {relative_path}"]
    if not candidate.is_file():
        return None, [f"read path is not a file: {relative_path}"]
    try:
        size = candidate.stat().st_size
    except Exception as exc:
        return None, [f"failed to stat read path {relative_path}: {exc}"]
    if size > max_bytes:
        return None, [f"read path exceeds max bytes ({max_bytes}): {relative_path}"]
    try:
        data = candidate.read_bytes()
    except Exception as exc:
        return None, [f"failed to read path {relative_path}: {exc}"]

    text = data.decode("utf-8", errors="replace")
    return {
        "path": str(relative_path),
        "bytes_read": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "line_count": 0 if not text else len(text.splitlines()),
        "content_recorded": False,
    }, []


def create_readonly_inspection_audit(
    manifest: dict[str, Any],
    *,
    manifest_path: str | Path,
    read_paths: list[str | Path],
    output_path: str | Path | None = None,
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
    created_at_utc: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Create a bounded read-only inspection audit without starting Goose or recording content."""
    errors: list[str] = []
    if max_bytes <= 0:
        errors.append("max_bytes must be greater than 0")
    if not read_paths:
        errors.append("at least one --read-file path is required")
    target = manifest.get("target") if isinstance(manifest.get("target"), dict) else {}
    repo_value = target.get("repo", "")
    if not isinstance(repo_value, str) or not repo_value:
        errors.append("manifest target.repo is required")
    if errors:
        return None, errors

    repo_root = Path(repo_value)
    repository_files_read: list[dict[str, Any]] = []
    seen: set[str] = set()
    for read_path in read_paths:
        relative_path = Path(read_path)
        key = str(relative_path)
        if key in seen:
            continue
        seen.add(key)
        metadata, metadata_errors = _read_file_metadata(repo_root, relative_path, max_bytes=max_bytes)
        if metadata_errors:
            errors.extend(metadata_errors)
        elif metadata is not None:
            repository_files_read.append(metadata)
    if errors:
        return None, errors

    agent = manifest.get("agent_profile") if isinstance(manifest.get("agent_profile"), dict) else {}
    links = manifest.get("links") if isinstance(manifest.get("links"), dict) else {}

    audit = {
        "kind": GOOSE_READONLY_INSPECTION_KIND,
        "schema_version": GOOSE_READONLY_INSPECTION_SCHEMA_VERSION,
        "runtime_mode": "read_only",
        "capability_state": "read_only_runtime_candidate",
        "current_runtime_state": "CANDIDATE_INSPECTION",
        "runtime_started": False,
        "goose_process_started": False,
        "manifest_path": str(manifest_path),
        "manifest_kind": manifest.get("kind", ""),
        "manifest_schema_version": manifest.get("schema_version", 0),
        "manifest_requested_runtime_mode": manifest.get("requested_runtime_mode", ""),
        "task": manifest.get("task", ""),
        "target": {
            "name": target.get("name", ""),
            "repo": target.get("repo", ""),
            "description": target.get("description", ""),
        },
        "agent_profile": {
            "name": agent.get("name", ""),
            "description": agent.get("description", ""),
            "authority": agent.get("authority", ""),
        },
        "linked_artifacts_declared": dict(links),
        "expected_audit_artifact": manifest.get("expected_audit_artifact", ""),
        "actual_audit_artifact": "" if output_path is None else str(output_path),
        "timestamps": {
            "created_at_utc": created_at_utc or _utc_now(),
            "runtime_started_at_utc": "",
            "runtime_ended_at_utc": "",
        },
        "actions_performed": list(_ALLOWED_ACTIONS),
        "allowed_actions": list(_ALLOWED_ACTIONS),
        "denied_actions": list(_DENIED_ACTIONS),
        "files_read": [str(manifest_path), *[entry["path"] for entry in repository_files_read]],
        "requested_repository_paths": [str(Path(path)) for path in read_paths],
        "repository_files_read": repository_files_read,
        "repository_file_contents_recorded": False,
        "target_artifacts_read": [],
        "git_status_inspected": False,
        "commands_proposed": [],
        "commands_executed": [],
        "shell_commands_executed": [],
        "source_writes_proposed": [],
        "source_writes_applied": [],
        "patches_applied": [],
        "model_calls": [],
        "deepagents_constructed": False,
        "denied_action_attempts": [],
        "approval_events": [],
        "verification_output_refs": [],
        "rollback_refs": [
            "no source mutation performed; delete this inspection audit artifact to roll back the candidate output"
        ],
        "handoff_ref": links.get("handoff", "") if isinstance(links.get("handoff", ""), str) else "",
        "governance": {
            "capability_state": "read_only_runtime_candidate",
            "runtime_execution": "READ_ONLY_CANDIDATE_INSPECTION",
            "goose_runtime_start": "DISABLED",
            "model_execution": "DISABLED",
            "agent_construction": "DISABLED",
            "deepagents_construction": "DISABLED",
            "shell_execution": "DISABLED",
            "command_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "commit_push": "DISABLED",
            "pull_request_creation": "DISABLED",
            "source_collection": "DISABLED",
            "web_search": "DISABLED",
            "mcp_execution": "DISABLED",
            "repository_file_reads": "ENABLED_FOR_EXPLICIT_OPERATOR_PATHS_ONLY",
            "target_artifact_reads": "DISABLED_IN_THIS_CANDIDATE",
            "git_status_inspection": "DISABLED_IN_THIS_CANDIDATE",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    audit_errors = validate_readonly_inspection_audit(audit)
    if audit_errors:
        return None, audit_errors
    return audit, []


def create_readonly_inspection_audit_from_manifest_file(
    manifest_path: Path,
    *,
    read_paths: list[str | Path],
    output_path: Path | None = None,
    max_bytes: int = DEFAULT_MAX_READ_BYTES,
    created_at_utc: str | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    if not manifest_path.exists():
        return None, [f"file not found: {manifest_path}"]
    try:
        manifest = json_lib.loads(manifest_path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return None, [f"invalid JSON: {exc}"]
    except Exception as exc:
        return None, [f"failed to read file: {exc}"]

    manifest_errors = validate_goose_session_manifest(manifest)
    if manifest_errors:
        return None, [f"manifest: {error}" for error in manifest_errors]
    if manifest.get("requested_runtime_mode") != "read_only":
        return None, ["manifest.requested_runtime_mode must be read_only for read-only inspection"]

    return create_readonly_inspection_audit(
        manifest,
        manifest_path=manifest_path,
        read_paths=read_paths,
        output_path=output_path,
        max_bytes=max_bytes,
        created_at_utc=created_at_utc,
    )


def dumps_readonly_inspection_audit(audit: dict[str, Any]) -> str:
    return json_lib.dumps(audit, indent=2, sort_keys=True) + "\n"


def write_readonly_inspection_audit(audit: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_readonly_inspection_audit(audit), encoding="utf-8")


def validate_readonly_inspection_audit(audit: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(audit, dict):
        return ["Goose read-only inspection audit must be a JSON object"]
    if audit.get("kind") != GOOSE_READONLY_INSPECTION_KIND:
        errors.append(f"kind must be {GOOSE_READONLY_INSPECTION_KIND}")
    if audit.get("schema_version") != GOOSE_READONLY_INSPECTION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_READONLY_INSPECTION_SCHEMA_VERSION}")
    if audit.get("runtime_mode") != "read_only":
        errors.append("runtime_mode must be read_only")
    if audit.get("capability_state") != "read_only_runtime_candidate":
        errors.append("capability_state must be read_only_runtime_candidate")
    if audit.get("current_runtime_state") != "CANDIDATE_INSPECTION":
        errors.append("current_runtime_state must be CANDIDATE_INSPECTION")
    if audit.get("runtime_started") is not False:
        errors.append("runtime_started must be false")
    if audit.get("goose_process_started") is not False:
        errors.append("goose_process_started must be false")
    if audit.get("manifest_requested_runtime_mode") != "read_only":
        errors.append("manifest_requested_runtime_mode must be read_only")
    if not audit.get("manifest_path"):
        errors.append("manifest_path is required")
    if not isinstance(audit.get("target"), dict) or not audit["target"].get("name"):
        errors.append("target.name is required")
    if not isinstance(audit.get("agent_profile"), dict) or not audit["agent_profile"].get("name"):
        errors.append("agent_profile.name is required")

    for field in (
        "actions_performed",
        "allowed_actions",
        "denied_actions",
        "files_read",
        "requested_repository_paths",
        "repository_files_read",
        "target_artifacts_read",
        "commands_proposed",
        "commands_executed",
        "shell_commands_executed",
        "source_writes_proposed",
        "source_writes_applied",
        "patches_applied",
        "model_calls",
        "denied_action_attempts",
        "approval_events",
        "verification_output_refs",
        "rollback_refs",
    ):
        if not isinstance(audit.get(field), list):
            errors.append(f"{field} must be a list")

    denied = audit.get("denied_actions")
    if isinstance(denied, list):
        for required in _DENIED_ACTIONS:
            if required not in denied:
                errors.append(f"denied_actions must include {required}")

    repository_files_read = audit.get("repository_files_read")
    if isinstance(repository_files_read, list):
        if not repository_files_read:
            errors.append("repository_files_read must be non-empty")
        for index, entry in enumerate(repository_files_read):
            if not isinstance(entry, dict):
                errors.append(f"repository_files_read[{index}] must be an object")
                continue
            for key in ("path", "bytes_read", "sha256", "line_count", "content_recorded"):
                if key not in entry:
                    errors.append(f"repository_files_read[{index}].{key} is required")
            if entry.get("content_recorded") is not False:
                errors.append(f"repository_files_read[{index}].content_recorded must be false")
            if not isinstance(entry.get("bytes_read"), int) or entry.get("bytes_read", -1) < 0:
                errors.append(f"repository_files_read[{index}].bytes_read must be a non-negative integer")
    if audit.get("repository_file_contents_recorded") is not False:
        errors.append("repository_file_contents_recorded must be false")
    if audit.get("target_artifacts_read") != []:
        errors.append("target_artifacts_read must be empty")
    if audit.get("git_status_inspected") is not False:
        errors.append("git_status_inspected must be false")
    if audit.get("commands_executed") != []:
        errors.append("commands_executed must be empty")
    if audit.get("shell_commands_executed") != []:
        errors.append("shell_commands_executed must be empty")
    if audit.get("source_writes_applied") != []:
        errors.append("source_writes_applied must be empty")
    if audit.get("patches_applied") != []:
        errors.append("patches_applied must be empty")
    if audit.get("model_calls") != []:
        errors.append("model_calls must be empty")
    if audit.get("deepagents_constructed") is not False:
        errors.append("deepagents_constructed must be false")

    governance = audit.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "read_only_runtime_candidate":
            errors.append("governance.capability_state must be read_only_runtime_candidate")
        if governance.get("runtime_execution") != "READ_ONLY_CANDIDATE_INSPECTION":
            errors.append("governance.runtime_execution must be READ_ONLY_CANDIDATE_INSPECTION")
        for key in _DISABLED_GOVERNANCE_KEYS:
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("repository_file_reads") != "ENABLED_FOR_EXPLICIT_OPERATOR_PATHS_ONLY":
            errors.append("governance.repository_file_reads must be ENABLED_FOR_EXPLICIT_OPERATOR_PATHS_ONLY")
        if governance.get("target_artifact_reads") != "DISABLED_IN_THIS_CANDIDATE":
            errors.append("governance.target_artifact_reads must be DISABLED_IN_THIS_CANDIDATE")
        if governance.get("git_status_inspection") != "DISABLED_IN_THIS_CANDIDATE":
            errors.append("governance.git_status_inspection must be DISABLED_IN_THIS_CANDIDATE")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_readonly_inspection_audit_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_readonly_inspection_audit(data)
