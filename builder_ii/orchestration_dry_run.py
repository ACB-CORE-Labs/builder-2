from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.goose_projection import create_goose_projection, validate_goose_projection
from builder_ii.goose_wrapper_plan import create_goose_wrapper_plan, validate_goose_wrapper_plan
from builder_ii.orchestration_plan import validate_orchestration_plan
from builder_ii.session_config import create_session_configuration, validate_session_configuration

ORCHESTRATION_DRY_RUN_KIND = "builder_ii.orchestration_dry_run"
ORCHESTRATION_DRY_RUN_SCHEMA_VERSION = 1


def create_orchestration_dry_run(
    settings: Settings,
    orchestration_plan: dict[str, Any],
    *,
    repo_path: str,
    verification_profile_name: str = "generic_basic",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    plan_errors = validate_orchestration_plan(orchestration_plan)
    if plan_errors:
        raise ValueError("orchestration plan is invalid: " + "; ".join(plan_errors))

    target = orchestration_plan["target"]
    task = orchestration_plan["task"]
    steps: list[dict[str, Any]] = []

    for planned_step in orchestration_plan["roles"]:
        role = planned_step["role"]
        config = create_session_configuration(
            settings,
            target,
            agent_profile_name=role,
            verification_profile_name=verification_profile_name,
            repo_path=repo_path,
            task=task,
            generic_repo=generic_repo,
        )
        projection = create_goose_projection(settings, config)
        wrapper_plan = create_goose_wrapper_plan(projection)
        config_errors = validate_session_configuration(config)
        projection_errors = validate_goose_projection(projection)
        wrapper_errors = validate_goose_wrapper_plan(wrapper_plan)
        steps.append(
            {
                "step_id": planned_step["step_id"],
                "role": role,
                "depends_on": list(planned_step.get("depends_on", [])),
                "session_configuration_kind": config["kind"],
                "goose_projection_kind": projection["kind"],
                "goose_wrapper_plan_kind": wrapper_plan["kind"],
                "session_name": projection["goose_native_surface"]["session_name"],
                "working_directory": wrapper_plan["operator_launch"]["working_directory"],
                "operator_review_required": wrapper_plan["operator_launch"]["requires_operator_execution"],
                "executes_now": wrapper_plan["operator_launch"]["executes_now"],
                "validation_errors": config_errors + projection_errors + wrapper_errors,
                "handoff_contract": planned_step["handoff_contract"],
            }
        )

    return {
        "kind": ORCHESTRATION_DRY_RUN_KIND,
        "schema_version": ORCHESTRATION_DRY_RUN_SCHEMA_VERSION,
        "dry_run_state": "PLANNED_ONLY",
        "source_orchestration_plan_kind": orchestration_plan["kind"],
        "target": target,
        "task": task,
        "repo_path": repo_path,
        "steps": steps,
        "final_handoff": {
            "summary": "prepared per-role session configuration, Goose projection, and wrapper-plan surfaces",
            "next_operator_action": "review role plans and decide whether to continue with explicit human-controlled work",
            "verification_status": "NOT_RUN",
        },
        "governance": {
            "capability_state": "orchestration_dry_run",
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


def dumps_orchestration_dry_run(dry_run: dict[str, Any]) -> str:
    return json_lib.dumps(dry_run, indent=2, sort_keys=True) + "\n"


def write_orchestration_dry_run(dry_run: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_orchestration_dry_run(dry_run), encoding="utf-8")


def validate_orchestration_dry_run(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["orchestration dry run must be a JSON object"]
    if data.get("kind") != ORCHESTRATION_DRY_RUN_KIND:
        errors.append(f"kind must be {ORCHESTRATION_DRY_RUN_KIND}")
    if data.get("schema_version") != ORCHESTRATION_DRY_RUN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ORCHESTRATION_DRY_RUN_SCHEMA_VERSION}")
    if data.get("dry_run_state") != "PLANNED_ONLY":
        errors.append("dry_run_state must be PLANNED_ONLY")
    for field in ("source_orchestration_plan_kind", "target", "task", "repo_path"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")

    steps = data.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("steps must be a non-empty list")
    else:
        for index, step in enumerate(steps):
            if not isinstance(step, dict):
                errors.append(f"steps[{index}] must be an object")
                continue
            for field in (
                "step_id",
                "role",
                "session_configuration_kind",
                "goose_projection_kind",
                "goose_wrapper_plan_kind",
                "session_name",
                "working_directory",
                "handoff_contract",
            ):
                if not isinstance(step.get(field), str) or not step[field]:
                    errors.append(f"steps[{index}].{field} must be a non-empty string")
            if not isinstance(step.get("depends_on"), list) or any(
                not isinstance(item, str) for item in step.get("depends_on", [])
            ):
                errors.append(f"steps[{index}].depends_on must be a list of strings")
            if step.get("operator_review_required") is not True:
                errors.append(f"steps[{index}].operator_review_required must be true")
            if step.get("executes_now") is not False:
                errors.append(f"steps[{index}].executes_now must be false")
            if not isinstance(step.get("validation_errors"), list):
                errors.append(f"steps[{index}].validation_errors must be a list")
            elif step["validation_errors"]:
                errors.append(f"steps[{index}].validation_errors must be empty")

    final_handoff = data.get("final_handoff")
    if not isinstance(final_handoff, dict):
        errors.append("final_handoff must be an object")
    else:
        for field in ("summary", "next_operator_action", "verification_status"):
            if not isinstance(final_handoff.get(field), str) or not final_handoff[field]:
                errors.append(f"final_handoff.{field} must be a non-empty string")
        if final_handoff.get("verification_status") != "NOT_RUN":
            errors.append("final_handoff.verification_status must be NOT_RUN")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "orchestration_dry_run":
            errors.append("governance.capability_state must be orchestration_dry_run")
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
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_orchestration_dry_run_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_orchestration_dry_run(data)
