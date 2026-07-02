"""
deeagents_forge_preview.py

Dry-run preview renderer and governance checker for the Forge wizard.
Builds a ForgePreview that shows the operator exactly what will happen
before emit_agent() writes anything to disk.

The check_governance() function enforces the builder-II Capability
Promotion Rule: every capability that can mutate state must have docs,
output artifact, rollback path, verification profile, HITL gates,
approval boundary, and failure mode declared.

This module is generic-first and must not import CORE-specific modules.
"""

from __future__ import annotations

import yaml
from dataclasses import dataclass, field
from typing import Optional

from builder_ii.deepagents_forge_schema import DeepAgentSpec


# ---------------------------------------------------------------------------
# Write / Shell capability sets (mirrors forge_wizard)
# ---------------------------------------------------------------------------

WRITE_CAPS = {"write_files", "write_memory", "write_artifacts"}
SHELL_CAPS = {"run_shell", "run_tests", "run_commands"}


def _has_write_cap(spec: DeepAgentSpec) -> bool:
    return bool(set(spec.capabilities) & WRITE_CAPS)


def _has_shell_cap(spec: DeepAgentSpec) -> bool:
    return bool(set(spec.capabilities) & SHELL_CAPS)


# ---------------------------------------------------------------------------
# GovernanceCheck
# ---------------------------------------------------------------------------

@dataclass
class GovernanceCheck:
    """
    Result of evaluating a DeepAgentSpec against the
    builder-II Capability Promotion Rule.
    """
    checks: dict = field(default_factory=dict)
    all_pass: bool = False
    failing: list = field(default_factory=list)

    def as_lines(self) -> list[str]:
        """Return human-readable checklist lines for TUI display."""
        lines = []
        for key, passed in self.checks.items():
            icon = "\u2705" if passed else "\u274c"
            label = key.replace("_", " ")
            lines.append(f"{icon}  {label}")
        return lines


# ---------------------------------------------------------------------------
# ForgePreview
# ---------------------------------------------------------------------------

@dataclass
class ForgePreview:
    """Full dry-run preview of what emit_agent() will do."""
    yaml_preview: str = ""
    profile_diff: str = ""
    bridge_spec: dict = field(default_factory=dict)
    governance_check: Optional[GovernanceCheck] = None
    warnings: list = field(default_factory=list)
    artifact_path: str = ""
    rollback_path: str = ""


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def check_governance(spec: DeepAgentSpec) -> GovernanceCheck:
    """
    Validate spec against the builder-II Capability Promotion Rule.
    Every capability that can mutate state requires:
      - docs (description)
      - output_artifact
      - rollback_path
      - verification_profile
      - HITL gate for write ops
      - HITL gate for shell ops
      - approval_required = True
    """
    checks = {
        "has_docs": bool(spec.description and spec.description.strip()),
        "has_output_artifact": bool(spec.output_artifact and spec.output_artifact.strip()),
        "has_rollback_path": bool(spec.rollback_path and spec.rollback_path.strip()),
        "has_verification_profile": bool(
            spec.verification_profile and spec.verification_profile.strip()
        ),
        "hitl_for_write": (
            not _has_write_cap(spec) or "before_write" in spec.hitl_gates
        ),
        "hitl_for_shell": (
            not _has_shell_cap(spec) or "before_shell" in spec.hitl_gates
        ),
        "approval_boundary": spec.approval_required is True,
    }

    failing = [k for k, v in checks.items() if not v]
    return GovernanceCheck(
        checks=checks,
        all_pass=(len(failing) == 0),
        failing=failing,
    )


def collect_warnings(spec: DeepAgentSpec) -> list[str]:
    """Return non-blocking warnings about the spec (will not block emit)."""
    warnings = []

    if not spec.context_pack:
        warnings.append("No context pack attached — agent will have no repo context on first run.")

    if not spec.mcp_tools:
        warnings.append("No MCP tools wired — agent cannot call external tools.")

    if not spec.hitl_gates and (spec.capabilities):
        warnings.append("No HITL gates set — consider adding 'on_error' at minimum.")

    if spec.target_profile == "core" and not spec.context_pack:
        warnings.append("Core target profile without a context pack — CORE agents should have context.")

    if not spec.description:
        warnings.append("No description set — governance check 'has_docs' will fail.")

    return warnings


def spec_to_yaml(spec: DeepAgentSpec) -> str:
    """Render spec as pretty YAML string."""
    return spec.to_yaml()


def render_bridge_spec(spec: DeepAgentSpec) -> dict:
    """
    Render the bridge spec dict that deepagents_bridge will consume.
    Subset of DeepAgentSpec fields relevant to the bridge.
    """
    return {
        "slug": spec.slug,
        "name": spec.name,
        "persona": spec.persona,
        "target_profile": spec.target_profile,
        "capabilities": spec.capabilities,
        "hitl_gates": spec.hitl_gates,
        "mcp_tools": spec.mcp_tools,
        "goose_recipe": spec.goose_recipe,
        "context_pack": spec.context_pack,
        "memory_routes": spec.memory_routes,
        "verification_profile": spec.verification_profile,
        "approval_required": spec.approval_required,
        "output_artifact": spec.output_artifact,
        "rollback_path": spec.rollback_path,
        "schema_version": spec.schema_version,
    }


def compute_profile_diff(spec: DeepAgentSpec) -> str:
    """
    Describe what will change in agent_profiles when this spec is emitted.
    Returns a human-readable diff-style string.
    """
    lines = [
        f"+ profiles/deepagents/{spec.slug}.yaml  (new)",
        f"+ agent_profiles registry: add entry '{spec.slug}'",
        f"+ deepagents_bridge: register bridge spec for '{spec.slug}'",
        f"+ event_ledger: forge_emit event",
        f"+ handoff_notes: forge handoff for '{spec.slug}'",
    ]
    return "\n".join(lines)


def render_preview(spec: DeepAgentSpec) -> ForgePreview:
    """Build a complete ForgePreview for the preview TUI step."""
    return ForgePreview(
        yaml_preview=spec_to_yaml(spec),
        profile_diff=compute_profile_diff(spec),
        bridge_spec=render_bridge_spec(spec),
        governance_check=check_governance(spec),
        warnings=collect_warnings(spec),
        artifact_path=spec.output_artifact,
        rollback_path=spec.rollback_path,
    )
