from __future__ import annotations

import datetime
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable


ONBOARDING_INTENT_KIND = "builder_ii.onboarding_intent_report"
ONBOARDING_INTENT_SCHEMA_VERSION = 1

DISABLED_AUTHORITY: dict[str, str] = {
    "runtime_execution": "disabled",
    "model_execution": "disabled",
    "shell_execution": "disabled",
    "subprocess_execution": "disabled",
    "goose_runtime": "disabled",
    "deepagents_runtime": "disabled",
    "mcp_tool_invocation": "disabled",
    "patch_authority": "disabled",
    "b1_verification_execution": "disabled",
    "b2_patch_authority": "disabled",
    "autonomous_writes": "disabled",
}

FORBIDDEN_COMMAND_PATTERNS = [
    ";",
    "&&",
    "||",
    "|",
    "`",
    "$(",
    "\n",
    "\r",
    ">",
    "<",
    "&",
]

FORBIDDEN_RUNTIME_WORDS = [
    "bash",
    "sh",
    "zsh",
    "python",
    "python3",
    "goose",
    "model",
    "mcp",
    "deepagents",
    "deepagent",
    "git",
    "patch",
]

FORBIDDEN_SUBSTRINGS = [
    "eval(",
    "exec(",
    "goose run",
    "goose start",
    "model execution",
    "patch authority",
]


def finalize_onboarding_intent_report(
    *,
    setup_plan_path: str,
    setup_plan_digest: str,
    setup_overlay_path: str,
    overlay_plan_digest: str,
    rollback_snapshot_path: str,
    rollback_snapshot_digest: str,
    onboarding_mode: str,
    apply_command: str,
    validate_receipt_command: str,
    rollback_command: str,
    validate_rollback_receipt_command: str,
    selected_summary: dict[str, Any] | None = None,
    setup_apply_executed: bool = False,
    rollback_executed: bool = False,
    generated_at: str | None = None,
) -> dict[str, Any]:
    if generated_at is None:
        generated_at = datetime.datetime.now(datetime.timezone.utc).isoformat()

    report: dict[str, Any] = {
        "kind": ONBOARDING_INTENT_KIND,
        "schema_version": ONBOARDING_INTENT_SCHEMA_VERSION,
        "generated_at": generated_at,
        "setup_plan_path": setup_plan_path,
        "setup_plan_digest": setup_plan_digest,
        "setup_overlay_path": setup_overlay_path,
        "overlay_plan_digest": overlay_plan_digest,
        "rollback_snapshot_path": rollback_snapshot_path,
        "rollback_snapshot_digest": rollback_snapshot_digest,
        "onboarding_mode": onboarding_mode,
        "planned_only": True,
        "artifact_is_authority": False,
        "setup_apply_executed": setup_apply_executed,
        "rollback_executed": rollback_executed,
        "apply_command": apply_command,
        "validate_receipt_command": validate_receipt_command,
        "rollback_command": rollback_command,
        "validate_rollback_receipt_command": validate_rollback_receipt_command,
        "selected_summary": selected_summary or {},
        "disabled_authority": dict(DISABLED_AUTHORITY),
    }
    return attach_digest(report, digest_key="onboarding_intent_digest")


def dumps_onboarding_intent_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"


def write_onboarding_intent_report(report: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_onboarding_intent_report(report), encoding="utf-8")


def _is_sha256_hex(val: Any) -> bool:
    return isinstance(val, str) and len(val) == 64 and bool(re.fullmatch(r"[0-9a-f]{64}", val))


def _check_command_string(cmd: Any, field_name: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(cmd, str) or not cmd.strip():
        return [f"{field_name} must be a non-empty command string"]
    
    first_token = cmd.strip().split()[0]
    if not first_token.endswith("builder-setup"):
        errors.append(f"{field_name} must reference only governed builder-setup commands")

    clean_cmd = cmd.replace("<setup_receipt_digest>", "PLACEHOLDER").replace("<overlay_plan_digest>", "PLACEHOLDER")

    for forbidden in FORBIDDEN_COMMAND_PATTERNS:
        if forbidden in clean_cmd:
            errors.append(f"{field_name} contains forbidden command pattern: {repr(forbidden)}")

    for token in clean_cmd.split():
        basename = token.replace("\\", "/").split("/")[-1]
        for candidate in (token, basename):
            low = candidate.lower()
            if low in FORBIDDEN_RUNTIME_WORDS or (
                low.startswith("python")
                and not low.endswith(".json")
                and not low.endswith(".yaml")
                and "lab" not in low
            ):
                errors.append(f"{field_name} contains unmanaged shell/runtime/tool language: {candidate}")
                break

    for sub in FORBIDDEN_SUBSTRINGS:
        if sub.lower() in cmd.lower():
            errors.append(f"{field_name} contains forbidden command pattern: {repr(sub)}")

    return errors


def validate_onboarding_intent_report_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["onboarding intent report must be a JSON object"]
    if data.get("kind") != ONBOARDING_INTENT_KIND:
        errors.append(f"kind must be {ONBOARDING_INTENT_KIND}")
    if data.get("schema_version") != ONBOARDING_INTENT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ONBOARDING_INTENT_SCHEMA_VERSION}")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if data.get("planned_only") is not True:
        errors.append("planned_only must be true")
    if not isinstance(data.get("setup_apply_executed"), bool):
        errors.append("setup_apply_executed must be a boolean")
    if not isinstance(data.get("rollback_executed"), bool):
        errors.append("rollback_executed must be a boolean")
    if data.get("onboarding_mode") not in ("init", "wizard"):
        errors.append("onboarding_mode must be 'init' or 'wizard'")

    for digest_field in (
        "setup_plan_digest",
        "overlay_plan_digest",
        "rollback_snapshot_digest",
        "onboarding_intent_digest",
    ):
        if not _is_sha256_hex(data.get(digest_field)):
            errors.append(f"{digest_field} must be a valid SHA-256 hex string")

    digest = data.get("onboarding_intent_digest")
    if _is_sha256_hex(digest):
        expected = digest_jsonable(data, digest_key="onboarding_intent_digest")
        if digest != expected:
            errors.append("onboarding_intent_digest does not match canonical schema payload")

    disabled_auth = data.get("disabled_authority")
    if not isinstance(disabled_auth, dict):
        errors.append("disabled_authority must be an object")
    else:
        for k, expected_val in DISABLED_AUTHORITY.items():
            if disabled_auth.get(k) != expected_val:
                errors.append(f"disabled_authority.{k} must remain disabled")

    for cmd_field in (
        "apply_command",
        "validate_receipt_command",
        "rollback_command",
        "validate_rollback_receipt_command",
    ):
        errors.extend(_check_command_string(data.get(cmd_field), cmd_field))

    apply_cmd = data.get("apply_command")
    if isinstance(apply_cmd, str) and apply_cmd.strip():
        if not apply_cmd.strip().startswith("builder-setup apply "):
            errors.append("apply_command must begin with 'builder-setup apply '")
        overlay_digest = data.get("overlay_plan_digest")
        if isinstance(overlay_digest, str) and _is_sha256_hex(overlay_digest):
            if f"--approve-digest {overlay_digest}" not in apply_cmd:
                errors.append("apply_command must include --approve-digest matching overlay_plan_digest")
        elif "--approve-digest " not in apply_cmd:
            errors.append("apply_command must include --approve-digest")

    val_receipt_cmd = data.get("validate_receipt_command")
    if isinstance(val_receipt_cmd, str) and val_receipt_cmd.strip():
        if not val_receipt_cmd.strip().startswith("builder-setup validate-receipt "):
            errors.append("validate_receipt_command must begin with 'builder-setup validate-receipt '")

    rollback_cmd = data.get("rollback_command")
    if isinstance(rollback_cmd, str) and rollback_cmd.strip():
        if not rollback_cmd.strip().startswith("builder-setup rollback "):
            errors.append("rollback_command must begin with 'builder-setup rollback '")
        if "--approve-digest <setup_receipt_digest>" not in rollback_cmd and not re.search(r"--approve-digest\s+[0-9a-f]{64}", rollback_cmd):
            errors.append("rollback_command must include --approve-digest placeholder or setup receipt digest")

    val_rollback_cmd = data.get("validate_rollback_receipt_command")
    if isinstance(val_rollback_cmd, str) and val_rollback_cmd.strip():
        if not val_rollback_cmd.strip().startswith("builder-setup validate-rollback-receipt "):
            errors.append("validate_rollback_receipt_command must begin with 'builder-setup validate-rollback-receipt '")

    return errors


def validate_onboarding_intent_report_file(path: Path) -> list[str]:
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"failed to read onboarding intent artifact file: {exc}"]
    return validate_onboarding_intent_report_artifact(data)
