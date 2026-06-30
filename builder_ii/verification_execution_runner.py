from __future__ import annotations

import hashlib
import json as json_lib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest
from builder_ii.verification_execution_approval import (
    validate_verification_execution_approval_against_plan,
    validate_verification_execution_approval_artifact,
)
from builder_ii.verification_execution_plan import validate_verification_execution_plan_artifact
from builder_ii.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    finalize_verification_execution_receipt,
    validate_verification_execution_receipt_against_plan_and_approval,
    validate_verification_execution_receipt_artifact,
    write_verification_execution_receipt,
)


STDOUT_STDERR_CAPTURE_BYTES = 65536
GIT_STATUS_TIMEOUT_SECONDS = 10
FORBIDDEN_ARG_TOKENS = ("&&", "||", ";", "|", "`", "$(", "\n", "\r", ">", "<")
SAFE_ENV_KEYS = (
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "HOME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "USER",
    "TZ",
    "SYSTEMROOT",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "SYSTEMDRIVE",
    "TERM",
)


@dataclass(frozen=True)
class BoundedCommandProfile:
    profile: str
    step_id: str
    command_profile_ref: str
    argv: tuple[str, ...]
    timeout_seconds: int


SUPPORTED_COMMAND_PROFILES: dict[str, BoundedCommandProfile] = {
    "platform_status": BoundedCommandProfile(
        profile="platform_status",
        step_id="platform_status",
        command_profile_ref="verification_profiles.builder_full.platform_status",
        argv=(sys.executable, "-m", "builder_ii.verification_runner_entrypoints", "platform-status"),
        timeout_seconds=30,
    )
}


def _read_json_object(path: Path) -> Any:
    return json_lib.loads(path.read_text(encoding="utf-8"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _excerpt(value: str, limit: int = STDOUT_STDERR_CAPTURE_BYTES) -> tuple[str, bool]:
    encoded = value.encode("utf-8")
    if len(encoded) <= limit:
        return value, False
    clipped = encoded[:limit].decode("utf-8", errors="replace")
    return clipped, True


def _path_is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_output_path(*, output: Path, target_repo: Path, artifact_root: Path) -> list[str]:
    errors: list[str] = []
    resolved_output = output.expanduser().resolve()
    if resolved_output.exists() and resolved_output.is_dir():
        errors.append("output path must be a file path, not a directory")
    if not _path_is_relative_to(resolved_output, artifact_root) or resolved_output == artifact_root:
        errors.append("output path must be under the configured artifact root inside target_repo")
    if not _path_is_relative_to(artifact_root, target_repo):
        errors.append("artifact_root must resolve inside target_repo")
    return errors


def _minimal_env(target_repo: Path) -> dict[str, str]:
    env = {key: value for key, value in os.environ.items() if key in SAFE_ENV_KEYS}
    env.update(
        {
            "CORE_REPO_PATH": ".",
            "PYTHONUNBUFFERED": "1",
            "PYTHONPATH": str(target_repo),
        }
    )
    return env


def _validate_fixed_profile(profile: BoundedCommandProfile) -> list[str]:
    errors: list[str] = []
    if profile.profile != "platform_status":
        errors.append("B1.3B initially supports only profile=platform_status")
    if profile.step_id != "platform_status":
        errors.append("B1.3B initially supports only step_id=platform_status")
    if profile.command_profile_ref != "verification_profiles.builder_full.platform_status":
        errors.append("profile command_profile_ref must remain verification_profiles.builder_full.platform_status")
    if not profile.argv or not all(isinstance(item, str) and item for item in profile.argv):
        errors.append("fixed argv must be a non-empty tuple of non-empty strings")
        return errors
    for index, item in enumerate(profile.argv):
        lowered = item.lower()
        for token in FORBIDDEN_ARG_TOKENS:
            if token in lowered:
                errors.append(f"fixed argv[{index}] contains forbidden shell token {token!r}")
    if any(item in {"-c", "--command"} for item in profile.argv):
        errors.append("fixed argv must not use python -c or command-string forms")
    if profile.timeout_seconds <= 0:
        errors.append("timeout_seconds must be positive")
    return errors


def _git_state(target_repo: Path, label: str) -> dict[str, Any]:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain=v1"],
            cwd=target_repo,
            env=_minimal_env(target_repo),
            capture_output=True,
            text=True,
            timeout=GIT_STATUS_TIMEOUT_SECONDS,
            shell=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "state_label": label,
            "captured": False,
            "error": "git status timed out",
        }
    except OSError as exc:
        return {
            "state_label": label,
            "captured": False,
            "error": f"git status failed: {exc}",
        }
    return {
        "state_label": label,
        "captured": result.returncode == 0,
        "returncode": result.returncode,
        "porcelain_sha256": _sha256_text(result.stdout),
        "porcelain_lines": result.stdout.splitlines(),
        "stderr_sha256": _sha256_text(result.stderr),
    }


def _state_fingerprint(state: dict[str, Any]) -> tuple[Any, ...]:
    return (
        state.get("captured"),
        state.get("returncode"),
        state.get("porcelain_sha256"),
        tuple(state.get("porcelain_lines") or []),
    )


def _process_result_from_completed(
    *,
    profile: BoundedCommandProfile,
    completed: subprocess.CompletedProcess[str],
    timed_out: bool = False,
) -> dict[str, Any]:
    stdout_excerpt, stdout_truncated = _excerpt(completed.stdout or "")
    stderr_excerpt, stderr_truncated = _excerpt(completed.stderr or "")
    status = "success" if completed.returncode == 0 else "non_zero_exit"
    if timed_out:
        status = "timeout"
    return {
        "step_id": profile.step_id,
        "profile": profile.profile,
        "command_profile_ref": profile.command_profile_ref,
        "status": status,
        "returncode": completed.returncode,
        "timeout_seconds": profile.timeout_seconds,
        "shell": False,
        "argv_digest": _sha256_text(json_lib.dumps(list(profile.argv), sort_keys=True)),
        "stdout_sha256": _sha256_text(completed.stdout or ""),
        "stderr_sha256": _sha256_text(completed.stderr or ""),
        "stdout_excerpt": stdout_excerpt,
        "stderr_excerpt": stderr_excerpt,
        "stdout_truncated": stdout_truncated,
        "stderr_truncated": stderr_truncated,
    }


def _blocked_process_result(*, profile: str, step_id: str, reason: str) -> dict[str, Any]:
    return {
        "step_id": step_id,
        "profile": profile,
        "status": "blocked_before_execution",
        "reason": reason,
        "shell": False,
    }


def _maybe_write_blocked_receipt(
    *,
    receipt: dict[str, Any],
    output: Path,
    target_repo: Path | None,
    artifact_root: Path | None,
) -> None:
    if target_repo is None or artifact_root is None:
        return
    if _validate_output_path(output=output, target_repo=target_repo, artifact_root=artifact_root):
        return
    write_verification_execution_receipt(receipt, output)


def _receipt_for_block(
    *,
    plan: dict[str, Any],
    approval: dict[str, Any],
    plan_path: Path,
    approval_path: Path,
    output: Path,
    target_repo: Path | None,
    artifact_root: Path | None,
    requested_profile: str,
    errors: list[str],
) -> dict[str, Any]:
    profile = SUPPORTED_COMMAND_PROFILES.get(requested_profile)
    process_result = _blocked_process_result(
        profile=requested_profile,
        step_id=profile.step_id if profile else requested_profile,
        reason="; ".join(errors),
    )
    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        receipt_status="BLOCKED_BEFORE_EXECUTION",
        executed_steps=[],
        skipped_steps=[
            {
                "step_id": process_result["step_id"],
                "status": "blocked_before_execution",
                "reason": process_result["reason"],
            }
        ],
        process_results=[process_result],
        preflight_git_state={"state_label": "preflight", "captured": False, "errors": errors},
        postflight_git_state={"state_label": "postflight", "captured": False, "errors": errors},
        workspace_mutation_detected=False,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    )
    receipt["errors"] = list(dict.fromkeys(list(receipt.get("errors") or []) + errors))
    receipt["valid"] = False
    receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")
    _maybe_write_blocked_receipt(
        receipt=receipt,
        output=output,
        target_repo=target_repo,
        artifact_root=artifact_root,
    )
    return receipt


def run_approved_verification(
    *,
    plan_path: Path,
    approval_path: Path,
    output: Path,
    requested_profile: str = "platform_status",
) -> dict[str, Any]:
    plan_data = _read_json_object(plan_path)
    approval_data = _read_json_object(approval_path)
    plan = plan_data if isinstance(plan_data, dict) else {}
    approval = approval_data if isinstance(approval_data, dict) else {}
    profile = SUPPORTED_COMMAND_PROFILES.get(requested_profile)
    errors: list[str] = []

    errors.extend(validate_verification_execution_plan_artifact(plan_data))
    errors.extend(validate_verification_execution_approval_artifact(approval_data))
    if isinstance(plan_data, dict) and plan_data.get("valid") is not True:
        errors.append("referenced verification execution plan must be valid (valid=true)")
    if isinstance(approval_data, dict) and approval_data.get("valid") is not True:
        errors.append("referenced verification execution approval must be valid (valid=true)")
    if not errors:
        errors.extend(validate_verification_execution_approval_against_plan(approval, plan))
    if profile is None:
        errors.append("B1.3B initially supports only profile=platform_status")
    else:
        errors.extend(_validate_fixed_profile(profile))

    target_repo = Path(str(plan.get("target_repo", "."))).expanduser().resolve()
    artifact_root_value = str(plan.get("artifact_root", ".builder/verification"))
    artifact_root_path = Path(artifact_root_value).expanduser()
    artifact_root = artifact_root_path.resolve() if artifact_root_path.is_absolute() else (target_repo / artifact_root_path).resolve()

    if not target_repo.exists() or not target_repo.is_dir():
        errors.append("target_repo must exist and be a directory")
    if not _path_is_relative_to(artifact_root, target_repo):
        errors.append("artifact_root must resolve inside target_repo")
    errors.extend(_validate_output_path(output=output, target_repo=target_repo, artifact_root=artifact_root))

    approved_profiles = approval.get("approved_command_profiles", [])
    approved_steps = approval.get("approved_step_ids", [])
    if profile is not None:
        if not isinstance(approved_profiles, list) or profile.profile not in approved_profiles:
            errors.append("requested command profile is not approved by approval artifact")
        if not isinstance(approved_steps, list) or profile.step_id not in approved_steps:
            errors.append("requested step id is not approved by approval artifact")

    if errors or profile is None:
        return _receipt_for_block(
            plan=plan,
            approval=approval,
            plan_path=plan_path,
            approval_path=approval_path,
            output=output,
            target_repo=target_repo,
            artifact_root=artifact_root,
            requested_profile=requested_profile,
            errors=list(dict.fromkeys(errors)),
        )

    preflight = _git_state(target_repo, "preflight")
    if not preflight.get("captured"):
        return _receipt_for_block(
            plan=plan,
            approval=approval,
            plan_path=plan_path,
            approval_path=approval_path,
            output=output,
            target_repo=target_repo,
            artifact_root=artifact_root,
            requested_profile=requested_profile,
            errors=["git preflight state could not be captured"],
        )

    try:
        completed = subprocess.run(
            list(profile.argv),
            cwd=target_repo,
            env=_minimal_env(target_repo),
            capture_output=True,
            text=True,
            timeout=profile.timeout_seconds,
            shell=False,
        )
        process_result = _process_result_from_completed(profile=profile, completed=completed)
    except subprocess.TimeoutExpired as exc:
        completed = subprocess.CompletedProcess(
            args=list(profile.argv),
            returncode=124,
            stdout=exc.stdout if isinstance(exc.stdout, str) else "",
            stderr=exc.stderr if isinstance(exc.stderr, str) else "verification command timed out",
        )
        process_result = _process_result_from_completed(profile=profile, completed=completed, timed_out=True)

    postflight = _git_state(target_repo, "postflight")
    workspace_mutation_detected = _state_fingerprint(preflight) != _state_fingerprint(postflight)
    receipt_status = "EXECUTED" if process_result["status"] == "success" else "FAILED"
    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        receipt_status=receipt_status,
        executed_steps=[
            {
                "step_id": profile.step_id,
                "status": process_result["status"],
                "profile": profile.profile,
            }
        ],
        skipped_steps=[],
        process_results=[process_result],
        preflight_git_state=preflight,
        postflight_git_state=postflight,
        workspace_mutation_detected=workspace_mutation_detected,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    )
    if workspace_mutation_detected:
        receipt["errors"] = list(dict.fromkeys(list(receipt.get("errors") or []) + ["workspace mutation detected"]))
        receipt["valid"] = False
        receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")

    validation_errors = validate_verification_execution_receipt_artifact(receipt)
    validation_errors.extend(validate_verification_execution_receipt_against_plan_and_approval(receipt, plan, approval))
    if validation_errors:
        receipt["errors"] = list(dict.fromkeys(list(receipt.get("errors") or []) + validation_errors))
        receipt["valid"] = False
        receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")

    write_verification_execution_receipt(receipt, output)
    return receipt
