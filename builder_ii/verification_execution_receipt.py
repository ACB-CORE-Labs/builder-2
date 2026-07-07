from __future__ import annotations

import datetime
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable
from builder_ii.verification_execution_approval import (
    VERIFICATION_EXECUTION_APPROVAL_KIND,
    VERIFICATION_EXECUTION_APPROVAL_SCHEMA_VERSION,
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
)
from builder_ii.verification_execution_plan import (
    VERIFICATION_EXECUTION_PLAN_KIND,
    VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION,
    validate_verification_execution_plan_artifact,
)

VERIFICATION_EXECUTION_RECEIPT_KIND = "builder_ii.verification_execution_receipt"
# Schema v2 (D9 hard cut, in lockstep with the plan and approval): adds target-repo
# commit identity (`target_commit`/`target_branch`) so a receipt is digest-bound to an
# exact source state, records ignored pytest byproducts observed during the run
# (`observed_byproducts`), and echoes the D7 execution-risk acknowledgment the runner
# verified before spawning.
VERIFICATION_EXECUTION_RECEIPT_SCHEMA_VERSION = 2
RUNNER_MODE_CONTRACT_ONLY = "receipt_contract_only"
RUNNER_MODE_BOUNDED_APPROVED = "bounded_approved_verification"
SUBPROCESS_MODE_NOT_STARTED = "not_started"
SUBPROCESS_MODE_SHELL_FALSE_BOUNDED = "shell_false_bounded"

REQUIRED_DISABLED_AUTHORITY: dict[str, str] = {
    "arbitrary_shell": "disabled",
    "shell_true": "disabled",
    "source_writes": "disabled",
    "patch_authority": "disabled",
    "git_mutation": "disabled",
    "model_execution": "disabled",
    "mcp_tool_invocation": "disabled",
    "goose_runtime": "disabled",
    "deepagents_runtime": "disabled",
    "autonomous_writes": "disabled",
    "b2_patch_authority": "disabled",
    "direct_unapproved_execution": "disabled",
}

RECEIPT_STATUSES = {"NOT_EXECUTED", "BLOCKED_BEFORE_EXECUTION", "EXECUTED", "PARTIALLY_EXECUTED", "FAILED"}
PROCESS_RESULT_STATUSES = {
    "success",
    "non_zero_exit",
    "timeout",
    "blocked_before_execution",
    "skipped_not_approved",
    "skipped_dependency_failed",
    "not_executed",
}
RUNNER_MODES = {RUNNER_MODE_CONTRACT_ONLY, RUNNER_MODE_BOUNDED_APPROVED}
SUBPROCESS_MODES = {SUBPROCESS_MODE_NOT_STARTED, SUBPROCESS_MODE_SHELL_FALSE_BOUNDED}


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value.lower())


def _dedupe_errors(errors: list[str]) -> list[str]:
    return list(dict.fromkeys(errors))


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if _is_non_empty_string(item)]


def _default_capture_policy(stream: str) -> dict[str, Any]:
    return {
        "stream": stream,
        "capture_enabled": True,
        "max_bytes": 65536,
        "stores_full_output": False,
        "stores_digest": True,
        "redaction_required": True,
    }


def _default_timeout_policy() -> dict[str, Any]:
    return {"timeout_required": True, "timeout_seconds_source": "command_profile", "operator_override_enabled": False}


def _default_environment_policy() -> dict[str, Any]:
    return {
        "ambient_environment_forwarded": False,
        "allowlist_required": True,
        "secrets_forwarded": False,
        "model_provider_keys_forwarded": False,
        "mcp_credentials_forwarded": False,
    }


def _default_cwd_policy() -> dict[str, Any]:
    return {"cwd_source": "validated_target_repo", "cwd_must_exist": True, "cwd_escape_allowed": False}


def _default_git_state(label: str) -> dict[str, Any]:
    return {
        "state_label": label,
        "captured": False,
        "capture_reason": "B1.3A receipt artifact is passive and does not execute git inspection.",
    }


def _default_skipped_steps(approval: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "step_id": step_id,
            "status": "not_executed",
            "reason": "B1.3A defines the receipt contract only; B1.3B runner is required before execution.",
        }
        for step_id in _string_list(approval.get("approved_step_ids"))
    ]


def finalize_verification_execution_receipt(
    *,
    plan: dict[str, Any],
    approval: dict[str, Any],
    plan_path: str,
    approval_path: str,
    runner_mode: str = RUNNER_MODE_CONTRACT_ONLY,
    generated_at: str | None = None,
    receipt_status: str = "NOT_EXECUTED",
    executed_steps: list[dict[str, Any]] | None = None,
    skipped_steps: list[dict[str, Any]] | None = None,
    process_results: list[dict[str, Any]] | None = None,
    preflight_git_state: dict[str, Any] | None = None,
    postflight_git_state: dict[str, Any] | None = None,
    workspace_mutation_detected: bool = False,
    execution_enabled: bool | None = None,
    subprocess_mode: str | None = None,
    target_commit: str | None = None,
    target_branch: str | None = None,
    observed_byproducts: list[str] | None = None,
    execution_risk_acknowledged: bool = False,
    acknowledged_risk: str | None = None,
) -> dict[str, Any]:
    effective_execution_enabled = (
        execution_enabled if execution_enabled is not None else runner_mode == RUNNER_MODE_BOUNDED_APPROVED
    )
    effective_subprocess_mode = subprocess_mode or (
        SUBPROCESS_MODE_SHELL_FALSE_BOUNDED
        if runner_mode == RUNNER_MODE_BOUNDED_APPROVED
        else SUBPROCESS_MODE_NOT_STARTED
    )
    receipt: dict[str, Any] = {
        "kind": VERIFICATION_EXECUTION_RECEIPT_KIND,
        "schema_version": VERIFICATION_EXECUTION_RECEIPT_SCHEMA_VERSION,
        "generated_at": generated_at or _utc_now(),
        "receipt_status": receipt_status,
        "target_profile": plan.get("target_profile"),
        "verification_profile": plan.get("verification_profile"),
        "target_repo": plan.get("target_repo"),
        "artifact_root": plan.get("artifact_root"),
        "plan_path": plan_path,
        "plan_digest": plan.get("verification_execution_plan_digest"),
        "plan_kind": plan.get("kind"),
        "plan_schema_version": plan.get("schema_version"),
        "approval_path": approval_path,
        "approval_digest": approval.get("verification_execution_approval_digest"),
        "approval_kind": approval.get("kind"),
        "approval_schema_version": approval.get("schema_version"),
        "runner_mode": runner_mode,
        "execution_enabled": effective_execution_enabled,
        "shell_enabled": False,
        "subprocess_mode": effective_subprocess_mode,
        "approved_command_profiles": _string_list(approval.get("approved_command_profiles")),
        "executed_steps": list(executed_steps or []),
        "skipped_steps": list(skipped_steps if skipped_steps is not None else _default_skipped_steps(approval)),
        "process_results": list(process_results or []),
        "preflight_git_state": preflight_git_state or _default_git_state("preflight"),
        "postflight_git_state": postflight_git_state or _default_git_state("postflight"),
        "workspace_mutation_detected": workspace_mutation_detected,
        # Commit identity binds the receipt to an exact target-repo source state
        # ("tests ran at commit X"); null when the target is not a git repo.
        "target_commit": target_commit,
        "target_branch": target_branch,
        # Paths that changed during the run and matched the profile's pinned ignore-globs
        # (e.g. pytest cache/bytecode). Recorded, never silently hidden: an ignore channel
        # is exactly where a malicious patch would try to write.
        "observed_byproducts": list(observed_byproducts or []),
        # Echo of the D7 acknowledgment the runner verified before spawning a target-code
        # profile. Evidence only; it never authorizes anything on its own.
        "execution_risk_acknowledged": bool(execution_risk_acknowledged),
        "acknowledged_risk": acknowledged_risk,
        "stdout_capture_policy": _default_capture_policy("stdout"),
        "stderr_capture_policy": _default_capture_policy("stderr"),
        "timeout_policy": _default_timeout_policy(),
        "environment_policy": _default_environment_policy(),
        "cwd_policy": _default_cwd_policy(),
        "disabled_authority": dict(REQUIRED_DISABLED_AUTHORITY),
        "errors": [],
        "valid": True,
    }
    receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")
    errors = _dedupe_errors(
        validate_verification_execution_receipt_artifact(receipt)
        + validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval)
    )
    if errors:
        receipt["errors"] = errors
        receipt["valid"] = False
        receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")
    return receipt


def dumps_verification_execution_receipt(receipt: dict[str, Any]) -> str:
    return json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n"


def write_verification_execution_receipt(receipt: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_verification_execution_receipt(receipt), encoding="utf-8")


def _validate_disabled_authority(data: dict[str, Any]) -> list[str]:
    disabled = data.get("disabled_authority")
    if not isinstance(disabled, dict):
        return ["disabled_authority must be an object"]
    return [
        f"disabled_authority.{key} must remain {expected}"
        for key, expected in REQUIRED_DISABLED_AUTHORITY.items()
        if disabled.get(key) != expected
    ]


def _validate_string_list(field: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    errors: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(value):
        if not _is_non_empty_string(item):
            errors.append(f"{field}[{index}] must be a non-empty string")
            continue
        cleaned = item.strip()
        if cleaned in seen:
            errors.append(f"{field}[{index}] must be unique")
        else:
            seen.add(cleaned)
    return errors


def _validate_policy(name: str, value: Any, required_false_keys: tuple[str, ...] = ()) -> list[str]:
    if not isinstance(value, dict):
        return [f"{name} must be an object"]
    return [f"{name}.{key} must be false or NOT_AUTHORIZED" for key in required_false_keys if value.get(key) is not False]


def _validate_step_records(field: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    errors: list[str] = []
    for index, item in enumerate(value):
        prefix = f"{field}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not _is_non_empty_string(item.get("step_id")):
            errors.append(f"{prefix}.step_id must be a non-empty string")
        if not _is_non_empty_string(item.get("status")):
            errors.append(f"{prefix}.status must be a non-empty string")
    return errors


def _validate_process_results(value: Any) -> list[str]:
    if not isinstance(value, list):
        return ["process_results must be a list"]
    errors: list[str] = []
    for index, item in enumerate(value):
        prefix = f"process_results[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{prefix} must be an object")
            continue
        if not _is_non_empty_string(item.get("step_id")):
            errors.append(f"{prefix}.step_id must be a non-empty string")
        if item.get("status") not in PROCESS_RESULT_STATUSES:
            errors.append(f"{prefix}.status must be one of: {', '.join(sorted(PROCESS_RESULT_STATUSES))}")
        if item.get("shell") is not False:
            errors.append(f"{prefix}.shell must be false or NOT_AUTHORIZED")
    return errors


def _validate_commit_identity_and_byproducts(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    target_commit = data.get("target_commit")
    if target_commit is not None and not _is_non_empty_string(target_commit):
        errors.append("target_commit must be null or a non-empty string")
    target_branch = data.get("target_branch")
    if target_branch is not None and not _is_non_empty_string(target_branch):
        errors.append("target_branch must be null or a non-empty string")
    errors.extend(_validate_string_list("observed_byproducts", data.get("observed_byproducts")))
    if not isinstance(data.get("execution_risk_acknowledged"), bool):
        errors.append("execution_risk_acknowledged must be a boolean")
    acknowledged_risk = data.get("acknowledged_risk")
    if acknowledged_risk is not None and not _is_non_empty_string(acknowledged_risk):
        errors.append("acknowledged_risk must be null or a non-empty string")
    return errors


def _validate_runner_mode(data: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    runner_mode = data.get("runner_mode")
    subprocess_mode = data.get("subprocess_mode")
    if runner_mode not in RUNNER_MODES:
        return [f"runner_mode must be one of: {', '.join(sorted(RUNNER_MODES))}"]
    if data.get("shell_enabled") is not False:
        errors.append("shell_enabled must be false or NOT_AUTHORIZED")
    if subprocess_mode not in SUBPROCESS_MODES:
        errors.append(f"subprocess_mode must be one of: {', '.join(sorted(SUBPROCESS_MODES))}")
    if runner_mode == RUNNER_MODE_CONTRACT_ONLY:
        if data.get("execution_enabled") is not False:
            errors.append("execution_enabled must be false or NOT_AUTHORIZED for B1.3A")
        if subprocess_mode != SUBPROCESS_MODE_NOT_STARTED:
            errors.append(f"subprocess_mode must be {SUBPROCESS_MODE_NOT_STARTED} for B1.3A")
        if data.get("workspace_mutation_detected") is not False:
            errors.append("workspace_mutation_detected must be false or NOT_AUTHORIZED for B1.3A")
    if runner_mode == RUNNER_MODE_BOUNDED_APPROVED:
        if data.get("execution_enabled") is not True:
            errors.append("execution_enabled must be true for B1.3B bounded runner receipts")
        if subprocess_mode != SUBPROCESS_MODE_SHELL_FALSE_BOUNDED:
            errors.append(f"subprocess_mode must be {SUBPROCESS_MODE_SHELL_FALSE_BOUNDED} for B1.3B")
        if not isinstance(data.get("workspace_mutation_detected"), bool):
            errors.append("workspace_mutation_detected must be a boolean")
    return errors


def validate_verification_execution_receipt_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["verification execution receipt artifact must be a JSON object"]
    if data.get("kind") != VERIFICATION_EXECUTION_RECEIPT_KIND:
        errors.append(f"kind must be {VERIFICATION_EXECUTION_RECEIPT_KIND}")
    if data.get("schema_version") != VERIFICATION_EXECUTION_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {VERIFICATION_EXECUTION_RECEIPT_SCHEMA_VERSION}")
    if not _is_non_empty_string(data.get("generated_at")):
        errors.append("generated_at must be a non-empty string")
    if data.get("receipt_status") not in RECEIPT_STATUSES:
        errors.append(f"receipt_status must be one of: {', '.join(sorted(RECEIPT_STATUSES))}")
    for field in (
        "target_profile",
        "verification_profile",
        "target_repo",
        "artifact_root",
        "plan_path",
        "approval_path",
    ):
        if not _is_non_empty_string(data.get(field)):
            errors.append(f"{field} must be a non-empty string")
    if data.get("plan_kind") != VERIFICATION_EXECUTION_PLAN_KIND:
        errors.append(f"plan_kind must be {VERIFICATION_EXECUTION_PLAN_KIND}")
    if data.get("plan_schema_version") != VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION:
        errors.append(f"plan_schema_version must be {VERIFICATION_EXECUTION_PLAN_SCHEMA_VERSION}")
    if not _is_sha256_hex(data.get("plan_digest")):
        errors.append("plan_digest must be a SHA-256 hex string")
    if data.get("approval_kind") != VERIFICATION_EXECUTION_APPROVAL_KIND:
        errors.append(f"approval_kind must be {VERIFICATION_EXECUTION_APPROVAL_KIND}")
    if data.get("approval_schema_version") != VERIFICATION_EXECUTION_APPROVAL_SCHEMA_VERSION:
        errors.append(f"approval_schema_version must be {VERIFICATION_EXECUTION_APPROVAL_SCHEMA_VERSION}")
    if not _is_sha256_hex(data.get("approval_digest")):
        errors.append("approval_digest must be a SHA-256 hex string")
    errors.extend(_validate_runner_mode(data))
    errors.extend(_validate_string_list("approved_command_profiles", data.get("approved_command_profiles")))
    errors.extend(_validate_step_records("executed_steps", data.get("executed_steps")))
    errors.extend(_validate_step_records("skipped_steps", data.get("skipped_steps")))
    errors.extend(_validate_process_results(data.get("process_results")))
    if not isinstance(data.get("preflight_git_state"), dict):
        errors.append("preflight_git_state must be an object")
    if not isinstance(data.get("postflight_git_state"), dict):
        errors.append("postflight_git_state must be an object")
    errors.extend(_validate_policy("stdout_capture_policy", data.get("stdout_capture_policy"), ("stores_full_output",)))
    errors.extend(_validate_policy("stderr_capture_policy", data.get("stderr_capture_policy"), ("stores_full_output",)))
    if not isinstance(data.get("timeout_policy"), dict):
        errors.append("timeout_policy must be an object")
    errors.extend(
        _validate_policy(
            "environment_policy",
            data.get("environment_policy"),
            (
                "ambient_environment_forwarded",
                "secrets_forwarded",
                "model_provider_keys_forwarded",
                "mcp_credentials_forwarded",
            ),
        )
    )
    errors.extend(_validate_policy("cwd_policy", data.get("cwd_policy"), ("cwd_escape_allowed",)))
    errors.extend(_validate_disabled_authority(data))
    errors.extend(_validate_commit_identity_and_byproducts(data))
    artifact_errors = data.get("errors")
    if not isinstance(artifact_errors, list) or not all(isinstance(item, str) for item in artifact_errors):
        errors.append("errors must be a list of strings")
    valid = data.get("valid")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    elif valid is True and artifact_errors:
        errors.append("errors must be empty when valid is true")
    elif valid is False and not artifact_errors:
        errors.append("errors must be non-empty when valid is false")
    digest = data.get("verification_execution_receipt_digest")
    if not _is_sha256_hex(digest):
        errors.append("verification_execution_receipt_digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(data, digest_key="verification_execution_receipt_digest"):
        errors.append("verification_execution_receipt_digest drift detected")
    return _dedupe_errors(errors)


def validate_verification_execution_receipt_against_plan_and_approval(
    receipt: Any, plan: Any, approval: Any
) -> list[str]:
    errors: list[str] = []
    if not isinstance(receipt, dict):
        return ["verification execution receipt artifact must be a JSON object"]
    if not isinstance(plan, dict):
        return ["referenced verification execution plan must be a JSON object"]
    if not isinstance(approval, dict):
        return ["referenced verification execution approval must be a JSON object"]
    plan_errors = validate_verification_execution_plan_artifact(plan)
    if plan_errors:
        return [f"referenced verification execution plan invalid: {error}" for error in plan_errors]
    approval_errors = validate_verification_execution_approval_artifact(approval)
    if approval_errors:
        return [f"referenced verification execution approval invalid: {error}" for error in approval_errors]
    binding_errors = validate_verification_execution_approval_against_plan(approval, plan)
    if binding_errors:
        return [f"referenced verification execution approval not bound to plan: {error}" for error in binding_errors]
    if receipt.get("plan_digest") != plan.get("verification_execution_plan_digest"):
        errors.append("plan_digest does not match referenced plan")
    if receipt.get("approval_digest") != approval.get("verification_execution_approval_digest"):
        errors.append("approval_digest does not match referenced approval")
    if receipt.get("target_profile") != plan.get("target_profile"):
        errors.append("target_profile does not match referenced plan")
    if receipt.get("verification_profile") != plan.get("verification_profile"):
        errors.append("verification_profile does not match referenced plan")
    if receipt.get("target_repo") != plan.get("target_repo"):
        errors.append("target_repo does not match referenced plan")
    if receipt.get("artifact_root") != plan.get("artifact_root"):
        errors.append("artifact_root does not match referenced plan")
    approved_profiles = set(_string_list(approval.get("approved_command_profiles")))
    receipt_profiles = set(_string_list(receipt.get("approved_command_profiles")))
    if not receipt_profiles.issubset(approved_profiles):
        errors.append("approved_command_profiles must be a subset of the referenced approval")
    approved_steps = set(_string_list(approval.get("approved_step_ids")))
    for field in ("executed_steps", "skipped_steps", "process_results"):
        records = receipt.get(field)
        if not isinstance(records, list):
            continue
        extras = sorted(
            step_id
            for item in records
            if isinstance(item, dict)
            for step_id in (item.get("step_id"),)
            if isinstance(step_id, str) and step_id not in approved_steps
        )
        if extras:
            errors.append(f"{field}.step_id values must be approved by the referenced approval")
    return _dedupe_errors(errors)


def validate_verification_execution_receipt_file(path: Path) -> list[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [f"verification execution receipt file could not be read: {exc}"]
    try:
        data = json_lib.loads(raw)
    except json_lib.JSONDecodeError as exc:
        return [f"verification execution receipt file is not valid JSON: {exc}"]
    return validate_verification_execution_receipt_artifact(data)
