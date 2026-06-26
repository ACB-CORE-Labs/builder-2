from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from builder_ii.target_profiles import TargetName, TargetProfile

AgentProfileName = Literal[
    "repo_mapper",
    "context_planner",
    "code_reviewer",
    "patch_planner",
    "verification_planner",
    "handoff_scribe",
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
    for expected in ("repo_mapper", "context_planner", "code_reviewer", "patch_planner", "verification_planner", "handoff_scribe"):
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
