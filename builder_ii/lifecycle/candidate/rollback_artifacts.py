from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.core.config import Settings
from builder_ii.lifecycle.setup.target_profiles import TargetName, target_names, target_profile

ROLLBACK_PLAN_KIND = "builder_ii.rollback_plan"
ROLLBACK_PLAN_SCHEMA_VERSION = 1

ROLLBACK_RECEIPT_KIND = "builder_ii.rollback_receipt"
ROLLBACK_RECEIPT_SCHEMA_VERSION = 1

_GOVERNANCE_DISABLED_KEYS = (
    "runtime_execution",
    "shell_execution",
    "model_execution",
    "source_writes",
    "git_mutation",
    "network_access",
    "goose_runtime_activation",
    "deepagents_runtime",
)


def _governance_block(capability_state: str) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        **{key: "DISABLED" for key in _GOVERNANCE_DISABLED_KEYS},
        "artifact_is_authority": False,
        "core_workbench_coupling": "NONE",
    }


def create_rollback_plan(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    related_artifact_refs: list[str] | None = None,
    rollback_strategy: str = "",
    operator_note: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a rollback plan artifact.

    This is a governance record only. It does not execute rollback, mutate files,
    run shell commands, perform git operations, or activate any runtime.
    """
    if settings is None:
        from builder_ii.core.config import load_settings

        settings = load_settings()

    selected = target_profile(settings, target_name, generic_repo=generic_repo)

    return {
        "kind": ROLLBACK_PLAN_KIND,
        "schema_version": ROLLBACK_PLAN_SCHEMA_VERSION,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "related_artifact_refs": list(related_artifact_refs or []),
        "rollback_strategy": rollback_strategy,
        "operator_note": operator_note,
        "current_state": "PLAN_RECORDED_ONLY",
        "runtime_execution": "DISABLED",
        "performed_actions": [],
        "artifact_is_authority": False,
        "governance": _governance_block("PLAN_RECORDED_ONLY"),
    }


def create_rollback_receipt(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    rollback_plan_ref: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a rollback receipt artifact.

    This is a receipt template only. It records that rollback has not executed.
    """
    if settings is None:
        from builder_ii.core.config import load_settings

        settings = load_settings()

    selected = target_profile(settings, target_name, generic_repo=generic_repo)

    return {
        "kind": ROLLBACK_RECEIPT_KIND,
        "schema_version": ROLLBACK_RECEIPT_SCHEMA_VERSION,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "rollback_plan_ref": rollback_plan_ref,
        "rollback_state": "NOT_EXECUTED",
        "performed_actions": [],
        "current_state": "RECEIPT_TEMPLATE_ONLY",
        "artifact_is_authority": False,
        "governance": _governance_block("RECEIPT_TEMPLATE_ONLY"),
    }


def dumps_rollback_plan(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def dumps_rollback_receipt(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_rollback_plan(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_rollback_plan(artifact), encoding="utf-8")


def write_rollback_receipt(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_rollback_receipt(artifact), encoding="utf-8")


def validate_rollback_plan(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["rollback plan artifact must be a JSON object"]

    if artifact.get("kind") != ROLLBACK_PLAN_KIND:
        errors.append(f"kind must be {ROLLBACK_PLAN_KIND}")
    if artifact.get("schema_version") != ROLLBACK_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ROLLBACK_PLAN_SCHEMA_VERSION}")

    errors.extend(_validate_target(artifact))

    refs = artifact.get("related_artifact_refs")
    if not isinstance(refs, list) or not refs or not all(isinstance(ref, str) and ref for ref in refs):
        errors.append("related_artifact_refs must be a non-empty list of non-empty strings")

    if not isinstance(artifact.get("rollback_strategy"), str) or not artifact["rollback_strategy"]:
        errors.append("rollback_strategy must be a non-empty string")

    if not isinstance(artifact.get("operator_note"), str):
        errors.append("operator_note must be a string")

    if artifact.get("current_state") != "PLAN_RECORDED_ONLY":
        errors.append("current_state must be PLAN_RECORDED_ONLY")
    if artifact.get("runtime_execution") != "DISABLED":
        errors.append("runtime_execution must be DISABLED or NOT_AUTHORIZED")
    if artifact.get("performed_actions") != []:
        errors.append("performed_actions must be empty")
    if artifact.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")

    errors.extend(_validate_governance_block(artifact, "PLAN_RECORDED_ONLY"))
    return errors


def validate_rollback_receipt(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["rollback receipt artifact must be a JSON object"]

    if artifact.get("kind") != ROLLBACK_RECEIPT_KIND:
        errors.append(f"kind must be {ROLLBACK_RECEIPT_KIND}")
    if artifact.get("schema_version") != ROLLBACK_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ROLLBACK_RECEIPT_SCHEMA_VERSION}")

    errors.extend(_validate_target(artifact))

    if not isinstance(artifact.get("rollback_plan_ref"), str) or not artifact["rollback_plan_ref"]:
        errors.append("rollback_plan_ref must be a non-empty string")
    rollback_state = artifact.get("rollback_state")
    current_state = artifact.get("current_state")
    if rollback_state not in ("NOT_EXECUTED", "EXECUTED"):
        errors.append("rollback_state must be NOT_EXECUTED")
        errors.append("rollback_state must be NOT_EXECUTED or EXECUTED")
    if current_state not in ("RECEIPT_TEMPLATE_ONLY", "OPERATIONALLY_VERIFIED"):
        errors.append("current_state must be RECEIPT_TEMPLATE_ONLY or OPERATIONALLY_VERIFIED")
    if rollback_state == "NOT_EXECUTED":
        if artifact.get("performed_actions") != []:
            errors.append("performed_actions must be empty")
            errors.append("performed_actions must be empty when rollback_state is NOT_EXECUTED")
        if current_state != "RECEIPT_TEMPLATE_ONLY":
            errors.append("current_state must be RECEIPT_TEMPLATE_ONLY when rollback_state is NOT_EXECUTED")
        expected_governance_state = "RECEIPT_TEMPLATE_ONLY"
    else:
        executed_error_start = len(errors)
        actions = artifact.get("performed_actions")
        if not isinstance(actions, list) or not actions:
            errors.append("performed_actions must be a non-empty list when rollback_state is EXECUTED")
        if current_state != "OPERATIONALLY_VERIFIED":
            errors.append("current_state must be OPERATIONALLY_VERIFIED when rollback_state is EXECUTED")
        if artifact.get("workspace_clean_after_rollback") is not True:
            errors.append("workspace_clean_after_rollback must be true when rollback_state is EXECUTED")
        if len(errors) > executed_error_start:
            errors.append("rollback_state must be NOT_EXECUTED")
        expected_governance_state = "OPERATIONALLY_VERIFIED"
    if artifact.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")

    errors.extend(_validate_governance_block(artifact, expected_governance_state))
    return errors


def validate_rollback_plan_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_rollback_plan(data)


def validate_rollback_receipt_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_rollback_receipt(data)


def _validate_target(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    target = artifact.get("target")
    if not isinstance(target, dict):
        return ["target must be an object"]

    if target.get("name") not in target_names():
        errors.append("target.name must be one of: generic, builder, core")
    if not target.get("repo"):
        errors.append("target.repo is required")
    return errors


def _validate_governance_block(artifact: dict[str, Any], expected_capability_state: str) -> list[str]:
    errors: list[str] = []
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        return ["governance must be an object"]

    if governance.get("capability_state") != expected_capability_state:
        errors.append(f"governance.capability_state must be {expected_capability_state}")

    for key in _GOVERNANCE_DISABLED_KEYS:
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")

    if governance.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors
