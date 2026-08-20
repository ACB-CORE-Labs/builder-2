from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.core.config import Settings
from builder_ii.governance.authority.governance_standard import build_standard_governance, validate_standard_governance
from builder_ii.lifecycle.setup.target_profiles import TargetName, target_names, target_profile

HITL_PATCH_PROPOSAL_KIND = "builder_ii.hitl_patch_proposal"
HITL_PATCH_PROPOSAL_SCHEMA_VERSION = 2
HITL_PATCH_PROPOSAL_LEGACY_SCHEMA_VERSION = 1
MAX_UNIFIED_DIFF_BYTES = 64 * 1024
_HEAD_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")

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


def _diff_path(header_value: str, *, field: str) -> str | None:
    value = header_value.split("\t", 1)[0]
    if value == "/dev/null":
        return None
    prefix = "a/" if field == "old" else "b/"
    if not value.startswith(prefix):
        raise ValueError(f"{field} diff path must use {prefix!r} or /dev/null")
    relative = value[len(prefix) :]
    path = Path(relative)
    if not relative or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ValueError(f"{field} diff path must be a normalized repository-relative path")
    return relative


def exact_scope_from_unified_diff(unified_diff: str) -> dict[str, Any]:
    """Parse the narrow text unified-diff subset admitted for passive proposals."""
    if not isinstance(unified_diff, str) or not unified_diff:
        raise ValueError("unified_diff must be a non-empty string")
    try:
        raw = unified_diff.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("unified_diff must be valid UTF-8 text") from exc
    if len(raw) > MAX_UNIFIED_DIFF_BYTES:
        raise ValueError(f"unified_diff exceeds the {MAX_UNIFIED_DIFF_BYTES}-byte limit")
    forbidden = ("GIT binary patch", "Binary files ", "diff --cc ", "diff --combined ", "rename from ", "rename to ", "copy from ", "copy to ")
    if any(line.startswith(forbidden) for line in unified_diff.splitlines()):
        raise ValueError("unified_diff uses an unsupported binary, combined, rename, or copy form")

    lines = unified_diff.splitlines()
    files: list[dict[str, str | None]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith("diff --git "):
            index += 1
            continue
        if not line.startswith("--- "):
            raise ValueError("unified_diff must contain only unified file sections")
        if index + 1 >= len(lines) or not lines[index + 1].startswith("+++ "):
            raise ValueError("each old-file header must be followed by a new-file header")
        old_path = _diff_path(line[4:], field="old")
        new_path = _diff_path(lines[index + 1][4:], field="new")
        if old_path is None and new_path is None:
            raise ValueError("a diff section cannot delete and create /dev/null")
        index += 2
        hunks = 0
        while index < len(lines) and not lines[index].startswith(("--- ", "diff --git ")):
            current = lines[index]
            if current.startswith("@@ "):
                hunks += 1
            elif not current.startswith((" ", "+", "-", "\\ No newline at end of file")):
                raise ValueError("unified_diff contains unsupported section metadata")
            index += 1
        if hunks == 0:
            raise ValueError("each diff section must contain at least one hunk")
        files.append({"old_path": old_path, "new_path": new_path})
    if not files:
        raise ValueError("unified_diff must contain at least one file section")
    return {"format": "unified_text_diff", "files": files}


def create_bound_hitl_patch_proposal(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    patch_description: str,
    reason: str,
    unified_diff: str,
    generic_repo: Path | None = None,
    bound_target_repo: Path | None = None,
    target_head_sha: str,
    verification_receipt_bytes: bytes,
) -> dict[str, Any]:
    """Create one canonical passive proposal with internally derived bindings."""
    if not isinstance(patch_description, str) or not patch_description.strip():
        raise ValueError("patch_description must be a non-empty string")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason must be a non-empty string")
    if not isinstance(target_head_sha, str) or not _HEAD_SHA_RE.fullmatch(target_head_sha):
        raise ValueError("target_head_sha must be a 40-character commit SHA")
    if not isinstance(verification_receipt_bytes, bytes) or not verification_receipt_bytes:
        raise ValueError("verification_receipt_bytes must be non-empty bytes")
    exact_scope = exact_scope_from_unified_diff(unified_diff)
    diff_bytes = unified_diff.encode("utf-8")
    proposal = create_hitl_patch_proposal(
        settings,
        target_name=target_name,
        patch_description=patch_description.strip(),
        reason=reason.strip(),
        patch_digest=hashlib.sha256(diff_bytes).hexdigest(),
        unified_diff=unified_diff,
        generic_repo=generic_repo,
        target_head_sha=target_head_sha.lower(),
        verification_receipt_file_sha256=hashlib.sha256(verification_receipt_bytes).hexdigest(),
    )
    if bound_target_repo is not None:
        proposal["target"]["repo"] = str(bound_target_repo.resolve())
    proposal["exact_scope"] = exact_scope
    errors = validate_hitl_patch_proposal(proposal)
    if errors:
        raise ValueError("generated HITL patch proposal is invalid: " + "; ".join(errors))
    return proposal


def create_hitl_patch_proposal(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    patch_description: str = "",
    reason: str = "",
    patch_digest: str = "",
    unified_diff: str = "",
    generic_repo: Path | None = None,
    target_head_sha: str = "",
    verification_receipt_file_sha256: str = "",
) -> dict[str, Any]:
    """Create a design/spec artifact for the future HITL patch application path.

    This function ONLY produces a data record.  No patch is applied, no source
    file is written, no shell command is executed, and no subprocess is
    launched.  All runtime capability fields are explicitly set to DISABLED.
    """
    if settings is None:
        from builder_ii.core.config import load_settings

        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": HITL_PATCH_PROPOSAL_KIND,
        "schema_version": HITL_PATCH_PROPOSAL_SCHEMA_VERSION,
        "target_head_sha": target_head_sha,
        "verification_receipt_file_sha256": verification_receipt_file_sha256,
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
    if artifact.get("schema_version") not in {
        HITL_PATCH_PROPOSAL_SCHEMA_VERSION,
        HITL_PATCH_PROPOSAL_LEGACY_SCHEMA_VERSION,
    }:
        errors.append(f"schema_version must be {HITL_PATCH_PROPOSAL_SCHEMA_VERSION} or legacy {HITL_PATCH_PROPOSAL_LEGACY_SCHEMA_VERSION}")

    if artifact.get("schema_version") == HITL_PATCH_PROPOSAL_LEGACY_SCHEMA_VERSION:
        # v1 remains valid for passive/historical recognition. The authority boundary
        # in apply_hitl_patch refuses it and requires regeneration plus fresh approval.
        pass
    else:
        target_head_sha = artifact.get("target_head_sha")
        if not isinstance(target_head_sha, str) or len(target_head_sha) != 40:
            errors.append("target_head_sha must be a 40-character commit SHA")
        receipt_digest = artifact.get("verification_receipt_file_sha256")
        if not isinstance(receipt_digest, str) or len(receipt_digest) != 64:
            errors.append("verification_receipt_file_sha256 must be a SHA-256 hex digest")

        unified_diff = artifact.get("unified_diff")
        if "exact_scope" in artifact and isinstance(unified_diff, str):
            try:
                expected_scope = exact_scope_from_unified_diff(unified_diff)
            except ValueError as exc:
                errors.append(str(exc))
            else:
                expected_digest = hashlib.sha256(unified_diff.encode("utf-8")).hexdigest()
                if artifact.get("patch_digest") != expected_digest:
                    errors.append("patch_digest must bind the exact UTF-8 unified_diff bytes")
                if artifact.get("exact_scope") != expected_scope:
                    errors.append("exact_scope must match the canonical unified_diff projection")

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
