from __future__ import annotations

from typing import Any

from builder_ii.target_profiles import target_names

READONLY_INSPECTION_PROMOTION_SPEC_KIND = "builder_ii.readonly_inspection_promotion_spec"
READONLY_INSPECTION_PROMOTION_SPEC_SCHEMA_VERSION = 1

_REQUIRED_GATES = (
    "explicit_operator_paths",
    "target_profile_bound",
    "verification_profile_bound",
    "git_state_bound",
    "artifact_output_declared",
    "denied_actions_tested",
    "handoff_record_required",
)
_DENIED_ACTIONS = (
    "source_writes",
    "shell_execution",
    "model_execution",
    "network_access",
    "mcp_execution",
    "deepagents_runtime",
    "git_mutation",
    "commit_push",
    "memory_mutation",
)


def create_readonly_inspection_promotion_spec(*, target: str = "builder", capability_name: str = "bounded_readonly_inspection") -> dict[str, Any]:
    return {
        "kind": READONLY_INSPECTION_PROMOTION_SPEC_KIND,
        "schema_version": READONLY_INSPECTION_PROMOTION_SPEC_SCHEMA_VERSION,
        "capability_name": capability_name,
        "target": target,
        "candidate_state": "DESIGN_ONLY",
        "current_state": "DISABLED",
        "runtime_promotion": "BLOCKED_UNTIL_APPROVED",
        "required_gates": list(_REQUIRED_GATES),
        "denied_actions": list(_DENIED_ACTIONS),
        "read_boundary": {
            "repo_paths": "EXPLICIT_OPERATOR_INPUT_REQUIRED",
            "file_allowlist": "EXPLICIT_OPERATOR_INPUT_REQUIRED",
            "git_state": "EXPLICIT_ARTIFACT_REQUIRED",
            "artifact_output": "EXPLICIT_OPERATOR_OUTPUT_REQUIRED",
        },
        "required_artifacts": [
            "builder_ii.target_profile",
            "builder_ii.verification_profile",
            "builder_ii.context_pack_record",
            "builder_ii.agent_profile_record",
            "builder_ii.git_state_record",
            "builder_ii.promotion_readiness_record",
            "builder_ii.promotion_decision_record",
        ],
        "performed_actions": [],
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "governance": {
            "capability_state": "readonly_inspection_promotion_spec",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def _string_list_errors(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{field} must be a non-empty list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_readonly_inspection_promotion_spec(spec: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["readonly inspection promotion spec must be a JSON object"]
    if spec.get("kind") != READONLY_INSPECTION_PROMOTION_SPEC_KIND:
        errors.append(f"kind must be {READONLY_INSPECTION_PROMOTION_SPEC_KIND}")
    if spec.get("schema_version") != READONLY_INSPECTION_PROMOTION_SPEC_SCHEMA_VERSION:
        errors.append(f"schema_version must be {READONLY_INSPECTION_PROMOTION_SPEC_SCHEMA_VERSION}")
    if not isinstance(spec.get("capability_name"), str) or not spec["capability_name"]:
        errors.append("capability_name must be a non-empty string")
    if spec.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    if spec.get("candidate_state") != "DESIGN_ONLY":
        errors.append("candidate_state must be DESIGN_ONLY")
    if spec.get("current_state") != "DISABLED":
        errors.append("current_state must be DISABLED")
    if spec.get("runtime_promotion") != "BLOCKED_UNTIL_APPROVED":
        errors.append("runtime_promotion must be BLOCKED_UNTIL_APPROVED")
    errors.extend(_string_list_errors(spec.get("required_gates"), field="required_gates"))
    errors.extend(_string_list_errors(spec.get("denied_actions"), field="denied_actions"))
    for gate in _REQUIRED_GATES:
        if gate not in spec.get("required_gates", []):
            errors.append(f"missing required gate: {gate}")
    for action in _DENIED_ACTIONS:
        if action not in spec.get("denied_actions", []):
            errors.append(f"missing denied action: {action}")
    boundary = spec.get("read_boundary")
    if not isinstance(boundary, dict):
        errors.append("read_boundary must be an object")
    else:
        for key in ("repo_paths", "file_allowlist", "git_state", "artifact_output"):
            if not isinstance(boundary.get(key), str) or not boundary[key]:
                errors.append(f"read_boundary.{key} must be a non-empty string")
    errors.extend(_string_list_errors(spec.get("required_artifacts"), field="required_artifacts"))
    if spec.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    for key in ("grants_runtime_authority", "grants_action_authority"):
        if spec.get(key) is not False:
            errors.append(f"{key} must be false")
    governance = spec.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors
