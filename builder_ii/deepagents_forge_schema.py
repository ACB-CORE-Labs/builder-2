"""
deepagents_forge_schema.py

Defines DeepAgentSpec — the incrementally-buildable agent specification
that the Forge wizard populates step by step. All fields are optional at
construction time; is_emit_ready() enforces required fields at emit time.

This module is generic-first and must not import CORE-specific modules.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Optional

import yaml

SAFE_SLUG_PATTERN = r"^[a-z0-9]+(?:_[a-z0-9]+)*$"
SAFE_SLUG_RE = re.compile(SAFE_SLUG_PATTERN)
VALID_TARGET_PROFILES = ("generic", "builder", "core")

READ_CAPABILITIES = frozenset({"read_files", "read_git", "read_tests"})
WRITE_CAPABILITIES = frozenset({"write_files", "write_memory", "write_artifacts"})
SHELL_CAPABILITIES = frozenset({"run_shell", "run_tests", "run_commands"})
TOOL_CAPABILITIES = frozenset({"call_mcp_tools", "emit_handoffs"})
KNOWN_CAPABILITIES = frozenset(
    (*READ_CAPABILITIES, *WRITE_CAPABILITIES, *SHELL_CAPABILITIES, *TOOL_CAPABILITIES)
)
KNOWN_HITL_GATES = frozenset(
    {
        "before_write",
        "before_shell",
        "before_promote",
        "before_memory_write",
        "on_error",
    }
)

_SAFE_RELATIVE_PATH_RE = re.compile(r"^[A-Za-z0-9._/\-]+$")
_WINDOWS_ABSOLUTE_RE = re.compile(r"^[A-Za-z]:[\\/]")
_FORBIDDEN_PATH_TOKENS = ("\x00", "\n", "\r", "&&", "||", ";", "|", "`", "$(", ">", "<")
_AUTHORIZING_PATH_PARTS = {
    "approval",
    "approved",
    "authority",
    "authorization",
    "promote",
    "promoted",
    "promotion",
}


@dataclass(frozen=True)
class ValidationIssue:
    """Human-readable validation failure for a Forge spec."""

    field: str
    message: str
    blocking: bool = True

    def as_text(self) -> str:
        return f"{self.field}: {self.message}"


def derive_slug(name: str) -> str:
    """Convert a human name into a safe lowercase slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug


def is_valid_slug(slug: str) -> bool:
    """Return True when slug is safe for profiles/deepagents/{slug}.yaml."""
    return bool(
        isinstance(slug, str)
        and slug == slug.strip()
        and SAFE_SLUG_RE.fullmatch(slug)
    )


def validate_slug(slug: str) -> list[ValidationIssue]:
    """Validate a flat, safe, lowercase profile slug."""
    if not isinstance(slug, str):
        return [ValidationIssue("slug", "must be a string")]
    if not slug:
        return [ValidationIssue("slug", "must be non-empty")]
    if slug != slug.strip():
        return [ValidationIssue("slug", "must not contain leading or trailing whitespace")]
    if not SAFE_SLUG_RE.fullmatch(slug):
        return [
            ValidationIssue(
                "slug",
                f"must match {SAFE_SLUG_PATTERN}; use lowercase letters, digits, and single underscores only",
            )
        ]
    return []


def has_write_capability(capabilities: list[str]) -> bool:
    return bool(set(capabilities) & WRITE_CAPABILITIES)


def has_shell_capability(capabilities: list[str]) -> bool:
    return bool(set(capabilities) & SHELL_CAPABILITIES)


def validate_relative_artifact_path(value: str, *, field_name: str) -> list[ValidationIssue]:
    """
    Validate a sane relative artifact path.

    These paths are declarations for future outputs/rollback evidence. They are
    not command strings, approval artifacts, or authority grants.
    """
    if not isinstance(value, str):
        return [ValidationIssue(field_name, "must be a string")]
    if not value:
        return [ValidationIssue(field_name, "must be non-empty")]
    if value != value.strip():
        return [ValidationIssue(field_name, "must not contain leading or trailing whitespace")]
    if any(token in value for token in _FORBIDDEN_PATH_TOKENS):
        return [ValidationIssue(field_name, "must not contain shell/control tokens")]
    if "\\" in value:
        return [ValidationIssue(field_name, "must use forward-slash relative paths")]
    if value.startswith("/") or value.startswith("~") or _WINDOWS_ABSOLUTE_RE.match(value):
        return [ValidationIssue(field_name, "must be relative, not absolute or home-relative")]
    if not _SAFE_RELATIVE_PATH_RE.fullmatch(value):
        return [ValidationIssue(field_name, "contains unsupported path characters")]

    normalized = value.rstrip("/")
    if not normalized:
        return [ValidationIssue(field_name, "must include at least one path segment")]
    if "//" in normalized:
        return [ValidationIssue(field_name, "must not contain empty path segments")]

    parts = normalized.split("/")
    for part in parts:
        if part in {"", ".", ".."}:
            return [ValidationIssue(field_name, "must not contain '.', '..', or empty path segments")]
        folded = part.lower().replace("_", "-")
        if folded in _AUTHORIZING_PATH_PARTS:
            return [
                ValidationIssue(
                    field_name,
                    "must not point at approval, promotion, or authority artifacts",
                )
            ]
    return []


def validate_spec(spec: "DeepAgentSpec") -> list[ValidationIssue]:
    """Validate a DeepAgentSpec before preview or emission."""
    issues: list[ValidationIssue] = []
    required_fields = (
        "name",
        "slug",
        "persona",
        "verification_profile",
        "output_artifact",
        "rollback_path",
    )
    for field_name in required_fields:
        value = getattr(spec, field_name, "")
        if not isinstance(value, str) or not value.strip():
            issues.append(ValidationIssue(field_name, "is required"))
        elif value != value.strip():
            issues.append(ValidationIssue(field_name, "must not contain leading or trailing whitespace"))

    if spec.slug:
        issues.extend(validate_slug(spec.slug))

    if spec.target_profile not in VALID_TARGET_PROFILES:
        issues.append(
            ValidationIssue(
                "target_profile",
                f"must be one of: {', '.join(VALID_TARGET_PROFILES)}",
            )
        )

    if not isinstance(spec.capabilities, list):
        issues.append(ValidationIssue("capabilities", "must be a list"))
        capabilities: list[str] = []
    else:
        capabilities = spec.capabilities
        for index, capability in enumerate(capabilities):
            if not isinstance(capability, str) or not capability.strip():
                issues.append(ValidationIssue(f"capabilities[{index}]", "must be a non-empty string"))
            elif capability not in KNOWN_CAPABILITIES:
                issues.append(ValidationIssue(f"capabilities[{index}]", f"unknown capability: {capability}"))

    if not isinstance(spec.hitl_gates, list):
        issues.append(ValidationIssue("hitl_gates", "must be a list"))
        gates: list[str] = []
    else:
        gates = spec.hitl_gates
        for index, gate in enumerate(gates):
            if not isinstance(gate, str) or not gate.strip():
                issues.append(ValidationIssue(f"hitl_gates[{index}]", "must be a non-empty string"))
            elif gate not in KNOWN_HITL_GATES:
                issues.append(ValidationIssue(f"hitl_gates[{index}]", f"unknown HITL gate: {gate}"))

    if has_write_capability(capabilities) and "before_write" not in gates:
        issues.append(ValidationIssue("hitl_gates", "write capability requires before_write"))
    if has_shell_capability(capabilities) and "before_shell" not in gates:
        issues.append(ValidationIssue("hitl_gates", "shell capability requires before_shell"))

    if spec.output_artifact:
        issues.extend(validate_relative_artifact_path(spec.output_artifact, field_name="output_artifact"))
    if spec.rollback_path:
        issues.extend(validate_relative_artifact_path(spec.rollback_path, field_name="rollback_path"))

    if spec.approval_required is not True:
        issues.append(ValidationIssue("approval_required", "must remain true"))

    return issues


@dataclass
class DeepAgentSpec:
    """
    Incrementally-buildable specification for a deepagent.
    Populated step-by-step by ForgeWizard; validated at emit time.
    """

    # --- Identity ---
    name: str = ""
    slug: str = ""          # auto-derived from name; editable
    description: str = ""
    target_profile: str = "generic"   # generic | builder | core

    # --- Role / Persona ---
    persona: str = ""       # system prompt seed: "You are an agent that..."
    lane: str = "default"   # maps to existing lane_guides

    # --- Capability grants ---
    capabilities: list[str] = field(default_factory=list)
    # e.g. ["read_files", "run_tests"] — write/shell require HITL gates

    # --- Tool wiring ---
    mcp_tools: list[str] = field(default_factory=list)
    goose_recipe: Optional[str] = None

    # --- Subagent / orchestration ---
    subagent_of: Optional[str] = None   # parent agent slug if nested
    hitl_gates: list[str] = field(default_factory=list)
    # e.g. ["before_write", "before_shell"]

    # --- Memory / context ---
    context_pack: Optional[str] = None
    memory_routes: list[str] = field(default_factory=list)

    # --- Governance (required at emit) ---
    verification_profile: str = "default"
    approval_required: bool = True
    rollback_path: str = ""
    output_artifact: str = ""   # where the agent writes its work

    # --- Meta ---
    author: str = ""
    created_at: str = ""
    schema_version: str = "1.0"

    # --- Required fields for emit ---
    _REQUIRED_FIELDS: list[str] = field(
        default_factory=lambda: [
            "name",
            "slug",
            "persona",
            "verification_profile",
            "output_artifact",
            "rollback_path",
        ],
        repr=False,
    )

    def is_emit_ready(self) -> tuple[bool, list[str]]:
        """
        Returns (ready, list_of_missing_or_invalid_fields).
        All required fields must be non-empty strings; slug and target profile
        must also be safe because the emitter writes durable repo artifacts.
        """
        issues = validate_spec(self)
        fields = list(dict.fromkeys(issue.field.split("[", 1)[0] for issue in issues))
        return (len(issues) == 0), fields

    def auto_derive_slug(self) -> None:
        """Derive slug from name if slug is not yet set."""
        if self.name and not self.slug:
            self.slug = derive_slug(self.name)

    def stamp_created_at(self) -> None:
        """Set created_at to current UTC ISO timestamp."""
        self.created_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict:
        """Render spec as plain dict (excludes private _REQUIRED_FIELDS)."""
        d = asdict(self)
        d.pop("_REQUIRED_FIELDS", None)
        return d

    def to_yaml(self) -> str:
        """Render spec as pretty YAML string."""
        return yaml.dump(
            self.to_dict(),
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=True,
        )

    def summary_lines(self) -> list[str]:
        """Return short human-readable summary lines for TUI display."""
        lines = []
        has_identity = bool(self.name or self.slug)
        if self.name:
            lines.append(f"name:    {self.name}")
        if self.slug:
            lines.append(f"slug:    {self.slug}")
        if self.target_profile and (has_identity or self.target_profile != "generic"):
            lines.append(f"target:  {self.target_profile}")
        if self.persona:
            preview = self.persona[:60] + ("..." if len(self.persona) > 60 else "")
            lines.append(f"persona: {preview}")
        if self.capabilities:
            lines.append(f"caps:    {', '.join(self.capabilities)}")
        if self.hitl_gates:
            lines.append(f"hitl:    {', '.join(self.hitl_gates)}")
        if self.output_artifact:
            lines.append(f"output:  {self.output_artifact}")
        return lines
