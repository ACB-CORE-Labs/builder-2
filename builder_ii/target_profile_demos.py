from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from builder_ii.target_profiles import TargetName, target_names

DemoName = Literal["generic", "builder", "core"]


@dataclass(frozen=True)
class TargetProfileDemo:
    target: TargetName
    title: str
    purpose: str
    commands: tuple[str, ...]
    expected_artifacts: tuple[str, ...]
    boundaries: tuple[str, ...]


def target_profile_demos() -> tuple[TargetProfileDemo, ...]:
    return (
        TargetProfileDemo(
            target="generic",
            title="Generic repository planning demo",
            purpose="Show the generic target path for ordinary software repositories without project doctrine.",
            commands=(
                "builder-targets artifact generic --generic-repo /path/to/repo --output .builder/artifacts/generic-target.json",
                "builder-context artifact --target generic --task 'map generic repo' --no-repomix --output .builder/artifacts/generic-context.json",
                "builder-agent artifact repo_mapper --target generic --task 'map generic repo' --output .builder/artifacts/generic-agent.json",
                "builder-verification artifact generic_basic --target generic --task 'verify generic repo' --output .builder/artifacts/generic-verification.json",
            ),
            expected_artifacts=(
                "builder_ii.target_profile",
                "builder_ii.context_pack_record",
                "builder_ii.agent_profile_record",
                "builder_ii.verification_profile",
            ),
            boundaries=(
                "no project-specific doctrine is assumed",
                "no command execution is performed by the demo",
                "operator supplies repo path explicitly",
            ),
        ),
        TargetProfileDemo(
            target="builder",
            title="builder-II self-development demo",
            purpose="Show the builder target path for governed platform self-development.",
            commands=(
                "builder-targets artifact builder --output .builder/artifacts/builder-target.json",
                "builder-context artifact --target builder --task 'builder platform change' --no-repomix --output .builder/artifacts/builder-context.json",
                "builder-agent artifact patch_planner --target builder --task 'builder platform change' --output .builder/artifacts/builder-agent.json",
                "builder-verification artifact builder_full --target builder --task 'builder platform change' --output .builder/artifacts/builder-verification.json",
                "builder-git-state artifact --target builder --branch main --commit-sha <40-hex-sha> --state clean --output .builder/artifacts/builder-git-state.json",
            ),
            expected_artifacts=(
                "builder_ii.target_profile",
                "builder_ii.context_pack_record",
                "builder_ii.agent_profile_record",
                "builder_ii.verification_profile",
                "builder_ii.git_state_record",
            ),
            boundaries=(
                "builder-II remains generic-first",
                "no autonomous writes are enabled",
                "deepagents remains optional and governed",
            ),
        ),
        TargetProfileDemo(
            target="core",
            title="CORE target-profile demo",
            purpose="Show CORE as a target profile without making builder-II the CORE Workbench or CORE runtime.",
            commands=(
                "builder-targets artifact core --output .builder/artifacts/core-target.json",
                "builder-context artifact --target core --task 'CORE target planning' --no-repomix --output .builder/artifacts/core-context.json",
                "builder-agent artifact verification_planner --target core --task 'CORE target planning' --output .builder/artifacts/core-agent.json",
                "builder-verification artifact core_smoke --target core --task 'CORE target planning' --output .builder/artifacts/core-verification.json",
                "builder-git-state artifact --target core --branch main --commit-sha <40-hex-sha> --state clean --output .builder/artifacts/core-git-state.json",
            ),
            expected_artifacts=(
                "builder_ii.target_profile",
                "builder_ii.context_pack_record",
                "builder_ii.agent_profile_record",
                "builder_ii.verification_profile",
                "builder_ii.git_state_record",
            ),
            boundaries=(
                "CORE is only a target profile",
                "builder-II is not CORE Workbench/UI",
                "no CORE runtime authority is granted",
            ),
        ),
    )


def get_target_profile_demo(target: TargetName) -> TargetProfileDemo:
    demos = {demo.target: demo for demo in target_profile_demos()}
    try:
        return demos[target]
    except KeyError as exc:
        raise ValueError(f"unknown target profile demo: {target}") from exc


def validate_target_profile_demos() -> tuple[str, ...]:
    errors: list[str] = []
    seen: set[str] = set()
    for demo in target_profile_demos():
        if demo.target in seen:
            errors.append(f"duplicate demo target: {demo.target}")
        seen.add(demo.target)
        if not demo.title:
            errors.append(f"demo {demo.target} missing title")
        if not demo.purpose:
            errors.append(f"demo {demo.target} missing purpose")
        if not demo.commands:
            errors.append(f"demo {demo.target} missing commands")
        if not demo.expected_artifacts:
            errors.append(f"demo {demo.target} missing expected artifacts")
        if not demo.boundaries:
            errors.append(f"demo {demo.target} missing boundaries")
        if any("CORE Workbench" in command for command in demo.commands):
            errors.append(f"demo {demo.target} command must not mention CORE Workbench")
    for expected in target_names():
        if expected not in seen:
            errors.append(f"missing demo target: {expected}")
    return tuple(errors)


def render_target_profile_demo(demo: TargetProfileDemo) -> str:
    lines = [
        f"# Target demo: {demo.target}",
        "",
        demo.title,
        "",
        "## Purpose",
        "",
        demo.purpose,
        "",
        "## Commands",
        "",
    ]
    lines.extend(f"- `{command}`" for command in demo.commands)
    lines.extend(["", "## Expected artifacts", ""])
    lines.extend(f"- `{artifact}`" for artifact in demo.expected_artifacts)
    lines.extend(["", "## Boundaries", ""])
    lines.extend(f"- {boundary}" for boundary in demo.boundaries)
    lines.append("")
    return "\n".join(lines)
