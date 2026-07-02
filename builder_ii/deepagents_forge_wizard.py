"""
deeagents_forge_wizard.py

Defines ForgeStep (a single wizard step descriptor) and ForgeWizard
(the step engine that drives the Forge TUI). The wizard populates a
DeepAgentSpec incrementally, with branching logic to skip irrelevant steps.

This module is generic-first and must not import CORE-specific modules.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any, Callable, Optional

from builder_ii.deepagents_forge_schema import (
    KNOWN_CAPABILITIES,
    KNOWN_HITL_GATES,
    SHELL_CAPABILITIES,
    VALID_TARGET_PROFILES,
    WRITE_CAPABILITIES,
    DeepAgentSpec,
    has_shell_capability,
    has_write_capability,
    validate_relative_artifact_path,
)


# ---------------------------------------------------------------------------
# Validation result
# ---------------------------------------------------------------------------

@dataclass
class ValidationResult:
    ok: bool
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# ForgeStep
# ---------------------------------------------------------------------------

@dataclass
class ForgeStep:
    """
    Descriptor for a single step in the Forge wizard.
    The TUI uses this to know what to render and how to validate input.
    """
    id: str
    title: str
    prompt: str

    # Field targeting
    field: Optional[str] = None           # single field on DeepAgentSpec
    fields: list = dataclass_field(default_factory=list)  # multiple fields (governance step)

    # Display
    hint: str = ""
    governance_note: str = ""
    render_mode: str = "default"          # default | dry_run_preview

    # Input type
    multi_line: bool = False
    multi_select: bool = False
    optional: bool = False
    default: Any = None

    # Options
    options: list = dataclass_field(default_factory=list)        # static options list
    options_from: Optional[str] = None                 # dynamic lookup hint (string)

    # Governance
    auto_required_if: Optional[Callable] = None        # callable(spec) -> bool
    validator: Optional[Callable] = None               # callable(value) -> ValidationResult

    def is_required(self, spec: DeepAgentSpec) -> bool:
        """Returns True if this step must not be skipped given current spec."""
        if self.optional:
            return False
        if self.auto_required_if is not None:
            return self.auto_required_if(spec)
        return True

    def validate(self, value: Any, spec: DeepAgentSpec) -> ValidationResult:
        """Run step-level validation on the provided value."""
        if self.validator is not None:
            return self.validator(value)
        if not self.optional and value in (None, "", [], {}):
            return ValidationResult(ok=False, error=f"{self.title} is required.")
        return ValidationResult(ok=True)

    def apply_to(self, value: Any, spec: DeepAgentSpec) -> None:
        """Write validated value(s) onto the spec."""
        if self.field:
            setattr(spec, self.field, value)
            # Auto-derive slug when name is set
            if self.field == "name":
                spec.auto_derive_slug()
        elif self.fields and isinstance(value, dict):
            for f in self.fields:
                if f in value:
                    setattr(spec, f, value[f])


# ---------------------------------------------------------------------------
# Capability helpers
# ---------------------------------------------------------------------------

WRITE_CAPS = WRITE_CAPABILITIES
SHELL_CAPS = SHELL_CAPABILITIES


def _has_write_cap(spec: DeepAgentSpec) -> bool:
    return has_write_capability(spec.capabilities)


def _has_shell_cap(spec: DeepAgentSpec) -> bool:
    return has_shell_capability(spec.capabilities)


def _hitl_auto_required(spec: DeepAgentSpec) -> bool:
    return _has_write_cap(spec) or _has_shell_cap(spec)


def _validate_name(value: Any) -> ValidationResult:
    if not isinstance(value, str) or not value.strip():
        return ValidationResult(ok=False, error="Agent name must be a non-empty string.")
    if len(value.strip()) < 2:
        return ValidationResult(ok=False, error="Agent name must be at least 2 characters.")
    return ValidationResult(ok=True)


def _validate_persona(value: Any) -> ValidationResult:
    if not isinstance(value, str) or not value.strip():
        return ValidationResult(ok=False, error="Persona is required.")
    if len(value.strip()) < 10:
        return ValidationResult(ok=False, error="Persona must be at least 10 characters.")
    return ValidationResult(ok=True)


def _validate_output_artifact(value: Any) -> ValidationResult:
    if not isinstance(value, dict):
        return ValidationResult(ok=True)  # handled per-field in governance step
    output = value.get("output_artifact", "")
    if not output.strip():
        return ValidationResult(ok=False, error="output_artifact path is required.")
    for field_name in ("output_artifact", "rollback_path"):
        path_value = value.get(field_name, "")
        if path_value:
            issues = validate_relative_artifact_path(path_value, field_name=field_name)
            if issues:
                return ValidationResult(ok=False, error=issues[0].as_text())
    return ValidationResult(ok=True)


# ---------------------------------------------------------------------------
# FORGE_STEPS — the canonical 9-step wizard definition
# ---------------------------------------------------------------------------

FORGE_STEPS: list[ForgeStep] = [
    ForgeStep(
        id="identity",
        title="Name your agent",
        prompt="What should this agent be called?",
        field="name",
        hint="Use snake_case (e.g. pr_reviewer, test_writer). Slug is auto-derived.",
        validator=_validate_name,
    ),
    ForgeStep(
        id="persona",
        title="Define the persona",
        prompt="Complete: 'You are an agent that...'",
        field="persona",
        hint="This becomes the system prompt seed. Be specific about scope and limits.",
        multi_line=True,
        validator=_validate_persona,
    ),
    ForgeStep(
        id="target_profile",
        title="Choose a target profile",
        prompt="Which repo/environment will this agent work in?",
        field="target_profile",
        options=list(VALID_TARGET_PROFILES),
        default="generic",
        hint="'generic' works for any repo. 'core' is for AssetOverflow/core only.",
    ),
    ForgeStep(
        id="capabilities",
        title="Grant capabilities",
        prompt="What can this agent do? Select all that apply.",
        field="capabilities",
        multi_select=True,
        options=sorted(KNOWN_CAPABILITIES),
        hint="Write/shell caps require HITL gates — you will set those next.",
        governance_note="write_files, write_memory, run_shell require before_write/before_shell HITL gates.",
    ),
    ForgeStep(
        id="hitl_gates",
        title="Set HITL gates",
        prompt="Where must a human approve before the agent proceeds?",
        field="hitl_gates",
        multi_select=True,
        options=sorted(KNOWN_HITL_GATES),
        hint="HITL gates are required for any write or shell capability.",
        auto_required_if=_hitl_auto_required,
        governance_note="Builder-II Capability Promotion Rule: write/shell caps require explicit HITL gates.",
    ),
    ForgeStep(
        id="context_pack",
        title="Attach a context pack",
        prompt="Which context pack should prime this agent? (optional)",
        field="context_pack",
        optional=True,
        hint="Context packs inject repo/project knowledge into the agent's first message.",
        options_from="context_packs.list_all()",
    ),
    ForgeStep(
        id="mcp_tools",
        title="Wire MCP tools",
        prompt="Which MCP tools should be available to this agent? (optional)",
        field="mcp_tools",
        multi_select=True,
        optional=True,
        hint="Only approved tools from mcp_policy are available.",
        options_from="mcp_policy.list_approved()",
    ),
    ForgeStep(
        id="governance",
        title="Set governance",
        prompt="Set verification profile, output artifact path, and rollback path.",
        fields=["verification_profile", "output_artifact", "rollback_path"],
        hint="These fields satisfy the builder-II Capability Promotion Rule.",
        validator=_validate_output_artifact,
    ),
    ForgeStep(
        id="preview",
        title="Preview & confirm",
        prompt="Review your agent spec before writing it to disk.",
        render_mode="dry_run_preview",
        hint="All governance checks must pass before you can emit.",
        optional=True,  # no data input — just confirm
    ),
]


# ---------------------------------------------------------------------------
# ForgeWizard
# ---------------------------------------------------------------------------

class ForgeWizard:
    """
    Step engine that drives the Forge wizard.
    Maintains a DeepAgentSpec that accumulates values step by step.
    Supports forward navigation (with branching), back navigation,
    and optional step skipping.
    """

    def __init__(self, seed_name: str = "", seed_profile: str = "generic") -> None:
        self.spec = DeepAgentSpec(
            name=seed_name,
            target_profile=seed_profile,
        )
        if seed_name:
            self.spec.auto_derive_slug()
        self.steps = FORGE_STEPS
        self.cursor: int = 0
        self.history: list[int] = []

    def current_step(self) -> ForgeStep:
        """Return the ForgeStep at the current cursor position."""
        return self.steps[self.cursor]

    def get_progress(self) -> tuple[int, int]:
        """Return (1-based current step index, total steps)."""
        return self.cursor + 1, len(self.steps)

    def apply(self, value: Any) -> ValidationResult:
        """
        Validate and apply a value to the current step.
        Advances cursor on success (with branching/skip logic).
        Returns ValidationResult.
        """
        step = self.current_step()
        result = step.validate(value, self.spec)
        if result.ok:
            step.apply_to(value, self.spec)
            self.history.append(self.cursor)
            self.cursor = self._next_cursor(self.cursor)
        return result

    def skip(self) -> bool:
        """
        Skip the current step if it is optional.
        Returns True if skipped, False if step is required.
        """
        step = self.current_step()
        if step.optional or not step.is_required(self.spec):
            self.history.append(self.cursor)
            self.cursor = self._next_cursor(self.cursor)
            return True
        return False

    def back(self) -> bool:
        """Go back to the previous step. Returns True if successful."""
        if self.history:
            self.cursor = self.history.pop()
            return True
        return False

    def is_complete(self) -> bool:
        """Return True when wizard has passed the final step."""
        return self.cursor >= len(self.steps)

    def _next_cursor(self, current: int) -> int:
        """
        Determine the next cursor position.
        Skips hitl_gates step automatically if no write/shell caps selected.
        """
        next_idx = current + 1
        if next_idx >= len(self.steps):
            return next_idx  # past end = complete

        next_step = self.steps[next_idx]

        # Auto-skip hitl_gates if not required
        if next_step.id == "hitl_gates" and not _hitl_auto_required(self.spec):
            return next_idx + 1

        return next_idx
