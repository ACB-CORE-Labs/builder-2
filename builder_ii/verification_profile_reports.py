from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any, Literal

from builder_ii.config import Settings
from builder_ii.profile_resolution import (
    AgentProfileName,
    ProfileResolver,
    TargetName,
    VerificationProfileName,
)
from builder_ii.target_profiles import validate_target_profile_artifact
from builder_ii.agent_profiles import validate_agent_profile_record
from builder_ii.verification_profiles import validate_profile_artifact
from builder_ii.goose_readonly_session import validate_goose_readonly_session_plan

VERIFICATION_PROFILE_REPORT_KIND = "builder_ii.verification_profile_report"
VERIFICATION_PROFILE_REPORT_SCHEMA_VERSION = 1

CheckClassification = Literal["required", "optional", "manual", "blocked"]

_ALLOWED_CLASSIFICATIONS = {"required", "optional", "manual", "blocked"}


def _planned_check(*, index: int, command_preview: str, evidence_required: str) -> dict[str, Any]:
    return {
        "name": f"verification_check_{index + 1}",
        "classification": "required",
        "command_preview": command_preview,
        "evidence_required": evidence_required,
        "execution_state": "NOT_RUN",
        "human_operator_required": True,
        "completed_evidence_ref": None,
    }


def create_verification_profile_report(
    settings: Settings,
    target_name: TargetName,
    *,
    agent_profile_name: AgentProfileName | None = None,
    prompt_profile_name: str | None = None,
    verification_profile_name: VerificationProfileName | None = None,
    repo_path: str | None = None,
    task: str = "",
    goose_readonly_session_plan: dict[str, Any] | None = None,
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a deterministic verification planning report.

    This function renders planned verification checks from a resolved
    verification profile. It never executes commands and never treats planned
    checks as completed evidence.
    """

    resolver = ProfileResolver(settings, generic_repo=generic_repo)
    resolved = resolver.resolve(
        target_name=target_name,
        agent_profile_name=agent_profile_name,
        prompt_profile_name=prompt_profile_name,
        verification_profile_name=verification_profile_name,
        repo_path=repo_path,
    )
    resolved_dict = resolved.to_dict()

    evidence = list(resolved.verification_profile.required_evidence)
    checks = [
        _planned_check(
            index=index,
            command_preview=command,
            evidence_required=evidence[index] if index < len(evidence) else "operator-captured verification evidence",
        )
        for index, command in enumerate(resolved.verification_profile.proposed_commands)
    ]

    report: dict[str, Any] = {
        "kind": VERIFICATION_PROFILE_REPORT_KIND,
        "schema_version": VERIFICATION_PROFILE_REPORT_SCHEMA_VERSION,
        "task": task or "governed verification profile report",
        "target_profile": resolved_dict["target_profile"],
        "repo_path": resolved.repo_path,
        "selected_agent_profile": resolved_dict["selected_agent_profile"],
        "selected_prompt_profile": resolved_dict["selected_prompt_profile"],
        "selected_verification_profile": resolved_dict["selected_verification_profile"],
        "goose_readonly_session_plan": goose_readonly_session_plan,
        "planned_checks": checks,
        "required_evidence": evidence,
        "report_state": "PLANNED_ONLY",
        "completed_verification": False,
        "governance": {
            "capability_state": "verification_profile_report",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "executes_commands": False,
            "report_is_completed_evidence": False,
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    return report


def _validate_prompt_profile(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["selected_prompt_profile must be a dictionary"]
    if not isinstance(value.get("name"), str) or not value["name"]:
        errors.append("selected_prompt_profile.name must be a non-empty string")
    if not isinstance(value.get("description"), str) or not value["description"]:
        errors.append("selected_prompt_profile.description must be a non-empty string")
    if not isinstance(value.get("system_prompt"), str) or not value["system_prompt"]:
        errors.append("selected_prompt_profile.system_prompt must be a non-empty string")
    compatible = value.get("compatible_targets")
    if not isinstance(compatible, list) or any(not isinstance(item, str) for item in compatible):
        errors.append("selected_prompt_profile.compatible_targets must be a list of strings")
    return errors


def _validate_planned_checks(value: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list) or not value:
        return ["planned_checks must be a non-empty list"]
    for index, item in enumerate(value):
        prefix = f"planned_checks[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not isinstance(item.get("name"), str) or not item["name"]:
            errors.append(f"{prefix}.name must be a non-empty string")
        if item.get("classification") not in _ALLOWED_CLASSIFICATIONS:
            errors.append(f"{prefix}.classification must be one of: blocked, manual, optional, required")
        if not isinstance(item.get("command_preview"), str) or not item["command_preview"]:
            errors.append(f"{prefix}.command_preview must be a non-empty string")
        if not isinstance(item.get("evidence_required"), str) or not item["evidence_required"]:
            errors.append(f"{prefix}.evidence_required must be a non-empty string")
        if item.get("execution_state") != "NOT_RUN":
            errors.append(f"{prefix}.execution_state must be NOT_RUN")
        if item.get("human_operator_required") is not True:
            errors.append(f"{prefix}.human_operator_required must be true")
        if item.get("completed_evidence_ref") is not None:
            errors.append(f"{prefix}.completed_evidence_ref must be null for planned-only reports")
    return errors


def validate_verification_profile_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["verification profile report must be a JSON object"]

    if data.get("kind") != VERIFICATION_PROFILE_REPORT_KIND:
        errors.append(f"kind must be {VERIFICATION_PROFILE_REPORT_KIND}")
    if data.get("schema_version") != VERIFICATION_PROFILE_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_PROFILE_REPORT_SCHEMA_VERSION}")

    target_profile = data.get("target_profile")
    if not isinstance(target_profile, dict):
        errors.append("target_profile must be a dictionary")
    else:
        errors.extend(validate_target_profile_artifact(target_profile))

    agent_profile = data.get("selected_agent_profile")
    if not isinstance(agent_profile, dict):
        errors.append("selected_agent_profile must be a dictionary")
    else:
        errors.extend(validate_agent_profile_record(agent_profile))

    errors.extend(_validate_prompt_profile(data.get("selected_prompt_profile")))

    verification_profile = data.get("selected_verification_profile")
    if not isinstance(verification_profile, dict):
        errors.append("selected_verification_profile must be a dictionary")
    else:
        errors.extend(validate_profile_artifact(verification_profile))

    goose_plan = data.get("goose_readonly_session_plan")
    if goose_plan is not None:
        if not isinstance(goose_plan, dict):
            errors.append("goose_readonly_session_plan must be a dictionary when present")
        else:
            errors.extend(validate_goose_readonly_session_plan(goose_plan))

    errors.extend(_validate_planned_checks(data.get("planned_checks")))

    evidence = data.get("required_evidence")
    if not isinstance(evidence, list) or any(not isinstance(item, str) or not item for item in evidence):
        errors.append("required_evidence must be a list of non-empty strings")

    if data.get("report_state") != "PLANNED_ONLY":
        errors.append("report_state must be PLANNED_ONLY")
    if data.get("completed_verification") is not False:
        errors.append("completed_verification must be false")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "verification_profile_report":
            errors.append("governance.capability_state must be verification_profile_report")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("executes_commands") is not False:
            errors.append("governance.executes_commands must be false")
        if governance.get("report_is_completed_evidence") is not False:
            errors.append("governance.report_is_completed_evidence must be false")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    return errors


def validate_verification_profile_report_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_verification_profile_report(data)
