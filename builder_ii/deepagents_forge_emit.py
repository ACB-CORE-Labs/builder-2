"""
deepagents_forge_emit.py

Governed artifact writer and registrar for the Forge wizard.
Only called after governance check passes and operator confirms.

Emit pipeline:
  1. Validate spec is emit-ready
  2. Run governance check (unless dry_run)
  3. Write profiles/deepagents/{slug}.yaml
  4. Register in agent_profiles if that optional bridge exists
  5. Register bridge spec in deepagents_bridge if that optional bridge exists
  6. Write forge handoff note if that optional surface exists
  7. Log forge event if that optional surface exists
  8. Return EmitResult

dry_run=True is always safe — no side effects, returns what WOULD happen.

This module is generic-first and must not import CORE-specific modules.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from builder_ii.deepagents_forge_preview import (
    GovernanceCheck,
    check_governance,
    render_bridge_spec,
)
from builder_ii.deepagents_forge_schema import DeepAgentSpec, is_valid_slug


# ---------------------------------------------------------------------------
# EmitResult
# ---------------------------------------------------------------------------

@dataclass
class EmitResult:
    """Result of an emit_agent() call."""
    ok: bool
    error: Optional[str] = None
    profile_path: str = ""
    slug: str = ""
    next_command: str = ""
    detail: Optional[object] = None
    dry_run: bool = False

    def as_lines(self) -> list[str]:
        """Return human-readable result lines for TUI/CLI display."""
        if not self.ok:
            lines = ["\u274c  Emit failed:", f"   {self.error}"]
            if isinstance(self.detail, GovernanceCheck):
                lines.append("   Failing governance checks:")
                for failing_check in self.detail.failing:
                    lines.append(f"     - {failing_check}")
            return lines
        prefix = "[DRY-RUN] " if self.dry_run else ""
        return [
            f"\u2705  {prefix}Agent profile prepared successfully",
            f"   profile: {self.profile_path}",
            f"   slug:    {self.slug}",
            f"   next:    {self.next_command}",
        ]


# ---------------------------------------------------------------------------
# Profile output directory
# ---------------------------------------------------------------------------

DEEPAGENTS_PROFILES_DIR = Path("profiles/deepagents")


def _profiles_dir() -> Path:
    """Return the profiles/deepagents directory, creating it if needed."""
    DEEPAGENTS_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return DEEPAGENTS_PROFILES_DIR


def _profile_path_for_slug(slug: str) -> Path:
    """
    Resolve the profile path for a safe slug.

    The slug is validated separately from the filesystem path so an editable
    slug can never traverse out of profiles/deepagents/ or smuggle separators.
    """
    if not is_valid_slug(slug):
        raise ValueError("slug must match ^[a-z0-9]+(?:_[a-z0-9]+)*$")
    return DEEPAGENTS_PROFILES_DIR / f"{slug}.yaml"


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def write_agent_profile(spec: DeepAgentSpec) -> str:
    """
    Write the agent YAML to profiles/deepagents/{slug}.yaml.
    Returns the path written.
    """
    profiles_dir = _profiles_dir()
    path = _profile_path_for_slug(spec.slug)
    if path.parent != profiles_dir:
        raise ValueError("profile path escaped profiles/deepagents")
    path.write_text(spec.to_yaml(), encoding="utf-8")
    return path.as_posix()


def register_agent_profile(spec: DeepAgentSpec) -> None:
    """
    Register the agent in the agent_profiles module.
    Calls register_from_forge_spec() if available; silently skips if not.
    """
    try:
        from builder_ii.agent_profiles import register_from_forge_spec
        register_from_forge_spec(spec)
    except (ImportError, AttributeError):
        pass  # additive — safe to skip if function is not wired yet


def register_bridge_spec(spec: DeepAgentSpec) -> None:
    """
    Register the bridge spec in deepagents_bridge.
    Calls register_forge_spec() if available; silently skips if not.
    """
    try:
        from builder_ii.deepagents_bridge import register_forge_spec
        bridge_spec = render_bridge_spec(spec)
        register_forge_spec(bridge_spec)
    except (ImportError, AttributeError):
        pass  # additive — safe to skip if function is not wired yet


def write_forge_handoff(spec: DeepAgentSpec) -> None:
    """
    Write a forge handoff note artifact.
    Uses handoff_notes if available; silently skips if not.
    """
    try:
        from builder_ii.handoff_notes import write_handoff_note
        content = (
            f"# Forge Handoff: {spec.name}\n\n"
            f"Agent `{spec.slug}` was created via the deepagents Forge wizard.\n\n"
            f"**Target profile:** {spec.target_profile}\n"
            f"**Persona:** {spec.persona}\n"
            f"**Capabilities:** {', '.join(spec.capabilities) or 'none'}\n"
            f"**HITL gates:** {', '.join(spec.hitl_gates) or 'none'}\n"
            f"**Output artifact:** {spec.output_artifact}\n"
            f"**Rollback path:** {spec.rollback_path}\n"
            f"**Next:** review `profiles/deepagents/{spec.slug}.yaml` before promotion.\n"
        )
        write_handoff_note(
            slug=f"forge_{spec.slug}",
            content=content,
        )
    except (ImportError, TypeError, AttributeError):
        pass  # additive — safe to skip


def log_forge_event(spec: DeepAgentSpec) -> None:
    """
    Log the forge emit event to the event ledger.
    Uses event_ledger if available; silently skips if not.
    """
    try:
        from builder_ii.event_ledger import log_event
        log_event(
            event_type="forge_emit",
            payload={
                "slug": spec.slug,
                "name": spec.name,
                "target_profile": spec.target_profile,
                "capabilities": spec.capabilities,
                "hitl_gates": spec.hitl_gates,
                "created_at": spec.created_at,
            },
        )
    except (ImportError, TypeError, AttributeError):
        pass  # additive — safe to skip


# ---------------------------------------------------------------------------
# Main emit entry point
# ---------------------------------------------------------------------------

def emit_agent(spec: DeepAgentSpec, dry_run: bool = False) -> EmitResult:
    """
    Emit a deepagent from a completed DeepAgentSpec.

    dry_run=True: validates and renders everything but writes nothing.
    Always safe to call with dry_run=True.
    """
    # 1. Spec readiness check
    ready, missing = spec.is_emit_ready()
    if not ready:
        return EmitResult(
            ok=False,
            error=f"Spec incomplete or invalid. Fields: {', '.join(missing)}",
            dry_run=dry_run,
        )

    try:
        profile_path_obj = _profile_path_for_slug(spec.slug)
    except ValueError as exc:
        return EmitResult(ok=False, error=str(exc), dry_run=dry_run)

    # 2. Governance check
    governance = check_governance(spec)
    if not governance.all_pass and not dry_run:
        return EmitResult(
            ok=False,
            error="Governance check failed. Fix failing checks before emitting.",
            detail=governance,
            dry_run=dry_run,
        )

    # Dry run stops here — no side effects
    if dry_run:
        return EmitResult(
            ok=True,
            profile_path=profile_path_obj.as_posix(),
            slug=spec.slug,
            next_command=f"review profiles/deepagents/{spec.slug}.yaml before promotion",
            dry_run=True,
        )

    # 3. Stamp timestamp
    spec.stamp_created_at()

    # 4. Write profile YAML
    try:
        profile_path = write_agent_profile(spec)
    except (OSError, ValueError) as exc:
        return EmitResult(ok=False, error=f"Failed to write profile: {exc}")

    # 5. Register in agent_profiles
    register_agent_profile(spec)

    # 6. Register bridge spec
    register_bridge_spec(spec)

    # 7. Write handoff note
    write_forge_handoff(spec)

    # 8. Log to event ledger
    log_forge_event(spec)

    return EmitResult(
        ok=True,
        profile_path=profile_path,
        slug=spec.slug,
        next_command=f"review profiles/deepagents/{spec.slug}.yaml before promotion",
        dry_run=False,
    )
