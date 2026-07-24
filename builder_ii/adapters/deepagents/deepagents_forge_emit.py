"""
deepagents_forge_emit.py

Governed artifact writer and registrar for the Forge wizard.
Only called after governance check passes and operator confirms.

Emit pipeline:
  1. Validate spec is emit-ready
  2. Run validation and governance checks
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

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from builder_ii.adapters.deepagents.deepagents_forge_preview import (
    GovernanceCheck,
    check_governance,
    collect_warnings,
)
from builder_ii.adapters.deepagents.deepagents_forge_schema import DeepAgentSpec, is_valid_slug, validate_spec


@dataclass
class HookResult:
    """Truth record for an optional Forge integration hook."""

    name: str
    status: str
    path: str = ""
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.status in {"succeeded", "skipped"}

    def as_line(self) -> str:
        suffix = f" -> {self.path}" if self.path else ""
        if self.error:
            suffix = f"{suffix}: {self.error}"
        return f"{self.name}: {self.status}{suffix}"


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
    profile_written: bool = False
    handoff_written: bool = False
    handoff_path: str = ""
    written_paths: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    hook_results: list[HookResult] = field(default_factory=list)

    def as_lines(self) -> list[str]:
        """Return human-readable result lines for TUI/CLI display."""
        if not self.ok:
            lines = ["\u274c  Emit failed:", f"   {self.error}"]
            if self.blockers:
                lines.append("   Blockers:")
                lines.extend(f"     - {blocker}" for blocker in self.blockers)
            if isinstance(self.detail, GovernanceCheck):
                lines.append("   Failing governance checks:")
                for failing_check in self.detail.failing:
                    lines.append(f"     - {failing_check}")
            return lines
        prefix = "[DRY-RUN] " if self.dry_run else ""
        lines = [
            f"\u2705  {prefix}Agent profile prepared successfully",
            f"   profile: {self.profile_path}",
            f"   slug:    {self.slug}",
            f"   next:    {self.next_command}",
        ]
        if self.written_paths:
            lines.append("   written:")
            lines.extend(f"     - {path}" for path in self.written_paths)
        if self.hook_results:
            lines.append("   hooks:")
            lines.extend(f"     - {hook.as_line()}" for hook in self.hook_results)
        if self.warnings:
            lines.append("   warnings:")
            lines.extend(f"     - {warning}" for warning in self.warnings)
        return lines


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


def write_forge_handoff(spec: DeepAgentSpec) -> HookResult:
    """
    Write a governed forge handoff note when the handoff note API is available.
    The profile YAML remains the canonical Forge output.
    """
    from builder_ii.core.handoff_notes import create_handoff_note, write_handoff_note

    output_path = DEEPAGENTS_PROFILES_DIR / f"forge_{spec.slug}.handoff.json"
    try:
        summary = (
            f"Agent `{spec.slug}` was created via the deepagents Forge wizard.\n\n"
            f"Target profile: {spec.target_profile}\n"
            f"Persona: {spec.persona}\n"
            f"Capabilities: {', '.join(spec.capabilities) or 'none'}\n"
            f"HITL gates: {', '.join(spec.hitl_gates) or 'none'}\n"
            f"Output artifact: {spec.output_artifact}\n"
            f"Rollback path: {spec.rollback_path}\n\n"
            "Forge emitted governed profile and handoff artifacts only. "
            "This handoff does not grant runtime promotion, shell authority, "
            "source-write authority, Goose activation, MCP/tool invocation, or deepagents execution."
        )
        note = create_handoff_note(
            target_name=spec.target_profile,
            summary=summary,
            changed_files_summary=[f"profiles/deepagents/{spec.slug}.yaml"],
            open_risks=[
                "Forge emits a governed profile artifact only; runtime promotion still requires a separate reviewed path."
            ],
            next_recommended_action=f"review profiles/deepagents/{spec.slug}.yaml before any separate promotion path",
            human_review_required=True,
            status="DRAFT",
        )
        write_handoff_note(note, output_path)
    except (TypeError, ValueError, OSError) as exc:
        return HookResult(
            "handoff_notes.write_handoff_note",
            "failed",
            path=output_path.as_posix(),
            error=f"{type(exc).__name__}: {exc}",
        )
    return HookResult("handoff_notes.write_handoff_note", "succeeded", path=output_path.as_posix())


def emit_agent(spec: DeepAgentSpec, dry_run: bool = False) -> EmitResult:
    """
    Emit a deepagent from a completed DeepAgentSpec.

    dry_run=True: validates and renders everything but writes nothing.
    Always safe to call with dry_run=True.
    """
    validation_issues = validate_spec(spec)
    if validation_issues:
        blockers = [issue.as_text() for issue in validation_issues]
        fields = ", ".join(dict.fromkeys(issue.field.split("[", 1)[0] for issue in validation_issues))
        return EmitResult(
            ok=False,
            error=f"Spec incomplete or invalid. Fields: {fields}",
            dry_run=dry_run,
            blockers=blockers,
        )

    try:
        profile_path_obj = _profile_path_for_slug(spec.slug)
    except ValueError as exc:
        return EmitResult(ok=False, error=str(exc), dry_run=dry_run, blockers=[str(exc)])

    governance = check_governance(spec)
    if not governance.all_pass:
        blockers = list(governance.validation_errors)
        blockers.extend(f"governance failed: {item}" for item in governance.failing if item != "spec_validation")
        return EmitResult(
            ok=False,
            error="Governance check failed. Fix failing checks before emitting.",
            detail=governance,
            dry_run=dry_run,
            blockers=blockers,
        )

    warnings = collect_warnings(spec)

    if dry_run:
        return EmitResult(
            ok=True,
            profile_path=profile_path_obj.as_posix(),
            slug=spec.slug,
            next_command=f"review profiles/deepagents/{spec.slug}.yaml before any separate promotion path",
            dry_run=True,
            profile_written=False,
            handoff_written=False,
            warnings=warnings,
        )

    spec.stamp_created_at()

    try:
        profile_path = write_agent_profile(spec)
    except (OSError, ValueError) as exc:
        return EmitResult(
            ok=False,
            error=f"Failed to write profile: {exc}",
            dry_run=False,
            blockers=[f"profile write failed: {exc}"],
        )

    hook_results = [
        write_forge_handoff(spec),
    ]
    hook_warnings = [f"optional hook failed: {hook.as_line()}" for hook in hook_results if hook.status == "failed"]
    handoff_hook = next(
        (hook for hook in hook_results if hook.name == "handoff_notes.write_handoff_note"),
        None,
    )
    handoff_written = bool(handoff_hook and handoff_hook.status == "succeeded")
    handoff_path = handoff_hook.path if handoff_hook and handoff_hook.path else ""
    written_paths = [profile_path]
    if handoff_written:
        written_paths.append(handoff_path)

    return EmitResult(
        ok=True,
        profile_path=profile_path,
        slug=spec.slug,
        next_command=f"review profiles/deepagents/{spec.slug}.yaml before any separate promotion path",
        dry_run=False,
        profile_written=True,
        handoff_written=handoff_written,
        handoff_path=handoff_path,
        written_paths=written_paths,
        warnings=[*warnings, *hook_warnings],
        hook_results=hook_results,
    )
