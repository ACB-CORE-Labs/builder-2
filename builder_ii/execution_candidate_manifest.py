from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.command_authority import TIER_4, get_command_record
from builder_ii.hitl_promotion_artifacts import (
    ALLOWED_PROPOSAL_KINDS,
    HITL_APPROVAL_BOUNDARY_KIND,
    HITL_PROMOTION_DECISION_KIND,
    HITL_PROMOTION_REQUEST_KIND,
    HITL_PROMOTION_REVIEW_KIND,
    _validate_ref,
)

EXECUTION_CANDIDATE_MANIFEST_KIND = "builder_ii.execution_candidate_manifest"
EXECUTION_CANDIDATE_MANIFEST_SCHEMA_VERSION = 1

EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND = (
    "builder_ii.execution_candidate_manifest_validation_report"
)
EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_FORBIDDEN_COMMAND_FRAGMENTS = (
    "\n",
    "\r",
    "&&",
    "||",
    "|",
    ";",
    "`",
    "$(",
    ">",
    "<",
)

_FORBIDDEN_COMMANDS = (
    "sh -c",
    "bash -c",
    "python -c",
    "curl",
    "wget",
    "chmod",
    "rm -rf",
)

_FORBIDDEN_ACTIVE_STATES = {
    "execute",
    "run",
    "activate",
    "authorized",
    "enabled",
    "promoted",
    "executable",
    "running",
    "applied",
    "merged",
    "verified",
    "active",
}

_FORBIDDEN_ACTIVE_STATE_RE = re.compile(
    r"(?<![a-z0-9])("
    + "|".join(re.escape(term) for term in sorted(_FORBIDDEN_ACTIVE_STATES))
    + r")(?![a-z0-9])",
    re.IGNORECASE,
)

_SAFE_PASSIVE_EXACT_STRINGS = {
    "candidate_recorded_only",
    "boundary_checked_only",
    "preflight_required_only",
    "rollback_required_only",
    "verification_required_only",
    "validation_only",
    "approved_for_candidate_design",
    "requested_only",
    "reviewed_only",
    "decision_recorded_only",
    "boundary_recorded_only",
    "rejected_only",
    "records_human_decision",
    "records_candidate_intent",
}


def canonical_digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _is_passive_or_denial_context(text: str, start: int, end: int) -> bool:
    lower = text.strip().lower()
    if lower in _SAFE_PASSIVE_EXACT_STRINGS:
        return True

    term = text[start:end].lower()
    window = text[max(0, start - 80) : min(len(text), end + 80)].lower()
    escaped = re.escape(term)

    denial_patterns = (
        rf"\bnot\s+{escaped}\b",
        rf"\bno\s+{escaped}\b",
        rf"\bnever\s+{escaped}\b",
        rf"\bwithout\s+{escaped}\b",
        rf"\b{escaped}\s+(?:is\s+)?(?:disabled|denied|blocked|disallowed|prevented|forbidden|refused|rejected)\b",
    )
    if any(re.search(pattern, window) for pattern in denial_patterns):
        return True

    if term in ("active", "running", "execute", "run") and re.search(
        r"\b(?:active\s+execution|runtime\s+execution|running|execute|run)\s+(?:is\s+)?(?:disabled|denied|blocked|disallowed|prevented|forbidden|refused|rejected)\b",
        window,
    ):
        return True

    return False


_ACTIVE_STATE_SCAN_SKIP_FIELD_NAMES = {
    "kind",
    "path",
    "sha256",
    "role",
    "name",
}

_ACTIVE_STATE_SCAN_SKIP_ROOTS = (
    "approval_boundary_ref",
    "promotion_decision_ref",
    "promotion_review_ref",
    "promotion_request_ref",
    "source_proposal_refs",
    "target_profile_ref",
    "command_authority_ref",
    "command_authority_snapshot_ref",
    "verification_profile_ref",
    "verification_profile_report_ref",
    "rollback_plan_ref",
    "git_state_ref",
    "preflight_ref",
    "artifact_chain_verification_report_ref",
    "specialized_candidate_ref",
)


def _should_skip_active_state_scan(path: str) -> bool:
    if not path:
        return False
    leaf = path.rsplit(".", 1)[-1]
    if leaf in _ACTIVE_STATE_SCAN_SKIP_FIELD_NAMES:
        return True
    if path.startswith("subject_refs["):
        return True
    return any(
        path == root or path.startswith(f"{root}.") or path.startswith(f"{root}[")
        for root in _ACTIVE_STATE_SCAN_SKIP_ROOTS
    )


def _validate_no_active_state_claims(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if _should_skip_active_state_scan(path):
        return errors

    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(
                _validate_no_active_state_claims(item, f"{path}.{key}" if path else key)
            )
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_validate_no_active_state_claims(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        for match in _FORBIDDEN_ACTIVE_STATE_RE.finditer(value):
            term = match.group(1)
            if _is_passive_or_denial_context(value, match.start(), match.end()):
                continue
            errors.append(f"field '{path}' claims active authority state '{term}'")
    return errors


def _scan_forbidden_boolean_keys(data: Any, path: str) -> list[str]:
    errors: list[str] = []
    forbidden_keys = {
        "records_execution",
        "authorizes_activation",
        "activation_requested",
        "runtime_activation",
        "execution_started",
        "execution_completed",
        "commands_executed",
        "tools_invoked",
        "model_invoked",
        "goose_started",
        "deepagents_dispatched",
        "mcp_invoked",
        "network_called",
        "target_repo_mutated",
        "memory_mutated",
    }
    if isinstance(data, dict):
        for k, v in data.items():
            if k in forbidden_keys and v is True:
                errors.append(
                    f"field '{path}.{k}' claims forbidden active capability '{k}'"
                )
            errors.extend(_scan_forbidden_boolean_keys(v, f"{path}.{k}" if path else k))
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            errors.extend(_scan_forbidden_boolean_keys(item, f"{path}[{idx}]"))
    return errors


def _scan_platform_identity_rejection(data: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(data, dict):
        for k, v in data.items():
            if (
                k in ("platform_identity", "platform_name")
                and isinstance(v, str)
                and v.upper() == "CORE"
            ):
                errors.append(
                    f"Forbidden CORE platform identity claim in field '{path}.{k}'"
                )
            errors.extend(
                _scan_platform_identity_rejection(v, f"{path}.{k}" if path else k)
            )
    elif isinstance(data, list):
        for idx, item in enumerate(data):
            errors.extend(_scan_platform_identity_rejection(item, f"{path}[{idx}]"))
    elif isinstance(data, str):
        normalized = data.lower()
        if (
            "builder-ii is core" in normalized
            or "builder_ii is core" in normalized
            or "builder ii is core" in normalized
        ):
            errors.append(
                f"Forbidden text implying builder-II is CORE in field '{path}'"
            )
    return errors


def _manifest_top_level_invariants() -> dict[str, Any]:
    return {
        "executes_model": False,
        "executes_tools": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "constructs_subagents": False,
        "invokes_mcp": False,
        "performs_network_calls": False,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "runtime_execution": False,
        "source_writes": False,
        "memory_mutation": False,
        "artifact_is_authority": False,
        "bypasses_command_authority": False,
        "bypasses_verification": False,
        "grants_runtime_authority": False,
        "authorizes_execution": False,
        "grants_authority": False,
        "requires_separate_activation_artifact": True,
        "core_workbench_coupling": "NONE",
    }


def _manifest_default_governance(capability_state: str) -> dict[str, Any]:
    gov = _manifest_top_level_invariants()
    gov["capability_state"] = capability_state
    return gov


def _validate_manifest_invariants(
    data: dict[str, Any], capability_state: str
) -> list[str]:
    errors: list[str] = []
    invariant_keys = (
        "executes_model",
        "executes_tools",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "constructs_subagents",
        "invokes_mcp",
        "performs_network_calls",
        "mutates_target_repo",
        "mutates_memory",
        "runtime_execution",
        "source_writes",
        "memory_mutation",
        "artifact_is_authority",
        "bypasses_command_authority",
        "bypasses_verification",
        "grants_runtime_authority",
        "authorizes_execution",
        "grants_authority",
    )
    for key in invariant_keys:
        if data.get(key) is not False:
            errors.append(f"{key} must be false")
    if data.get("requires_separate_activation_artifact") is not True:
        errors.append("requires_separate_activation_artifact must be true")
    if data.get("core_workbench_coupling") != "NONE":
        errors.append("core_workbench_coupling must be NONE")

    gov = data.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be a dictionary")
    else:
        if gov.get("capability_state") != capability_state:
            errors.append(f"governance.capability_state must be {capability_state}")
        for key in invariant_keys:
            if gov.get(key) is not False:
                errors.append(f"governance.{key} must be false")
        if gov.get("requires_separate_activation_artifact") is not True:
            errors.append(
                "governance.requires_separate_activation_artifact must be true"
            )
        if gov.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def create_execution_candidate_manifest(
    approval_boundary_ref: dict[str, Any],
    promotion_decision_ref: dict[str, Any],
    promotion_review_ref: dict[str, Any],
    promotion_request_ref: dict[str, Any],
    source_proposal_refs: list[dict[str, Any]],
    target_profile_ref: dict[str, Any],
    command_authority_ref: dict[str, Any],
    verification_profile_ref: dict[str, Any],
    rollback_requirements: dict[str, Any],
    verification_requirements: dict[str, Any],
    candidate_scope: dict[str, Any],
    *,
    source_approval_boundary_record_state: str,
    source_approval_boundary_decision_result: str,
    source_approval_boundary_decision_record_state: str,
    source_approval_boundary_requires_separate_execution_candidate: bool,
    rollback_plan_ref: dict[str, Any] | None = None,
    git_state_ref: dict[str, Any] | None = None,
    preflight_ref: dict[str, Any] | None = None,
    artifact_chain_verification_report_ref: dict[str, Any] | None = None,
    specialized_candidate_ref: dict[str, Any] | None = None,
) -> dict[str, Any]:
    manifest = {
        "kind": EXECUTION_CANDIDATE_MANIFEST_KIND,
        "schema_version": EXECUTION_CANDIDATE_MANIFEST_SCHEMA_VERSION,
        "record_state": "CANDIDATE_RECORDED_ONLY",
        "records_candidate_intent": True,
        "approval_boundary_ref": approval_boundary_ref,
        "promotion_decision_ref": promotion_decision_ref,
        "promotion_review_ref": promotion_review_ref,
        "promotion_request_ref": promotion_request_ref,
        "source_proposal_refs": source_proposal_refs,
        "target_profile_ref": target_profile_ref,
        "command_authority_ref": command_authority_ref,
        "verification_profile_ref": verification_profile_ref,
        "rollback_requirements": rollback_requirements,
        "verification_requirements": verification_requirements,
        "candidate_scope": candidate_scope,
        "source_approval_boundary_record_state": source_approval_boundary_record_state,
        "source_approval_boundary_decision_result": source_approval_boundary_decision_result,
        "source_approval_boundary_decision_record_state": source_approval_boundary_decision_record_state,
        "source_approval_boundary_requires_separate_execution_candidate": source_approval_boundary_requires_separate_execution_candidate,
        **_manifest_top_level_invariants(),
        "governance": _manifest_default_governance("CANDIDATE_RECORDED_ONLY"),
    }
    if rollback_plan_ref is not None:
        manifest["rollback_plan_ref"] = rollback_plan_ref
    if git_state_ref is not None:
        manifest["git_state_ref"] = git_state_ref
    if preflight_ref is not None:
        manifest["preflight_ref"] = preflight_ref
    if artifact_chain_verification_report_ref is not None:
        manifest["artifact_chain_verification_report_ref"] = (
            artifact_chain_verification_report_ref
        )
    if specialized_candidate_ref is not None:
        manifest["specialized_candidate_ref"] = specialized_candidate_ref
    return manifest


def _validate_deephaven_rejection(val: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(val, dict):
        for k, v in val.items():
            current_path = f"{path}.{k}" if path else k
            if "deephaven" in k.lower():
                errors.append(f"Deephaven work is forbidden in key '{current_path}'")
            errors.extend(_validate_deephaven_rejection(v, current_path))
    elif isinstance(val, list):
        for idx, item in enumerate(val):
            errors.extend(_validate_deephaven_rejection(item, f"{path}[{idx}]"))
    elif isinstance(val, str):
        if "deephaven" in val.lower():
            errors.append(f"Deephaven work is forbidden in field '{path}'")
    return errors


def _validate_command_previews(previews: Any, path: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(previews, list):
        errors.append(f"field '{path}' must be a list")
        return errors

    for idx, preview in enumerate(previews):
        curr_path = f"{path}[{idx}]"
        if not isinstance(preview, str):
            errors.append(f"field '{curr_path}' must be a string")
            continue

        # Check for shell control syntax
        for frag in _FORBIDDEN_COMMAND_FRAGMENTS:
            if frag in preview:
                errors.append(
                    f"shell control syntax '{frag}' detected in preview command '{preview}' at '{curr_path}'"
                )

        # Check for forbidden commands/utilities
        for cmd in _FORBIDDEN_COMMANDS:
            if re.search(rf"\b{re.escape(cmd)}\b", preview, re.IGNORECASE):
                errors.append(
                    f"forbidden active command '{cmd}' detected in preview command '{preview}' at '{curr_path}'"
                )

        # Command authority classification validation
        tokens = preview.strip().split()
        if tokens:
            matched_record = None
            for end in range(len(tokens), 0, -1):
                sub_name = " ".join(tokens[:end])
                record = get_command_record(sub_name)
                if record is not None:
                    matched_record = record
                    break

            if matched_record is not None:
                if matched_record.tier == TIER_4:
                    errors.append(
                        f"preview command '{preview}' references forbidden Tier 4 subcommand '{matched_record.name}' at '{curr_path}'"
                    )
            else:
                errors.append(
                    f"preview command '{preview}' has no matching command authority record at '{curr_path}'"
                )
    return errors


def validate_execution_candidate_manifest(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["execution candidate manifest must be a JSON object"]

    if data.get("kind") != EXECUTION_CANDIDATE_MANIFEST_KIND:
        errors.append(f"kind must be {EXECUTION_CANDIDATE_MANIFEST_KIND}")
    if data.get("schema_version") != EXECUTION_CANDIDATE_MANIFEST_SCHEMA_VERSION:
        errors.append(
            f"schema_version must be {EXECUTION_CANDIDATE_MANIFEST_SCHEMA_VERSION}"
        )
    if data.get("record_state") != "CANDIDATE_RECORDED_ONLY":
        errors.append("record_state must be CANDIDATE_RECORDED_ONLY")

    # Source approval boundary snapshot validation
    if data.get("source_approval_boundary_record_state") != "BOUNDARY_RECORDED_ONLY":
        errors.append(
            "source_approval_boundary_record_state must be BOUNDARY_RECORDED_ONLY"
        )
    if (
        data.get("source_approval_boundary_decision_result")
        != "approved_for_candidate_design"
    ):
        errors.append(
            "source_approval_boundary_decision_result must be approved_for_candidate_design"
        )
    if (
        data.get("source_approval_boundary_decision_record_state")
        != "DECISION_RECORDED_ONLY"
    ):
        errors.append(
            "source_approval_boundary_decision_record_state must be DECISION_RECORDED_ONLY"
        )
    if (
        data.get("source_approval_boundary_requires_separate_execution_candidate")
        is not True
    ):
        errors.append(
            "source_approval_boundary_requires_separate_execution_candidate must be true"
        )

    # Required refs validation
    errors.extend(
        _validate_ref(
            data.get("approval_boundary_ref"),
            "approval_boundary_ref",
            expected_kinds={HITL_APPROVAL_BOUNDARY_KIND},
            required=True,
        )
    )
    errors.extend(
        _validate_ref(
            data.get("promotion_decision_ref"),
            "promotion_decision_ref",
            expected_kinds={HITL_PROMOTION_DECISION_KIND},
            required=True,
        )
    )
    errors.extend(
        _validate_ref(
            data.get("promotion_review_ref"),
            "promotion_review_ref",
            expected_kinds={HITL_PROMOTION_REVIEW_KIND},
            required=True,
        )
    )
    errors.extend(
        _validate_ref(
            data.get("promotion_request_ref"),
            "promotion_request_ref",
            expected_kinds={HITL_PROMOTION_REQUEST_KIND},
            required=True,
        )
    )

    source_proposal_refs = data.get("source_proposal_refs")
    if not isinstance(source_proposal_refs, list):
        errors.append("source_proposal_refs must be a list")
    elif not source_proposal_refs:
        errors.append("source_proposal_refs list cannot be empty")
    else:
        for idx, ref in enumerate(source_proposal_refs):
            errors.extend(
                _validate_ref(
                    ref,
                    f"source_proposal_refs[{idx}]",
                    expected_kinds=ALLOWED_PROPOSAL_KINDS,
                    required=True,
                )
            )

    errors.extend(
        _validate_ref(
            data.get("target_profile_ref"), "target_profile_ref", required=True
        )
    )

    cmd_auth_ref = data.get("command_authority_ref")
    cmd_auth_snap_ref = data.get("command_authority_snapshot_ref")
    if not cmd_auth_ref and not cmd_auth_snap_ref:
        errors.append(
            "either command_authority_ref or command_authority_snapshot_ref is required"
        )
    else:
        if cmd_auth_ref:
            errors.extend(
                _validate_ref(cmd_auth_ref, "command_authority_ref", required=False)
            )
        if cmd_auth_snap_ref:
            errors.extend(
                _validate_ref(
                    cmd_auth_snap_ref, "command_authority_snapshot_ref", required=False
                )
            )

    ver_prof_ref = data.get("verification_profile_ref")
    ver_prof_rep_ref = data.get("verification_profile_report_ref")
    if not ver_prof_ref and not ver_prof_rep_ref:
        errors.append(
            "either verification_profile_ref or verification_profile_report_ref is required"
        )
    else:
        if ver_prof_ref:
            errors.extend(
                _validate_ref(ver_prof_ref, "verification_profile_ref", required=False)
            )
        if ver_prof_rep_ref:
            errors.extend(
                _validate_ref(
                    ver_prof_rep_ref, "verification_profile_report_ref", required=False
                )
            )

    # Rollback requirements validation
    rollback_reqs = data.get("rollback_requirements")
    if not isinstance(rollback_reqs, dict):
        errors.append("rollback_requirements must be a dictionary")
    else:
        if rollback_reqs.get("rollback_required") is not True:
            errors.append("rollback_requirements.rollback_required must be true")
        no_mutation = rollback_reqs.get("no_mutation_assertion") is True
        rollback_plan_ref = data.get("rollback_plan_ref")
        if not no_mutation and not rollback_plan_ref:
            errors.append(
                "rollback_plan_ref is required unless rollback_requirements.no_mutation_assertion is true"
            )
        if rollback_plan_ref:
            errors.extend(
                _validate_ref(
                    rollback_plan_ref,
                    "rollback_plan_ref",
                    expected_kinds={"builder_ii.rollback_plan"},
                    required=False,
                )
            )

    # Verification requirements validation
    ver_reqs = data.get("verification_requirements")
    if not isinstance(ver_reqs, dict):
        errors.append("verification_requirements must be a dictionary")
    else:
        if ver_reqs.get("verification_required") is not True:
            errors.append(
                "verification_requirements.verification_required must be true"
            )
        if (
            ver_reqs.get("verification_executed") is True
            or ver_reqs.get("verified") is True
        ):
            errors.append("manifest must not claim verification has been executed")

    # Optional refs validation
    if "git_state_ref" in data:
        errors.extend(
            _validate_ref(
                data.get("git_state_ref"),
                "git_state_ref",
                expected_kinds={"builder_ii.git_state_record"},
                required=False,
            )
        )
    if "preflight_ref" in data:
        errors.extend(
            _validate_ref(
                data.get("preflight_ref"),
                "preflight_ref",
                expected_kinds={"builder_ii.preflight_record"},
                required=False,
            )
        )
    if "artifact_chain_verification_report_ref" in data:
        errors.extend(
            _validate_ref(
                data.get("artifact_chain_verification_report_ref"),
                "artifact_chain_verification_report_ref",
                expected_kinds={"builder_ii.artifact_chain_verification_report"},
                required=False,
            )
        )
    if "specialized_candidate_ref" in data:
        errors.extend(
            _validate_ref(
                data.get("specialized_candidate_ref"),
                "specialized_candidate_ref",
                expected_kinds={"builder_ii.hitl_verification_execution_candidate"},
                required=False,
            )
        )

    # Candidate scope validation
    scope = data.get("candidate_scope")
    if not isinstance(scope, dict):
        errors.append("candidate_scope must be a dictionary")
    else:
        target_profile = scope.get("target_profile")
        if target_profile not in ("generic", "builder", "core"):
            errors.append(
                "candidate_scope.target_profile must be generic, builder, or core"
            )
        if scope.get("core_workbench_coupling") != "NONE":
            errors.append("candidate_scope.core_workbench_coupling must be NONE")
        errors.extend(_validate_deephaven_rejection(scope, "candidate_scope"))

        if "command_previews" in scope:
            errors.extend(
                _validate_command_previews(
                    scope.get("command_previews"), "candidate_scope.command_previews"
                )
            )

    target_prof_ref = data.get("target_profile_ref")
    if isinstance(target_prof_ref, dict):
        errors.extend(
            _validate_deephaven_rejection(target_prof_ref, "target_profile_ref")
        )

    errors.extend(_validate_manifest_invariants(data, "CANDIDATE_RECORDED_ONLY"))
    errors.extend(_validate_no_active_state_claims(data, ""))
    errors.extend(_scan_forbidden_boolean_keys(data, ""))
    errors.extend(_scan_platform_identity_rejection(data, ""))

    return errors


def validate_execution_candidate_manifest_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"file not found or is not a file: {path}"]
    try:
        content = path.read_text(encoding="utf-8")
        data = json_lib.loads(content)
    except Exception as exc:
        return [f"invalid JSON: {exc}"]
    return validate_execution_candidate_manifest(data)


def create_execution_candidate_manifest_validation_report(
    subject_refs: list[dict[str, Any]],
    *,
    valid: bool,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    checked_invariants: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND,
        "schema_version": EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_SCHEMA_VERSION,
        "record_state": "VALIDATION_ONLY",
        "subject_refs": subject_refs,
        "valid": valid,
        "errors": errors or [],
        "warnings": warnings or [],
        "checked_invariants": checked_invariants or ["all authority flags false"],
        **_manifest_top_level_invariants(),
        "governance": _manifest_default_governance("VALIDATION_ONLY"),
    }


def validate_execution_candidate_manifest_validation_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["execution candidate manifest validation report must be a JSON object"]

    if data.get("kind") != EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND:
        errors.append(
            f"kind must be {EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_KIND}"
        )
    if (
        data.get("schema_version")
        != EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_SCHEMA_VERSION
    ):
        errors.append(
            f"schema_version must be {EXECUTION_CANDIDATE_MANIFEST_VALIDATION_REPORT_SCHEMA_VERSION}"
        )
    if data.get("record_state") != "VALIDATION_ONLY":
        errors.append("record_state must be VALIDATION_ONLY")

    subjects = data.get("subject_refs")
    if not isinstance(subjects, list):
        errors.append("subject_refs must be a list")
    else:
        for idx, subj in enumerate(subjects):
            errors.extend(
                _validate_ref(
                    subj,
                    f"subject_refs[{idx}]",
                    expected_kinds={EXECUTION_CANDIDATE_MANIFEST_KIND},
                    required=True,
                )
            )

    if not isinstance(data.get("valid"), bool):
        errors.append("valid must be a boolean")

    errors.extend(_validate_manifest_invariants(data, "VALIDATION_ONLY"))
    errors.extend(_validate_no_active_state_claims(data, ""))
    errors.extend(_scan_forbidden_boolean_keys(data, ""))
    errors.extend(_scan_platform_identity_rejection(data, ""))
    return errors


def validate_execution_candidate_manifest_validation_report_file(
    path: Path,
) -> list[str]:
    if not path.is_file():
        return [f"file not found or is not a file: {path}"]
    try:
        content = path.read_text(encoding="utf-8")
        data = json_lib.loads(content)
    except Exception as exc:
        return [f"invalid JSON: {exc}"]
    return validate_execution_candidate_manifest_validation_report(data)


def write_execution_candidate_manifest(data: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def write_execution_candidate_manifest_validation_report(
    data: dict[str, Any], output: Path
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json_lib.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
