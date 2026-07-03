from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.target_profiles import TargetName, target_names, target_profile

# ---------------------------------------------------------------------------
# Artifact kind constants
# ---------------------------------------------------------------------------

HITL_EVIDENCE_BUNDLE_KIND = "builder_ii.hitl_evidence_bundle"
HITL_EVIDENCE_BUNDLE_SCHEMA_VERSION = 1

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
    "subprocess_execution",
)


def create_hitl_evidence_bundle(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    bundle_id: str = "",
    created_at: str = "",
    created_by: str = "",
    proposal_ref: str = "",
    approval_ref: str = "",
    preflight_ref: str = "",
    request_ref: str = "",
    postflight_ref: str = "",
    verification_ref: str = "",
    rollback_plan_ref: str | None = None,
    rollback_receipt_ref: str | None = None,
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a read-only HITL execution evidence bundle/index.

    This is an aggregation and index record. It is read-only metadata, not a
    proof of execution, and does not grant any runtime authority.
    """
    if settings is None:
        from builder_ii.config import load_settings

        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": HITL_EVIDENCE_BUNDLE_KIND,
        "schema_version": HITL_EVIDENCE_BUNDLE_SCHEMA_VERSION,
        "target_name": selected.name,
        "bundle_id": bundle_id,
        "created_at": created_at,
        "created_by": created_by,
        "proposal_ref": proposal_ref,
        "approval_ref": approval_ref,
        "preflight_ref": preflight_ref,
        "request_ref": request_ref,
        "postflight_ref": postflight_ref,
        "verification_ref": verification_ref,
        "rollback_plan_ref": rollback_plan_ref,
        "rollback_receipt_ref": rollback_receipt_ref,
        "execution_authority": "NOT_GRANTED",
        "runtime_execution": "NOT_PERFORMED_BY_BUNDLE",
        "bundle_state": "INDEX_ONLY",
        "governance": {
            **{key: "DISABLED" for key in _GOVERNANCE_DISABLED_KEYS},
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_hitl_evidence_bundle(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_evidence_bundle(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_evidence_bundle(artifact), encoding="utf-8")


def _is_safe_relative_path(path_str: str) -> bool:
    if not path_str:
        return False
    # No absolute paths
    if path_str.startswith("/") or path_str.startswith("\\"):
        return False
    if ":" in path_str:  # No Windows drive letters
        return False
    # No directory traversal (..)
    parts = path_str.replace("\\", "/").split("/")
    if ".." in parts:
        return False
    return True


def validate_hitl_evidence_bundle(artifact: Any) -> list[str]:
    """Validate an HITL execution evidence bundle/index artifact.

    Returns a list of error strings, or an empty list if valid.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl evidence bundle artifact must be a JSON object"]

    if artifact.get("kind") != HITL_EVIDENCE_BUNDLE_KIND:
        errors.append(f"kind must be {HITL_EVIDENCE_BUNDLE_KIND}")
    if artifact.get("schema_version") != HITL_EVIDENCE_BUNDLE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_EVIDENCE_BUNDLE_SCHEMA_VERSION}")

    # target name check
    target_name = artifact.get("target_name")
    if target_name not in target_names():
        errors.append("target_name must be one of: generic, builder, core")

    # required refs checking
    required_refs = (
        "proposal_ref",
        "approval_ref",
        "preflight_ref",
        "request_ref",
        "postflight_ref",
        "verification_ref",
    )
    for ref in required_refs:
        val = artifact.get(ref)
        if not isinstance(val, str) or not val:
            errors.append(f"{ref} is required and must be a non-empty string")
        elif not _is_safe_relative_path(val):
            errors.append(f"{ref} must be a safe relative path (no absolute paths or directory traversal)")

    # optional rollback refs
    for ref in ("rollback_plan_ref", "rollback_receipt_ref"):
        if ref in artifact:
            val = artifact.get(ref)
            if val is not None:
                if not isinstance(val, str) or not val:
                    errors.append(f"{ref} must be a non-empty string or None")
                elif not _is_safe_relative_path(val):
                    errors.append(f"{ref} must be a safe relative path (no absolute paths or directory traversal)")

    # state & authority restrictions
    if artifact.get("execution_authority") != "NOT_GRANTED":
        errors.append("execution_authority must be NOT_GRANTED")
    if artifact.get("runtime_execution") != "NOT_PERFORMED_BY_BUNDLE":
        errors.append("runtime_execution must be NOT_PERFORMED_BY_BUNDLE")
    if artifact.get("bundle_state") != "INDEX_ONLY":
        errors.append("bundle_state must be INDEX_ONLY")

    if "execution_state" in artifact and artifact.get("execution_state") not in (
        "NOT_RUN",
        "NOT_EXECUTED",
        "INDEX_ONLY",
    ):
        errors.append("execution_state cannot imply execution authority")

    if "verification_state" in artifact and artifact.get("verification_state") not in ("NOT_RUN", "PASS", "FAIL"):
        errors.append("verification_state cannot imply approval")

    # governance block check
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in _GOVERNANCE_DISABLED_KEYS:
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def validate_hitl_evidence_bundle_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_hitl_evidence_bundle(data)
