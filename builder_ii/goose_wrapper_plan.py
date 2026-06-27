from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.goose_projection import GOOSE_PROJECTION_KIND, validate_goose_projection

GOOSE_WRAPPER_PLAN_KIND = "builder_ii.goose_wrapper_plan"
GOOSE_WRAPPER_PLAN_SCHEMA_VERSION = 1


def create_goose_wrapper_plan(projection: dict[str, Any]) -> dict[str, Any]:
    projection_errors = validate_goose_projection(projection)
    if projection_errors:
        raise ValueError("goose projection is invalid: " + "; ".join(projection_errors))

    surface = projection["goose_native_surface"]
    env = surface["env"]
    argv = ["goose", "session", "--recipe", surface["recipe_path"], "--name", surface["session_name"]]

    return {
        "kind": GOOSE_WRAPPER_PLAN_KIND,
        "schema_version": GOOSE_WRAPPER_PLAN_SCHEMA_VERSION,
        "plan_state": "PLANNED_ONLY",
        "source_goose_projection_kind": GOOSE_PROJECTION_KIND,
        "task": projection["task"],
        "target": projection["target"],
        "repo_path": projection["repo_path"],
        "agent_profile": projection["agent_profile"],
        "authority_mode": projection["authority_mode"],
        "operator_launch": {
            "argv": argv,
            "working_directory": surface["working_directory"],
            "env_keys": sorted(env.keys()),
            "env_preview": {key: env[key] for key in sorted(env.keys()) if key.startswith("BUILDER_") or key.startswith("GOOSE_")},
            "requires_operator_execution": True,
            "executes_now": False,
        },
        "handoff": {
            "next_action": "operator may review this wrapper plan before explicitly launching Codename Goose",
            "evidence_required_after_launch": projection.get("required_evidence", []),
        },
        "governance": {
            "capability_state": "goose_wrapper_plan",
            "runtime_execution": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_goose_wrapper_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def write_goose_wrapper_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_goose_wrapper_plan(plan), encoding="utf-8")


def validate_goose_wrapper_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["goose wrapper plan must be a JSON object"]
    if data.get("kind") != GOOSE_WRAPPER_PLAN_KIND:
        errors.append(f"kind must be {GOOSE_WRAPPER_PLAN_KIND}")
    if data.get("schema_version") != GOOSE_WRAPPER_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_WRAPPER_PLAN_SCHEMA_VERSION}")
    if data.get("plan_state") != "PLANNED_ONLY":
        errors.append("plan_state must be PLANNED_ONLY")
    if data.get("source_goose_projection_kind") != GOOSE_PROJECTION_KIND:
        errors.append(f"source_goose_projection_kind must be {GOOSE_PROJECTION_KIND}")
    for field in ("task", "target", "repo_path", "agent_profile", "authority_mode"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")

    launch = data.get("operator_launch")
    if not isinstance(launch, dict):
        errors.append("operator_launch must be an object")
    else:
        argv = launch.get("argv")
        if not isinstance(argv, list) or any(not isinstance(item, str) or not item for item in argv):
            errors.append("operator_launch.argv must be a list of non-empty strings")
        if not isinstance(launch.get("working_directory"), str) or not launch["working_directory"]:
            errors.append("operator_launch.working_directory must be a non-empty string")
        if not isinstance(launch.get("env_keys"), list) or any(not isinstance(item, str) or not item for item in launch.get("env_keys", [])):
            errors.append("operator_launch.env_keys must be a list of non-empty strings")
        if not isinstance(launch.get("env_preview"), dict):
            errors.append("operator_launch.env_preview must be an object")
        if launch.get("requires_operator_execution") is not True:
            errors.append("operator_launch.requires_operator_execution must be true")
        if launch.get("executes_now") is not False:
            errors.append("operator_launch.executes_now must be false")

    handoff = data.get("handoff")
    if not isinstance(handoff, dict):
        errors.append("handoff must be an object")
    else:
        if not isinstance(handoff.get("next_action"), str) or not handoff["next_action"]:
            errors.append("handoff.next_action must be a non-empty string")
        evidence = handoff.get("evidence_required_after_launch")
        if not isinstance(evidence, list) or any(not isinstance(item, str) for item in evidence):
            errors.append("handoff.evidence_required_after_launch must be a list of strings")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "goose_wrapper_plan":
            errors.append("governance.capability_state must be goose_wrapper_plan")
        for key in ("runtime_execution", "goose_runtime_start", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_goose_wrapper_plan_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_goose_wrapper_plan(data)
