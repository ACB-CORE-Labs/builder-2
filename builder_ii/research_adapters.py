from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.research_plans import RESEARCH_PLAN_KIND
from builder_ii.target_profiles import target_names

RESEARCH_ADAPTER_KIND = "builder_ii.research_adapter"
RESEARCH_ADAPTER_SCHEMA_VERSION = 1


def _clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _clean_list(values: tuple[str, ...] | list[str] | None) -> list[str]:
    if values is None:
        return []
    return [item for item in (_clean(value) for value in values) if item]


def create_research_adapter_artifact(
    *,
    target: str,
    topic: str,
    research_question: str,
    plan_path: str | Path,
    plan_sha256: str,
    adapter_name: str = "open_deep_research_reference",
    output_contract: tuple[str, ...] | list[str] | None = None,
    review_notes: tuple[str, ...] | list[str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": RESEARCH_ADAPTER_KIND,
        "schema_version": RESEARCH_ADAPTER_SCHEMA_VERSION,
        "target": _clean(target),
        "adapter_name": _clean(adapter_name),
        "topic": _clean(topic),
        "research_question": _clean(research_question),
        "research_plan": {"path": str(plan_path), "kind": RESEARCH_PLAN_KIND, "sha256": _clean(plan_sha256)},
        "adapter_relation": "REFERENCE_ONLY",
        "handoff_state": "NOT_INVOKED",
        "output_contract": _clean_list(output_contract) or ["plan remains review-only", "collection requires later approval"],
        "review_notes": _clean_list(review_notes),
        "performed_actions": [],
        "governance": {
            "capability_state": "research_adapter_artifact",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "agent_construction": "DISABLED",
            "search_execution": "DISABLED",
            "mcp_execution": "DISABLED",
            "source_collection": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_research_adapter_artifact(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_research_adapter_artifact(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_research_adapter_artifact(artifact), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if not allow_empty and not value:
        return [f"{field} must be a non-empty list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_research_adapter_artifact(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["research adapter artifact must be a JSON object"]
    if artifact.get("kind") != RESEARCH_ADAPTER_KIND:
        errors.append(f"kind must be {RESEARCH_ADAPTER_KIND}")
    if artifact.get("schema_version") != RESEARCH_ADAPTER_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RESEARCH_ADAPTER_SCHEMA_VERSION}")
    if artifact.get("target") not in target_names():
        errors.append("target must be one of: generic, builder, core")
    for field in ("adapter_name", "topic", "research_question"):
        if not isinstance(artifact.get(field), str) or not artifact[field]:
            errors.append(f"{field} must be a non-empty string")
    plan = artifact.get("research_plan")
    if not isinstance(plan, dict):
        errors.append("research_plan must be an object")
    else:
        if not isinstance(plan.get("path"), str) or not plan["path"]:
            errors.append("research_plan.path must be a non-empty string")
        if plan.get("kind") != RESEARCH_PLAN_KIND:
            errors.append(f"research_plan.kind must be {RESEARCH_PLAN_KIND}")
        if not isinstance(plan.get("sha256"), str) or not plan["sha256"]:
            errors.append("research_plan.sha256 must be a non-empty string")
    if artifact.get("adapter_relation") != "REFERENCE_ONLY":
        errors.append("adapter_relation must be REFERENCE_ONLY")
    if artifact.get("handoff_state") != "NOT_INVOKED":
        errors.append("handoff_state must be NOT_INVOKED")
    errors.extend(_string_list_errors(artifact.get("output_contract"), field="output_contract"))
    errors.extend(_string_list_errors(artifact.get("review_notes", []), field="review_notes", allow_empty=True))
    if artifact.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "research_adapter_artifact":
            errors.append("governance.capability_state must be research_adapter_artifact")
        for key in ("runtime_execution", "model_execution", "agent_construction", "search_execution", "mcp_execution", "source_collection", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_research_adapter_artifact_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_research_adapter_artifact(data)
