from __future__ import annotations

import json as json_lib
import shlex
from pathlib import Path
from typing import Any, Literal

from builder_ii.command_authority import TIER_0, TIER_1, get_command_record
from builder_ii.config import Settings
from builder_ii.execution_postflight_records import (
    EXECUTION_POSTFLIGHT_RECORD_KIND,
    EXECUTION_VERIFICATION_RECORD_KIND,
)
from builder_ii.hitl_chain_binding import HITL_CHAIN_BINDING_KIND
from builder_ii.hitl_execution_records import HITL_EXECUTION_RECEIPT_KIND
from builder_ii.rollback_artifacts import ROLLBACK_PLAN_KIND, ROLLBACK_RECEIPT_KIND
from builder_ii.target_profiles import TargetName, target_names, target_profile
from builder_ii.verification_profile_reports import VERIFICATION_PROFILE_REPORT_KIND
from builder_ii.verification_profiles import VERIFICATION_ARTIFACT_KIND

HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND = "builder_ii.hitl_verification_execution_candidate"
HITL_VERIFICATION_EXECUTION_CANDIDATE_SCHEMA_VERSION = 1

CandidateState = Literal["CANDIDATE_ONLY", "PLANNED_ONLY"]
AllowedCommandKind = Literal[
    "repo_native_pytest",
    "builder_structural_validation",
    "verification_profile_reference",
]

_ALLOWED_CANDIDATE_STATES = ("CANDIDATE_ONLY", "PLANNED_ONLY")
_ALLOWED_COMMAND_KINDS = (
    "repo_native_pytest",
    "builder_structural_validation",
    "verification_profile_reference",
)
_ALLOWED_VERIFICATION_REF_KINDS = (
    VERIFICATION_PROFILE_REPORT_KIND,
    VERIFICATION_ARTIFACT_KIND,
)
_PYTEST_PREFIXES = (
    ("uv", "run", "pytest"),
    ("uv", "run", "python", "-m", "pytest"),
    ("python", "-m", "pytest"),
    ("python3", "-m", "pytest"),
    ("pytest",),
)
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
_GOVERNANCE_DISABLED_KEYS = (
    "runtime_execution",
    "model_execution",
    "shell_execution",
    "command_execution",
    "source_writes",
    "target_repo_writes",
    "memory_mutation",
    "git_mutation",
    "commit_push",
    "network_access",
    "goose_runtime_start",
    "deepagents_runtime",
)
_ALLOWED_TOP_LEVEL_FIELDS = {
    "kind",
    "schema_version",
    "candidate_state",
    "target_profile",
    "target",
    "verification_command",
    "verification_command_ref",
    "verification_command_ref_kind",
    "allowed_command_kind",
    "verification_scope",
    "proposal_ref",
    "approval_ref",
    "preflight_ref",
    "request_ref",
    "receipt_requirements",
    "postflight_requirements",
    "rollback_or_no_mutation_assertion",
    "verification_record_requirements",
    "chain_binding_requirements",
    "operator_review_required",
    "executes_now",
    "runtime_execution",
    "command_execution",
    "source_writes",
    "target_repo_writes",
    "artifact_is_authority",
    "governance",
}


def create_hitl_verification_execution_candidate(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    candidate_state: CandidateState = "CANDIDATE_ONLY",
    verification_command: str = "",
    verification_command_ref: str = "",
    verification_command_ref_kind: str = "",
    allowed_command_kind: AllowedCommandKind = "repo_native_pytest",
    verification_scope: dict[str, Any] | None = None,
    proposal_ref: str = "",
    approval_ref: str = "",
    preflight_ref: str = "",
    request_ref: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    """Create a passive candidate for future operator-approved verification.

    The returned artifact is metadata only. It records bounded intent and the
    required future evidence chain; it does not run or authorize the command.
    """
    if settings is None:
        from builder_ii.config import load_settings

        settings = load_settings()

    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    scope = {
        "scope_kind": "bounded_verification_command",
        "target_profile": selected.name,
        "target_repo": str(selected.repo),
        "source_mutation_expected": False,
        "target_repo_writes_expected": False,
    }
    if verification_scope:
        scope.update(verification_scope)

    return {
        "kind": HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND,
        "schema_version": HITL_VERIFICATION_EXECUTION_CANDIDATE_SCHEMA_VERSION,
        "candidate_state": candidate_state,
        "target_profile": selected.name,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "verification_command": verification_command.strip(),
        "verification_command_ref": verification_command_ref.strip(),
        "verification_command_ref_kind": verification_command_ref_kind.strip(),
        "allowed_command_kind": allowed_command_kind,
        "verification_scope": scope,
        "proposal_ref": proposal_ref,
        "approval_ref": approval_ref,
        "preflight_ref": preflight_ref,
        "request_ref": request_ref,
        "receipt_requirements": {
            "required": True,
            "expected_kind": HITL_EXECUTION_RECEIPT_KIND,
            "required_after_operator_execution": True,
            "candidate_stage_may_be_unresolved": True,
            "must_reference": "request_ref",
        },
        "postflight_requirements": {
            "required": True,
            "expected_kind": EXECUTION_POSTFLIGHT_RECORD_KIND,
            "required_after_receipt": True,
            "candidate_stage_may_be_unresolved": True,
            "must_reference": ("request_ref", "receipt_ref", "preflight_ref", "approval_ref"),
        },
        "rollback_or_no_mutation_assertion": {
            "required": True,
            "mode": "NO_SOURCE_MUTATION_OR_ROLLBACK_REQUIRED",
            "source_mutation_allowed": False,
            "target_repo_writes_allowed": False,
            "rollback_plan_expected_kind": ROLLBACK_PLAN_KIND,
            "rollback_receipt_expected_kind": ROLLBACK_RECEIPT_KIND,
        },
        "verification_record_requirements": {
            "required": True,
            "expected_kind": EXECUTION_VERIFICATION_RECORD_KIND,
            "required_after_postflight": True,
            "candidate_stage_may_be_unresolved": True,
            "must_reference": ("request_ref", "receipt_ref", "postflight_ref"),
        },
        "chain_binding_requirements": {
            "required": True,
            "expected_kind": HITL_CHAIN_BINDING_KIND,
            "required_after_verification_record": True,
            "candidate_stage_may_be_unresolved": True,
        },
        "operator_review_required": True,
        "executes_now": False,
        "runtime_execution": "DISABLED",
        "command_execution": "DISABLED",
        "source_writes": "DISABLED",
        "target_repo_writes": "DISABLED",
        "artifact_is_authority": False,
        "governance": {
            "capability_state": candidate_state,
            **{key: "DISABLED" for key in _GOVERNANCE_DISABLED_KEYS},
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def dumps_hitl_verification_execution_candidate(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"


def write_hitl_verification_execution_candidate(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_verification_execution_candidate(artifact), encoding="utf-8")


def validate_hitl_verification_execution_candidate(artifact: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(artifact, dict):
        return ["hitl verification execution candidate artifact must be a JSON object"]

    for key in artifact:
        if key not in _ALLOWED_TOP_LEVEL_FIELDS:
            errors.append(f"unknown field: {key}")

    if artifact.get("kind") != HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND:
        errors.append(f"kind must be {HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND}")
    if artifact.get("schema_version") != HITL_VERIFICATION_EXECUTION_CANDIDATE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_VERIFICATION_EXECUTION_CANDIDATE_SCHEMA_VERSION}")

    state = artifact.get("candidate_state")
    if state not in _ALLOWED_CANDIDATE_STATES:
        errors.append("candidate_state must be CANDIDATE_ONLY or PLANNED_ONLY")

    target = artifact.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") not in target_names():
            errors.append("target.name must be one of: generic, builder, core")
        if not target.get("repo"):
            errors.append("target.repo is required")
        if artifact.get("target_profile") != target.get("name"):
            errors.append("target_profile must match target.name")

    errors.extend(_validate_command_intent(artifact))
    errors.extend(_validate_candidate_refs(artifact))
    errors.extend(_validate_verification_scope(artifact.get("verification_scope")))
    errors.extend(_validate_requirement_blocks(artifact))
    errors.extend(_validate_no_authority_fields(artifact))
    errors.extend(_validate_governance_block(artifact, state))
    return errors


def validate_hitl_verification_execution_candidate_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_hitl_verification_execution_candidate(data)


def _validate_command_intent(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    command = artifact.get("verification_command")
    command_ref = artifact.get("verification_command_ref")
    command_ref_kind = artifact.get("verification_command_ref_kind")
    allowed_kind = artifact.get("allowed_command_kind")

    if allowed_kind not in _ALLOWED_COMMAND_KINDS:
        errors.append("allowed_command_kind must be a supported verification command kind")
        return errors

    if not isinstance(command, str):
        errors.append("verification_command must be a string")
        command = ""
    if not isinstance(command_ref, str):
        errors.append("verification_command_ref must be a string")
        command_ref = ""
    if not isinstance(command_ref_kind, str):
        errors.append("verification_command_ref_kind must be a string")
        command_ref_kind = ""

    if allowed_kind == "verification_profile_reference":
        if command:
            errors.append("verification_command must be empty for verification_profile_reference")
        if not command_ref:
            errors.append("verification_command_ref is required for verification_profile_reference")
        elif not _is_safe_relative_path(command_ref):
            errors.append("verification_command_ref must be a safe relative path")
        if command_ref_kind not in _ALLOWED_VERIFICATION_REF_KINDS:
            errors.append("verification_command_ref_kind must be a verification profile artifact kind")
        return errors

    if command_ref:
        errors.append(
            "verification_command_ref must be empty unless allowed_command_kind is verification_profile_reference"
        )
    if command_ref_kind:
        errors.append("verification_command_ref_kind must be empty unless verification_command_ref is used")
    if not command:
        errors.append("verification_command is required")
        return errors

    errors.extend(_validate_no_shell_control(command))
    if errors:
        return errors

    try:
        tokens = tuple(shlex.split(command, posix=True))
    except ValueError as exc:
        return [f"verification_command must parse as simple arguments: {exc}"]
    if not tokens:
        return ["verification_command is required"]

    if allowed_kind == "repo_native_pytest":
        if not any(tokens[: len(prefix)] == prefix for prefix in _PYTEST_PREFIXES):
            errors.append("verification_command must be an allowlisted repo-native pytest command")
    elif allowed_kind == "builder_structural_validation":
        record_name = _matched_registry_command(tokens)
        if record_name is None:
            errors.append("verification_command must begin with a registered builder command")
        else:
            record = get_command_record(record_name)
            if record is None:
                errors.append("verification_command registry record could not be resolved")
            elif record.tier not in (TIER_0, TIER_1):
                errors.append("verification_command registry record must be Tier 0 or Tier 1")
            elif (
                record.allows_runtime_start
                or record.allows_model_execution
                or record.allows_shell_execution
                or record.allows_source_writes
                or record.allows_memory_mutation
                or record.allows_git_mutation
                or record.allows_state_writes
                or record.allows_external_tool_invocation
            ):
                errors.append("verification_command registry record must not claim execution or mutation authority")
    return errors


def _validate_no_shell_control(command: str) -> list[str]:
    errors: list[str] = []
    for fragment in _FORBIDDEN_COMMAND_FRAGMENTS:
        if fragment in command:
            errors.append("verification_command must not contain shell control syntax")
            break
    return errors


def _matched_registry_command(tokens: tuple[str, ...]) -> str | None:
    for end in range(len(tokens), 0, -1):
        name = " ".join(tokens[:end])
        if get_command_record(name) is not None:
            return name
    return None


def _validate_candidate_refs(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for field in ("proposal_ref", "approval_ref", "preflight_ref", "request_ref"):
        value = artifact.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{field} is required")
        elif not _is_safe_relative_path(value):
            errors.append(f"{field} must be a safe relative path")
    return errors


def _validate_verification_scope(scope: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(scope, dict):
        return ["verification_scope must be an object"]
    if not isinstance(scope.get("scope_kind"), str) or not scope["scope_kind"]:
        errors.append("verification_scope.scope_kind must be a non-empty string")
    if scope.get("target_profile") not in target_names():
        errors.append("verification_scope.target_profile must be one of: generic, builder, core")
    if not isinstance(scope.get("target_repo"), str) or not scope["target_repo"]:
        errors.append("verification_scope.target_repo must be a non-empty string")
    if scope.get("source_mutation_expected") is not False:
        errors.append("verification_scope.source_mutation_expected must be false")
    if scope.get("target_repo_writes_expected") is not False:
        errors.append("verification_scope.target_repo_writes_expected must be false")
    return errors


def _validate_requirement_blocks(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    expected_blocks: dict[str, dict[str, Any]] = {
        "receipt_requirements": {
            "required": True,
            "expected_kind": HITL_EXECUTION_RECEIPT_KIND,
            "required_after_operator_execution": True,
            "candidate_stage_may_be_unresolved": True,
            "must_reference": "request_ref",
        },
        "postflight_requirements": {
            "required": True,
            "expected_kind": EXECUTION_POSTFLIGHT_RECORD_KIND,
            "required_after_receipt": True,
            "candidate_stage_may_be_unresolved": True,
            "must_reference": ("request_ref", "receipt_ref", "preflight_ref", "approval_ref"),
        },
        "verification_record_requirements": {
            "required": True,
            "expected_kind": EXECUTION_VERIFICATION_RECORD_KIND,
            "required_after_postflight": True,
            "candidate_stage_may_be_unresolved": True,
            "must_reference": ("request_ref", "receipt_ref", "postflight_ref"),
        },
        "chain_binding_requirements": {
            "required": True,
            "expected_kind": HITL_CHAIN_BINDING_KIND,
            "required_after_verification_record": True,
            "candidate_stage_may_be_unresolved": True,
        },
    }
    for field, expected in expected_blocks.items():
        block = artifact.get(field)
        if not isinstance(block, dict):
            errors.append(f"{field} must be an object")
            continue
        for key, expected_value in expected.items():
            value = block.get(key)
            if isinstance(expected_value, tuple):
                if tuple(value or ()) != expected_value:
                    errors.append(f"{field}.{key} must be {expected_value}")
            elif value != expected_value:
                errors.append(f"{field}.{key} must be {expected_value}")

    rollback = artifact.get("rollback_or_no_mutation_assertion")
    if not isinstance(rollback, dict):
        errors.append("rollback_or_no_mutation_assertion must be an object")
    else:
        expected_rollback = {
            "required": True,
            "mode": "NO_SOURCE_MUTATION_OR_ROLLBACK_REQUIRED",
            "source_mutation_allowed": False,
            "target_repo_writes_allowed": False,
            "rollback_plan_expected_kind": ROLLBACK_PLAN_KIND,
            "rollback_receipt_expected_kind": ROLLBACK_RECEIPT_KIND,
        }
        for key, expected_value in expected_rollback.items():
            if rollback.get(key) != expected_value:
                errors.append(f"rollback_or_no_mutation_assertion.{key} must be {expected_value}")
    return errors


def _validate_no_authority_fields(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if artifact.get("operator_review_required") is not True:
        errors.append("operator_review_required must be true")
    if artifact.get("executes_now") is not False:
        errors.append("executes_now must be false")
    for field in ("runtime_execution", "command_execution", "source_writes", "target_repo_writes"):
        if artifact.get(field) != "DISABLED":
            errors.append(f"{field} must be DISABLED")
    if artifact.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    return errors


def _validate_governance_block(artifact: dict[str, Any], expected_state: Any) -> list[str]:
    errors: list[str] = []
    governance = artifact.get("governance")
    if not isinstance(governance, dict):
        return ["governance must be an object"]
    if governance.get("capability_state") != expected_state:
        errors.append(f"governance.capability_state must be {expected_state}")
    for key in _GOVERNANCE_DISABLED_KEYS:
        if governance.get(key) != "DISABLED":
            errors.append(f"governance.{key} must be DISABLED")
    if governance.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false")
    if governance.get("core_workbench_coupling") != "NONE":
        errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def _is_safe_relative_path(path_str: str) -> bool:
    if not path_str:
        return False
    if path_str.startswith("/") or path_str.startswith("\\"):
        return False
    if ":" in path_str:
        return False
    parts = path_str.replace("\\", "/").split("/")
    return ".." not in parts
