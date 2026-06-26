from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.goose_session import validate_goose_session_manifest

GooseCommandRisk = Literal["low", "medium", "high", "critical"]

GOOSE_COMMAND_PROPOSAL_KIND = "builder_ii.goose_command_proposal"
GOOSE_COMMAND_PROPOSAL_SCHEMA_VERSION = 1

_ALLOWED_ACTIONS = (
    "validate_goose_session_manifest",
    "render_command_proposal_artifact",
    "validate_command_proposal_artifact",
)

_DENIED_ACTIONS = (
    "start_goose_process",
    "start_goose_runtime",
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


def _clean_text(value: str | Path | None) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _clean_list(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if values is None:
        return []
    return [item for item in (_clean_text(value) for value in values) if item]


def create_goose_command_proposal(
    manifest: dict[str, Any],
    *,
    manifest_path: str | Path,
    command: str,
    reason: str = "",
    risk_level: GooseCommandRisk = "medium",
    output_path: str | Path | None = None,
    rollback_note: str = "command was not executed; delete this proposal artifact to roll back the proposed action",
    verification_refs: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    """Create a proposed command artifact without executing the command."""
    target = manifest.get("target") if isinstance(manifest.get("target"), dict) else {}
    agent = manifest.get("agent_profile") if isinstance(manifest.get("agent_profile"), dict) else {}
    clean_command = _clean_text(command)
    return {
        "kind": GOOSE_COMMAND_PROPOSAL_KIND,
        "schema_version": GOOSE_COMMAND_PROPOSAL_SCHEMA_VERSION,
        "capability_state": "command_proposal",
        "execution_state": "PROPOSED_ONLY",
        "current_runtime_state": "DISABLED",
        "requires_human_approval": True,
        "executed": False,
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
        "command": clean_command,
        "reason": _clean_text(reason),
        "risk_level": risk_level,
        "working_directory": {
            "binding": "target.repo",
            "target_repo": target.get("repo", ""),
            "resolved_or_inspected": False,
        },
        "expected_output_artifact": "" if output_path is None else str(output_path),
        "approval": {
            "required": True,
            "approved": False,
            "approved_by": "",
            "approved_at_utc": "",
        },
        "execution_result": {
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "started_at_utc": "",
            "ended_at_utc": "",
        },
        "actions_performed": list(_ALLOWED_ACTIONS),
        "allowed_actions": list(_ALLOWED_ACTIONS),
        "denied_actions": list(_DENIED_ACTIONS),
        "commands_proposed": [clean_command],
        "commands_executed": [],
        "shell_commands_executed": [],
        "source_writes_proposed": [],
        "source_writes_applied": [],
        "patches_applied": [],
        "model_calls": [],
        "deepagents_constructed": False,
        "approval_events": [],
        "verification_output_refs": _clean_list(verification_refs),
        "rollback_refs": [_clean_text(rollback_note)],
        "governance": {
            "capability_state": "command_proposal",
            **{key: "DISABLED" for key in _DISABLED_GOVERNANCE_KEYS},
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def create_goose_command_proposal_from_manifest_file(
    manifest_path: Path,
    *,
    command: str,
    reason: str = "",
    risk_level: GooseCommandRisk = "medium",
    output_path: Path | None = None,
    rollback_note: str = "command was not executed; delete this proposal artifact to roll back the proposed action",
    verification_refs: tuple[str, ...] | list[str] | None = None,
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

    proposal = create_goose_command_proposal(
        manifest,
        manifest_path=manifest_path,
        command=command,
        reason=reason,
        risk_level=risk_level,
        output_path=output_path,
        rollback_note=rollback_note,
        verification_refs=verification_refs,
    )
    errors = validate_goose_command_proposal(proposal)
    if errors:
        return None, errors
    return proposal, []


def dumps_goose_command_proposal(proposal: dict[str, Any]) -> str:
    return json_lib.dumps(proposal, indent=2, sort_keys=True) + "\n"


def write_goose_command_proposal(proposal: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_goose_command_proposal(proposal), encoding="utf-8")


def validate_goose_command_proposal(proposal: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(proposal, dict):
        return ["Goose command proposal must be a JSON object"]
    if proposal.get("kind") != GOOSE_COMMAND_PROPOSAL_KIND:
        errors.append(f"kind must be {GOOSE_COMMAND_PROPOSAL_KIND}")
    if proposal.get("schema_version") != GOOSE_COMMAND_PROPOSAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_COMMAND_PROPOSAL_SCHEMA_VERSION}")
    for key, expected in (
        ("capability_state", "command_proposal"),
        ("execution_state", "PROPOSED_ONLY"),
        ("current_runtime_state", "DISABLED"),
    ):
        if proposal.get(key) != expected:
            errors.append(f"{key} must be {expected}")
    if proposal.get("requires_human_approval") is not True:
        errors.append("requires_human_approval must be true")
    for key in ("executed", "runtime_started", "goose_process_started", "deepagents_constructed"):
        if proposal.get(key) is not False:
            errors.append(f"{key} must be false")
    if not proposal.get("command") or not isinstance(proposal.get("command"), str):
        errors.append("command is required")
    if proposal.get("risk_level") not in ("low", "medium", "high", "critical"):
        errors.append("risk_level must be low, medium, high, or critical")
    if proposal.get("commands_proposed") != [proposal.get("command")]:
        errors.append("commands_proposed must contain only command")
    for field in ("commands_executed", "shell_commands_executed", "source_writes_applied", "patches_applied", "model_calls"):
        if proposal.get(field) != []:
            errors.append(f"{field} must be empty")
    result = proposal.get("execution_result")
    if not isinstance(result, dict):
        errors.append("execution_result must be an object")
    else:
        if result.get("exit_code") is not None:
            errors.append("execution_result.exit_code must be null")
        if result.get("stdout") != "":
            errors.append("execution_result.stdout must be empty")
        if result.get("stderr") != "":
            errors.append("execution_result.stderr must be empty")
    approval = proposal.get("approval")
    if not isinstance(approval, dict):
        errors.append("approval must be an object")
    else:
        if approval.get("required") is not True:
            errors.append("approval.required must be true")
        if approval.get("approved") is not False:
            errors.append("approval.approved must be false")
    denied = proposal.get("denied_actions")
    if isinstance(denied, list):
        for required in _DENIED_ACTIONS:
            if required not in denied:
                errors.append(f"denied_actions must include {required}")
    else:
        errors.append("denied_actions must be a list")
    governance = proposal.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "command_proposal":
            errors.append("governance.capability_state must be command_proposal")
        for key in _DISABLED_GOVERNANCE_KEYS:
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_goose_command_proposal_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_goose_command_proposal(data)
