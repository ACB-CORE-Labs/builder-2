from __future__ import annotations

import json as json_lib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.agent_profiles import AgentProfileName, agent_profile_names, get_agent_profile
from builder_ii.config import Settings
from builder_ii.target_profiles import TargetName, target_names, target_profile
from builder_ii.verification_profiles import default_profile_for_target, validate_profile_artifact

GooseRuntimeMode = Literal["disabled", "read_only"]
GOOSE_SESSION_KIND = "builder_ii.goose_session_manifest"
GOOSE_SESSION_SCHEMA_VERSION = 1

_ALLOWED_ACTIONS = (
    "render_session_manifest",
    "validate_session_manifest",
    "link_existing_artifacts",
)

_DENIED_ACTIONS = (
    "start_goose_runtime",
    "read_repository_files_as_runtime",
    "execute_commands",
    "execute_shell",
    "write_source_files",
    "apply_patches",
    "mutate_memory",
    "create_commits",
    "push_refs",
    "open_pull_requests",
    "construct_deepagents",
    "call_models",
)

_APPROVAL_REQUIREMENTS = (
    "future runtime start requires a promoted runtime mode",
    "future command execution requires approved command artifacts",
    "future patch application requires approved patch artifacts",
    "future writes require rollback and verification paths",
)


@dataclass(frozen=True)
class GooseSessionLinks:
    target_bundle: str = ""
    verification_profile: str = ""
    quality_gate: str = ""
    research_plan: str = ""
    handoff: str = ""
    context_pack: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "target_bundle": self.target_bundle,
            "verification_profile": self.verification_profile,
            "quality_gate": self.quality_gate,
            "research_plan": self.research_plan,
            "handoff": self.handoff,
            "context_pack": self.context_pack,
        }


def _clean_path(path: str | Path | None) -> str:
    if path is None:
        return ""
    return str(path).strip()


def _target_dict(settings: Settings, target: TargetName, generic_repo: Path | None) -> dict[str, Any]:
    selected = target_profile(settings, target, generic_repo=generic_repo)
    return {
        "name": selected.name,
        "repo": str(selected.repo),
        "description": selected.description,
    }


def create_goose_session_manifest(
    settings: Settings,
    *,
    target_name: TargetName,
    agent_profile: AgentProfileName,
    task: str = "",
    runtime_mode: GooseRuntimeMode = "disabled",
    target_bundle: str | Path | None = None,
    verification_profile: str | Path | None = None,
    quality_gate: str | Path | None = None,
    research_plan: str | Path | None = None,
    handoff: str | Path | None = None,
    context_pack: str | Path | None = None,
    expected_audit_artifact: str | Path = ".builder/artifacts/goose-runtime-audit.json",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    selected_agent = get_agent_profile(agent_profile)
    selected_verification = default_profile_for_target(target_name)
    verification_artifact = selected_verification.to_artifact_dict(target=target_name, task=task)
    links = GooseSessionLinks(
        target_bundle=_clean_path(target_bundle),
        verification_profile=_clean_path(verification_profile),
        quality_gate=_clean_path(quality_gate),
        research_plan=_clean_path(research_plan),
        handoff=_clean_path(handoff),
        context_pack=_clean_path(context_pack),
    )

    return {
        "kind": GOOSE_SESSION_KIND,
        "schema_version": GOOSE_SESSION_SCHEMA_VERSION,
        "task": task,
        "target": _target_dict(settings, target_name, generic_repo),
        "agent_profile": {
            "name": selected_agent.name,
            "description": selected_agent.description,
            "authority": selected_agent.authority,
        },
        "verification_profile": verification_artifact,
        "requested_runtime_mode": runtime_mode,
        "current_runtime_state": "DISABLED",
        "manifest_starts_goose": False,
        "links": links.to_dict(),
        "expected_audit_artifact": _clean_path(expected_audit_artifact),
        "allowed_actions": list(_ALLOWED_ACTIONS),
        "denied_actions": list(_DENIED_ACTIONS),
        "approval_requirements": list(_APPROVAL_REQUIREMENTS),
        "governance": {
            "capability_state": "artifact_only",
            "runtime_execution": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "model_execution": "DISABLED",
            "agent_construction": "DISABLED",
            "shell_execution": "DISABLED",
            "command_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "commit_push": "DISABLED",
            "file_writes": "DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_goose_session_manifest(manifest: dict[str, Any]) -> str:
    return json_lib.dumps(manifest, indent=2, sort_keys=True) + "\n"


def write_goose_session_manifest(manifest: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_goose_session_manifest(manifest), encoding="utf-8")


def validate_goose_session_manifest(manifest: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["goose session manifest must be a JSON object"]
    if manifest.get("kind") != GOOSE_SESSION_KIND:
        errors.append(f"kind must be {GOOSE_SESSION_KIND}")
    if manifest.get("schema_version") != GOOSE_SESSION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_SESSION_SCHEMA_VERSION}")
    target = manifest.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")
    agent = manifest.get("agent_profile")
    if not isinstance(agent, dict):
        errors.append("agent_profile must be an object")
    elif agent.get("name") not in agent_profile_names():
        errors.append("agent_profile.name is unknown")
    if manifest.get("requested_runtime_mode") not in ("disabled", "read_only"):
        errors.append("requested_runtime_mode must be disabled or read_only")
    if manifest.get("current_runtime_state") != "DISABLED":
        errors.append("current_runtime_state must be DISABLED")
    if manifest.get("manifest_starts_goose") is not False:
        errors.append("manifest_starts_goose must be false")
    profile_errors = validate_profile_artifact(manifest.get("verification_profile"))
    errors.extend(f"verification_profile: {error}" for error in profile_errors)
    links = manifest.get("links")
    if not isinstance(links, dict):
        errors.append("links must be an object")
    else:
        for key in (
            "target_bundle",
            "verification_profile",
            "quality_gate",
            "research_plan",
            "handoff",
            "context_pack",
        ):
            if key not in links:
                errors.append(f"links.{key} is required")
            elif not isinstance(links.get(key), str):
                errors.append(f"links.{key} must be a string")
    if not manifest.get("expected_audit_artifact"):
        errors.append("expected_audit_artifact is required")
    for field in ("allowed_actions", "denied_actions", "approval_requirements"):
        value = manifest.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"{field} must be a non-empty list")
    denied = manifest.get("denied_actions")
    if isinstance(denied, list):
        for required in _DENIED_ACTIONS:
            if required not in denied:
                errors.append(f"denied_actions must include {required}")
    governance = manifest.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "goose_runtime_start",
            "model_execution",
            "agent_construction",
            "shell_execution",
            "command_execution",
            "source_writes",
            "memory_mutation",
            "commit_push",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_goose_session_manifest_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_goose_session_manifest(data)
