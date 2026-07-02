from __future__ import annotations

import json as json_lib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from builder_ii.agent_profiles import AgentProfileName, agent_profile_names
from builder_ii.target_profiles import TargetName, target_names

HANDOFF_KIND = "builder_ii.handoff_artifact"
HANDOFF_SCHEMA_VERSION = 1


def _clean_items(values: tuple[str, ...]) -> list[str]:
    return [value.strip() for value in values if value.strip()]


@dataclass(frozen=True)
class HandoffArtifact:
    target: TargetName
    agent_profile: AgentProfileName
    task: str
    summary: str
    next_steps: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    verification: tuple[str, ...] = ()
    created_at: str | None = None

    def to_artifact_dict(self) -> dict[str, Any]:
        return {
            "kind": HANDOFF_KIND,
            "schema_version": HANDOFF_SCHEMA_VERSION,
            "created_at": self.created_at
            or datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "target": self.target,
            "agent_profile": self.agent_profile,
            "task": self.task,
            "summary": self.summary,
            "next_steps": _clean_items(self.next_steps),
            "blockers": _clean_items(self.blockers),
            "verification": _clean_items(self.verification),
            "governance": {
                "runtime_execution": "DISABLED",
                "model_execution": "DISABLED",
                "agent_construction": "DISABLED",
                "notes_vault_mutation": "DISABLED",
                "shell_execution": "DISABLED",
                "file_writes": "DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH",
                "commit_push": "DISABLED",
                "artifact_is_authority": False,
                "core_workbench_coupling": "NONE",
            },
        }


def create_handoff_artifact(
    *,
    target: TargetName,
    agent_profile: AgentProfileName,
    task: str,
    summary: str,
    next_steps: tuple[str, ...] = (),
    blockers: tuple[str, ...] = (),
    verification: tuple[str, ...] = (),
    created_at: str | None = None,
) -> dict[str, Any]:
    return HandoffArtifact(
        target=target,
        agent_profile=agent_profile,
        task=task,
        summary=summary,
        next_steps=next_steps,
        blockers=blockers,
        verification=verification,
        created_at=created_at,
    ).to_artifact_dict()


def dumps_handoff_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_handoff_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_handoff_artifact(artifact), encoding="utf-8")


def validate_handoff_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["handoff artifact must be a JSON object"]

    if artifact.get("kind") != HANDOFF_KIND:
        errors.append(f"kind must be {HANDOFF_KIND}")
    if artifact.get("schema_version") != HANDOFF_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HANDOFF_SCHEMA_VERSION}")
    if not artifact.get("created_at"):
        errors.append("created_at is required")
    if artifact.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    if artifact.get("agent_profile") not in agent_profile_names():
        errors.append("agent_profile must be known")
    if not artifact.get("task"):
        errors.append("task is required")
    if not artifact.get("summary"):
        errors.append("summary is required")

    for field in ("next_steps", "blockers", "verification"):
        if not isinstance(artifact.get(field), list):
            errors.append(f"{field} must be a list")

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
        if governance.get("notes_vault_mutation") != "DISABLED":
            errors.append("governance.notes_vault_mutation must be DISABLED")
        if governance.get("shell_execution") != "DISABLED":
            errors.append("governance.shell_execution must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    return errors


def validate_handoff_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_handoff_artifact(data)
