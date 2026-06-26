from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.agent_profiles import AgentProfile, AgentProfileName, agent_profile_names, get_agent_profile
from builder_ii.config import Settings
from builder_ii.deepagents_bridge import REQUIRED_DENIED_TOOLS, bridge_spec_for, deepagents_availability, validate_bridge_spec
from builder_ii.target_profiles import TargetName, TargetProfile, target_names, target_profile

BUNDLE_KIND = "builder_ii.target_profile_bundle"
BUNDLE_SCHEMA_VERSION = 1


def _target_dict(profile: TargetProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "description": profile.description,
        "repo": str(profile.repo),
        "context_defaults": list(profile.context_defaults),
        "verification_hints": list(profile.verification_hints),
        "principles": list(profile.principles),
        "notes": list(profile.notes),
    }


def _agent_dict(profile: AgentProfile) -> dict[str, Any]:
    return {
        "name": profile.name,
        "description": profile.description,
        "purpose": profile.purpose,
        "authority": profile.authority,
        "compatible_targets": list(profile.compatible_targets),
        "required_context": list(profile.required_context),
        "allowed_tools": list(profile.allowed_tools),
        "forbidden_tools": list(profile.forbidden_tools),
        "hitl_required_for": list(profile.hitl_required_for),
        "output_contract": profile.output_contract,
    }


def _governance_dict() -> dict[str, Any]:
    return {
        "capability_state": "validation_only",
        "dependency_mode": "OPTIONAL",
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "agent_construction": "DISABLED",
        "file_writes": "DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH",
        "shell_execution": "DISABLED",
        "memory_mutation": "DISABLED",
        "commit_push": "DISABLED",
        "artifacts_are_authority": False,
        "core_workbench_coupling": "NONE",
    }


def _suggested_next_steps(target: TargetName, agent: AgentProfileName) -> list[str]:
    return [
        f"builder-targets show {target}",
        f"builder-agent render {agent} --target {target}",
        f"builder-bridge render {agent} --target {target} --format json --output .builder/artifacts/bridge-spec.json",
        "builder-bridge validate-artifact .builder/artifacts/bridge-spec.json",
        f"builder-context pack --target {target} --task '<task>' --no-repomix",
    ]


def create_target_bundle(
    settings: Settings,
    *,
    target_name: TargetName,
    agent_profile: AgentProfileName,
    task: str | None = None,
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a governed, no-runtime target bundle artifact."""
    selected_target = target_profile(settings, target_name, generic_repo=generic_repo)
    selected_agent = get_agent_profile(agent_profile)
    bridge_spec = bridge_spec_for(agent_profile, selected_target)
    bridge_errors = validate_bridge_spec(bridge_spec)

    return {
        "kind": BUNDLE_KIND,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "task": {
            "description": task or "",
        },
        "target": _target_dict(selected_target),
        "agent_profile": _agent_dict(selected_agent),
        "bridge_spec": bridge_spec.to_artifact_dict(),
        "bridge_spec_validation_errors": list(bridge_errors),
        "deepagents_readiness": deepagents_availability().to_json_dict(),
        "governance": _governance_dict(),
        "suggested_next_steps": _suggested_next_steps(target_name, agent_profile),
    }


def dumps_bundle(bundle: dict[str, Any]) -> str:
    return json_lib.dumps(bundle, indent=2, sort_keys=True) + "\n"


def write_bundle(bundle: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_bundle(bundle), encoding="utf-8")


def validate_target_bundle(bundle: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return ["bundle must be a JSON object"]

    if bundle.get("kind") != BUNDLE_KIND:
        errors.append(f"kind must be {BUNDLE_KIND}")
    if bundle.get("schema_version") != BUNDLE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {BUNDLE_SCHEMA_VERSION}")

    target = bundle.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")

    agent = bundle.get("agent_profile")
    if not isinstance(agent, dict):
        errors.append("agent_profile must be an object")
    else:
        if agent.get("name") not in agent_profile_names():
            errors.append("agent_profile.name is unknown")
        forbidden_tools = agent.get("forbidden_tools")
        if not isinstance(forbidden_tools, list):
            errors.append("agent_profile.forbidden_tools must be a list")
        elif "execute_shell" not in forbidden_tools:
            errors.append("agent profile must forbid execute_shell")

    bridge_spec = bundle.get("bridge_spec")
    if not isinstance(bridge_spec, dict):
        errors.append("bridge_spec must be an object")
    else:
        if bridge_spec.get("kind") != "builder_ii.deepagents_bridge_spec":
            errors.append("bridge_spec.kind must be builder_ii.deepagents_bridge_spec")
        if bridge_spec.get("runtime_enabled") is not False:
            errors.append("bridge_spec.runtime_enabled must be false")
        denied_tools = bridge_spec.get("denied_tools")
        if not isinstance(denied_tools, list):
            errors.append("bridge_spec.denied_tools must be a list")
        else:
            for tool in REQUIRED_DENIED_TOOLS:
                if tool not in denied_tools:
                    errors.append(f"bridge_spec missing required denied tool: {tool}")

    readiness = bundle.get("deepagents_readiness")
    if not isinstance(readiness, dict):
        errors.append("deepagents_readiness must be an object")
    else:
        if readiness.get("kind") != "builder_ii.deepagents_smoke":
            errors.append("deepagents_readiness.kind must be builder_ii.deepagents_smoke")
        if readiness.get("builder_ii_dependency_mode") != "OPTIONAL":
            errors.append("deepagents dependency mode must be OPTIONAL")
        if readiness.get("runtime_execution") != "DISABLED":
            errors.append("deepagents runtime execution must be DISABLED")
        if readiness.get("shell_execution") != "DISABLED":
            errors.append("deepagents shell execution must be DISABLED")

    governance = bundle.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "validation_only":
            errors.append("governance.capability_state must be validation_only")
        if governance.get("runtime_execution") != "DISABLED":
            errors.append("governance.runtime_execution must be DISABLED")
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED")
        if governance.get("agent_construction") != "DISABLED":
            errors.append("governance.agent_construction must be DISABLED")
        if governance.get("shell_execution") != "DISABLED":
            errors.append("governance.shell_execution must be DISABLED")
        if governance.get("artifacts_are_authority") is not False:
            errors.append("governance.artifacts_are_authority must be false")

    bridge_errors = bundle.get("bridge_spec_validation_errors")
    if bridge_errors not in ([], None):
        errors.append("bridge_spec_validation_errors must be empty")

    return errors


def validate_target_bundle_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_target_bundle(data)
