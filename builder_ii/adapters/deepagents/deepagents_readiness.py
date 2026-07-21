from __future__ import annotations

import importlib.metadata as metadata
import importlib.util
import json as json_lib
from pathlib import Path
from typing import Any, Literal

DeepAgentsReadinessMode = Literal["metadata_only", "import_check"]
DeepAgentsDependencyState = Literal["unknown", "available", "unavailable"]

DEEPAGENTS_READINESS_KIND = "builder_ii.deepagents_dependency_readiness"
DEEPAGENTS_READINESS_SCHEMA_VERSION = 1

_ALLOWED_ACTIONS = (
    "render_deepagents_dependency_readiness_artifact",
    "validate_deepagents_dependency_readiness_artifact",
    "optionally_check_import_metadata",
)

_DENIED_ACTIONS = (
    "construct_deepagents_agent",
    "call_create_governed_deep_agent",
    "start_deepagents_runtime",
    "invoke_subagents",
    "call_models",
    "execute_commands",
    "execute_shell",
    "read_repository_files_as_runtime",
    "write_source_files",
    "apply_patches",
    "mutate_memory",
    "connect_mcp_servers",
)

_EXPECTED_EXPORTS = (
    "create_governed_deep_agent",
    "DEFAULT_GOVERNED_ALLOW_TOOLS",
)


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _package_version(package_name: str) -> str:
    try:
        return metadata.version(package_name)
    except metadata.PackageNotFoundError:
        return ""


def _export_available(module_name: str, export_name: str) -> bool | None:
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False
    if module_name != "deepagents":
        return None
    try:
        module = __import__(module_name, fromlist=[export_name])
    except Exception:
        return False
    return hasattr(module, export_name)


def create_deepagents_readiness_artifact(
    *,
    mode: DeepAgentsReadinessMode = "metadata_only",
    package_name: str = "deepagents",
    module_name: str = "deepagents",
    expected_factory: str = "create_governed_deep_agent",
    expected_exports: tuple[str, ...] | list[str] = _EXPECTED_EXPORTS,
    package_source: str = "local_or_environment",
) -> dict[str, Any]:
    if mode not in ("metadata_only", "import_check"):
        raise ValueError("mode must be metadata_only or import_check")
    dependency_state: DeepAgentsDependencyState = "unknown"
    observed_version = ""
    observed_module = False
    observed_exports: dict[str, bool | None] = {name: None for name in expected_exports}

    if mode == "import_check":
        observed_module = _module_available(module_name)
        observed_version = _package_version(package_name)
        dependency_state = "available" if observed_module else "unavailable"
        observed_exports = {name: _export_available(module_name, name) for name in expected_exports}

    return {
        "kind": DEEPAGENTS_READINESS_KIND,
        "schema_version": DEEPAGENTS_READINESS_SCHEMA_VERSION,
        "mode": mode,
        "package": {
            "name": package_name,
            "module": module_name,
            "source": package_source,
            "expected_factory": expected_factory,
            "expected_exports": list(expected_exports),
        },
        "observed": {
            "dependency_state": dependency_state,
            "module_available": observed_module,
            "version": observed_version,
            "exports": observed_exports,
        },
        "current_runtime_state": "DISABLED",
        "readiness_constructs_deepagents": False,
        "readiness_imports_deepagents": mode == "import_check",
        "allowed_actions": list(_ALLOWED_ACTIONS),
        "denied_actions": list(_DENIED_ACTIONS),
        "approval_requirements": [
            "future dependency usage requires explicit optional dependency policy",
            "future agent construction requires runtime promotion",
            "future tool invocation requires human approval boundary",
            "future audit events require an output artifact path",
        ],
        "governance": {
            "capability_state": "readiness_artifact",
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


def dumps_deepagents_readiness_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_deepagents_readiness_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_readiness_artifact(artifact), encoding="utf-8")


def validate_deepagents_readiness_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["deepagents readiness artifact must be a JSON object"]
    if artifact.get("kind") != DEEPAGENTS_READINESS_KIND:
        errors.append(f"kind must be {DEEPAGENTS_READINESS_KIND}")
    if artifact.get("schema_version") != DEEPAGENTS_READINESS_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_READINESS_SCHEMA_VERSION}")
    if artifact.get("mode") not in ("metadata_only", "import_check"):
        errors.append("mode must be metadata_only or import_check")
    package = artifact.get("package")
    if not isinstance(package, dict):
        errors.append("package must be an object")
    else:
        if package.get("name") != "deepagents":
            errors.append("package.name must be deepagents")
        if package.get("module") != "deepagents":
            errors.append("package.module must be deepagents")
        if package.get("expected_factory") != "create_governed_deep_agent":
            errors.append("package.expected_factory must be create_governed_deep_agent")
        if not isinstance(package.get("expected_exports"), list) or "create_governed_deep_agent" not in package.get(
            "expected_exports", []
        ):
            errors.append("package.expected_exports must include create_governed_deep_agent")
    observed = artifact.get("observed")
    if not isinstance(observed, dict):
        errors.append("observed must be an object")
    else:
        if observed.get("dependency_state") not in ("unknown", "available", "unavailable"):
            errors.append("observed.dependency_state must be unknown, available, or unavailable")
        if not isinstance(observed.get("module_available"), bool):
            errors.append("observed.module_available must be boolean")
        if not isinstance(observed.get("version"), str):
            errors.append("observed.version must be a string")
        if not isinstance(observed.get("exports"), dict):
            errors.append("observed.exports must be an object")
    if artifact.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED or NOT_AUTHORIZED")
    if artifact.get("readiness_constructs_deepagents") is not False:
        errors.append("readiness_constructs_deepagents must be false or NOT_AUTHORIZED")
    if not isinstance(artifact.get("readiness_imports_deepagents"), bool):
        errors.append("readiness_imports_deepagents must be boolean")
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


def validate_deepagents_readiness_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_deepagents_readiness_artifact(data)
