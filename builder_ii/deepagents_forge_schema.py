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

_SAFE_SLUG_RE = re.compile(r"^[a-z0-9]+(?:_[a-z0-9]+)*$")
_VALID_TARGET_PROFILES = {"generic", "builder", "core"}


def derive_slug(name: str) -> str:
    """Convert a human name into a safe lowercase slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug


def is_valid_slug(slug: str) -> bool:
    """Return True when slug is safe for profiles/deepagents/{slug}.yaml."""
    return bool(isinstance(slug, str) and _SAFE_SLUG_RE.fullmatch(slug.strip()))


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
        missing = [
            field_name
            for field_name in self._REQUIRED_FIELDS
            if not str(getattr(self, field_name, "")).strip()
        ]
        if self.slug and not is_valid_slug(self.slug):
            missing.append("slug")
        if self.target_profile not in _VALID_TARGET_PROFILES:
            missing.append("target_profile")
        return (len(missing) == 0), missing

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
