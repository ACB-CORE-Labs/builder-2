from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from builder_ii.config import Settings

TargetName = Literal["generic", "builder", "core"]


@dataclass(frozen=True)
class TargetProfile:
    name: TargetName
    description: str
    repo: Path
    context_defaults: tuple[str, ...]
    verification_hints: tuple[str, ...]
    principles: tuple[str, ...]
    notes: tuple[str, ...] = ()


_GENERIC_CONTEXT_DEFAULTS = (
    "README.md",
    "pyproject.toml",
    "package.json",
    "src",
    "tests",
    "docs",
)

_BUILDER_CONTEXT_DEFAULTS = (
    "README.md",
    "docs/ROADMAP.md",
    "docs/TOOLING.md",
    "builder_ii",
    "recipes",
    "tests",
)

_CORE_CONTEXT_DEFAULTS = (
    "README.md",
    "AGENTS.md",
    "GROK.md",
    "CLAUDE.md",
    "docs",
    "tests",
)


def target_names() -> tuple[TargetName, ...]:
    return ("generic", "builder", "core")


def _existing_defaults(repo: Path, defaults: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(path for path in defaults if (repo / path).exists())


def build_target_profiles(settings: Settings, *, generic_repo: Path | None = None) -> tuple[TargetProfile, ...]:
    generic_root = (generic_repo or Path.cwd()).resolve()
    builder_root = settings.project_root.resolve()
    core_root = settings.core_repo.resolve()
    return (
        TargetProfile(
            name="generic",
            description="Generic software repository target with no project-specific doctrine.",
            repo=generic_root,
            context_defaults=_existing_defaults(generic_root, _GENERIC_CONTEXT_DEFAULTS),
            verification_hints=("inspect project config", "run the smallest relevant tests"),
            principles=("stay repo-local", "prefer minimal patches", "do not invent project policy"),
        ),
        TargetProfile(
            name="builder",
            description="builder-II self-development target profile.",
            repo=builder_root,
            context_defaults=_existing_defaults(builder_root, _BUILDER_CONTEXT_DEFAULTS),
            verification_hints=("uv run pytest -q", "uv run builder-targets list", "uv run builder-context pack --target builder --no-repomix"),
            principles=(
                "generic-first platform behavior",
                "no CORE Workbench identity",
                "no autonomous writes by default",
                "deepagents remains optional until proven",
            ),
        ),
        TargetProfile(
            name="core",
            description="AssetOverflow/core target profile. CORE is a target, not builder-II identity.",
            repo=core_root,
            context_defaults=_existing_defaults(core_root, _CORE_CONTEXT_DEFAULTS),
            verification_hints=("builder verify <changed-path>", "run focused pytest suites", "preserve CORE invariants"),
            principles=(
                "treat CORE as target profile only",
                "do not conflate with CORE Workbench/UI",
                "preserve deterministic verification discipline",
                "surface uncertainty and refusal boundaries",
            ),
            notes=("CORE-specific behavior must remain isolated in this target profile.",),
        ),
    )


def target_profile(settings: Settings, name: TargetName, *, generic_repo: Path | None = None) -> TargetProfile:
    profiles = {profile.name: profile for profile in build_target_profiles(settings, generic_repo=generic_repo)}
    try:
        return profiles[name]
    except KeyError as exc:
        raise ValueError(f"unknown target profile: {name}") from exc


def validate_target_profiles(settings: Settings) -> tuple[str, ...]:
    errors: list[str] = []
    profiles = build_target_profiles(settings)
    seen: set[str] = set()
    for profile in profiles:
        if profile.name in seen:
            errors.append(f"duplicate target profile: {profile.name}")
        seen.add(profile.name)
        if not profile.description:
            errors.append(f"target profile {profile.name} missing description")
        if not profile.principles:
            errors.append(f"target profile {profile.name} missing principles")
        if profile.name in {"builder", "core"} and not profile.repo.exists():
            errors.append(f"target profile {profile.name} repo missing: {profile.repo}")
    for expected in target_names():
        if expected not in seen:
            errors.append(f"missing target profile: {expected}")
    return tuple(errors)


def render_target_profile(profile: TargetProfile) -> str:
    lines = [
        f"# Target profile: {profile.name}",
        "",
        profile.description,
        "",
        "## Repository",
        "",
        f"`{profile.repo}`",
        "",
        "## Context defaults",
        "",
    ]
    lines.extend(f"- `{path}`" for path in profile.context_defaults) if profile.context_defaults else lines.append("(none found)")
    lines.extend(["", "## Verification hints", ""])
    lines.extend(f"- {hint}" for hint in profile.verification_hints)
    lines.extend(["", "## Principles", ""])
    lines.extend(f"- {principle}" for principle in profile.principles)
    if profile.notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in profile.notes)
    lines.append("")
    return "\n".join(lines)
