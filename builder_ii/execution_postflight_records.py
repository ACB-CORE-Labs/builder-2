from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.target_profiles import TargetName, target_names, target_profile

# ---------------------------------------------------------------------------
# Artifact kind constants
# ---------------------------------------------------------------------------

EXECUTION_POSTFLIGHT_RECORD_KIND = "builder_ii.execution_postflight_record"
EXECUTION_POSTFLIGHT_RECORD_SCHEMA_VERSION = 1

EXECUTION_VERIFICATION_RECORD_KIND = "builder_ii.execution_verification_record"
EXECUTION_VERIFICATION_RECORD_SCHEMA_VERSION = 1

_GOVERNANCE_DISABLED_KEYS = (
    "runtime_execution",
    "shell_execution",
    "command_execution",
    "model_execution",
    "source_writes",
    "git_mutation",
    "network_access",
    "goose_runtime_activation",
    "deepagents_runtime",
)


# ===================================================================
#  Execution Postflight Record
# ===================================================================

def create_execution_postflight_record(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    request_ref: str = "",
    receipt_ref: str = "",
    preflight_ref: str = "",
    approval_ref: str = "",
    expected_outcome: str = "",
    observed_state_ref: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a design-only execution postflight record."""
    if settings is None:
        from builder_ii.config import load_settings
        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": EXECUTION_POSTFLIGHT_RECORD_KIND,
        "schema_version": EXECUTION_POSTFLIGHT_RECORD_SCHEMA_VERSION,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "request_ref": request_ref,
        "receipt_ref": receipt_ref,
        "preflight_ref": preflight_ref,
        "approval_ref": approval_ref,
        "expected_outcome": expected_outcome,
        "observed_state_ref": observed_state_ref,
        "postflight_state": "NOT_RUN",
        "performed_actions": [],
        "artifact_is_authority": False,
        "governance": {
            **{key: "DISABLED" for key in _GOVERNANCE_DISABLED_KEYS},
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_execution_postflight_record(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_execution_postflight_record(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_execution_postflight_record(artifact), encoding="utf-8")


def validate_execution_postflight_record(artifact: Any) -> list[str]:
    """Validate an execution postflight record artifact.

    Returns an empty list when the artifact is valid.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["execution postflight record artifact must be a JSON object"]

    if artifact.get("kind") != EXECUTION_POSTFLIGHT_RECORD_KIND:
        errors.append(f"kind must be {EXECUTION_POSTFLIGHT_RECORD_KIND}")
    if artifact.get("schema_version") != EXECUTION_POSTFLIGHT_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EXECUTION_POSTFLIGHT_RECORD_SCHEMA_VERSION}")

    # Target validation
    target = artifact.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")

    # Required refs — all must be non-empty strings
    for ref_field in ("request_ref", "receipt_ref", "preflight_ref", "approval_ref"):
        val = artifact.get(ref_field)
        if not isinstance(val, str) or not val:
            errors.append(f"{ref_field} is required and must be a non-empty string")

    # Required string fields
    for field in ("expected_outcome", "observed_state_ref"):
        if not isinstance(artifact.get(field), str):
            errors.append(f"{field} must be a string")

    # State
    postflight_state = artifact.get("postflight_state")
    if postflight_state not in ("NOT_RUN", "RUN_COMPLETE"):
        errors.append("postflight_state must be NOT_RUN")
        errors.append("postflight_state must be NOT_RUN or RUN_COMPLETE")

    # Performed actions are empty for templates and populated for executed postflight records.
    performed_actions = artifact.get("performed_actions")
    if postflight_state == "NOT_RUN" and performed_actions != []:
        errors.append("performed_actions must be empty")
        errors.append("performed_actions must be empty when postflight_state is NOT_RUN")
    if postflight_state == "RUN_COMPLETE" and (
        not isinstance(performed_actions, list) or not performed_actions
    ):
        errors.append("performed_actions must be a non-empty list when postflight_state is RUN_COMPLETE")

    # Authority
    if artifact.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")

    # Governance block
    errors.extend(_validate_governance_block(artifact))

    return errors


# ===================================================================
#  Execution Verification Record
# ===================================================================

def create_execution_verification_record(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    request_ref: str = "",
    receipt_ref: str = "",
    postflight_ref: str = "",
    verification_state: str = "NOT_RUN",
    verification_summary: str = "",
    evidence_refs: list[str] | None = None,
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a design-only execution verification record."""
    if settings is None:
        from builder_ii.config import load_settings
        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": EXECUTION_VERIFICATION_RECORD_KIND,
        "schema_version": EXECUTION_VERIFICATION_RECORD_SCHEMA_VERSION,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "request_ref": request_ref,
        "receipt_ref": receipt_ref,
        "postflight_ref": postflight_ref,
        "verification_state": verification_state,
        "verification_summary": verification_summary,
        "evidence_refs": list(evidence_refs or []),
        "performed_actions": [],
        "artifact_is_authority": False,
        "governance": {
            **{key: "DISABLED" for key in _GOVERNANCE_DISABLED_KEYS},
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_execution_verification_record(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_execution_verification_record(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_execution_verification_record(artifact), encoding="utf-8")


def validate_execution_verification_record(artifact: Any) -> list[str]:
    """Validate an execution verification record artifact.

    Returns an empty list when the artifact is valid.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["execution verification record artifact must be a JSON object"]

    if artifact.get("kind") != EXECUTION_VERIFICATION_RECORD_KIND:
        errors.append(f"kind must be {EXECUTION_VERIFICATION_RECORD_KIND}")
    if artifact.get("schema_version") != EXECUTION_VERIFICATION_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {EXECUTION_VERIFICATION_RECORD_SCHEMA_VERSION}")

    # Target validation
    target = artifact.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")

    # Required refs — all must be non-empty strings
    for ref_field in ("request_ref", "receipt_ref", "postflight_ref"):
        val = artifact.get(ref_field)
        if not isinstance(val, str) or not val:
            errors.append(f"{ref_field} is required and must be a non-empty string")

    # State validation
    state = artifact.get("verification_state")
    if state not in ("NOT_RUN", "PASS", "FAIL"):
        errors.append("verification_state must be NOT_RUN, PASS, or FAIL")

    # Summary
    if not isinstance(artifact.get("verification_summary"), str):
        errors.append("verification_summary must be a string")

    # Evidence refs
    evidence_refs = artifact.get("evidence_refs")
    if not isinstance(evidence_refs, list) or not all(isinstance(ref, str) for ref in evidence_refs):
        errors.append("evidence_refs must be a list of strings")

    # Performed actions must be empty
    if artifact.get("performed_actions") != []:
        errors.append("performed_actions must be empty")

    # Authority
    if artifact.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")

    # Governance block
    errors.extend(_validate_governance_block(artifact))

    return errors


# ===================================================================
#  File I/O helpers
# ===================================================================

def validate_execution_postflight_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_execution_postflight_record(data)


def validate_execution_verification_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_execution_verification_record(data)


# ===================================================================
#  Internal helpers
# ===================================================================

def _validate_governance_block(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
        return errors

    for key in _GOVERNANCE_DISABLED_KEYS:
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED")

    if governance.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")

    return errors
