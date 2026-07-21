from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.lifecycle.setup.target_profiles import TargetName
from builder_ii.routing.agent_profiles import AgentProfileName, get_agent_profile

ORCHESTRATION_PLAN_KIND = "builder_ii.orchestration_plan"
ORCHESTRATION_PLAN_SCHEMA_VERSION = 1

_DEFAULT_SEQUENCE: tuple[AgentProfileName, ...] = (
    "repo_mapper",
    "context_planner",
    "patch_planner",
    "verification_planner",
    "handoff_scribe",
)


def create_orchestration_plan(
    *,
    target: TargetName,
    task: str,
    roles: tuple[AgentProfileName, ...] = _DEFAULT_SEQUENCE,
) -> dict[str, Any]:
    role_steps: list[dict[str, Any]] = []
    previous_step_id = ""
    for index, role in enumerate(roles, start=1):
        profile = get_agent_profile(role)
        step_id = f"step_{index}_{role}"
        role_steps.append(
            {
                "step_id": step_id,
                "role": role,
                "purpose": profile.purpose,
                "authority": profile.authority,
                "depends_on": [previous_step_id] if previous_step_id else [],
                "input_context": list(profile.required_context),
                "forbidden_tools": list(profile.forbidden_tools),
                "expected_output": profile.output_contract,
                "handoff_contract": "produce a typed, reviewable artifact or summary for the next role",
                "verification_expectation": "no completion claim without human-captured evidence",
                "runtime_binding": "UNBOUND",
            }
        )
        previous_step_id = step_id

    return {
        "kind": ORCHESTRATION_PLAN_KIND,
        "schema_version": ORCHESTRATION_PLAN_SCHEMA_VERSION,
        "plan_state": "PLANNED_ONLY",
        "target": target,
        "task": task or "governed local engineering orchestration",
        "orchestration_mode": "plan_only",
        "roles": role_steps,
        "handoff": {
            "entry_role": roles[0],
            "exit_role": roles[-1],
            "continuity_requirement": "each role must preserve task, target, authority, risks, and evidence status",
        },
        "governance": {
            "capability_state": "orchestration_plan",
            "runtime_execution": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "deepagents_runtime_start": "DISABLED",
            "agent_construction": "DISABLED",
            "subagent_construction": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_orchestration_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def write_orchestration_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_orchestration_plan(plan), encoding="utf-8")


def validate_orchestration_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["orchestration plan must be a JSON object"]
    if data.get("kind") != ORCHESTRATION_PLAN_KIND:
        errors.append(f"kind must be {ORCHESTRATION_PLAN_KIND}")
    if data.get("schema_version") != ORCHESTRATION_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ORCHESTRATION_PLAN_SCHEMA_VERSION}")
    if data.get("plan_state") != "PLANNED_ONLY":
        errors.append("plan_state must be PLANNED_ONLY")
    if data.get("orchestration_mode") != "plan_only":
        errors.append("orchestration_mode must be plan_only")
    if data.get("target") not in {"generic", "builder", "core"}:
        errors.append("target must be generic, builder, or core")
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task must be a non-empty string")

    roles = data.get("roles")
    if not isinstance(roles, list) or not roles:
        errors.append("roles must be a non-empty list")
    else:
        seen: set[str] = set()
        for index, step in enumerate(roles):
            if not isinstance(step, dict):
                errors.append(f"roles[{index}] must be an object")
                continue
            step_id = step.get("step_id")
            if not isinstance(step_id, str) or not step_id:
                errors.append(f"roles[{index}].step_id must be a non-empty string")
            elif step_id in seen:
                errors.append(f"duplicate step_id: {step_id}")
            else:
                seen.add(step_id)
            if step.get("runtime_binding") != "UNBOUND":
                errors.append(f"roles[{index}].runtime_binding must be UNBOUND")
            for field in (
                "role",
                "purpose",
                "authority",
                "expected_output",
                "handoff_contract",
                "verification_expectation",
            ):
                if not isinstance(step.get(field), str) or not step[field]:
                    errors.append(f"roles[{index}].{field} must be a non-empty string")
            for field in ("depends_on", "input_context", "forbidden_tools"):
                if not isinstance(step.get(field), list) or any(
                    not isinstance(item, str) for item in step.get(field, [])
                ):
                    errors.append(f"roles[{index}].{field} must be a list of strings")
            if "execute_shell" not in step.get("forbidden_tools", []):
                errors.append(f"roles[{index}].forbidden_tools must include execute_shell")

    handoff = data.get("handoff")
    if not isinstance(handoff, dict):
        errors.append("handoff must be an object")
    else:
        for field in ("entry_role", "exit_role", "continuity_requirement"):
            if not isinstance(handoff.get(field), str) or not handoff[field]:
                errors.append(f"handoff.{field} must be a non-empty string")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "orchestration_plan":
            errors.append("governance.capability_state must be orchestration_plan")
        for key in (
            "runtime_execution",
            "goose_runtime_start",
            "deepagents_runtime_start",
            "agent_construction",
            "subagent_construction",
            "model_execution",
            "shell_execution",
            "source_writes",
            "memory_mutation",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_orchestration_plan_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_orchestration_plan(data)
