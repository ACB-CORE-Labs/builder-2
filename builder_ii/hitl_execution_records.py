from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.target_profiles import TargetName, target_names, target_profile

# ---------------------------------------------------------------------------
# Artifact kind constants
# ---------------------------------------------------------------------------

HITL_EXECUTION_REQUEST_KIND = "builder_ii.hitl_execution_request"
HITL_EXECUTION_REQUEST_SCHEMA_VERSION = 1

HITL_EXECUTION_RECEIPT_KIND = "builder_ii.hitl_execution_receipt"
HITL_EXECUTION_RECEIPT_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Governance denial list – shared by both request and receipt artifacts
# ---------------------------------------------------------------------------

_GOVERNANCE_DENIED_KEYS = (
    "shell_execution",
    "subprocess_execution",
    "command_execution",
    "model_execution",
    "source_writes",
    "git_mutation",
    "commit_push",
    "network_mcp_execution",
    "goose_runtime_activation",
    "deepagents_runtime",
)

# ---------------------------------------------------------------------------
# Required future chain (documented by the request artifact)
# ---------------------------------------------------------------------------

_REQUIRED_FUTURE_CHAIN = (
    "command proposal",
    "approval",
    "preflight",
    "explicit execution request",
    "execution receipt",
    "postflight/handoff",
    "rollback",
    "verification",
)


# ===================================================================
#  Execution Request Artifact
# ===================================================================

def create_hitl_execution_request(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    command_proposal_ref: str = "",
    approval_record_ref: str = "",
    preflight_record_ref: str = "",
    requested_by: str = "",
    requested_at: str = "",
    explicit_operator_intent: str = "",
    command_preview: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create an HITL execution request artifact.

    This is a design/record artifact only.  It does not execute commands,
    does not grant authority, and records operator intent for future
    governed execution flows.
    """
    if settings is None:
        from builder_ii.config import load_settings
        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": HITL_EXECUTION_REQUEST_KIND,
        "schema_version": HITL_EXECUTION_REQUEST_SCHEMA_VERSION,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "command_proposal_ref": command_proposal_ref,
        "approval_record_ref": approval_record_ref,
        "preflight_record_ref": preflight_record_ref,
        "requested_by": requested_by,
        "requested_at": requested_at,
        "explicit_operator_intent": explicit_operator_intent,
        "command_preview": command_preview,
        "current_state": "REQUEST_RECORDED_ONLY",
        "runtime_execution": "DISABLED",
        "artifact_is_authority": False,
        "required_future_chain": list(_REQUIRED_FUTURE_CHAIN),
        "governance": {
            "capability_state": "REQUEST_RECORDED_ONLY",
            "runtime_execution": "DISABLED",
            **{key: "DISABLED" for key in _GOVERNANCE_DENIED_KEYS},
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_hitl_execution_request(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_execution_request(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_execution_request(artifact), encoding="utf-8")


def validate_hitl_execution_request(artifact: Any) -> list[str]:
    """Validate an HITL execution request artifact.

    Returns an empty list when the artifact is valid.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl execution request artifact must be a JSON object"]

    if artifact.get("kind") != HITL_EXECUTION_REQUEST_KIND:
        errors.append(f"kind must be {HITL_EXECUTION_REQUEST_KIND}")
    if artifact.get("schema_version") != HITL_EXECUTION_REQUEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_EXECUTION_REQUEST_SCHEMA_VERSION}")

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
    for ref_field in ("command_proposal_ref", "approval_record_ref", "preflight_record_ref"):
        val = artifact.get(ref_field)
        if not isinstance(val, str) or not val:
            errors.append(f"{ref_field} is required")

    # Required string fields
    for field in ("requested_by", "requested_at", "explicit_operator_intent", "command_preview"):
        if not isinstance(artifact.get(field), str):
            errors.append(f"{field} must be a string")

    # Current state / runtime
    if artifact.get("current_state") != "REQUEST_RECORDED_ONLY":
        errors.append("current_state must be REQUEST_RECORDED_ONLY")
    if artifact.get("runtime_execution") != "DISABLED":
        errors.append("runtime_execution must be DISABLED")

    # Authority and coupling
    if artifact.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")

    # Governance block
    errors.extend(_validate_governance_block(artifact, "REQUEST_RECORDED_ONLY"))

    return errors


# ===================================================================
#  Execution Receipt Artifact
# ===================================================================

def create_hitl_execution_receipt(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    request_ref: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create an HITL execution receipt artifact.

    This is a receipt template only.  It records the fact that NO execution
    has occurred and all execution-result fields are null/empty.  It does
    not execute commands and does not grant authority.
    """
    if settings is None:
        from builder_ii.config import load_settings
        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": HITL_EXECUTION_RECEIPT_KIND,
        "schema_version": HITL_EXECUTION_RECEIPT_SCHEMA_VERSION,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "request_ref": request_ref,
        "execution_state": "NOT_EXECUTED",
        "exit_code": None,
        "stdout_ref": None,
        "stderr_ref": None,
        "started_at": None,
        "completed_at": None,
        "performed_actions": [],
        "current_state": "RECEIPT_TEMPLATE_ONLY",
        "artifact_is_authority": False,
        "governance": {
            "capability_state": "RECEIPT_TEMPLATE_ONLY",
            "runtime_execution": "DISABLED",
            **{key: "DISABLED" for key in _GOVERNANCE_DENIED_KEYS},
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_hitl_execution_receipt(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_execution_receipt(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_execution_receipt(artifact), encoding="utf-8")


def validate_hitl_execution_receipt(artifact: Any) -> list[str]:
    """Validate an HITL execution receipt artifact.

    Returns an empty list when the artifact is valid.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl execution receipt artifact must be a JSON object"]

    if artifact.get("kind") != HITL_EXECUTION_RECEIPT_KIND:
        errors.append(f"kind must be {HITL_EXECUTION_RECEIPT_KIND}")
    if artifact.get("schema_version") != HITL_EXECUTION_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_EXECUTION_RECEIPT_SCHEMA_VERSION}")

    # Target validation
    target = artifact.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")

    # Execution state must be NOT_EXECUTED
    if artifact.get("execution_state") != "NOT_EXECUTED":
        errors.append("execution_state must be NOT_EXECUTED")

    # Execution-result fields must be null/empty (no actual execution occurred)
    if artifact.get("exit_code") is not None:
        errors.append("exit_code must be null (no execution)")
    if artifact.get("stdout_ref") is not None:
        errors.append("stdout_ref must be null (no execution)")
    if artifact.get("stderr_ref") is not None:
        errors.append("stderr_ref must be null (no execution)")
    if artifact.get("started_at") is not None:
        errors.append("started_at must be null (no execution)")
    if artifact.get("completed_at") is not None:
        errors.append("completed_at must be null (no execution)")

    # Performed actions must be empty
    if artifact.get("performed_actions") != []:
        errors.append("performed_actions must be empty (no execution)")

    # Current state / authority
    if artifact.get("current_state") != "RECEIPT_TEMPLATE_ONLY":
        errors.append("current_state must be RECEIPT_TEMPLATE_ONLY")
    if artifact.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")

    # Governance block
    errors.extend(_validate_governance_block(artifact, "RECEIPT_TEMPLATE_ONLY"))

    return errors


# ===================================================================
#  File I/O helpers (shared)
# ===================================================================

def validate_hitl_execution_request_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_hitl_execution_request(data)


def validate_hitl_execution_receipt_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_hitl_execution_receipt(data)


# ===================================================================
#  Internal helpers
# ===================================================================

def _validate_governance_block(artifact: dict[str, Any], expected_capability_state: str) -> list[str]:
    """Validate the governance block shared by both artifact types."""
    errors: list[str] = []
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
        return errors

    if governance.get("capability_state") != expected_capability_state:
        errors.append(f"governance.capability_state must be {expected_capability_state}")

    for key in ("runtime_execution", *_GOVERNANCE_DENIED_KEYS):
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED")

    if governance.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")

    return errors
