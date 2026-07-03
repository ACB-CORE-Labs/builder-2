from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.agent_profiles import (
    AgentProfileName,
    create_agent_profile_record,
    validate_agent_profile_record,
)
from builder_ii.config import Settings
from builder_ii.profile_resolution import (
    ProfileResolver,
)
from builder_ii.target_profiles import (
    TargetName,
    validate_target_profile_artifact,
)
from builder_ii.verification_profiles import (
    VerificationProfileName,
    validate_profile_artifact,
)

SESSION_WORKFLOW_PLAN_KIND = "builder_ii.session_workflow_plan"
SESSION_WORKFLOW_PLAN_SCHEMA_VERSION = 1


def create_session_workflow_plan(
    settings: Settings,
    target_name: TargetName,
    *,
    agent_profile_name: AgentProfileName | None = None,
    prompt_profile_name: str | None = None,
    verification_profile_name: VerificationProfileName | None = None,
    repo_path: str | None = None,
) -> dict[str, Any]:
    if repo_path is None and target_name == "core" and not settings.core_repo.exists():
        repo_path = str(settings.project_root)
    # Use the unified profile resolver
    resolver = ProfileResolver(settings)
    resolved = resolver.resolve(
        target_name=target_name,
        agent_profile_name=agent_profile_name,
        prompt_profile_name=prompt_profile_name,
        verification_profile_name=verification_profile_name,
        repo_path=repo_path,
    )

    t_profile_dict = resolved.target_profile.to_artifact_dict()
    t_profile_dict["repo"] = resolved.repo_path
    t_profile_dict["context_defaults"] = list(resolved.context_defaults)

    a_profile = resolved.agent_profile
    p_profile = resolved.prompt_profile
    v_profile = resolved.verification_profile
    resolved_repo = resolved.repo_path

    # Assemble planned commands
    planned_commands = [
        f"builder-context pack --target {target_name}",
        "builder start --task 'local development session' --mode coding",
    ]
    planned_commands.extend(v_profile.proposed_commands)
    planned_commands.append(f"builder-handoff bundle --bundle-name handoff-session-{target_name}")

    # Build complete session plan artifact
    return {
        "kind": SESSION_WORKFLOW_PLAN_KIND,
        "schema_version": SESSION_WORKFLOW_PLAN_SCHEMA_VERSION,
        "target_profile": t_profile_dict,
        "repo_path": resolved_repo,
        "selected_agent_profile": create_agent_profile_record(
            a_profile, resolved.target_profile, task="governed session"
        ),
        "selected_prompt_profile": p_profile.to_dict(),
        "selected_verification_profile": v_profile.to_artifact_dict(target=target_name, task="governed session"),
        "planned_artifacts": [
            ".builder/session-plan.json",
            ".builder/context-pack.md",
            "docs/HANDOFF-session.md",
        ],
        "planned_commands": planned_commands,
        "governance": {
            "capability_state": "session_workflow_plan",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def validate_session_workflow_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["session workflow plan must be a JSON object"]

    if data.get("kind") != SESSION_WORKFLOW_PLAN_KIND:
        errors.append(f"kind must be {SESSION_WORKFLOW_PLAN_KIND}")
    if data.get("schema_version") != SESSION_WORKFLOW_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {SESSION_WORKFLOW_PLAN_SCHEMA_VERSION}")

    # Validate target profile
    t_profile = data.get("target_profile")
    if not isinstance(t_profile, dict):
        errors.append("target_profile must be a dictionary")
    else:
        errors.extend(validate_target_profile_artifact(t_profile))

    # Validate agent profile
    a_profile = data.get("selected_agent_profile")
    if not isinstance(a_profile, dict):
        errors.append("selected_agent_profile must be a dictionary")
    else:
        errors.extend(validate_agent_profile_record(a_profile))

    # Validate prompt profile
    p_profile = data.get("selected_prompt_profile")
    if not isinstance(p_profile, dict):
        errors.append("selected_prompt_profile must be a dictionary")
    else:
        if not p_profile.get("name") or not isinstance(p_profile.get("name"), str):
            errors.append("selected_prompt_profile.name must be a non-empty string")
        if not p_profile.get("description") or not isinstance(p_profile.get("description"), str):
            errors.append("selected_prompt_profile.description must be a non-empty string")
        if not p_profile.get("system_prompt") or not isinstance(p_profile.get("system_prompt"), str):
            errors.append("selected_prompt_profile.system_prompt must be a non-empty string")
        compat = p_profile.get("compatible_targets")
        if not isinstance(compat, list) or any(not isinstance(t, str) for t in compat):
            errors.append("selected_prompt_profile.compatible_targets must be a list of strings")

    # Validate verification profile
    v_profile = data.get("selected_verification_profile")
    if not isinstance(v_profile, dict):
        errors.append("selected_verification_profile must be a dictionary")
    else:
        errors.extend(validate_profile_artifact(v_profile))

    # Validate planned fields
    if not isinstance(data.get("planned_artifacts"), list) or any(
        not isinstance(a, str) for a in data.get("planned_artifacts", [])
    ):
        errors.append("planned_artifacts must be a list of strings")
    if not isinstance(data.get("planned_commands"), list) or any(
        not isinstance(c, str) for c in data.get("planned_commands", [])
    ):
        errors.append("planned_commands must be a list of strings")

    # Validate governance
    gov = data.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        if gov.get("capability_state") != "session_workflow_plan":
            errors.append("governance.capability_state must be session_workflow_plan")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if gov.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if gov.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if gov.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def validate_session_workflow_plan_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_session_workflow_plan(data)
