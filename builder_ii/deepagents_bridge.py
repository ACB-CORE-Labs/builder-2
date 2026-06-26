from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
from importlib import metadata
from typing import Any

from builder_ii.agent_profiles import AgentProfile, AgentProfileName, get_agent_profile, render_agent_profile
from builder_ii.target_profiles import TargetName, TargetProfile

REQUIRED_DENIED_TOOLS = ("write_file", "edit_file", "execute_shell", "commit", "push")


@dataclass(frozen=True)
class DeepAgentsAvailability:
    available: bool
    source: str | None
    detail: str
    version: str | None = None
    create_deep_agent_present: bool = False
    import_status: str = "MISS"
    dependency_mode: str = "optional"
    runtime_execution: str = "disabled"
    file_writes: str = "disabled"
    shell_execution: str = "disabled"

    def rows(self) -> tuple[tuple[str, str, str], ...]:
        return (
            ("deepagents import", self.import_status, self.detail),
            ("deepagents source", self.source or "n/a", ""),
            ("deepagents version", self.version or "unknown", ""),
            ("create_deep_agent", "PRESENT" if self.create_deep_agent_present else "MISSING", ""),
            ("runtime execution", self.runtime_execution.upper(), "bridge renders specs only"),
            ("file writes", self.file_writes.upper(), "requires future HITL-gated capability"),
            ("shell execution", self.shell_execution.upper(), "requires future HITL-gated capability"),
            ("builder-II dependency mode", self.dependency_mode.upper(), "deepagents is optional"),
        )

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "kind": "builder_ii.deepagents_smoke",
            "schema_version": 1,
            "deepagents_import": self.import_status,
            "deepagents_source": self.source or "n/a",
            "deepagents_version": self.version or "unknown",
            "create_deep_agent": "PRESENT" if self.create_deep_agent_present else "MISSING",
            "runtime_execution": self.runtime_execution.upper(),
            "file_writes": self.file_writes.upper(),
            "shell_execution": self.shell_execution.upper(),
            "builder_ii_dependency_mode": self.dependency_mode.upper(),
        }



@dataclass(frozen=True)
class DeepAgentBridgeSpec:
    name: str
    description: str
    target: TargetName
    prompt: str
    tools: tuple[str, ...]
    denied_tools: tuple[str, ...]
    hitl_required_for: tuple[str, ...]
    agent_profile: AgentProfileName
    runtime_enabled: bool = False

    def to_artifact_dict(self) -> dict[str, Any]:
        return {
            "kind": "builder_ii.deepagents_bridge_spec",
            "schema_version": 1,
            "name": self.name,
            "description": self.description,
            "agent_profile": self.agent_profile,
            "target": self.target,
            "runtime_enabled": self.runtime_enabled,
            "tools": list(self.tools),
            "denied_tools": list(self.denied_tools),
            "hitl_required_for": list(self.hitl_required_for),
            "builder_ii_bridge": True,
            "subagent": self.as_subagent_dict(),
        }

    def as_subagent_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "prompt": self.prompt,
            "tools": list(self.tools),
            "metadata": {
                "target": self.target,
                "denied_tools": list(self.denied_tools),
                "hitl_required_for": list(self.hitl_required_for),
                "runtime_enabled": self.runtime_enabled,
                "builder_ii_bridge": True,
            },
        }


def _deepagents_version() -> str | None:
    try:
        return metadata.version("deepagents")
    except metadata.PackageNotFoundError:
        return None


def deepagents_availability() -> DeepAgentsAvailability:
    """Report optional deepagents import/readiness status without enabling runtime."""
    spec = importlib.util.find_spec("deepagents")
    if spec is None:
        return DeepAgentsAvailability(
            available=False,
            source=None,
            detail="deepagents is not installed; bridge rendering remains available.",
            import_status="MISS",
        )

    source = spec.origin
    try:
        module = importlib.import_module("deepagents")
    except Exception as exc:  # pragma: no cover - exercised via monkeypatch
        return DeepAgentsAvailability(
            available=False,
            source=source,
            detail=f"deepagents import failed: {type(exc).__name__}: {exc}",
            version=_deepagents_version(),
            import_status="ERROR",
        )

    create_deep_agent = getattr(module, "create_deep_agent", None)
    create_deep_agent_present = callable(create_deep_agent)
    module_source = getattr(module, "__file__", None) or source
    detail = (
        "deepagents import passed; create_deep_agent found; runtime remains disabled."
        if create_deep_agent_present
        else "deepagents import passed; create_deep_agent missing; runtime remains disabled."
    )

    return DeepAgentsAvailability(
        available=True,
        source=module_source,
        detail=detail,
        version=_deepagents_version(),
        create_deep_agent_present=create_deep_agent_present,
        import_status="PASS",
    )


def _subagent_name(profile: AgentProfile, target: TargetProfile) -> str:
    return f"{target.name}-{profile.name}".replace("_", "-")


def _denied_tools(profile: AgentProfile) -> tuple[str, ...]:
    return tuple(dict.fromkeys((*profile.forbidden_tools, *REQUIRED_DENIED_TOOLS)))


def render_bridge_prompt(profile: AgentProfile, target: TargetProfile) -> str:
    base = render_agent_profile(profile, target)
    boundary = "\n".join(
        [
            "## deepagents bridge boundary",
            "",
            "This is a builder-II rendered subagent prompt/specification.",
            "It is not runtime execution permission.",
            "Do not write files, edit files, execute shell commands, mutate memory, commit, push, or open PRs unless a later HITL-gated capability explicitly authorizes it.",
            "Treat the selected target profile as the scope boundary.",
            "",
        ]
    )
    return base + "\n" + boundary


def deepagent_bridge_spec(profile: AgentProfile, target: TargetProfile) -> DeepAgentBridgeSpec:
    return DeepAgentBridgeSpec(
        name=_subagent_name(profile, target),
        description=f"{profile.description} Target: {target.name}.",
        target=target.name,
        prompt=render_bridge_prompt(profile, target),
        tools=profile.allowed_tools,
        denied_tools=_denied_tools(profile),
        hitl_required_for=profile.hitl_required_for,
        agent_profile=profile.name,
        runtime_enabled=False,
    )


def bridge_spec_for(profile_name: AgentProfileName, target: TargetProfile) -> DeepAgentBridgeSpec:
    return deepagent_bridge_spec(get_agent_profile(profile_name), target)


def validate_bridge_spec(spec: DeepAgentBridgeSpec) -> tuple[str, ...]:
    errors: list[str] = []
    if not spec.name:
        errors.append("bridge spec missing name")
    if not spec.prompt:
        errors.append("bridge spec missing prompt")
    if spec.runtime_enabled:
        errors.append("bridge spec runtime must be disabled by default")
    for forbidden in REQUIRED_DENIED_TOOLS:
        if forbidden not in spec.denied_tools:
            errors.append(f"bridge spec must deny {forbidden}")
    if "runtime execution permission" not in spec.prompt:
        errors.append("bridge prompt missing runtime boundary")
    return tuple(errors)


def render_bridge_spec(spec: DeepAgentBridgeSpec) -> str:
    lines = [
        f"# deepagents bridge spec: {spec.name}",
        "",
        spec.description,
        "",
        "## Target",
        "",
        f"`{spec.target}`",
        "",
        "## Runtime",
        "",
        "disabled" if not spec.runtime_enabled else "enabled",
        "",
        "## Tools",
        "",
    ]
    lines.extend(f"- {tool}" for tool in spec.tools)
    lines.extend(["", "## Denied tools", ""])
    lines.extend(f"- {tool}" for tool in spec.denied_tools)
    lines.extend(["", "## HITL required for", ""])
    lines.extend(f"- {item}" for item in spec.hitl_required_for)
    lines.extend(["", "## Prompt", "", spec.prompt, ""])
    return "\n".join(lines)
