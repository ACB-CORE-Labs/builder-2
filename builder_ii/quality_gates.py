from __future__ import annotations

import json as json_lib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.target_profiles import TargetName, target_names
from builder_ii.verification_profiles import VerificationProfileName, get_verification_profile, validate_profile_artifact

QUALITY_GATE_KIND = "builder_ii.quality_gate"
QUALITY_GATE_SCHEMA_VERSION = 1


def _clean_items(values: tuple[str, ...]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


@dataclass(frozen=True)
class QualityGateArtifact:
    target: TargetName
    verification_profile: VerificationProfileName
    task: str
    merge_blockers: tuple[str, ...] = ()
    rollback_requirements: tuple[str, ...] = ()

    def to_artifact_dict(self) -> dict[str, Any]:
        profile = get_verification_profile(self.verification_profile)
        profile_artifact = profile.to_artifact_dict(target=self.target, task=self.task)
        return {
            "kind": QUALITY_GATE_KIND,
            "schema_version": QUALITY_GATE_SCHEMA_VERSION,
            "target": self.target,
            "task": self.task,
            "verification_profile": profile_artifact,
            "required_commands": list(profile.proposed_commands),
            "required_evidence": list(profile.required_evidence),
            "merge_blockers": _clean_items(self.merge_blockers)
            or [
                "missing required evidence",
                "failing validation artifact",
                "runtime authority requested by an artifact-only gate",
            ],
            "rollback_requirements": _clean_items(self.rollback_requirements)
            or [profile.rollback_hint, "record rollback path before runtime promotion"],
            "approval_required": True,
            "governance": {
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "agent_construction": "DISABLED",
                "command_execution": "DISABLED",
                "shell_execution": "DISABLED",
                "file_writes": "DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH",
                "commit_push": "DISABLED",
                "artifact_is_authority": False,
                "quality_gate_executes_commands": False,
                "core_workbench_coupling": "NONE",
            },
        }


def create_quality_gate_artifact(
    *,
    target: TargetName,
    verification_profile: VerificationProfileName,
    task: str,
    merge_blockers: tuple[str, ...] = (),
    rollback_requirements: tuple[str, ...] = (),
) -> dict[str, Any]:
    return QualityGateArtifact(
        target=target,
        verification_profile=verification_profile,
        task=task,
        merge_blockers=merge_blockers,
        rollback_requirements=rollback_requirements,
    ).to_artifact_dict()


def dumps_quality_gate_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_quality_gate_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_quality_gate_artifact(artifact), encoding="utf-8")


def validate_quality_gate_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["quality gate artifact must be a JSON object"]

    if artifact.get("kind") != QUALITY_GATE_KIND:
        errors.append(f"kind must be {QUALITY_GATE_KIND}")
    if artifact.get("schema_version") != QUALITY_GATE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {QUALITY_GATE_SCHEMA_VERSION}")
    if artifact.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    if not artifact.get("task"):
        errors.append("task is required")

    verification_profile = artifact.get("verification_profile")
    profile_errors = validate_profile_artifact(verification_profile)
    errors.extend(f"verification_profile: {error}" for error in profile_errors)
    if isinstance(verification_profile, dict):
        selected_target = artifact.get("target")
        compatible_targets = verification_profile.get("compatible_targets")
        if isinstance(compatible_targets, list) and selected_target not in compatible_targets:
            errors.append("verification_profile must be compatible with target")

    for field in ("required_commands", "required_evidence", "merge_blockers", "rollback_requirements"):
        value = artifact.get(field)
        if not isinstance(value, list) or not value:
            errors.append(f"{field} must be a non-empty list")

    if artifact.get("approval_required") is not True:
        errors.append("approval_required must be true")

    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("runtime_execution") != "DISABLED":
            errors.append("governance.runtime_execution must be DISABLED")
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED")
        if governance.get("agent_construction") != "DISABLED":
            errors.append("governance.agent_construction must be DISABLED")
        if governance.get("command_execution") != "DISABLED":
            errors.append("governance.command_execution must be DISABLED")
        if governance.get("shell_execution") != "DISABLED":
            errors.append("governance.shell_execution must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("quality_gate_executes_commands") is not False:
            errors.append("governance.quality_gate_executes_commands must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    return errors


def validate_quality_gate_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_quality_gate_artifact(data)
