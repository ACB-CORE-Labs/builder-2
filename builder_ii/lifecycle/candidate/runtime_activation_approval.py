from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.adapters.goose.goose_wrapper_plan import GOOSE_WRAPPER_PLAN_KIND, validate_goose_wrapper_plan

RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND = "builder_ii.runtime_activation_approval_spec"
RUNTIME_ACTIVATION_APPROVAL_SPEC_SCHEMA_VERSION = 1


def create_runtime_activation_approval_spec(
    wrapper_plan: dict[str, Any],
    *,
    requested_by: str = "operator",
) -> dict[str, Any]:
    wrapper_errors = validate_goose_wrapper_plan(wrapper_plan)
    if wrapper_errors:
        raise ValueError("goose wrapper plan is invalid: " + "; ".join(wrapper_errors))

    return {
        "kind": RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND,
        "schema_version": RUNTIME_ACTIVATION_APPROVAL_SPEC_SCHEMA_VERSION,
        "approval_state": "PROPOSED_ONLY",
        "source_goose_wrapper_plan_kind": GOOSE_WRAPPER_PLAN_KIND,
        "requested_by": requested_by,
        "task": wrapper_plan["task"],
        "target": wrapper_plan["target"],
        "repo_path": wrapper_plan["repo_path"],
        "agent_profile": wrapper_plan["agent_profile"],
        "authority_mode": wrapper_plan["authority_mode"],
        "approval_boundary": {
            "runtime_activation": "NOT_AUTHORIZED",
            "model_execution": "NOT_AUTHORIZED",
            "operator_approval_required": True,
            "approval_evidence_ref": None,
            "approval_actor": "human_operator",
        },
        "preconditions": [
            "wrapper plan reviewed by operator",
            "target repository and working directory confirmed",
            "model/provider policy reviewed",
            "verification remains NOT_RUN until captured as evidence",
        ],
        "post_approval_requirements": [
            "capture runtime transcript or receipt artifact",
            "capture planned verification output before promotion",
            "record handoff state after operator action",
        ],
        "operator_plan_summary": {
            "argv_preview": list(wrapper_plan["operator_launch"]["argv"]),
            "working_directory": wrapper_plan["operator_launch"]["working_directory"],
            "env_keys": list(wrapper_plan["operator_launch"]["env_keys"]),
            "executes_now": False,
        },
        "governance": {
            "capability_state": "runtime_activation_approval_spec",
            "runtime_execution": "DISABLED",
            "runtime_activation": "NOT_AUTHORIZED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_runtime_activation_approval_spec(spec: dict[str, Any]) -> str:
    return json_lib.dumps(spec, indent=2, sort_keys=True) + "\n"


def write_runtime_activation_approval_spec(spec: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_runtime_activation_approval_spec(spec), encoding="utf-8")


def _string_list_errors(value: Any, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_runtime_activation_approval_spec(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["runtime activation approval spec must be a JSON object"]
    if data.get("kind") != RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND:
        errors.append(f"kind must be {RUNTIME_ACTIVATION_APPROVAL_SPEC_KIND}")
    if data.get("schema_version") != RUNTIME_ACTIVATION_APPROVAL_SPEC_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RUNTIME_ACTIVATION_APPROVAL_SPEC_SCHEMA_VERSION}")
    if data.get("approval_state") != "PROPOSED_ONLY":
        errors.append("approval_state must be PROPOSED_ONLY")
    if data.get("source_goose_wrapper_plan_kind") != GOOSE_WRAPPER_PLAN_KIND:
        errors.append(f"source_goose_wrapper_plan_kind must be {GOOSE_WRAPPER_PLAN_KIND}")
    for field in ("requested_by", "task", "target", "repo_path", "agent_profile", "authority_mode"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")

    boundary = data.get("approval_boundary")
    if not isinstance(boundary, dict):
        errors.append("approval_boundary must be an object")
    else:
        if boundary.get("runtime_activation") != "NOT_AUTHORIZED":
            errors.append("approval_boundary.runtime_activation must be NOT_AUTHORIZED")
        if boundary.get("model_execution") != "NOT_AUTHORIZED":
            errors.append("approval_boundary.model_execution must be NOT_AUTHORIZED")
        if boundary.get("operator_approval_required") is not True:
            errors.append("approval_boundary.operator_approval_required must be true")
        if boundary.get("approval_evidence_ref") is not None:
            errors.append("approval_boundary.approval_evidence_ref must be null")
        if boundary.get("approval_actor") != "human_operator":
            errors.append("approval_boundary.approval_actor must be human_operator")

    errors.extend(_string_list_errors(data.get("preconditions"), "preconditions"))
    errors.extend(_string_list_errors(data.get("post_approval_requirements"), "post_approval_requirements"))

    summary = data.get("operator_plan_summary")
    if not isinstance(summary, dict):
        errors.append("operator_plan_summary must be an object")
    else:
        if not isinstance(summary.get("argv_preview"), list) or any(
            not isinstance(item, str) or not item for item in summary.get("argv_preview", [])
        ):
            errors.append("operator_plan_summary.argv_preview must be a list of non-empty strings")
        if not isinstance(summary.get("working_directory"), str) or not summary["working_directory"]:
            errors.append("operator_plan_summary.working_directory must be a non-empty string")
        if not isinstance(summary.get("env_keys"), list) or any(
            not isinstance(item, str) or not item for item in summary.get("env_keys", [])
        ):
            errors.append("operator_plan_summary.env_keys must be a list of non-empty strings")
        if summary.get("executes_now") is not False:
            errors.append("operator_plan_summary.executes_now must be false or NOT_AUTHORIZED")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "runtime_activation_approval_spec":
            errors.append("governance.capability_state must be runtime_activation_approval_spec")
        if governance.get("runtime_activation") != "NOT_AUTHORIZED":
            errors.append("governance.runtime_activation must be NOT_AUTHORIZED")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_runtime_activation_approval_spec_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_runtime_activation_approval_spec(data)
