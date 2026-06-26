from __future__ import annotations

import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.goose_session import validate_goose_session_manifest

GOOSE_READONLY_AUDIT_KIND = "builder_ii.goose_readonly_runtime_audit"
GOOSE_READONLY_AUDIT_SCHEMA_VERSION = 1

_ALLOWED_ACTIONS = (
    "validate_goose_session_manifest",
    "emit_readonly_audit_artifact",
)

_DENIED_ACTIONS = (
    "start_goose_process",
    "start_goose_runtime",
    "read_repository_files",
    "inspect_git_status",
    "read_target_artifacts",
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
    "runtime_execution",
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


def _non_empty_link_values(manifest: dict[str, Any]) -> list[str]:
    links = manifest.get("links")
    if not isinstance(links, dict):
        return []
    return [str(value) for value in links.values() if isinstance(value, str) and value]


def create_readonly_runtime_audit(
    manifest: dict[str, Any],
    *,
    manifest_path: str | Path,
    output_path: str | Path | None = None,
    created_at_utc: str | None = None,
) -> dict[str, Any]:
    """Create a read-only runtime candidate audit artifact without starting Goose."""
    target = manifest.get("target") if isinstance(manifest.get("target"), dict) else {}
    agent = manifest.get("agent_profile") if isinstance(manifest.get("agent_profile"), dict) else {}
    links = manifest.get("links") if isinstance(manifest.get("links"), dict) else {}

    return {
        "kind": GOOSE_READONLY_AUDIT_KIND,
        "schema_version": GOOSE_READONLY_AUDIT_SCHEMA_VERSION,
        "runtime_mode": "read_only",
        "capability_state": "read_only_runtime_candidate",
        "current_runtime_state": "DISABLED",
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
        "files_read": [str(manifest_path)],
        "repository_files_read": [],
        "target_artifacts_read": [],
        "linked_artifacts_declared_but_not_read": _non_empty_link_values(manifest),
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
        "rollback_refs": ["no source mutation performed; delete this audit artifact to roll back the candidate output"],
        "handoff_ref": links.get("handoff", "") if isinstance(links.get("handoff", ""), str) else "",
        "governance": {
            "capability_state": "read_only_runtime_candidate",
            "runtime_execution": "DISABLED",
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
            "repository_file_reads": "DISABLED_IN_THIS_CANDIDATE_ARTIFACT",
            "target_artifact_reads": "DISABLED_IN_THIS_CANDIDATE_ARTIFACT",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def create_readonly_runtime_audit_from_manifest_file(
    manifest_path: Path,
    *,
    output_path: Path | None = None,
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
        return None, ["manifest.requested_runtime_mode must be read_only for read-only audit"]

    audit = create_readonly_runtime_audit(
        manifest,
        manifest_path=manifest_path,
        output_path=output_path,
        created_at_utc=created_at_utc,
    )
    audit_errors = validate_readonly_runtime_audit(audit)
    if audit_errors:
        return None, audit_errors
    return audit, []


def dumps_readonly_runtime_audit(audit: dict[str, Any]) -> str:
    return json_lib.dumps(audit, indent=2, sort_keys=True) + "\n"


def write_readonly_runtime_audit(audit: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_readonly_runtime_audit(audit), encoding="utf-8")


def validate_readonly_runtime_audit(audit: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(audit, dict):
        return ["Goose read-only audit must be a JSON object"]
    if audit.get("kind") != GOOSE_READONLY_AUDIT_KIND:
        errors.append(f"kind must be {GOOSE_READONLY_AUDIT_KIND}")
    if audit.get("schema_version") != GOOSE_READONLY_AUDIT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_READONLY_AUDIT_SCHEMA_VERSION}")
    if audit.get("runtime_mode") != "read_only":
        errors.append("runtime_mode must be read_only")
    if audit.get("capability_state") != "read_only_runtime_candidate":
        errors.append("capability_state must be read_only_runtime_candidate")
    if audit.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED")
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

    if audit.get("repository_files_read") != []:
        errors.append("repository_files_read must be empty")
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
        for key in _DISABLED_GOVERNANCE_KEYS:
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("repository_file_reads") != "DISABLED_IN_THIS_CANDIDATE_ARTIFACT":
            errors.append("governance.repository_file_reads must be DISABLED_IN_THIS_CANDIDATE_ARTIFACT")
        if governance.get("target_artifact_reads") != "DISABLED_IN_THIS_CANDIDATE_ARTIFACT":
            errors.append("governance.target_artifact_reads must be DISABLED_IN_THIS_CANDIDATE_ARTIFACT")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_readonly_runtime_audit_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_readonly_runtime_audit(data)
