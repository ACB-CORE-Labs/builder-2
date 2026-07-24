from __future__ import annotations

import json as json_lib
import re
from pathlib import Path
from typing import Any, Callable

from builder_ii.adapters.deepagents.deepagents_policy import (
    DEEPAGENTS_POLICY_KIND,
    validate_deepagents_policy_artifact,
)
from builder_ii.adapters.deepagents.deepagents_readiness import (
    DEEPAGENTS_READINESS_KIND,
    validate_deepagents_readiness_artifact,
)
from builder_ii.core.canonical_json import canonical_digest
from builder_ii.core.orchestration_assignment import (
    ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
    ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
    validate_orchestration_assignment_dry_run,
    validate_orchestration_assignment_plan,
)
from builder_ii.lifecycle.setup.target_profiles import target_names

DEEPAGENTS_WORK_PLAN_KIND = "builder_ii.deepagents_work_plan"
DEEPAGENTS_WORK_PLAN_SCHEMA_VERSION = 1

DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND = "builder_ii.deepagents_subagent_assignment"
DEEPAGENTS_SUBAGENT_ASSIGNMENT_SCHEMA_VERSION = 1

DEEPAGENTS_SUBAGENT_RESULT_KIND = "builder_ii.deepagents_subagent_result"
DEEPAGENTS_SUBAGENT_RESULT_SCHEMA_VERSION = 1

DEEPAGENTS_SUBAGENT_REVIEW_KIND = "builder_ii.deepagents_subagent_review"
DEEPAGENTS_SUBAGENT_REVIEW_SCHEMA_VERSION = 1

DEEPAGENTS_HUMAN_GATE_REQUEST_KIND = "builder_ii.deepagents_human_gate_request"
DEEPAGENTS_HUMAN_GATE_REQUEST_SCHEMA_VERSION = 1

DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND = "builder_ii.deepagents_blocked_action_record"
DEEPAGENTS_BLOCKED_ACTION_RECORD_SCHEMA_VERSION = 1

DEEPAGENTS_PROPOSAL_RESULT_KIND = "builder_ii.deepagents_proposal_result"
DEEPAGENTS_PROPOSAL_RESULT_SCHEMA_VERSION = 1

DEEPAGENTS_WORK_VALIDATION_REPORT_KIND = "builder_ii.deepagents_work_validation_report"
DEEPAGENTS_WORK_VALIDATION_REPORT_SCHEMA_VERSION = 1

DEEPAGENTS_RUNTIME_ENVELOPE_KIND = "builder_ii.deepagents_runtime_envelope"
DEEPAGENTS_RUNTIME_ENVELOPE_SCHEMA_VERSION = 1

DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND = "builder_ii.deepagents_subagent_execution_receipt"
DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

# Active state escalation words forbidden in values unless allowed under governance exceptions
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
}
_FORBIDDEN_ACTIVE_STATE_RE = re.compile(
    r"(?<![a-z0-9])(" + "|".join(re.escape(term) for term in sorted(_FORBIDDEN_ACTIVE_STATES)) + r")(?![a-z0-9])",
    re.IGNORECASE,
)

_DENIED_CAPABILITIES = [
    "model execution",
    "tool execution",
    "shell execution",
    "Goose invocation",
    "deepagents construction",
    "subagent construction",
    "MCP invocation",
    "network calls",
    "target repository mutation",
    "runtime authority grant",
    "memory mutation",
]


def _artifact_ref(
    data: dict[str, Any],
    *,
    role: str,
    path: Path | None,
    name: str = "",
) -> dict[str, Any]:
    return {
        "role": role,
        "kind": str(data.get("kind", "")),
        "path": str(path) if path is not None else "",
        "sha256": canonical_digest(data),
        "name": name,
        "required": True,
    }


def _default_authority_boundary(capability_state: str) -> dict[str, Any]:
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
    }


def _default_governance(capability_state: str) -> dict[str, Any]:
    return {
        "capability_state": capability_state,
        "runtime_execution": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime_start": "DISABLED",
        "agent_construction": "DISABLED",
        "subagent_construction": "DISABLED",
        "model_execution": "DISABLED",
        "tool_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "network_calls": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "mcp_tool_calls": "DISABLED",
        "verification_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
        "core_workbench_coupling": "NONE",
    }


def _validate_or_raise(label: str, errors: list[str]) -> None:
    if errors:
        raise ValueError(f"invalid {label}: " + "; ".join(errors))


def _validate_known_deepagents_work_artifact(
    label: str,
    artifact: dict[str, Any],
    *,
    allowed_kinds: set[str] | None = None,
) -> None:
    kind = artifact.get("kind")
    if not isinstance(kind, str) or not kind:
        raise ValueError(f"{label} kind must be a non-empty string")
    if allowed_kinds is not None and kind not in allowed_kinds:
        allowed = ", ".join(sorted(allowed_kinds))
        raise ValueError(f"{label} kind must be one of: {allowed}")
    validator = _deepagents_validators().get(kind)
    if validator is None:
        raise ValueError(f"{label} kind is not a deepagents work artifact: {kind}")
    _validate_or_raise(label, validator(artifact))


# Builders


def create_deepagents_work_plan(
    *,
    target: str,
    task: str,
    orchestration_assignment_plan: dict[str, Any],
    orchestration_assignment_dry_run: dict[str, Any],
    deepagents_policy: dict[str, Any],
    deepagents_readiness: dict[str, Any],
    orchestration_assignment_plan_path: Path | None = None,
    orchestration_assignment_dry_run_path: Path | None = None,
    deepagents_policy_path: Path | None = None,
    deepagents_readiness_path: Path | None = None,
    proposed_subagents: list[str] | None = None,
    expected_outputs: list[str] | None = None,
    review_gates: list[str] | None = None,
    blocked_capabilities: list[str] | None = None,
) -> dict[str, Any]:
    task_text = task.strip()
    if not task_text:
        raise ValueError("task must be a non-empty string")
    if target not in target_names():
        raise ValueError(f"unknown target profile: {target}")

    _validate_or_raise(
        "orchestration assignment plan",
        validate_orchestration_assignment_plan(orchestration_assignment_plan),
    )
    _validate_or_raise(
        "orchestration assignment dry run",
        validate_orchestration_assignment_dry_run(orchestration_assignment_dry_run),
    )
    _validate_or_raise("deepagents policy", validate_deepagents_policy_artifact(deepagents_policy))
    _validate_or_raise(
        "deepagents readiness",
        validate_deepagents_readiness_artifact(deepagents_readiness),
    )

    plan_ref = _artifact_ref(
        orchestration_assignment_plan,
        role="orchestration_assignment_plan",
        path=orchestration_assignment_plan_path,
        name="orchestration assignment plan",
    )
    dry_run_ref = _artifact_ref(
        orchestration_assignment_dry_run,
        role="orchestration_assignment_dry_run",
        path=orchestration_assignment_dry_run_path,
        name="orchestration assignment dry run",
    )
    policy_ref = _artifact_ref(
        deepagents_policy,
        role="deepagents_policy",
        path=deepagents_policy_path,
        name="deepagents governed policy",
    )
    readiness_ref = _artifact_ref(
        deepagents_readiness,
        role="deepagents_readiness",
        path=deepagents_readiness_path,
        name="deepagents readiness",
    )

    source_refs = [plan_ref, dry_run_ref, policy_ref, readiness_ref]
    source_digests = {ref["role"]: ref["sha256"] for ref in source_refs}

    plan = {
        "kind": DEEPAGENTS_WORK_PLAN_KIND,
        "schema_version": DEEPAGENTS_WORK_PLAN_SCHEMA_VERSION,
        "plan_state": "PLANNED_ONLY",
        "mode": "proposal_only",
        "target": target,
        "task": task_text,
        "orchestration_assignment_plan_ref": plan_ref,
        "orchestration_assignment_dry_run_ref": dry_run_ref,
        "deepagents_policy_ref": policy_ref,
        "deepagents_readiness_ref": readiness_ref,
        "source_refs": source_refs,
        "source_digests": source_digests,
        "proposed_subagents": proposed_subagents or [],
        "expected_outputs": expected_outputs or [],
        "review_gates": review_gates or [],
        "blocked_capabilities": blocked_capabilities or list(_DENIED_CAPABILITIES),
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_work_plan"),
        "governance": _default_governance("deepagents_work_plan"),
    }
    _validate_or_raise("deepagents work plan", validate_deepagents_work_plan(plan))
    return plan


def create_deepagents_subagent_assignment(
    *,
    target: str,
    task: str,
    subagent_profile: str,
    work_plan: dict[str, Any],
    work_plan_path: Path | None = None,
) -> dict[str, Any]:
    task_text = task.strip()
    if not task_text:
        raise ValueError("task must be a non-empty string")
    if target not in target_names():
        raise ValueError(f"unknown target: {target}")
    if not subagent_profile.strip():
        raise ValueError("subagent_profile must be a non-empty string")
    _validate_or_raise("deepagents work plan", validate_deepagents_work_plan(work_plan))

    work_plan_ref = _artifact_ref(
        work_plan,
        role="work_plan",
        path=work_plan_path,
        name="deepagents work plan",
    )

    source_refs = [work_plan_ref]
    source_digests = {"work_plan": work_plan_ref["sha256"]}

    assignment = {
        "kind": DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
        "schema_version": DEEPAGENTS_SUBAGENT_ASSIGNMENT_SCHEMA_VERSION,
        "assignment_state": "ASSIGNED_ONLY",
        "result_mode": "PROPOSAL_ONLY",
        "target": target,
        "task": task_text,
        "subagent_profile": subagent_profile,
        "work_plan_ref": work_plan_ref,
        "source_refs": source_refs,
        "source_digests": source_digests,
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_subagent_assignment"),
        "governance": _default_governance("deepagents_subagent_assignment"),
    }
    _validate_or_raise(
        "deepagents subagent assignment",
        validate_deepagents_subagent_assignment(assignment),
    )
    return assignment


def create_deepagents_subagent_result(
    *,
    target: str,
    subagent_profile: str,
    summary: str,
    subagent_assignment: dict[str, Any],
    subagent_assignment_path: Path | None = None,
) -> dict[str, Any]:
    if target not in target_names():
        raise ValueError(f"unknown target: {target}")
    if not subagent_profile.strip():
        raise ValueError("subagent_profile must be a non-empty string")
    _validate_or_raise(
        "deepagents subagent assignment",
        validate_deepagents_subagent_assignment(subagent_assignment),
    )

    assignment_ref = _artifact_ref(
        subagent_assignment,
        role="subagent_assignment",
        path=subagent_assignment_path,
        name="deepagents subagent assignment",
    )

    source_refs = [assignment_ref]
    source_digests = {"subagent_assignment": assignment_ref["sha256"]}

    result = {
        "kind": DEEPAGENTS_SUBAGENT_RESULT_KIND,
        "schema_version": DEEPAGENTS_SUBAGENT_RESULT_SCHEMA_VERSION,
        "result_state": "RECORDED_ONLY",
        "target": target,
        "subagent_profile": subagent_profile,
        "summary": summary,
        "subagent_assignment_ref": assignment_ref,
        "source_refs": source_refs,
        "source_digests": source_digests,
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_subagent_result"),
        "governance": _default_governance("deepagents_subagent_result"),
    }
    _validate_or_raise("deepagents subagent result", validate_deepagents_subagent_result(result))
    return result


def create_deepagents_subagent_review(
    *,
    target: str,
    disposition: str,
    subagent_result: dict[str, Any],
    subagent_assignment: dict[str, Any],
    subagent_result_path: Path | None = None,
    subagent_assignment_path: Path | None = None,
) -> dict[str, Any]:
    if target not in target_names():
        raise ValueError(f"unknown target: {target}")
    if disposition not in ("accepted_as_proposal", "needs_revision", "rejected"):
        raise ValueError(f"invalid disposition: {disposition}")
    _validate_or_raise(
        "deepagents subagent result",
        validate_deepagents_subagent_result(subagent_result),
    )
    _validate_or_raise(
        "deepagents subagent assignment",
        validate_deepagents_subagent_assignment(subagent_assignment),
    )
    result_assignment_ref = subagent_result.get("subagent_assignment_ref")
    if not isinstance(result_assignment_ref, dict) or result_assignment_ref.get("sha256") != canonical_digest(
        subagent_assignment
    ):
        raise ValueError("subagent_result must be bound to the supplied subagent_assignment")

    result_ref = _artifact_ref(
        subagent_result,
        role="subagent_result",
        path=subagent_result_path,
        name="deepagents subagent result",
    )
    assignment_ref = _artifact_ref(
        subagent_assignment,
        role="subagent_assignment",
        path=subagent_assignment_path,
        name="deepagents subagent assignment",
    )

    source_refs = [result_ref, assignment_ref]
    source_digests = {
        "subagent_result": result_ref["sha256"],
        "subagent_assignment": assignment_ref["sha256"],
    }

    review = {
        "kind": DEEPAGENTS_SUBAGENT_REVIEW_KIND,
        "schema_version": DEEPAGENTS_SUBAGENT_REVIEW_SCHEMA_VERSION,
        "review_state": "REVIEW_ONLY",
        "target": target,
        "disposition": disposition,
        "subagent_result_ref": result_ref,
        "subagent_assignment_ref": assignment_ref,
        "source_refs": source_refs,
        "source_digests": source_digests,
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_subagent_review"),
        "governance": _default_governance("deepagents_subagent_review"),
    }
    _validate_or_raise("deepagents subagent review", validate_deepagents_subagent_review(review))
    return review


def create_deepagents_human_gate_request(
    *,
    target: str,
    reviewed_artifact: dict[str, Any],
    reviewed_artifact_path: Path | None = None,
) -> dict[str, Any]:
    if target not in target_names():
        raise ValueError(f"unknown target: {target}")
    _validate_known_deepagents_work_artifact("reviewed artifact", reviewed_artifact)

    reviewed_ref = _artifact_ref(
        reviewed_artifact,
        role="reviewed_artifact",
        path=reviewed_artifact_path,
        name="reviewed artifact",
    )

    source_refs = [reviewed_ref]
    source_digests = {"reviewed_artifact": reviewed_ref["sha256"]}

    request = {
        "kind": DEEPAGENTS_HUMAN_GATE_REQUEST_KIND,
        "schema_version": DEEPAGENTS_HUMAN_GATE_REQUEST_SCHEMA_VERSION,
        "gate_state": "REQUESTED_ONLY",
        "approval_state": "NOT_GRANTED",
        "target": target,
        "reviewed_artifact_ref": reviewed_ref,
        "source_refs": source_refs,
        "source_digests": source_digests,
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_human_gate_request"),
        "governance": _default_governance("deepagents_human_gate_request"),
    }
    _validate_or_raise("deepagents human gate request", validate_deepagents_human_gate_request(request))
    return request


def create_deepagents_blocked_action_record(
    *,
    target: str,
    denied_capability: str,
    triggering_artifact: dict[str, Any] | None = None,
    triggering_artifact_path: Path | None = None,
) -> dict[str, Any]:
    if target not in target_names():
        raise ValueError(f"unknown target: {target}")
    if denied_capability not in _DENIED_CAPABILITIES:
        allowed = ", ".join(_DENIED_CAPABILITIES)
        raise ValueError(f"denied_capability must be one of: {allowed}")

    source_refs = []
    source_digests = {}

    if triggering_artifact is not None:
        _validate_known_deepagents_work_artifact("triggering artifact", triggering_artifact)
        trigger_ref = _artifact_ref(
            triggering_artifact,
            role="triggering_artifact",
            path=triggering_artifact_path,
            name="triggering artifact",
        )
        source_refs.append(trigger_ref)
        source_digests["triggering_artifact"] = trigger_ref["sha256"]

    record = {
        "kind": DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND,
        "schema_version": DEEPAGENTS_BLOCKED_ACTION_RECORD_SCHEMA_VERSION,
        "record_state": "BLOCKED_ONLY",
        "target": target,
        "denied_capability": denied_capability,
        "source_refs": source_refs,
        "source_digests": source_digests,
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_blocked_action_record"),
        "governance": _default_governance("deepagents_blocked_action_record"),
    }
    if triggering_artifact is not None:
        record["triggering_artifact_ref"] = source_refs[0]

    _validate_or_raise(
        "deepagents blocked action record",
        validate_deepagents_blocked_action_record(record),
    )
    return record


def create_deepagents_proposal_result(
    *,
    target: str,
    work_plan: dict[str, Any],
    reviewed_results: list[dict[str, Any]],
    work_plan_path: Path | None = None,
    reviewed_result_paths: list[Path | None] | None = None,
) -> dict[str, Any]:
    if target not in target_names():
        raise ValueError(f"unknown target: {target}")
    _validate_or_raise("deepagents work plan", validate_deepagents_work_plan(work_plan))
    if not reviewed_results:
        raise ValueError("reviewed_results must contain at least one artifact")
    if reviewed_result_paths is not None and len(reviewed_result_paths) != len(reviewed_results):
        raise ValueError("reviewed_result_paths length must match reviewed_results")
    reviewed_result_kinds = {
        DEEPAGENTS_SUBAGENT_RESULT_KIND,
        DEEPAGENTS_SUBAGENT_REVIEW_KIND,
    }
    for index, reviewed_result in enumerate(reviewed_results):
        _validate_known_deepagents_work_artifact(
            f"reviewed_results[{index}]",
            reviewed_result,
            allowed_kinds=reviewed_result_kinds,
        )

    work_plan_ref = _artifact_ref(
        work_plan,
        role="work_plan",
        path=work_plan_path,
        name="deepagents work plan",
    )

    source_refs = [work_plan_ref]
    reviewed_result_refs = []

    paths = reviewed_result_paths or [None] * len(reviewed_results)
    for idx, (res, path) in enumerate(zip(reviewed_results, paths)):
        ref = _artifact_ref(
            res,
            role=f"reviewed_result_{idx}",
            path=path,
            name=f"reviewed result {idx}",
        )
        source_refs.append(ref)
        reviewed_result_refs.append(ref)

    source_digests = {ref["role"]: ref["sha256"] for ref in source_refs}

    proposal = {
        "kind": DEEPAGENTS_PROPOSAL_RESULT_KIND,
        "schema_version": DEEPAGENTS_PROPOSAL_RESULT_SCHEMA_VERSION,
        "proposal_state": "PROPOSAL_ONLY",
        "target": target,
        "work_plan_ref": work_plan_ref,
        "reviewed_result_refs": reviewed_result_refs,
        "source_refs": source_refs,
        "source_digests": source_digests,
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_proposal_result"),
        "governance": _default_governance("deepagents_proposal_result"),
    }
    _validate_or_raise("deepagents proposal result", validate_deepagents_proposal_result(proposal))
    return proposal


def create_deepagents_work_validation_report(
    subject: Any,
    *,
    subject_path: Path | None = None,
) -> dict[str, Any]:
    subject_kind = ""
    errors: list[str] = []
    subject_ref = {
        "role": "subject",
        "kind": "",
        "path": str(subject_path) if subject_path else "",
        "sha256": "",
        "name": "",
        "required": True,
    }

    if not isinstance(subject, dict):
        errors.append("subject must be a JSON object")
    else:
        subject_kind = str(subject.get("kind", ""))
        subject_ref = _artifact_ref(subject, role="subject", path=subject_path, name=subject_kind)
        validator = _deepagents_validators().get(subject_kind)
        if validator is None:
            errors.append(f"unknown deepagents work artifact kind: {subject_kind or '<missing>'}")
        else:
            try:
                errors.extend(validator(subject))
            except Exception as exc:
                errors.append(f"subject validation raised: {exc}")

    valid = errors == []
    report = {
        "kind": DEEPAGENTS_WORK_VALIDATION_REPORT_KIND,
        "schema_version": DEEPAGENTS_WORK_VALIDATION_REPORT_SCHEMA_VERSION,
        "validation_state": "VALIDATION_ONLY",
        "subject_kind": subject_kind,
        "subject_ref": subject_ref,
        "source_refs": [subject_ref],
        "source_digests": {"subject": subject_ref["sha256"]},
        "status": "valid" if valid else "invalid",
        "valid": valid,
        "errors": errors,
        "warnings": [],
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
        "grants_authority": False,
        "artifact_is_authority": False,
        "requires_human_promotion_for_execution": True,
        "authority_boundary": _default_authority_boundary("deepagents_work_validation_report"),
        "governance": _default_governance("deepagents_work_validation_report"),
    }
    report_errors = validate_deepagents_work_validation_report(report)
    if report_errors:
        raise ValueError("created invalid deepagents work validation report: " + "; ".join(report_errors))
    return report


# Dumps and Writes


def dumps_deepagents_work_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_subagent_assignment(assignment: dict[str, Any]) -> str:
    return json_lib.dumps(assignment, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_subagent_result(result: dict[str, Any]) -> str:
    return json_lib.dumps(result, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_subagent_review(review: dict[str, Any]) -> str:
    return json_lib.dumps(review, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_human_gate_request(request: dict[str, Any]) -> str:
    return json_lib.dumps(request, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_blocked_action_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_proposal_result(proposal: dict[str, Any]) -> str:
    return json_lib.dumps(proposal, indent=2, sort_keys=True) + "\n"


def dumps_deepagents_work_validation_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"


def write_deepagents_work_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_work_plan(plan), encoding="utf-8")


def write_deepagents_subagent_assignment(assignment: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_subagent_assignment(assignment), encoding="utf-8")


def write_deepagents_subagent_result(result: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_subagent_result(result), encoding="utf-8")


def write_deepagents_subagent_review(review: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_subagent_review(review), encoding="utf-8")


def write_deepagents_human_gate_request(request: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_human_gate_request(request), encoding="utf-8")


def write_deepagents_blocked_action_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_blocked_action_record(record), encoding="utf-8")


def write_deepagents_proposal_result(proposal: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_proposal_result(proposal), encoding="utf-8")


def write_deepagents_work_validation_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_deepagents_work_validation_report(report), encoding="utf-8")


# Common Validators


def _validate_sha(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, str) or not _SHA256_RE.match(value):
        return [f"{field} must be a SHA-256 hex digest"]
    return []


def _validate_ref(
    value: Any,
    *,
    field: str,
    expected_kind: str | None = None,
    expected_role: str | None = None,
) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return [f"{field} must be an object"]
    if expected_role is not None and value.get("role") != expected_role:
        errors.append(f"{field}.role must be {expected_role}")
    kind = value.get("kind")
    if not isinstance(kind, str) or not kind:
        errors.append(f"{field}.kind must be a non-empty string")
    elif expected_kind is not None and kind != expected_kind:
        errors.append(f"{field}.kind must be {expected_kind}")
    if not isinstance(value.get("path", ""), str):
        errors.append(f"{field}.path must be a string")
    sha = value.get("sha256")
    errors.extend(_validate_sha(sha, field=f"{field}.sha256"))
    if value.get("required") is not True:
        errors.append(f"{field}.required must be true")
    if not isinstance(value.get("name", ""), str):
        errors.append(f"{field}.name must be a string")
    return errors


def _source_refs_by_role(
    data: dict[str, Any],
    *,
    allow_empty: bool = False,
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    errors: list[str] = []
    refs = data.get("source_refs")
    if not isinstance(refs, list):
        return {}, ["source_refs must be a list"]
    if not refs and not allow_empty:
        return {}, ["source_refs must be a non-empty list"]
    by_role: dict[str, dict[str, Any]] = {}
    for index, ref in enumerate(refs):
        field = f"source_refs[{index}]"
        if not isinstance(ref, dict):
            errors.append(f"{field} must be an object")
            continue
        role = ref.get("role")
        if not isinstance(role, str) or not role:
            errors.append(f"{field}.role must be a non-empty string")
            continue
        if role in by_role:
            errors.append(f"duplicate source ref role: {role}")
        by_role[role] = ref
    return by_role, errors


def _validate_source_ref_bindings(
    data: dict[str, Any],
    bindings: tuple[tuple[str, str, str | None], ...],
    *,
    allow_extra_roles: set[str] | None = None,
    allow_empty: bool = False,
) -> list[str]:
    errors: list[str] = []
    by_role, role_errors = _source_refs_by_role(data, allow_empty=allow_empty)
    errors.extend(role_errors)
    source_digests = data.get("source_digests")
    if not isinstance(source_digests, dict):
        errors.append("source_digests must be an object")
        source_digests = {}

    required_roles = {role for role, _, _ in bindings}
    allowed_roles = required_roles | (allow_extra_roles or set())

    for role, field, expected_kind in bindings:
        ref = by_role.get(role)
        if ref is None:
            errors.append(f"missing {role} source ref")
            continue
        errors.extend(
            _validate_ref(
                ref,
                field=f"source_refs.{role}",
                expected_kind=expected_kind,
                expected_role=role,
            )
        )
        if source_digests.get(role) != ref.get("sha256"):
            errors.append(f"source_digests.{role} must match {role} ref sha256")
        direct_ref = data.get(field)
        if isinstance(direct_ref, dict) and ref != direct_ref:
            errors.append(f"source_refs.{role} must match {field}")

    for role in by_role:
        if role not in allowed_roles:
            errors.append(f"unknown source ref role: {role}")
    for role in source_digests:
        if role not in allowed_roles:
            errors.append(f"unknown source digest role: {role}")

    return errors


def _validate_authority_boundary(data: dict[str, Any], *, capability_state: str) -> list[str]:
    errors: list[str] = []
    authority_keys = (
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
        "grants_authority",
        "artifact_is_authority",
    )
    for key in authority_keys:
        if data.get(key) is not False:
            errors.append(f"{key} must be false or NOT_AUTHORIZED")
    if data.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    boundary = data.get("authority_boundary")
    if not isinstance(boundary, dict):
        errors.append("authority_boundary must be an object")
    else:
        if boundary.get("capability_state") != capability_state:
            errors.append(f"authority_boundary.capability_state must be {capability_state}")
        for key in authority_keys:
            if boundary.get(key) is not False:
                errors.append(f"authority_boundary.{key} must be false or NOT_AUTHORIZED")
        if boundary.get("requires_human_promotion_for_execution") is not True:
            errors.append("authority_boundary.requires_human_promotion_for_execution must be true")
    return errors


def _validate_governance(governance: Any, *, capability_state: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    if governance.get("capability_state") != capability_state:
        errors.append(f"governance.capability_state must be {capability_state}")
    for key in (
        "runtime_execution",
        "goose_runtime_start",
        "deepagents_runtime_start",
        "agent_construction",
        "subagent_construction",
        "model_execution",
        "tool_execution",
        "shell_execution",
        "network_calls",
        "target_repo_writes",
        "memory_mutation",
        "mcp_tool_calls",
        "verification_execution",
    ):
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
    if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH":
        errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH")
    for key in ("artifact_is_authority", "grants_authority"):
        if governance.get(key) is not False:
            errors.append(f"governance.{key} must be false or NOT_AUTHORIZED")
    if governance.get("requires_human_promotion_for_execution") is not True:
        errors.append("governance.requires_human_promotion_for_execution must be true")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def _validate_no_active_state_claims(value: Any, path: str) -> list[str]:
    errors: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_validate_no_active_state_claims(item, f"{path}.{key}" if path else key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_validate_no_active_state_claims(item, f"{path}[{index}]"))
    elif isinstance(value, str):
        for match in _FORBIDDEN_ACTIVE_STATE_RE.finditer(value):
            term = match.group(1)
            if _is_denial_context(value, match.start(), match.end()):
                continue
            errors.append(f"field '{path}' claims active authority state '{term}'")
    return errors


def _is_denial_context(text: str, start: int, end: int) -> bool:
    lower = text.lower()
    prefix = lower[max(0, start - 48) : start]
    suffix = lower[end : min(len(lower), end + 48)]
    if re.search(r"(?:^|[\s_.,;:/-])(not|no|never|without|non)[\s_-]+$", prefix):
        return True
    if re.search(r"(blocked|denied|disabled|disallowed|prevented|refused|rejected)", prefix):
        return True
    if re.search(
        r"^(?:[\s_.,;:/-]*(blocked|denied|disabled|disallowed|prevented|refused|rejected))",
        suffix,
    ):
        return True
    return False


# Specific Schema Validators


def validate_deepagents_work_plan(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents work plan must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_WORK_PLAN_KIND:
        errors.append(f"kind must be {DEEPAGENTS_WORK_PLAN_KIND}")
    if data.get("schema_version") != DEEPAGENTS_WORK_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_WORK_PLAN_SCHEMA_VERSION}")
    if data.get("plan_state") != "PLANNED_ONLY":
        errors.append("plan_state must be PLANNED_ONLY")
    if data.get("mode") != "proposal_only":
        errors.append("mode must be proposal_only")
    if data.get("target") not in target_names():
        errors.append("target must be a known target profile")
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task must be a non-empty string")

    # Refs
    errors.extend(
        _validate_ref(
            data.get("orchestration_assignment_plan_ref"),
            field="orchestration_assignment_plan_ref",
            expected_kind=ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
            expected_role="orchestration_assignment_plan",
        )
    )
    errors.extend(
        _validate_ref(
            data.get("orchestration_assignment_dry_run_ref"),
            field="orchestration_assignment_dry_run_ref",
            expected_kind=ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
            expected_role="orchestration_assignment_dry_run",
        )
    )
    errors.extend(
        _validate_ref(
            data.get("deepagents_policy_ref"),
            field="deepagents_policy_ref",
            expected_kind=DEEPAGENTS_POLICY_KIND,
            expected_role="deepagents_policy",
        )
    )
    errors.extend(
        _validate_ref(
            data.get("deepagents_readiness_ref"),
            field="deepagents_readiness_ref",
            expected_kind=DEEPAGENTS_READINESS_KIND,
            expected_role="deepagents_readiness",
        )
    )

    # Lists
    for list_field in (
        "proposed_subagents",
        "expected_outputs",
        "review_gates",
        "blocked_capabilities",
    ):
        value = data.get(list_field)
        if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
            errors.append(f"{list_field} must be a list of non-empty strings")
    blocked_capabilities = data.get("blocked_capabilities")
    if isinstance(blocked_capabilities, list):
        for capability in blocked_capabilities:
            if capability not in _DENIED_CAPABILITIES:
                errors.append(f"blocked_capabilities contains unknown denied capability: {capability}")

    errors.extend(
        _validate_source_ref_bindings(
            data,
            (
                (
                    "orchestration_assignment_plan",
                    "orchestration_assignment_plan_ref",
                    ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
                ),
                (
                    "orchestration_assignment_dry_run",
                    "orchestration_assignment_dry_run_ref",
                    ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
                ),
                ("deepagents_policy", "deepagents_policy_ref", DEEPAGENTS_POLICY_KIND),
                (
                    "deepagents_readiness",
                    "deepagents_readiness_ref",
                    DEEPAGENTS_READINESS_KIND,
                ),
            ),
        )
    )

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_work_plan"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_work_plan"))
    errors.extend(_validate_no_active_state_claims(data, "work_plan"))
    return errors


def validate_deepagents_subagent_assignment(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents subagent assignment must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND}")
    if data.get("schema_version") != DEEPAGENTS_SUBAGENT_ASSIGNMENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_SUBAGENT_ASSIGNMENT_SCHEMA_VERSION}")
    if data.get("assignment_state") != "ASSIGNED_ONLY":
        errors.append("assignment_state must be ASSIGNED_ONLY")
    if data.get("result_mode") != "PROPOSAL_ONLY":
        errors.append("result_mode must be PROPOSAL_ONLY")
    if data.get("target") not in target_names():
        errors.append("target must be a known target profile")
    if not isinstance(data.get("task"), str) or not data["task"]:
        errors.append("task must be a non-empty string")
    if not isinstance(data.get("subagent_profile"), str) or not data["subagent_profile"]:
        errors.append("subagent_profile must be a non-empty string")

    errors.extend(
        _validate_ref(
            data.get("work_plan_ref"),
            field="work_plan_ref",
            expected_kind=DEEPAGENTS_WORK_PLAN_KIND,
            expected_role="work_plan",
        )
    )

    errors.extend(
        _validate_source_ref_bindings(
            data,
            (("work_plan", "work_plan_ref", DEEPAGENTS_WORK_PLAN_KIND),),
        )
    )

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_subagent_assignment"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_subagent_assignment"))
    errors.extend(_validate_no_active_state_claims(data, "subagent_assignment"))
    return errors


def validate_deepagents_subagent_result(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents subagent result must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_SUBAGENT_RESULT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_SUBAGENT_RESULT_KIND}")
    if data.get("schema_version") != DEEPAGENTS_SUBAGENT_RESULT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_SUBAGENT_RESULT_SCHEMA_VERSION}")
    if data.get("result_state") != "RECORDED_ONLY":
        errors.append("result_state must be RECORDED_ONLY")
    if data.get("target") not in target_names():
        errors.append("target must be a known target profile")
    if not isinstance(data.get("subagent_profile"), str) or not data["subagent_profile"]:
        errors.append("subagent_profile must be a non-empty string")
    if not isinstance(data.get("summary"), str):
        errors.append("summary must be a string")

    errors.extend(
        _validate_ref(
            data.get("subagent_assignment_ref"),
            field="subagent_assignment_ref",
            expected_kind=DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
            expected_role="subagent_assignment",
        )
    )

    errors.extend(
        _validate_source_ref_bindings(
            data,
            (
                (
                    "subagent_assignment",
                    "subagent_assignment_ref",
                    DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
                ),
            ),
        )
    )

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_subagent_result"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_subagent_result"))
    errors.extend(_validate_no_active_state_claims(data, "subagent_result"))
    return errors


def validate_deepagents_subagent_review(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents subagent review must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_SUBAGENT_REVIEW_KIND:
        errors.append(f"kind must be {DEEPAGENTS_SUBAGENT_REVIEW_KIND}")
    if data.get("schema_version") != DEEPAGENTS_SUBAGENT_REVIEW_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_SUBAGENT_REVIEW_SCHEMA_VERSION}")
    if data.get("review_state") != "REVIEW_ONLY":
        errors.append("review_state must be REVIEW_ONLY")
    if data.get("target") not in target_names():
        errors.append("target must be a known target profile")
    if data.get("disposition") not in (
        "accepted_as_proposal",
        "needs_revision",
        "rejected",
    ):
        errors.append("disposition must be accepted_as_proposal, needs_revision, or rejected")

    errors.extend(
        _validate_ref(
            data.get("subagent_result_ref"),
            field="subagent_result_ref",
            expected_kind=DEEPAGENTS_SUBAGENT_RESULT_KIND,
            expected_role="subagent_result",
        )
    )
    errors.extend(
        _validate_ref(
            data.get("subagent_assignment_ref"),
            field="subagent_assignment_ref",
            expected_kind=DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
            expected_role="subagent_assignment",
        )
    )

    errors.extend(
        _validate_source_ref_bindings(
            data,
            (
                (
                    "subagent_result",
                    "subagent_result_ref",
                    DEEPAGENTS_SUBAGENT_RESULT_KIND,
                ),
                (
                    "subagent_assignment",
                    "subagent_assignment_ref",
                    DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
                ),
            ),
        )
    )

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_subagent_review"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_subagent_review"))
    errors.extend(_validate_no_active_state_claims(data, "subagent_review"))
    return errors


def validate_deepagents_human_gate_request(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents human gate request must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_HUMAN_GATE_REQUEST_KIND:
        errors.append(f"kind must be {DEEPAGENTS_HUMAN_GATE_REQUEST_KIND}")
    if data.get("schema_version") != DEEPAGENTS_HUMAN_GATE_REQUEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_HUMAN_GATE_REQUEST_SCHEMA_VERSION}")
    if data.get("gate_state") != "REQUESTED_ONLY":
        errors.append("gate_state must be REQUESTED_ONLY")
    if data.get("approval_state") != "NOT_GRANTED":
        errors.append("approval_state must be NOT_GRANTED")
    if data.get("target") not in target_names():
        errors.append("target must be a known target profile")

    errors.extend(
        _validate_ref(
            data.get("reviewed_artifact_ref"),
            field="reviewed_artifact_ref",
            expected_role="reviewed_artifact",
        )
    )

    reviewed_ref = data.get("reviewed_artifact_ref")
    reviewed_kind = reviewed_ref.get("kind") if isinstance(reviewed_ref, dict) else None
    if isinstance(reviewed_kind, str) and reviewed_kind not in _deepagents_validators():
        errors.append("reviewed_artifact_ref.kind must be a deepagents work artifact kind")
    errors.extend(
        _validate_source_ref_bindings(
            data,
            (("reviewed_artifact", "reviewed_artifact_ref", reviewed_kind),),
        )
    )

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_human_gate_request"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_human_gate_request"))

    # Exclude reviewed_artifact_ref from active claim validation to avoid failures on valid subjects
    clean_data = dict(data)
    clean_data.pop("reviewed_artifact_ref", None)
    if "source_refs" in clean_data:
        clean_data["source_refs"] = [r for r in clean_data["source_refs"] if r.get("role") != "reviewed_artifact"]
    errors.extend(_validate_no_active_state_claims(clean_data, "human_gate_request"))
    return errors


def validate_deepagents_blocked_action_record(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents blocked action record must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND:
        errors.append(f"kind must be {DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND}")
    if data.get("schema_version") != DEEPAGENTS_BLOCKED_ACTION_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_BLOCKED_ACTION_RECORD_SCHEMA_VERSION}")
    if data.get("record_state") != "BLOCKED_ONLY":
        errors.append("record_state must be BLOCKED_ONLY")
    if data.get("target") not in target_names():
        errors.append("target must be a known target profile")
    if not isinstance(data.get("denied_capability"), str) or not data["denied_capability"]:
        errors.append("denied_capability must be a non-empty string")
    denied_capability = data.get("denied_capability")

    if "triggering_artifact_ref" in data:
        errors.extend(
            _validate_ref(
                data.get("triggering_artifact_ref"),
                field="triggering_artifact_ref",
                expected_role="triggering_artifact",
            )
        )

    if isinstance(denied_capability, str) and denied_capability not in _DENIED_CAPABILITIES:
        errors.append("denied_capability must be a known denied capability")

    has_trigger = "triggering_artifact_ref" in data
    trigger_ref = data.get("triggering_artifact_ref")
    trigger_kind = trigger_ref.get("kind") if isinstance(trigger_ref, dict) else None
    if has_trigger:
        if isinstance(trigger_kind, str) and trigger_kind not in _deepagents_validators():
            errors.append("triggering_artifact_ref.kind must be a deepagents work artifact kind")
        errors.extend(
            _validate_source_ref_bindings(
                data,
                (("triggering_artifact", "triggering_artifact_ref", trigger_kind),),
            )
        )
    else:
        by_role, role_errors = _source_refs_by_role(data, allow_empty=True)
        errors.extend(role_errors)
        if by_role:
            errors.append("source_refs must be empty without triggering_artifact_ref")
        if data.get("source_digests") != {}:
            errors.append("source_digests must be empty without triggering_artifact_ref")

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_blocked_action_record"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_blocked_action_record"))

    # Exclude triggering_artifact_ref from active claim validation to avoid false positives
    clean_data = dict(data)
    clean_data.pop("triggering_artifact_ref", None)
    if "source_refs" in clean_data:
        clean_data["source_refs"] = [r for r in clean_data["source_refs"] if r.get("role") != "triggering_artifact"]
    errors.extend(_validate_no_active_state_claims(clean_data, "blocked_action_record"))
    return errors


def validate_deepagents_proposal_result(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents proposal result must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_PROPOSAL_RESULT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_PROPOSAL_RESULT_KIND}")
    if data.get("schema_version") != DEEPAGENTS_PROPOSAL_RESULT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_PROPOSAL_RESULT_SCHEMA_VERSION}")
    if data.get("proposal_state") != "PROPOSAL_ONLY":
        errors.append("proposal_state must be PROPOSAL_ONLY")
    if data.get("target") not in target_names():
        errors.append("target must be a known target profile")

    errors.extend(
        _validate_ref(
            data.get("work_plan_ref"),
            field="work_plan_ref",
            expected_kind=DEEPAGENTS_WORK_PLAN_KIND,
            expected_role="work_plan",
        )
    )

    reviewed_result_refs = data.get("reviewed_result_refs")
    if not isinstance(reviewed_result_refs, list):
        errors.append("reviewed_result_refs must be a list")
    elif not reviewed_result_refs:
        errors.append("reviewed_result_refs must be a non-empty list")
    else:
        for idx, ref in enumerate(reviewed_result_refs):
            errors.extend(
                _validate_ref(
                    ref,
                    field=f"reviewed_result_refs[{idx}]",
                )
            )
            if isinstance(ref, dict) and ref.get("kind") not in {
                DEEPAGENTS_SUBAGENT_RESULT_KIND,
                DEEPAGENTS_SUBAGENT_REVIEW_KIND,
            }:
                errors.append(f"reviewed_result_refs[{idx}].kind must be a subagent result or review")

    by_role, role_errors = _source_refs_by_role(data)
    errors.extend(role_errors)
    source_digests = data.get("source_digests")
    if not isinstance(source_digests, dict):
        errors.append("source_digests must be an object")
        source_digests = {}
    else:
        for role, ref in by_role.items():
            if source_digests.get(role) != ref.get("sha256"):
                errors.append(f"source_digests.{role} must match ref sha256")
    work_plan_source_ref = by_role.get("work_plan")
    if work_plan_source_ref is None:
        errors.append("missing work_plan source ref")
    else:
        errors.extend(
            _validate_ref(
                work_plan_source_ref,
                field="source_refs.work_plan",
                expected_kind=DEEPAGENTS_WORK_PLAN_KIND,
                expected_role="work_plan",
            )
        )
        if work_plan_source_ref != data.get("work_plan_ref"):
            errors.append("source_refs.work_plan must match work_plan_ref")
    if isinstance(reviewed_result_refs, list):
        expected_review_roles = {
            str(ref.get("role"))
            for ref in reviewed_result_refs
            if isinstance(ref, dict) and isinstance(ref.get("role"), str)
        }
        for index, ref in enumerate(reviewed_result_refs):
            if not isinstance(ref, dict):
                continue
            role = ref.get("role")
            if not isinstance(role, str) or not role:
                continue
            source_ref = by_role.get(role)
            if source_ref is None:
                errors.append(f"missing {role} source ref")
            elif source_ref != ref:
                errors.append(f"source_refs.{role} must match reviewed_result_refs[{index}]")
            if not role.startswith("reviewed_result_"):
                errors.append(f"reviewed_result_refs[{index}].role must start with reviewed_result_")
        allowed_roles = {"work_plan", *expected_review_roles}
    else:
        allowed_roles = {"work_plan"}
    for role in by_role:
        if role not in allowed_roles:
            errors.append(f"unknown source ref role: {role}")
    for role in source_digests:
        if role not in allowed_roles:
            errors.append(f"unknown source digest role: {role}")

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_proposal_result"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_proposal_result"))

    # Exclude reviewed_result_refs and work_plan_ref from active claim validation
    clean_data = dict(data)
    clean_data.pop("work_plan_ref", None)
    clean_data.pop("reviewed_result_refs", None)
    if "source_refs" in clean_data:
        clean_data.pop("source_refs", None)
    errors.extend(_validate_no_active_state_claims(clean_data, "proposal_result"))
    return errors


def validate_deepagents_work_validation_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents work validation report must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_WORK_VALIDATION_REPORT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_WORK_VALIDATION_REPORT_KIND}")
    if data.get("schema_version") != DEEPAGENTS_WORK_VALIDATION_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_WORK_VALIDATION_REPORT_SCHEMA_VERSION}")
    if data.get("validation_state") != "VALIDATION_ONLY":
        errors.append("validation_state must be VALIDATION_ONLY")
    if data.get("status") not in ("valid", "invalid"):
        errors.append("status must be valid or invalid")
    if not isinstance(data.get("valid"), bool):
        errors.append("valid must be a boolean")
    if (data.get("status") == "valid") is not data.get("valid"):
        errors.append("valid must match status")
    if not isinstance(data.get("errors"), list):
        errors.append("errors must be a list")
    if not isinstance(data.get("warnings"), list):
        errors.append("warnings must be a list")

    errors.extend(
        _validate_ref(
            data.get("subject_ref"),
            field="subject_ref",
            expected_kind=data.get("subject_kind"),
            expected_role="subject",
        )
    )
    errors.extend(
        _validate_source_ref_bindings(
            data,
            (("subject", "subject_ref", data.get("subject_kind")),),
        )
    )

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_work_validation_report"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_work_validation_report"))

    # Exclude subject_ref from active claim validation
    clean_data = dict(data)
    clean_data.pop("subject_ref", None)
    errors.extend(_validate_no_active_state_claims(clean_data, "work_validation_report"))
    return errors


def validate_deepagents_runtime_envelope(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents runtime envelope must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_RUNTIME_ENVELOPE_KIND:
        errors.append(f"kind must be {DEEPAGENTS_RUNTIME_ENVELOPE_KIND}")
    if data.get("schema_version") != DEEPAGENTS_RUNTIME_ENVELOPE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_RUNTIME_ENVELOPE_SCHEMA_VERSION}")
    if data.get("envelope_state") not in ("RUNNING", "COMPLETED"):
        errors.append("envelope_state must be RUNNING or COMPLETED")

    # Check work_plan_ref
    errors.extend(
        _validate_ref(
            data.get("work_plan_ref"),
            field="work_plan_ref",
            expected_kind=DEEPAGENTS_WORK_PLAN_KIND,
            expected_role="work_plan",
        )
    )

    # Check execution_receipt_refs
    receipt_refs = data.get("execution_receipt_refs")
    if not isinstance(receipt_refs, list):
        errors.append("execution_receipt_refs must be a list")
    else:
        for idx, ref in enumerate(receipt_refs):
            errors.extend(
                _validate_ref(
                    ref,
                    field=f"execution_receipt_refs[{idx}]",
                    expected_kind=DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND,
                    expected_role=f"execution_receipt_{idx}",
                )
            )

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_runtime"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_runtime"))
    # The runtime envelope acts with runtime/execution authority, so we exclude it from no active state claims
    return errors


def validate_deepagents_subagent_execution_receipt(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["deepagents subagent execution receipt must be a JSON object"]
    if data.get("kind") != DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND:
        errors.append(f"kind must be {DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND}")
    if data.get("schema_version") != DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_SCHEMA_VERSION}")
    if data.get("receipt_state") != "PROJECTED_ONLY":
        errors.append("receipt_state must be PROJECTED_ONLY")
    if not isinstance(data.get("subagent_profile"), str) or not data["subagent_profile"]:
        errors.append("subagent_profile must be a non-empty string")

    # Check assignment_ref
    errors.extend(
        _validate_ref(
            data.get("assignment_ref"),
            field="assignment_ref",
            expected_kind=DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND,
            expected_role="assignment",
        )
    )

    # Check result_ref
    errors.extend(
        _validate_ref(
            data.get("result_ref"),
            field="result_ref",
            expected_kind=DEEPAGENTS_SUBAGENT_RESULT_KIND,
            expected_role="result",
        )
    )

    errors.extend(_validate_authority_boundary(data, capability_state="deepagents_runtime"))
    errors.extend(_validate_governance(data.get("governance"), capability_state="deepagents_runtime"))
    # The receipt has PROJECTED_ONLY state, so it does not check for no active state claims
    return errors


# File Load and Validators


def _validate_file_generic(path: Path, validator: Callable[[Any], list[str]]) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validator(data)


def validate_deepagents_work_plan_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_work_plan)


def validate_deepagents_subagent_assignment_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_subagent_assignment)


def validate_deepagents_subagent_result_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_subagent_result)


def validate_deepagents_subagent_review_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_subagent_review)


def validate_deepagents_human_gate_request_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_human_gate_request)


def validate_deepagents_blocked_action_record_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_blocked_action_record)


def validate_deepagents_proposal_result_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_proposal_result)


def validate_deepagents_work_validation_report_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_work_validation_report)


def validate_deepagents_runtime_envelope_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_runtime_envelope)


def validate_deepagents_subagent_execution_receipt_file(path: Path) -> list[str]:
    return _validate_file_generic(path, validate_deepagents_subagent_execution_receipt)


def _deepagents_validators() -> dict[str, Callable[[Any], list[str]]]:
    return {
        DEEPAGENTS_WORK_PLAN_KIND: validate_deepagents_work_plan,
        DEEPAGENTS_SUBAGENT_ASSIGNMENT_KIND: validate_deepagents_subagent_assignment,
        DEEPAGENTS_SUBAGENT_RESULT_KIND: validate_deepagents_subagent_result,
        DEEPAGENTS_SUBAGENT_REVIEW_KIND: validate_deepagents_subagent_review,
        DEEPAGENTS_HUMAN_GATE_REQUEST_KIND: validate_deepagents_human_gate_request,
        DEEPAGENTS_BLOCKED_ACTION_RECORD_KIND: validate_deepagents_blocked_action_record,
        DEEPAGENTS_PROPOSAL_RESULT_KIND: validate_deepagents_proposal_result,
        DEEPAGENTS_WORK_VALIDATION_REPORT_KIND: validate_deepagents_work_validation_report,
        DEEPAGENTS_RUNTIME_ENVELOPE_KIND: validate_deepagents_runtime_envelope,
        DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND: validate_deepagents_subagent_execution_receipt,
    }
