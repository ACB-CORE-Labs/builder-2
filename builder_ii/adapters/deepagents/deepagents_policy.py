from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.core.config import Settings
from builder_ii.lifecycle.setup.target_profiles import TargetName, target_names, target_profile

DeepAgentsPolicyMode = Literal["artifact_only"]
DeepAgentsMemoryMode = Literal["disabled", "proposal_only", "approved"]
DeepAgentsSubagentResultMode = Literal["trusted", "proposal_only"]

DEEPAGENTS_POLICY_KIND = "builder_ii.deepagents_governed_policy"
DEEPAGENTS_POLICY_SCHEMA_VERSION = 1

_DEFAULT_ALLOW_TOOLS = ("read_todos", "write_todos", "ls", "read_file", "glob", "grep", "task")
_DEFAULT_DENY_TOOLS = ("execute", "write_file", "edit_file")

_ALLOWED_ACTIONS = (
    "render_deepagents_policy_artifact",
    "validate_deepagents_policy_artifact",
    "describe_governed_factory_configuration",
)

_DENIED_ACTIONS = (
    "construct_deepagents_agent",
    "call_create_governed_deep_agent",
    "start_deepagents_runtime",
    "invoke_subagents",
    "read_repository_files_as_runtime",
    "execute_commands",
    "execute_shell",
    "write_source_files",
    "apply_patches",
    "mutate_memory",
    "connect_mcp_servers",
    "call_models",
)


def _clean_path(path: str | Path | None) -> str:
    if path is None:
        return ""
    return str(path).strip()


def _clean_tools(values: tuple[str, ...] | list[str] | None, default: tuple[str, ...]) -> list[str]:
    source = default if values is None else tuple(values)
    return [value for value in (item.strip() for item in source) if value]


def _target_dict(settings: Settings, target: TargetName, generic_repo: Path | None) -> dict[str, Any]:
    selected = target_profile(settings, target, generic_repo=generic_repo)
    return {"name": selected.name, "repo": str(selected.repo), "description": selected.description}


def create_deepagents_policy_artifact(
    settings: Settings,
    *,
    target_name: TargetName,
    task: str = "",
    policy_mode: DeepAgentsPolicyMode = "artifact_only",
    memory_mode: DeepAgentsMemoryMode = "proposal_only",
    subagent_result_mode: DeepAgentsSubagentResultMode = "proposal_only",
    allow_tools: tuple[str, ...] | list[str] | None = None,
    deny_tools: tuple[str, ...] | list[str] | None = None,
    memory_prefixes: tuple[str, ...] | list[str] = ("/memories/",),
    root_binding: str = "target.repo",
    expected_audit_artifact: str | Path = ".builder/artifacts/deepagents-audit-events.json",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    return {
        "kind": DEEPAGENTS_POLICY_KIND,
        "schema_version": DEEPAGENTS_POLICY_SCHEMA_VERSION,
        "task": task,
        "target": _target_dict(settings, target_name, generic_repo),
        "policy_mode": policy_mode,
        "current_runtime_state": "DISABLED",
        "policy_constructs_deepagents": False,
        "governed_factory": {
            "package": "deepagents",
            "factory": "create_governed_deep_agent",
            "root_binding": root_binding,
            "allow_tools": _clean_tools(allow_tools, _DEFAULT_ALLOW_TOOLS),
            "deny_tools": _clean_tools(deny_tools, _DEFAULT_DENY_TOOLS),
            "memory_mode": memory_mode,
            "memory_prefixes": [prefix for prefix in memory_prefixes if prefix],
            "subagent_result_mode": subagent_result_mode,
            "audit_sink": "artifact_events_only",
        },
        "expected_audit_artifact": _clean_path(expected_audit_artifact),
        "allowed_actions": list(_ALLOWED_ACTIONS),
        "denied_actions": list(_DENIED_ACTIONS),
        "approval_requirements": [
            "future agent construction requires runtime promotion",
            "future repository reads require explicit read-only inspection policy",
            "future tool invocation requires human approval boundaries",
            "future memory persistence requires approved memory policy",
        ],
        "governance": {
            "capability_state": "artifact_only",
            "runtime_execution": "DISABLED",
            "deepagents_runtime_start": "DISABLED",
            "agent_construction": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "command_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "mcp_connections": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_deepagents_policy_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_deepagents_policy_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_policy_artifact(artifact), encoding="utf-8")


def validate_deepagents_policy_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["deepagents policy artifact must be a JSON object"]
    if artifact.get("kind") != DEEPAGENTS_POLICY_KIND:
        errors.append(f"kind must be {DEEPAGENTS_POLICY_KIND}")
    if artifact.get("schema_version") != DEEPAGENTS_POLICY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_POLICY_SCHEMA_VERSION}")
    target = artifact.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")
    if artifact.get("policy_mode") != "artifact_only":
        errors.append("policy_mode must be artifact_only")
    if artifact.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED or NOT_AUTHORIZED")
    if artifact.get("policy_constructs_deepagents") is not False:
        errors.append("policy_constructs_deepagents must be false or NOT_AUTHORIZED")
    factory = artifact.get("governed_factory")
    if not isinstance(factory, dict):
        errors.append("governed_factory must be an object")
    else:
        if factory.get("factory") != "create_governed_deep_agent":
            errors.append("governed_factory.factory must be create_governed_deep_agent")
        if factory.get("root_binding") not in ("target.repo", "explicit_root_ref"):
            errors.append("governed_factory.root_binding must be target.repo or explicit_root_ref")
        if not isinstance(factory.get("allow_tools"), list) or not factory.get("allow_tools"):
            errors.append("governed_factory.allow_tools must be a non-empty list")
        if not isinstance(factory.get("deny_tools"), list):
            errors.append("governed_factory.deny_tools must be a list")
        if factory.get("memory_mode") not in ("disabled", "proposal_only", "approved"):
            errors.append("governed_factory.memory_mode must be disabled, proposal_only, or approved")
        if factory.get("subagent_result_mode") not in ("trusted", "proposal_only"):
            errors.append("governed_factory.subagent_result_mode must be trusted or proposal_only")
        if not isinstance(factory.get("memory_prefixes"), list) or not factory.get("memory_prefixes"):
            errors.append("governed_factory.memory_prefixes must be a non-empty list")
    if not artifact.get("expected_audit_artifact"):
        errors.append("expected_audit_artifact is required")
    for field in ("allowed_actions", "denied_actions", "approval_requirements"):
        value = artifact.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"{field} must be a non-empty list")
    denied = artifact.get("denied_actions")
    if isinstance(denied, list):
        for required in _DENIED_ACTIONS:
            if required not in denied:
                errors.append(f"denied_actions must include {required}")
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "deepagents_runtime_start",
            "agent_construction",
            "model_execution",
            "shell_execution",
            "command_execution",
            "source_writes",
            "memory_mutation",
            "mcp_connections",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_deepagents_policy_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_deepagents_policy_artifact(data)
