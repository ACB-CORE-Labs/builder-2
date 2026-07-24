from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any, Callable

from builder_ii.core.canonical_json import canonical_digest

# Kinds and schema versions
HITL_PROMOTION_REQUEST_KIND = "builder_ii.hitl_promotion_request"
HITL_PROMOTION_REQUEST_SCHEMA_VERSION = 1

HITL_PROMOTION_REVIEW_KIND = "builder_ii.hitl_promotion_review"
HITL_PROMOTION_REVIEW_SCHEMA_VERSION = 1

HITL_PROMOTION_DECISION_KIND = "builder_ii.hitl_promotion_decision"
HITL_PROMOTION_DECISION_SCHEMA_VERSION = 1

HITL_APPROVAL_BOUNDARY_KIND = "builder_ii.hitl_approval_boundary"
HITL_APPROVAL_BOUNDARY_SCHEMA_VERSION = 1

HITL_REJECTION_RECORD_KIND = "builder_ii.hitl_rejection_record"
HITL_REJECTION_RECORD_SCHEMA_VERSION = 1

HITL_PROMOTION_VALIDATION_REPORT_KIND = "builder_ii.hitl_promotion_validation_report"
HITL_PROMOTION_VALIDATION_REPORT_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_PROPOSAL_KINDS = {
    "builder_ii.deepagents_proposal_result",
    "builder_ii.deepagents_work_validation_report",
    "builder_ii.orchestration_assignment_validation_report",
    "builder_ii.orchestration_assignment_plan",
    "builder_ii.orchestration_assignment_dry_run",
    "builder_ii.deepagents_work_plan",
}

_FORBIDDEN_ACTIVE_STATES = {
    "executed",
    "authorized",
    "promoted",
    "enabled",
    "approved",
    "verified",
    "applied",
    "merged",
    "authoritative",
    "truth",
    "executable",
    "active",
    "running",
}

_FORBIDDEN_ACTIVE_STATE_RE = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(term) for term in sorted(_FORBIDDEN_ACTIVE_STATES)) + r")(?![a-z0-9])",
    re.IGNORECASE,
)


def _create_ref(
    data: dict[str, Any] | None = None,
    *,
    kind: str = "",
    path: str | Path = "",
    sha256: str = "",
    role: str = "",
    name: str = "",
) -> dict[str, Any]:
    if data is not None and isinstance(data, dict):
        kind = str(data.get("kind", kind))
        if not sha256:
            sha256 = canonical_digest(data)
    res = {
        "kind": kind,
        "path": str(path),
        "sha256": sha256,
    }
    if role:
        res["role"] = role
    if name:
        res["name"] = name
    return res


def _default_governance(capability_state: str) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
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
        "core_workbench_coupling": "NONE",
    }


def _top_level_invariants() -> dict[str, Any]:
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
        "core_workbench_coupling": "NONE",
    }


_SAFE_PASSIVE_EXACT_STRINGS = {
    "approved_for_candidate_design",
    "requested_only",
    "reviewed_only",
    "decision_recorded_only",
    "boundary_recorded_only",
    "rejected_only",
    "validation_only",
    "records_human_decision",
}


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

    if term == "active" and re.search(
        r"\bactive\s+execution\s+(?:is\s+)?(?:disabled|denied|blocked|disallowed|prevented|forbidden|refused|rejected)\b",
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
    "proposal_ref",
    "target_profile_ref",
    "session_manifest_ref",
    "promotion_request_ref",
    "promotion_review_ref",
    "promotion_decision_ref",
)


def _should_skip_active_state_scan(path: str) -> bool:
    if not path:
        return False

    leaf = path.rsplit(".", 1)[-1]
    if leaf in _ACTIVE_STATE_SCAN_SKIP_FIELD_NAMES:
        return True

    if path.startswith("subject_refs["):
        return True

    return any(path == root or path.startswith(f"{root}.") for root in _ACTIVE_STATE_SCAN_SKIP_ROOTS)


def _validate_no_active_state_claims(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if _should_skip_active_state_scan(path):
        return errors

    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_validate_no_active_state_claims(item, f"{path}.{key}" if path else key))
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


def _validate_ref(
    value: Any,
    field_name: str,
    expected_kinds: set[str] | None = None,
    required: bool = True,
) -> list[str]:
    errors: list[str] = []
    if value is None or value == {} or value == "":
        if required:
            return [f"{field_name} is required"]
        return []
    if not isinstance(value, dict):
        return [f"{field_name} must be a dictionary"]
    kind = value.get("kind")
    if not kind or not isinstance(kind, str):
        errors.append(f"{field_name} must specify a non-empty kind")
    elif expected_kinds is not None and kind not in expected_kinds:
        errors.append(f"{field_name} has wrong source kind '{kind}'")
    path = value.get("path")
    if not path or not isinstance(path, str):
        errors.append(f"{field_name} must specify a valid path")
    sha256 = value.get("sha256")
    if not sha256 or not isinstance(sha256, str) or not _SHA256_RE.match(sha256):
        errors.append(f"{field_name} sha256 mismatch or invalid digest")
    return errors


def _validate_invariants(data: dict[str, Any], capability_state: str) -> list[str]:
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
            errors.append(f"{key} must be false or NOT_AUTHORIZED")
    if data.get("core_workbench_coupling") != "NONE":
        errors.append("core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    gov = data.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be a dictionary")
    else:
        if gov.get("capability_state") != capability_state:
            errors.append(f"governance.capability_state must be {capability_state}")
        for key in invariant_keys:
            if gov.get(key) is not False:
                errors.append(f"governance.{key} must be false or NOT_AUTHORIZED")
        if gov.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


# 1. Promotion Request
def create_hitl_promotion_request(
    proposal: dict[str, Any] | None = None,
    *,
    proposal_path: str | Path = "",
    proposal_ref: dict[str, Any] | None = None,
    target_profile_ref: dict[str, Any] | None = None,
    session_manifest_ref: dict[str, Any] | None = None,
    requested_by: str = "operator",
    reason: str = "",
) -> dict[str, Any]:
    if proposal_ref is None and proposal is not None:
        proposal_ref = _create_ref(proposal, path=proposal_path, role="proposal")
    return {
        "kind": HITL_PROMOTION_REQUEST_KIND,
        "schema_version": HITL_PROMOTION_REQUEST_SCHEMA_VERSION,
        "record_state": "REQUESTED_ONLY",
        "proposal_ref": proposal_ref or {},
        "target_profile_ref": target_profile_ref or {},
        "session_manifest_ref": session_manifest_ref or {},
        "requested_by": requested_by,
        "reason": reason,
        **_top_level_invariants(),
        "governance": _default_governance("REQUESTED_ONLY"),
    }


def validate_hitl_promotion_request(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hitl promotion request must be a JSON object"]
    if data.get("kind") != HITL_PROMOTION_REQUEST_KIND:
        errors.append(f"kind must be {HITL_PROMOTION_REQUEST_KIND}")
    if data.get("schema_version") != HITL_PROMOTION_REQUEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_PROMOTION_REQUEST_SCHEMA_VERSION}")
    if data.get("record_state") != "REQUESTED_ONLY":
        errors.append("record_state must be REQUESTED_ONLY")

    errors.extend(
        _validate_ref(
            data.get("proposal_ref"),
            "proposal_ref",
            expected_kinds=ALLOWED_PROPOSAL_KINDS,
            required=True,
        )
    )
    errors.extend(_validate_ref(data.get("target_profile_ref"), "target_profile_ref", required=False))
    errors.extend(_validate_ref(data.get("session_manifest_ref"), "session_manifest_ref", required=False))

    errors.extend(_validate_invariants(data, "REQUESTED_ONLY"))
    errors.extend(_validate_no_active_state_claims(data, ""))
    return errors


# 2. Promotion Review
def create_hitl_promotion_review(
    promotion_request: dict[str, Any] | None = None,
    *,
    promotion_request_path: str | Path = "",
    promotion_request_ref: dict[str, Any] | None = None,
    policy_ref: dict[str, Any] | None = None,
    disposition: str = "acceptable_for_decision",
    findings: list[str] | None = None,
    warnings: list[str] | None = None,
    blocking_issues: list[str] | None = None,
    recommendation: str = "",
    reviewed_by: str = "operator",
) -> dict[str, Any]:
    if promotion_request_ref is None and promotion_request is not None:
        promotion_request_ref = _create_ref(promotion_request, path=promotion_request_path, role="promotion_request")
    return {
        "kind": HITL_PROMOTION_REVIEW_KIND,
        "schema_version": HITL_PROMOTION_REVIEW_SCHEMA_VERSION,
        "record_state": "REVIEWED_ONLY",
        "promotion_request_ref": promotion_request_ref or {},
        "policy_ref": policy_ref or {},
        "disposition": disposition,
        "findings": findings or [],
        "warnings": warnings or [],
        "blocking_issues": blocking_issues or [],
        "recommendation": recommendation,
        "reviewed_by": reviewed_by,
        **_top_level_invariants(),
        "governance": _default_governance("REVIEWED_ONLY"),
    }


def validate_hitl_promotion_review(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hitl promotion review must be a JSON object"]
    if data.get("kind") != HITL_PROMOTION_REVIEW_KIND:
        errors.append(f"kind must be {HITL_PROMOTION_REVIEW_KIND}")
    if data.get("schema_version") != HITL_PROMOTION_REVIEW_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_PROMOTION_REVIEW_SCHEMA_VERSION}")
    if data.get("record_state") != "REVIEWED_ONLY":
        errors.append("record_state must be REVIEWED_ONLY")

    errors.extend(
        _validate_ref(
            data.get("promotion_request_ref"),
            "promotion_request_ref",
            expected_kinds={HITL_PROMOTION_REQUEST_KIND},
            required=True,
        )
    )
    errors.extend(_validate_ref(data.get("policy_ref"), "policy_ref", required=False))

    disposition = data.get("disposition")
    if disposition not in ("acceptable_for_decision", "needs_revision", "blocked"):
        errors.append("disposition must be acceptable_for_decision, needs_revision, or blocked")

    errors.extend(_validate_invariants(data, "REVIEWED_ONLY"))
    errors.extend(_validate_no_active_state_claims(data, ""))
    return errors


# 3. Promotion Decision
def create_hitl_promotion_decision(
    promotion_request_ref: dict[str, Any],
    promotion_review_ref: dict[str, Any],
    *,
    decision_result: str,
    decided_by: str = "operator",
    reason: str = "",
    blockers: list[str] | None = None,
    source_review_disposition: str = "",
    source_review_blocking_issues: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": HITL_PROMOTION_DECISION_KIND,
        "schema_version": HITL_PROMOTION_DECISION_SCHEMA_VERSION,
        "record_state": "DECISION_RECORDED_ONLY",
        "promotion_request_ref": promotion_request_ref,
        "promotion_review_ref": promotion_review_ref,
        "decision_result": decision_result,
        "records_human_decision": True,
        "requires_separate_execution_candidate": True,
        "source_review_disposition": source_review_disposition,
        "source_review_blocking_issues": source_review_blocking_issues or [],
        "decided_by": decided_by,
        "reason": reason,
        "blockers": blockers or [],
        **_top_level_invariants(),
        "governance": _default_governance("DECISION_RECORDED_ONLY"),
    }


def validate_hitl_promotion_decision(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hitl promotion decision must be a JSON object"]
    if data.get("kind") != HITL_PROMOTION_DECISION_KIND:
        errors.append(f"kind must be {HITL_PROMOTION_DECISION_KIND}")
    if data.get("schema_version") != HITL_PROMOTION_DECISION_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_PROMOTION_DECISION_SCHEMA_VERSION}")
    if data.get("record_state") != "DECISION_RECORDED_ONLY":
        errors.append("record_state must be DECISION_RECORDED_ONLY")

    errors.extend(
        _validate_ref(
            data.get("promotion_request_ref"),
            "promotion_request_ref",
            expected_kinds={HITL_PROMOTION_REQUEST_KIND},
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

    result = data.get("decision_result")
    if result not in ("approved_for_candidate_design", "rejected", "needs_revision"):
        errors.append("decision_result must be approved_for_candidate_design, rejected, or needs_revision")

    source_review_disposition = data.get("source_review_disposition")
    if source_review_disposition not in (
        "acceptable_for_decision",
        "needs_revision",
        "blocked",
    ):
        errors.append("source_review_disposition must be acceptable_for_decision, needs_revision, or blocked")

    source_review_blocking_issues = data.get("source_review_blocking_issues")
    if not isinstance(source_review_blocking_issues, list):
        errors.append("source_review_blocking_issues must be a list")

    blockers = data.get("blockers", [])
    if not isinstance(blockers, list):
        errors.append("blockers must be a list")
    elif len(blockers) > 0 and result == "approved_for_candidate_design":
        errors.append("approved_for_candidate_design decision must not have unresolved blockers")

    if result == "approved_for_candidate_design":
        if source_review_disposition != "acceptable_for_decision":
            errors.append("approved_for_candidate_design requires source_review_disposition acceptable_for_decision")
        if isinstance(source_review_blocking_issues, list) and source_review_blocking_issues:
            errors.append("approved_for_candidate_design requires empty source_review_blocking_issues")

    if data.get("records_human_decision") is not True:
        errors.append("records_human_decision must be true")
    if data.get("requires_separate_execution_candidate") is not True:
        errors.append("requires_separate_execution_candidate must be true")

    errors.extend(_validate_invariants(data, "DECISION_RECORDED_ONLY"))
    errors.extend(_validate_no_active_state_claims(data, ""))
    return errors


# 4. Approval Boundary
def create_hitl_approval_boundary(
    promotion_decision_ref: dict[str, Any],
    promotion_request_ref: dict[str, Any],
    *,
    permitted_candidate_scope: dict[str, Any] | None = None,
    denied_boundaries: list[str] | None = None,
    required_future_artifacts: list[str] | None = None,
    rollback_requirements: dict[str, Any] | None = None,
    verification_requirements: dict[str, Any] | None = None,
    source_decision_result: str = "",
    source_decision_record_state: str = "",
) -> dict[str, Any]:
    return {
        "kind": HITL_APPROVAL_BOUNDARY_KIND,
        "schema_version": HITL_APPROVAL_BOUNDARY_SCHEMA_VERSION,
        "record_state": "BOUNDARY_RECORDED_ONLY",
        "promotion_decision_ref": promotion_decision_ref,
        "promotion_request_ref": promotion_request_ref,
        "source_decision_result": source_decision_result,
        "source_decision_record_state": source_decision_record_state,
        "permitted_candidate_scope": permitted_candidate_scope or {"allowed_profiles": ["generic"]},
        "denied_boundaries": denied_boundaries
        or [
            "runtime execution",
            "memory mutation",
            "target repo writes",
        ],
        "required_future_artifacts": required_future_artifacts or ["builder_ii.execution_candidate_manifest"],
        "rollback_requirements": rollback_requirements or {"required": True},
        "verification_requirements": verification_requirements or {"required": True},
        "requires_separate_execution_candidate": True,
        **_top_level_invariants(),
        "governance": _default_governance("BOUNDARY_RECORDED_ONLY"),
    }


def validate_hitl_approval_boundary(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hitl approval boundary must be a JSON object"]
    if data.get("kind") != HITL_APPROVAL_BOUNDARY_KIND:
        errors.append(f"kind must be {HITL_APPROVAL_BOUNDARY_KIND}")
    if data.get("schema_version") != HITL_APPROVAL_BOUNDARY_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_APPROVAL_BOUNDARY_SCHEMA_VERSION}")
    if data.get("record_state") != "BOUNDARY_RECORDED_ONLY":
        errors.append("record_state must be BOUNDARY_RECORDED_ONLY")

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
            data.get("promotion_request_ref"),
            "promotion_request_ref",
            expected_kinds={HITL_PROMOTION_REQUEST_KIND},
            required=True,
        )
    )

    if data.get("source_decision_result") != "approved_for_candidate_design":
        errors.append("approval boundary requires source_decision_result approved_for_candidate_design")
    if data.get("source_decision_record_state") != "DECISION_RECORDED_ONLY":
        errors.append("approval boundary requires source_decision_record_state DECISION_RECORDED_ONLY")

    if data.get("requires_separate_execution_candidate") is not True:
        errors.append("requires_separate_execution_candidate must be true")

    errors.extend(_validate_invariants(data, "BOUNDARY_RECORDED_ONLY"))
    errors.extend(_validate_no_active_state_claims(data, ""))
    return errors


# 5. Rejection Record
def create_hitl_rejection_record(
    promotion_request_ref: dict[str, Any],
    *,
    promotion_decision_ref: dict[str, Any] | None = None,
    rationale: str = "",
    rejected_by: str = "operator",
) -> dict[str, Any]:
    return {
        "kind": HITL_REJECTION_RECORD_KIND,
        "schema_version": HITL_REJECTION_RECORD_SCHEMA_VERSION,
        "record_state": "REJECTED_ONLY",
        "promotion_request_ref": promotion_request_ref,
        "promotion_decision_ref": promotion_decision_ref or {},
        "rationale": rationale,
        "rejected_by": rejected_by,
        "blocks_further_promotion": True,
        **_top_level_invariants(),
        "governance": _default_governance("REJECTED_ONLY"),
    }


def validate_hitl_rejection_record(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hitl rejection record must be a JSON object"]
    if data.get("kind") != HITL_REJECTION_RECORD_KIND:
        errors.append(f"kind must be {HITL_REJECTION_RECORD_KIND}")
    if data.get("schema_version") != HITL_REJECTION_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_REJECTION_RECORD_SCHEMA_VERSION}")
    if data.get("record_state") != "REJECTED_ONLY":
        errors.append("record_state must be REJECTED_ONLY")

    errors.extend(
        _validate_ref(
            data.get("promotion_request_ref"),
            "promotion_request_ref",
            expected_kinds={HITL_PROMOTION_REQUEST_KIND},
            required=True,
        )
    )
    errors.extend(
        _validate_ref(
            data.get("promotion_decision_ref"),
            "promotion_decision_ref",
            expected_kinds={HITL_PROMOTION_DECISION_KIND},
            required=False,
        )
    )

    if data.get("blocks_further_promotion") is not True:
        errors.append("blocks_further_promotion must be true")

    errors.extend(_validate_invariants(data, "REJECTED_ONLY"))
    errors.extend(_validate_no_active_state_claims(data, ""))
    return errors


# 6. Promotion Validation Report
def create_hitl_promotion_validation_report(
    subject_refs: list[dict[str, Any]],
    *,
    valid: bool,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    checked_invariants: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "kind": HITL_PROMOTION_VALIDATION_REPORT_KIND,
        "schema_version": HITL_PROMOTION_VALIDATION_REPORT_SCHEMA_VERSION,
        "record_state": "VALIDATION_ONLY",
        "subject_refs": subject_refs,
        "valid": valid,
        "errors": errors or [],
        "warnings": warnings or [],
        "checked_invariants": checked_invariants or ["all authority flags false"],
        **_top_level_invariants(),
        "governance": _default_governance("VALIDATION_ONLY"),
    }


def validate_hitl_promotion_validation_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hitl promotion validation report must be a JSON object"]
    if data.get("kind") != HITL_PROMOTION_VALIDATION_REPORT_KIND:
        errors.append(f"kind must be {HITL_PROMOTION_VALIDATION_REPORT_KIND}")
    if data.get("schema_version") != HITL_PROMOTION_VALIDATION_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_PROMOTION_VALIDATION_REPORT_SCHEMA_VERSION}")
    if data.get("record_state") != "VALIDATION_ONLY":
        errors.append("record_state must be VALIDATION_ONLY")

    subjects = data.get("subject_refs")
    if not isinstance(subjects, list):
        errors.append("subject_refs must be a list")
    else:
        for i, subj in enumerate(subjects):
            errors.extend(_validate_ref(subj, f"subject_refs[{i}]", required=True))

    if not isinstance(data.get("valid"), bool):
        errors.append("valid must be a boolean")

    errors.extend(_validate_invariants(data, "VALIDATION_ONLY"))
    errors.extend(_validate_no_active_state_claims(data, ""))
    return errors


# Dump / write / file validation helpers
def dumps_hitl_promotion_artifact(data: dict[str, Any]) -> str:
    return json_lib.dumps(data, indent=2, sort_keys=True) + "\n"


def write_hitl_promotion_artifact(data: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_promotion_artifact(data), encoding="utf-8")


def _read_and_validate_file(path: Path, validator: Callable[[Any], list[str]]) -> list[str]:
    if not path.is_file():
        return [f"file not found or is not a file: {path}"]
    try:
        content = path.read_text(encoding="utf-8")
        data = json_lib.loads(content)
    except Exception as exc:
        return [f"invalid JSON: {exc}"]
    return validator(data)


def validate_hitl_promotion_request_file(path: Path) -> list[str]:
    return _read_and_validate_file(path, validate_hitl_promotion_request)


def validate_hitl_promotion_review_file(path: Path) -> list[str]:
    return _read_and_validate_file(path, validate_hitl_promotion_review)


def validate_hitl_promotion_decision_file(path: Path) -> list[str]:
    return _read_and_validate_file(path, validate_hitl_promotion_decision)


def validate_hitl_approval_boundary_file(path: Path) -> list[str]:
    return _read_and_validate_file(path, validate_hitl_approval_boundary)


def validate_hitl_rejection_record_file(path: Path) -> list[str]:
    return _read_and_validate_file(path, validate_hitl_rejection_record)


def validate_hitl_promotion_validation_report_file(path: Path) -> list[str]:
    return _read_and_validate_file(path, validate_hitl_promotion_validation_report)
