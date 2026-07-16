from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config import Settings
from builder_ii.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.target_profiles import TargetName, target_names, target_profile

HITL_PATCH_PROPOSAL_KIND = "builder_ii.hitl_patch_proposal"
HITL_PATCH_PROPOSAL_SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Governed future path — ordered state machine (design record only)
# ---------------------------------------------------------------------------
_ALLOWED_FUTURE_TRANSITIONS = (
    "patch proposal",
    "human approval record",
    "preflight record",
    "explicit patch application request",
    "patch application receipt",
    "rollback artifact",
    "verification record",
    "handoff/postflight",
)

# ---------------------------------------------------------------------------
# Denied behaviours — enforced in DESIGN_ONLY mode
# ---------------------------------------------------------------------------
_DENIED_CURRENT_BEHAVIORS = (
    "no patch application",
    "no source writes",
    "no file mutation",
    "no git mutation",
    "no commit/push",
    "no shell execution",
    "no subprocess execution",
    "no model execution",
    "no network/MCP execution",
    "no Goose runtime activation",
    "no deepagents runtime",
    "no CORE Workbench/UI coupling",
)

# ---------------------------------------------------------------------------
# Required gates before any future promotion to active runtime
# ---------------------------------------------------------------------------
_REQUIRED_FUTURE_GATES = (
    "docs",
    "tests",
    "command surface",
    "failure mode",
    "human approval boundary",
    "output artifact",
    "rollback path",
    "verification path",
)


def create_hitl_patch_proposal(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    patch_description: str = "",
    reason: str = "",
    patch_digest: str = "",
    unified_diff: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a design/spec artifact for the future HITL patch application path.

    This function ONLY produces a data record.  No patch is applied, no source
    file is written, no shell command is executed, and no subprocess is
    launched.  All runtime capability fields are explicitly set to DISABLED.
    """
    if settings is None:
        from builder_ii.config import load_settings

        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": HITL_PATCH_PROPOSAL_KIND,
        "schema_version": HITL_PATCH_PROPOSAL_SCHEMA_VERSION,
        "patch_description": patch_description,
        "reason": reason,
        "patch_digest": patch_digest,
        "unified_diff": unified_diff,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "allowed_future_transition": list(_ALLOWED_FUTURE_TRANSITIONS),
        "current_state": {
            "mode": "PASSIVE_FOUNDATION",
            "runtime": "DISABLED",
            "artifact_is_authority": False,
        },
        "denied_current_behavior": list(_DENIED_CURRENT_BEHAVIORS),
        "required_future_gates": list(_REQUIRED_FUTURE_GATES),
        "governance": build_standard_governance("PASSIVE_FOUNDATION"),
    }


def dumps_hitl_patch_proposal(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_patch_proposal(artifact: dict[str, Any], output: Path) -> None:
    """Write the spec artifact to disk as JSON.  No source mutation occurs."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_patch_proposal(artifact), encoding="utf-8")


def validate_hitl_patch_proposal(artifact: Any) -> list[str]:
    """Validate a HITL patch application spec artifact dict.

    Returns a list of error strings; an empty list means the artifact is valid.
    """
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl patch application spec artifact must be a JSON object"]

    if artifact.get("kind") != HITL_PATCH_PROPOSAL_KIND:
        errors.append(f"kind must be {HITL_PATCH_PROPOSAL_KIND}")
    if artifact.get("schema_version") != HITL_PATCH_PROPOSAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_PATCH_PROPOSAL_SCHEMA_VERSION}")

    if not isinstance(artifact.get("patch_digest"), str):
        errors.append("patch_digest must be a string")
    if not isinstance(artifact.get("unified_diff"), str):
        errors.append("unified_diff must be a string")

    # target
    target = artifact.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")

    # future transitions
    transitions = artifact.get("allowed_future_transition")
    if not isinstance(transitions, list):
        errors.append("allowed_future_transition must be a list")
    else:
        for req in _ALLOWED_FUTURE_TRANSITIONS:
            if req not in transitions:
                errors.append(f"allowed_future_transition must include '{req}'")

    # current_state
    curr_state = artifact.get("current_state")
    if not isinstance(curr_state, dict):
        errors.append("current_state must be an object")
    else:
        if curr_state.get("mode") != "PASSIVE_FOUNDATION":
            errors.append("current_state.mode must be PASSIVE_FOUNDATION")
        if curr_state.get("runtime") != "DISABLED":
            errors.append("current_state.runtime must be DISABLED or NOT_AUTHORIZED")
        if curr_state.get("artifact_is_authority") is not False:
            errors.append("current_state.artifact_is_authority must be false or NOT_AUTHORIZED")

    # denied behaviors
    denied = artifact.get("denied_current_behavior")
    if not isinstance(denied, list):
        errors.append("denied_current_behavior must be a list")
    else:
        for req in _DENIED_CURRENT_BEHAVIORS:
            if req not in denied:
                errors.append(f"denied_current_behavior must include '{req}'")

    # required gates
    gates = artifact.get("required_future_gates")
    if not isinstance(gates, list):
        errors.append("required_future_gates must be a list")
    else:
        for req in _REQUIRED_FUTURE_GATES:
            if req not in gates:
                errors.append(f"required_future_gates must include '{req}'")

    # governance block
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        errors.extend(validate_standard_governance(governance, "PASSIVE_FOUNDATION"))

    return errors


def validate_hitl_patch_proposal_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_hitl_patch_proposal(data)
