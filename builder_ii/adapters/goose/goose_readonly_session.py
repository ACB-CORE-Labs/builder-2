from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.core.config import Settings
from builder_ii.core.context_pack import validate_context_pack_record
from builder_ii.lifecycle.candidate.verification_profiles import VerificationProfileName, validate_profile_artifact
from builder_ii.lifecycle.setup.profile_resolution import ProfileResolver, TargetName
from builder_ii.lifecycle.setup.target_profiles import validate_target_profile_artifact
from builder_ii.routing.agent_profiles import AgentProfileName, validate_agent_profile_record

GOOSE_READONLY_SESSION_PLAN_KIND = "builder_ii.goose_readonly_session_plan"
GOOSE_READONLY_SESSION_PLAN_SCHEMA_VERSION = 1


def render_goose_instructions(
    target_profile: dict[str, Any],
    agent_profile: dict[str, Any],
    prompt_profile: dict[str, Any],
    verification_profile: dict[str, Any],
    context_pack: dict[str, Any] | None = None,
) -> str:
    # Extract fields from agent_profile (may be nested inside profile record)
    agent_data = agent_profile.get("profile") or agent_profile
    agent_name = agent_data.get("name", "")
    agent_description = agent_data.get("description", "")
    agent_purpose = agent_data.get("purpose", "")
    agent_authority = agent_data.get("authority", "")
    agent_allowed_tools = agent_data.get("allowed_tools", [])
    agent_forbidden_tools = agent_data.get("forbidden_tools", [])
    agent_hitl = agent_data.get("hitl_required_for", [])
    agent_contract = agent_data.get("output_contract", "")

    # Extract fields from prompt_profile
    prompt_name = prompt_profile.get("name", "")
    prompt_description = prompt_profile.get("description", "")
    system_prompt = prompt_profile.get("system_prompt", "")

    # Extract fields from target_profile
    target_name = target_profile.get("name", "")
    target_repo = target_profile.get("repo", "")
    target_description = target_profile.get("description", "")
    target_principles = target_profile.get("principles", [])

    # Extract fields from verification_profile
    verification_name = verification_profile.get("name", "")
    verification_description = verification_profile.get("description", "")
    verification_purpose = verification_profile.get("purpose", "")
    verification_commands = verification_profile.get("proposed_commands", [])
    verification_evidence = verification_profile.get("required_evidence", [])

    # Resolve context files
    context_files = []
    context_path = ""
    if context_pack:
        context_files = context_pack.get("selected_files", [])
        context_path = context_pack.get("markdown_path", "")
    else:
        context_files = target_profile.get("context_defaults", [])

    # Build Goose instructions template
    lines = [
        "========================================================================",
        "GOOSE GOVERNED READ-ONLY SESSION INSTRUCTIONS",
        "========================================================================",
        f"Target Profile: {target_name}",
        f"Repository Path: {target_repo}",
        f"Description: {target_description}",
    ]
    if target_principles:
        lines.append("Target Principles:")
        for principle in target_principles:
            lines.append(f"  - {principle}")

    lines.extend(
        [
            "",
            "------------------------------------------------------------------------",
            f"Agent Profile: {agent_name}",
            f"Description: {agent_description}",
            f"Purpose: {agent_purpose}",
            f"Authority level: {agent_authority} (READ-ONLY)",
            "------------------------------------------------------------------------",
        ]
    )
    if agent_allowed_tools:
        lines.append(f"Allowed Tools: {', '.join(agent_allowed_tools)}")
    if agent_forbidden_tools:
        lines.append(f"Forbidden Tools: {', '.join(agent_forbidden_tools)}")
    if agent_hitl:
        lines.append("HITL Required For:")
        for item in agent_hitl:
            lines.append(f"  - {item}")
    if agent_contract:
        lines.append(f"Output Contract: {agent_contract}")

    lines.extend(
        [
            "",
            "------------------------------------------------------------------------",
            f"Prompt Profile: {prompt_name}",
            f"Description: {prompt_description}",
            "System prompt instruction:",
            "------------------------------------------------------------------------",
            system_prompt,
            "",
            "------------------------------------------------------------------------",
            "Context Pack Details:",
            "------------------------------------------------------------------------",
        ]
    )
    if context_path:
        lines.append(f"Context Pack Manifest: {context_path}")
    lines.append("Selected/Default files to inspect:")
    for path in context_files:
        lines.append(f"  - {path}")

    lines.extend(
        [
            "",
            "------------------------------------------------------------------------",
            f"Verification Profile: {verification_name}",
            f"Description: {verification_description}",
            f"Purpose: {verification_purpose}",
            "Proposed Verification Commands:",
            "------------------------------------------------------------------------",
        ]
    )
    for cmd in verification_commands:
        lines.append(f"  - {cmd}")
    if verification_evidence:
        lines.append("Required Evidence:")
        for ev in verification_evidence:
            lines.append(f"  - {ev}")

    lines.extend(
        [
            "",
            "========================================================================",
            "GOVERNANCE & RUNTIME RESTRICTIONS (MANDATORY)",
            "========================================================================",
            "Under the current session workflow: ",
            "  - runtime_mode is strictly 'read_only'.",
            "  - shell_execution is 'DISABLED'. No commands may be executed directly by Goose.",
            "  - autonomous_writes is 'DISABLED'. No modifications to the filesystem may be committed by Goose.",
            "  - HITL Boundaries: Any command run, or file write, requires a Human-in-the-Loop Proposal/Receipt cycle.",
            "  - Verification Plan: Verification must be executed out-of-band by the human operator.",
            "========================================================================",
        ]
    )

    return "\n".join(lines)


def create_goose_readonly_session_plan(
    settings: Settings,
    target_name: TargetName,
    *,
    agent_profile_name: AgentProfileName | None = None,
    prompt_profile_name: str | None = None,
    verification_profile_name: VerificationProfileName | None = None,
    repo_path: str | None = None,
    context_pack_record: dict[str, Any] | None = None,
    task: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    resolver = ProfileResolver(settings, generic_repo=generic_repo)
    resolved = resolver.resolve(
        target_name=target_name,
        agent_profile_name=agent_profile_name,
        prompt_profile_name=prompt_profile_name,
        verification_profile_name=verification_profile_name,
        repo_path=repo_path,
    )

    resolved_dict = resolved.to_dict()

    instructions = render_goose_instructions(
        target_profile=resolved_dict["target_profile"],
        agent_profile=resolved_dict["selected_agent_profile"],
        prompt_profile=resolved_dict["selected_prompt_profile"],
        verification_profile=resolved_dict["selected_verification_profile"],
        context_pack=context_pack_record,
    )

    return {
        "kind": GOOSE_READONLY_SESSION_PLAN_KIND,
        "schema_version": GOOSE_READONLY_SESSION_PLAN_SCHEMA_VERSION,
        "task": task or "Goose governed read-only session",
        "target_profile": resolved_dict["target_profile"],
        "selected_agent_profile": resolved_dict["selected_agent_profile"],
        "selected_prompt_profile": resolved_dict["selected_prompt_profile"],
        "selected_verification_profile": resolved_dict["selected_verification_profile"],
        "context_pack": context_pack_record,
        "goose_instructions": instructions,
        "runtime_mode": "read_only",
        "shell_execution": "DISABLED",
        "autonomous_writes": "DISABLED",
        "hitl_boundaries": [
            "Goose process is executed in read-only mode and cannot perform autonomous modifications.",
            "Any command execution requires external verification profile execution by the operator.",
            "File writes require a proposed HITL patch specification.",
        ],
        "verification_plan": {
            "profile_name": resolved.verification_profile.name,
            "commands": list(resolved.verification_profile.proposed_commands),
        },
        "governance": {
            "capability_state": "goose_readonly_session_plan",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def validate_goose_readonly_session_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Goose read-only session plan must be a JSON object"]

    if data.get("kind") != GOOSE_READONLY_SESSION_PLAN_KIND:
        errors.append(f"kind must be {GOOSE_READONLY_SESSION_PLAN_KIND}")
    if data.get("schema_version") != GOOSE_READONLY_SESSION_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_READONLY_SESSION_PLAN_SCHEMA_VERSION}")

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

    # Validate context pack if present
    c_pack = data.get("context_pack")
    if c_pack is not None:
        if not isinstance(c_pack, dict):
            errors.append("context_pack must be a dictionary when present")
        else:
            errors.extend(validate_context_pack_record(c_pack))

    if data.get("runtime_mode") != "read_only":
        errors.append("runtime_mode must be read_only")
    if data.get("shell_execution") != "DISABLED":
        errors.append("shell_execution must be DISABLED or NOT_AUTHORIZED")
    if data.get("autonomous_writes") != "DISABLED":
        errors.append("autonomous_writes must be DISABLED or NOT_AUTHORIZED")

    inst = data.get("goose_instructions")
    if not isinstance(inst, str) or not inst.strip():
        errors.append("goose_instructions must be a non-empty string")

    # Validate governance
    gov = data.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        if gov.get("capability_state") != "goose_readonly_session_plan":
            errors.append("governance.capability_state must be goose_readonly_session_plan")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if gov.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if gov.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if gov.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def validate_goose_readonly_session_plan_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_goose_readonly_session_plan(data)
