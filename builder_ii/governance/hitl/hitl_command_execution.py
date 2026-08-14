from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.core.config import Settings
from builder_ii.lifecycle.setup.target_profiles import TargetName, target_names, target_profile

HITL_COMMAND_EXECUTION_SPEC_KIND = "builder_ii.hitl_command_execution_spec"
HITL_COMMAND_EXECUTION_SPEC_SCHEMA_VERSION = 1

_ALLOWED_FUTURE_TRANSITIONS = (
    "command proposal",
    "approval record",
    "preflight record",
    "explicit execution request",
    "execution receipt",
    "postflight/handoff",
)

_DENIED_CURRENT_BEHAVIORS = (
    "no subprocess",
    "no shell execution",
    "no command execution",
    "no model execution",
    "no source writes",
    "no git mutation",
    "no commit/push",
    "no network/MCP execution",
    "no Goose runtime activation",
    "no deepagents runtime",
)

_REQUIRED_FUTURE_GATES = (
    "docs",
    "tests",
    "command surface",
    "failure mode",
    "human approval boundary",
    "output artifact",
    "rollback path",
    "verification path",
)


def create_hitl_command_execution_spec(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    task: str = "",
    reason: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a design/spec artifact for future HITL command execution without enabling runtime execution."""
    if settings is None:
        from builder_ii.core.config import load_settings

        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": HITL_COMMAND_EXECUTION_SPEC_KIND,
        "schema_version": HITL_COMMAND_EXECUTION_SPEC_SCHEMA_VERSION,
        "task": task,
        "reason": reason,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "allowed_future_transition": list(_ALLOWED_FUTURE_TRANSITIONS),
        "current_state": {
            "mode": "DESIGN_ONLY",
            "runtime": "DISABLED",
        },
        "denied_current_behavior": list(_DENIED_CURRENT_BEHAVIORS),
        "required_future_gates": list(_REQUIRED_FUTURE_GATES),
        "governance": {
            "capability_state": "DESIGN_ONLY",
            "runtime_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "command_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "git_mutation": "DISABLED",
            "commit_push": "DISABLED",
            "network_mcp_execution": "DISABLED",
            "goose_runtime_activation": "DISABLED",
            "deepagents_runtime": "DISABLED",
            "subprocess_execution": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_hitl_command_execution_spec(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_command_execution_spec(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_command_execution_spec(artifact), encoding="utf-8")


def validate_hitl_command_execution_spec(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl command execution spec artifact must be a JSON object"]
    if artifact.get("kind") != HITL_COMMAND_EXECUTION_SPEC_KIND:
        errors.append(f"kind must be {HITL_COMMAND_EXECUTION_SPEC_KIND}")
    if artifact.get("schema_version") != HITL_COMMAND_EXECUTION_SPEC_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_COMMAND_EXECUTION_SPEC_SCHEMA_VERSION}")

    target = artifact.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")

    transitions = artifact.get("allowed_future_transition")
    if not isinstance(transitions, list):
        errors.append("allowed_future_transition must be a list")
    else:
        for req in _ALLOWED_FUTURE_TRANSITIONS:
            if req not in transitions:
                errors.append(f"allowed_future_transition must include {req}")

    curr_state = artifact.get("current_state")
    if not isinstance(curr_state, dict):
        errors.append("current_state must be an object")
    else:
        if curr_state.get("mode") != "DESIGN_ONLY":
            errors.append("current_state.mode must be DESIGN_ONLY")
        if curr_state.get("runtime") != "DISABLED":
            errors.append("current_state.runtime must be DISABLED or NOT_AUTHORIZED")

    denied = artifact.get("denied_current_behavior")
    if not isinstance(denied, list):
        errors.append("denied_current_behavior must be a list")
    else:
        for req in _DENIED_CURRENT_BEHAVIORS:
            if req not in denied:
                errors.append(f"denied_current_behavior must include {req}")

    gates = artifact.get("required_future_gates")
    if not isinstance(gates, list):
        errors.append("required_future_gates must be a list")
    else:
        for req in _REQUIRED_FUTURE_GATES:
            if req not in gates:
                errors.append(f"required_future_gates must include {req}")

    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "DESIGN_ONLY":
            errors.append("governance.capability_state must be DESIGN_ONLY")
        for key in (
            "runtime_execution",
            "shell_execution",
            "command_execution",
            "model_execution",
            "source_writes",
            "git_mutation",
            "commit_push",
            "network_mcp_execution",
            "goose_runtime_activation",
            "deepagents_runtime",
            "subprocess_execution",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def validate_hitl_command_execution_spec_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_hitl_command_execution_spec(data)
