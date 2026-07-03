import hashlib
import json as json_lib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.target_profiles import TargetName, TargetProfile

AGENT_PROFILE_RECORD_KIND = "builder_ii.agent_profile_record"
AGENT_PROFILE_RECORD_SCHEMA_VERSION = 1


AgentProfileName = Literal[
    "repo_mapper",
    "context_planner",
    "code_reviewer",
    "patch_planner",
    "verification_planner",
    "handoff_scribe",
    "core.invariant_auditor",
    "core.patch_planner",
    "core.verification_planner",
]
Authority = Literal["read_only", "plan_only", "proposal_only", "notes_only"]


@dataclass(frozen=True)
class AgentProfile:
    name: AgentProfileName
    description: str
    purpose: str
    authority: Authority
    compatible_targets: tuple[TargetName, ...]
    required_context: tuple[str, ...]
    allowed_tools: tuple[str, ...]
    forbidden_tools: tuple[str, ...]
    hitl_required_for: tuple[str, ...]
    output_contract: str


_BASE_COMPATIBILITY: tuple[TargetName, ...] = ("generic", "builder", "core")


def agent_profiles() -> tuple[AgentProfile, ...]:
    return (
        AgentProfile(
            name="repo_mapper",
            description="Map repository shape, important files, and likely entry points.",
            purpose="Create a repo-local orientation summary before planning or review.",
            authority="read_only",
            compatible_targets=_BASE_COMPATIBILITY,
            required_context=("target profile", "repo root", "file tree or context pack"),
            allowed_tools=("context_pack", "read_file", "repo_search", "git_status"),
            forbidden_tools=("write_file", "edit_file", "execute_shell", "commit", "push"),
            hitl_required_for=("none; profile is read-only",),
            output_contract="Return a concise map of modules, likely change surfaces, unknowns, and next context needed.",
        ),
        AgentProfile(
            name="context_planner",
            description="Select task-scoped context before involving a model or agent runtime.",
            purpose="Decide which files, docs, tests, and tool outputs should be packed for a task.",
            authority="plan_only",
            compatible_targets=_BASE_COMPATIBILITY,
            required_context=("target profile", "task", "git status"),
            allowed_tools=("context_pack", "git_status", "repo_search"),
            forbidden_tools=("write_file", "edit_file", "execute_shell", "commit", "push"),
            hitl_required_for=("expanding beyond task scope",),
            output_contract="Return a context selection plan with include paths, exclude paths, and rationale.",
        ),
        AgentProfile(
            name="code_reviewer",
            description="Review code, diffs, or proposed patches without mutating the repo.",
            purpose="Identify correctness issues, boundary violations, missing tests, and unclear assumptions.",
            authority="read_only",
            compatible_targets=_BASE_COMPATIBILITY,
            required_context=("target profile", "context pack or diff", "verification hints"),
            allowed_tools=("context_pack", "read_file", "repo_search", "static_scan"),
            forbidden_tools=("write_file", "edit_file", "execute_shell", "commit", "push"),
            hitl_required_for=("running scans", "expanding review scope"),
            output_contract="Return findings grouped by severity, with evidence, uncertainty, and recommended verification.",
        ),
        AgentProfile(
            name="patch_planner",
            description="Plan a bounded implementation slice before edits.",
            purpose="Translate a task into a minimal patch plan with files, risks, rollback, and tests.",
            authority="proposal_only",
            compatible_targets=_BASE_COMPATIBILITY,
            required_context=("target profile", "task", "context pack", "git status"),
            allowed_tools=("context_pack", "read_file", "repo_search", "git_status", "test_plan"),
            forbidden_tools=("write_file", "edit_file", "execute_shell", "commit", "push"),
            hitl_required_for=("applying patches", "running commands", "changing durable notes"),
            output_contract="Return a patch plan only: files, ordered steps, expected tests, rollback path, and stop conditions.",
        ),
        AgentProfile(
            name="verification_planner",
            description="Choose the smallest responsible verification path for a proposed or completed change.",
            purpose="Map changed files and target profile hints to deterministic validation commands.",
            authority="plan_only",
            compatible_targets=_BASE_COMPATIBILITY,
            required_context=("target profile", "changed files", "verification hints"),
            allowed_tools=("git_status", "test_plan", "static_scan"),
            forbidden_tools=("write_file", "edit_file", "execute_shell", "commit", "push"),
            hitl_required_for=("running verification commands",),
            output_contract="Return exact proposed commands, why each is needed, and what evidence would count as pass or fail.",
        ),
        AgentProfile(
            name="handoff_scribe",
            description="Prepare continuity notes and handoff summaries from current evidence.",
            purpose="Summarize current state without inventing future work or unstated results.",
            authority="notes_only",
            compatible_targets=_BASE_COMPATIBILITY,
            required_context=("target profile", "git status", "test results", "open risks"),
            allowed_tools=("git_status", "context_pack", "notes_manifest"),
            forbidden_tools=("edit_source", "execute_shell", "commit", "push"),
            hitl_required_for=("writing notes", "publishing handoff", "updating PR body"),
            output_contract="Return a handoff with branch state, changes, validation, blockers, and next operator commands.",
        ),
        AgentProfile(
            name="core.invariant_auditor",
            description="Audit CORE invariants in read-only planning mode.",
            purpose="Identify invariant surfaces, proof obligations, and verification risks without mutating CORE.",
            authority="read_only",
            compatible_targets=("core",),
            required_context=("core target profile", "task", "repo map", "context pack", "verification hints"),
            allowed_tools=("context_pack", "read_file", "repo_search", "static_scan"),
            forbidden_tools=("write_file", "edit_file", "execute_shell", "commit", "push"),
            hitl_required_for=("running verification commands", "expanding beyond explicit read scope"),
            output_contract="Return CORE invariant findings, evidence refs, uncertainty, and required follow-up checks only.",
        ),
        AgentProfile(
            name="core.patch_planner",
            description="Plan CORE patches without source mutation.",
            purpose="Translate CORE findings into a bounded proposal with files, invariants, tests, and rollback proof requirements.",
            authority="proposal_only",
            compatible_targets=("core",),
            required_context=("core target profile", "task", "context pack", "invariant audit", "verification hints"),
            allowed_tools=("context_pack", "read_file", "repo_search", "git_status", "test_plan"),
            forbidden_tools=("write_file", "edit_file", "execute_shell", "commit", "push"),
            hitl_required_for=("applying patches", "running commands", "changing durable notes"),
            output_contract="Return a CORE patch proposal only: scope, invariant impact, exact verification plan, rollback path, and stop conditions.",
        ),
        AgentProfile(
            name="core.verification_planner",
            description="Plan CORE verification evidence without executing commands.",
            purpose="Map CORE proposal risks to exact verification commands and required evidence receipts.",
            authority="plan_only",
            compatible_targets=("core",),
            required_context=(
                "core target profile",
                "changed files or proposal",
                "invariant audit",
                "verification hints",
            ),
            allowed_tools=("git_status", "test_plan", "static_scan"),
            forbidden_tools=("write_file", "edit_file", "execute_shell", "commit", "push"),
            hitl_required_for=("running verification commands", "recording execution receipts"),
            output_contract="Return exact proposed CORE verification commands, pass criteria, evidence refs, and no-mutation assertions.",
        ),
    )


def agent_profile_names() -> tuple[AgentProfileName, ...]:
    return tuple(profile.name for profile in agent_profiles())


def get_agent_profile(name: AgentProfileName) -> AgentProfile:
    profiles = {profile.name: profile for profile in agent_profiles()}
    try:
        return profiles[name]
    except KeyError as exc:
        raise ValueError(f"unknown agent profile: {name}") from exc


def profiles_for_target(target: TargetName) -> tuple[AgentProfile, ...]:
    return tuple(profile for profile in agent_profiles() if target in profile.compatible_targets)


def validate_agent_profiles() -> tuple[str, ...]:
    errors: list[str] = []
    seen: set[str] = set()
    for profile in agent_profiles():
        if profile.name in seen:
            errors.append(f"duplicate agent profile: {profile.name}")
        seen.add(profile.name)
        if not profile.description:
            errors.append(f"agent profile {profile.name} missing description")
        if not profile.compatible_targets:
            errors.append(f"agent profile {profile.name} missing compatible targets")
        if any(target not in ("generic", "builder", "core") for target in profile.compatible_targets):
            errors.append(f"agent profile {profile.name} has unknown target")
        if "execute_shell" not in profile.forbidden_tools:
            errors.append(f"agent profile {profile.name} must forbid execute_shell by default")
        if not profile.output_contract:
            errors.append(f"agent profile {profile.name} missing output contract")
    for expected in (
        "repo_mapper",
        "context_planner",
        "code_reviewer",
        "patch_planner",
        "verification_planner",
        "handoff_scribe",
        "core.invariant_auditor",
        "core.patch_planner",
        "core.verification_planner",
    ):
        if expected not in seen:
            errors.append(f"missing agent profile: {expected}")
    return tuple(errors)


def render_agent_profile(profile: AgentProfile, target: TargetProfile | None = None) -> str:
    lines = [
        f"# Agent profile: {profile.name}",
        "",
        profile.description,
        "",
        "## Purpose",
        "",
        profile.purpose,
        "",
        "## Authority",
        "",
        profile.authority,
        "",
        "## Compatible targets",
        "",
    ]
    lines.extend(f"- `{name}`" for name in profile.compatible_targets)
    if target is not None:
        lines.extend(["", "## Selected target", "", f"`{target.name}` — `{target.repo}`", "", target.description])
    lines.extend(["", "## Required context", ""])
    lines.extend(f"- {item}" for item in profile.required_context)
    lines.extend(["", "## Allowed tools", ""])
    lines.extend(f"- {tool}" for tool in profile.allowed_tools)
    lines.extend(["", "## Forbidden tools", ""])
    lines.extend(f"- {tool}" for tool in profile.forbidden_tools)
    lines.extend(["", "## HITL required for", ""])
    lines.extend(f"- {item}" for item in profile.hitl_required_for)
    lines.extend(["", "## Output contract", "", profile.output_contract, ""])
    if target is not None:
        lines.extend(["## Target principles", ""])
        lines.extend(f"- {principle}" for principle in target.principles)
        lines.append("")
    return "\n".join(lines)


def create_agent_profile_record(
    profile: AgentProfile,
    target: TargetProfile | None = None,
    *,
    task: str | None = None,
) -> dict[str, Any]:
    rendered = render_agent_profile(profile, target)
    rendered_digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    return {
        "kind": AGENT_PROFILE_RECORD_KIND,
        "schema_version": AGENT_PROFILE_RECORD_SCHEMA_VERSION,
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
        "target": target.name if target else "",
        "task": task or "",
        "rendered_profile_sha256": rendered_digest,
        "governance": {
            "capability_state": "agent_profile_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_agent_profile_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_agent_profile_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_agent_profile_record(record), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_agent_profile_record(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["agent profile record must be a JSON object"]
    if data.get("kind") != AGENT_PROFILE_RECORD_KIND:
        errors.append(f"kind must be {AGENT_PROFILE_RECORD_KIND}")
    if data.get("schema_version") != AGENT_PROFILE_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {AGENT_PROFILE_RECORD_SCHEMA_VERSION}")
    if data.get("name") not in agent_profile_names():
        errors.append("name must be a known agent profile")
    if data.get("target") and data.get("target") not in ("generic", "builder", "core"):
        errors.append("target must be one of: generic, builder, core")

    for list_field in (
        "compatible_targets",
        "required_context",
        "allowed_tools",
        "forbidden_tools",
        "hitl_required_for",
    ):
        errors.extend(_string_list_errors(data.get(list_field), field=list_field))

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "agent_profile_record":
            errors.append("governance.capability_state must be agent_profile_record")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def validate_agent_profile_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_agent_profile_record(data)
