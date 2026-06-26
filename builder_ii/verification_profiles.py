from __future__ import annotations

import json as json_lib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.target_profiles import TargetName, target_names

VerificationProfileName = Literal[
    "generic_basic",
    "builder_fast",
    "builder_full",
    "core_smoke",
    "core_focused",
]

VERIFICATION_ARTIFACT_KIND = "builder_ii.verification_profile"
VERIFICATION_ARTIFACT_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class VerificationProfile:
    name: VerificationProfileName
    description: str
    compatible_targets: tuple[TargetName, ...]
    purpose: str
    proposed_commands: tuple[str, ...]
    required_evidence: tuple[str, ...]
    failure_mode: str
    rollback_hint: str
    runtime_execution: str = "disabled"
    shell_execution: str = "disabled"
    writes: str = "disabled except explicit artifact output path"
    executes_commands: bool = False

    def to_artifact_dict(self, *, target: TargetName | None = None, task: str | None = None) -> dict[str, Any]:
        return {
            "kind": VERIFICATION_ARTIFACT_KIND,
            "schema_version": VERIFICATION_ARTIFACT_SCHEMA_VERSION,
            "name": self.name,
            "description": self.description,
            "target": target or "",
            "task": task or "",
            "compatible_targets": list(self.compatible_targets),
            "purpose": self.purpose,
            "proposed_commands": list(self.proposed_commands),
            "required_evidence": list(self.required_evidence),
            "failure_mode": self.failure_mode,
            "rollback_hint": self.rollback_hint,
            "governance": {
                "capability_state": "verification_profile_artifact",
                "runtime_execution": self.runtime_execution.upper(),
                "model_execution": "DISABLED",
                "shell_execution": self.shell_execution.upper(),
                "source_writes": "DISABLED",
                "writes": self.writes.upper(),
                "memory_mutation": "DISABLED",
                "executes_commands": self.executes_commands,
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            },
        }


def verification_profiles() -> tuple[VerificationProfile, ...]:
    return (
        VerificationProfile(
            name="generic_basic",
            description="Generic repository verification planning profile.",
            compatible_targets=("generic",),
            purpose="Propose minimal repo-local verification without assuming project-specific tooling.",
            proposed_commands=(
                "inspect project config for test command",
                "run the smallest relevant test command after human approval",
                "run formatting/static checks only if the repo defines them",
            ),
            required_evidence=(
                "project config inspected",
                "selected command rationale recorded",
                "pass/fail output captured by the operator",
            ),
            failure_mode="If project tooling is unclear, stop and ask for the repo's canonical verification path.",
            rollback_hint="Do not modify files; discard the artifact if the selected verification path is wrong.",
        ),
        VerificationProfile(
            name="builder_fast",
            description="Fast builder-II self-check profile.",
            compatible_targets=("builder",),
            purpose="Propose the smallest responsible builder-II verification path for docs, CLI, and artifact changes.",
            proposed_commands=(
                "uv run pytest tests/test_target_bundles.py tests/test_deepagents_bridge.py",
                "uv run pytest",
                "git diff --check",
            ),
            required_evidence=(
                "focused tests pass for changed surfaces",
                "full pytest pass when code changed",
                "git diff --check pass",
            ),
            failure_mode="If focused tests fail, fix only the failing surface before expanding scope.",
            rollback_hint="Revert the bounded branch or discard generated artifacts; do not mutate target repos.",
        ),
        VerificationProfile(
            name="builder_full",
            description="Full builder-II foundation verification profile.",
            compatible_targets=("builder",),
            purpose="Propose full foundation verification before merging platform-surface changes.",
            proposed_commands=(
                "uv run pytest",
                "uv run builder-targets validate",
                "uv run builder-agent validate",
                "uv run builder-bridge deepagents-smoke --json",
                "uv run builder-bundle create --target builder --agent patch_planner --task '<task>' --output /tmp/target-bundle.json",
                "uv run builder-bundle validate /tmp/target-bundle.json",
                "git diff --check",
            ),
            required_evidence=(
                "full pytest pass",
                "target profiles validate",
                "agent profiles validate",
                "bridge smoke emits disabled-runtime artifact",
                "target bundle validates",
                "diff style check passes",
            ),
            failure_mode="If any registry or artifact validation fails, do not merge until the failed invariant is repaired.",
            rollback_hint="Rollback by reverting the PR branch or removing the invalid artifact surface.",
        ),
        VerificationProfile(
            name="core_smoke",
            description="CORE target smoke verification planning profile.",
            compatible_targets=("core",),
            purpose="Propose a conservative CORE verification path without making builder-II CORE-specific.",
            proposed_commands=(
                "builder verify --suite smoke",
                "run focused pytest suites selected by changed paths",
                "preserve CORE invariant and ADR boundaries",
            ),
            required_evidence=(
                "changed paths mapped to focused verification",
                "smoke or focused suite output captured by the operator",
                "CORE-specific assumptions kept inside the core target profile",
            ),
            failure_mode="If changed paths cannot be mapped safely, stop and request explicit CORE verification guidance.",
            rollback_hint="Do not repair CORE from builder-II; produce a target-scoped handoff for human review.",
        ),
        VerificationProfile(
            name="core_focused",
            description="CORE target focused verification planning profile.",
            compatible_targets=("core",),
            purpose="Propose focused CORE verification commands based on changed paths and known target hints.",
            proposed_commands=(
                "builder verify <changed-path>",
                "builder verify <changed-path> --fail-fast",
                "run additional invariant suites only when the changed path requires them",
            ),
            required_evidence=(
                "changed-path rationale recorded",
                "focused command output captured by the operator",
                "no CORE Workbench/UI conflation introduced by builder-II",
            ),
            failure_mode="If focused verification expands into policy or architecture changes, stop and create a separate review artifact.",
            rollback_hint="Use git revert in the target repo if a verified patch is wrong; builder-II should only record the plan.",
        ),
    )


def verification_profile_names() -> tuple[VerificationProfileName, ...]:
    return tuple(profile.name for profile in verification_profiles())


def get_verification_profile(name: VerificationProfileName) -> VerificationProfile:
    profiles = {profile.name: profile for profile in verification_profiles()}
    try:
        return profiles[name]
    except KeyError as exc:
        raise ValueError(f"unknown verification profile: {name}") from exc


def profiles_for_target(target: TargetName) -> tuple[VerificationProfile, ...]:
    return tuple(profile for profile in verification_profiles() if target in profile.compatible_targets)


def default_profile_for_target(target: TargetName) -> VerificationProfile:
    defaults: dict[TargetName, VerificationProfileName] = {
        "generic": "generic_basic",
        "builder": "builder_full",
        "core": "core_smoke",
    }
    return get_verification_profile(defaults[target])


def validate_verification_profiles() -> tuple[str, ...]:
    errors: list[str] = []
    seen: set[str] = set()
    for profile in verification_profiles():
        if profile.name in seen:
            errors.append(f"duplicate verification profile: {profile.name}")
        seen.add(profile.name)
        if not profile.description:
            errors.append(f"verification profile {profile.name} missing description")
        if not profile.compatible_targets:
            errors.append(f"verification profile {profile.name} missing compatible targets")
        if any(target not in target_names() for target in profile.compatible_targets):
            errors.append(f"verification profile {profile.name} has unknown target")
        if not profile.proposed_commands:
            errors.append(f"verification profile {profile.name} missing proposed commands")
        if not profile.required_evidence:
            errors.append(f"verification profile {profile.name} missing required evidence")
        if profile.executes_commands:
            errors.append(f"verification profile {profile.name} must not execute commands")
        if profile.runtime_execution != "disabled":
            errors.append(f"verification profile {profile.name} runtime must be disabled")
        if profile.shell_execution != "disabled":
            errors.append(f"verification profile {profile.name} shell execution must be disabled")
    for expected in ("generic_basic", "builder_fast", "builder_full", "core_smoke", "core_focused"):
        if expected not in seen:
            errors.append(f"missing verification profile: {expected}")
    return tuple(errors)


def render_verification_profile(profile: VerificationProfile, *, target: TargetName | None = None, task: str | None = None) -> str:
    lines = [
        f"# Verification profile: {profile.name}",
        "",
        profile.description,
        "",
        "## Purpose",
        "",
        profile.purpose,
        "",
        "## Compatible targets",
        "",
    ]
    lines.extend(f"- `{item}`" for item in profile.compatible_targets)
    if target:
        lines.extend(["", "## Selected target", "", f"`{target}`"])
    if task:
        lines.extend(["", "## Task", "", task])
    lines.extend(["", "## Proposed commands", ""])
    lines.extend(f"- `{command}`" for command in profile.proposed_commands)
    lines.extend(["", "## Required evidence", ""])
    lines.extend(f"- {item}" for item in profile.required_evidence)
    lines.extend(["", "## Failure mode", "", profile.failure_mode])
    lines.extend(["", "## Rollback hint", "", profile.rollback_hint])
    lines.extend([
        "",
        "## Governance boundary",
        "",
        "This profile proposes verification commands only. It does not execute commands, run models, construct agents, write files except explicit artifacts, mutate memory, commit, push, or grant runtime authority.",
        "",
    ])
    return "\n".join(lines)


def dumps_profile_artifact(profile: VerificationProfile, *, target: TargetName | None = None, task: str | None = None) -> str:
    return json_lib.dumps(profile.to_artifact_dict(target=target, task=task), indent=2, sort_keys=True) + "\n"


def write_profile_artifact(profile: VerificationProfile, output: Path, *, target: TargetName | None = None, task: str | None = None) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_profile_artifact(profile, target=target, task=task), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list) or not value:
        return [f"{field} must be a non-empty list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_profile_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["verification profile artifact must be a JSON object"]
    if data.get("kind") != VERIFICATION_ARTIFACT_KIND:
        errors.append(f"kind must be {VERIFICATION_ARTIFACT_KIND}")
    if data.get("schema_version") != VERIFICATION_ARTIFACT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_ARTIFACT_SCHEMA_VERSION}")
    if data.get("name") not in verification_profile_names():
        errors.append("name must be a known verification profile")
    target = data.get("target")
    if target and target not in target_names():
        errors.append("target must be one of: generic, builder, core")
    errors.extend(_string_list_errors(data.get("proposed_commands"), field="proposed_commands"))
    errors.extend(_string_list_errors(data.get("required_evidence"), field="required_evidence"))
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "verification_profile_artifact":
            errors.append("governance.capability_state must be verification_profile_artifact")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
            errors.append("governance.writes must be DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
        if governance.get("executes_commands") is not False:
            errors.append("governance.executes_commands must be false")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_profile_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_profile_artifact(data)
