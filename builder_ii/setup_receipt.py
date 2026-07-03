from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.config_schema import CAPABILITY_DEFAULTS, attach_digest, digest_jsonable

SETUP_RECEIPT_KIND = "builder_ii.setup_apply_receipt"
SETUP_RECEIPT_SCHEMA_VERSION = 1


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def dumps_setup_receipt(receipt: dict[str, Any]) -> str:
    return json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n"


def write_setup_receipt(receipt: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_setup_receipt(receipt), encoding="utf-8")


def finalize_setup_receipt(receipt: dict[str, Any]) -> dict[str, Any]:
    receipt.setdefault("kind", SETUP_RECEIPT_KIND)
    receipt.setdefault("schema_version", SETUP_RECEIPT_SCHEMA_VERSION)
    receipt.setdefault("artifact_is_authority", False)
    receipt.setdefault("setup_apply_executed", True)
    receipt.setdefault("rollback_executed", False)
    receipt.setdefault("runtime_execution", "disabled")
    receipt.setdefault("model_execution", "disabled")
    receipt.setdefault("shell_execution", "disabled")
    receipt.setdefault("subprocess_execution", "disabled")
    receipt.setdefault("goose_runtime", "disabled")
    receipt.setdefault("deepagents_runtime", "disabled")
    receipt.setdefault("mcp_tool_invocation", "disabled")
    receipt.setdefault("patch_authority", "disabled")
    receipt.setdefault(
        "governance",
        {
            "artifact_is_authority": False,
            **CAPABILITY_DEFAULTS,
            "setup_apply": "enabled_digest_bound_explicit_approval_only",
            "setup_rollback_execution": "disabled",
        },
    )
    return attach_digest(receipt, digest_key="receipt_digest")


def validate_setup_receipt_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["setup receipt artifact must be a JSON object"]
    if data.get("kind") != SETUP_RECEIPT_KIND:
        errors.append(f"kind must be {SETUP_RECEIPT_KIND}")
    if data.get("schema_version") != SETUP_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {SETUP_RECEIPT_SCHEMA_VERSION}")
    for field in (
        "setup_plan_digest",
        "overlay_plan_digest",
        "rollback_snapshot_digest",
        "approval_digest",
        "receipt_id",
    ):
        if not _is_sha256(data.get(field)):
            errors.append(f"{field} must be a SHA-256 hex string")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")
    if data.get("setup_apply_executed") is not True:
        errors.append("setup_apply_executed must be true")
    if data.get("rollback_executed") is not False:
        errors.append("rollback_executed must be false or NOT_AUTHORIZED")
    for disabled in (
        "runtime_execution",
        "model_execution",
        "shell_execution",
        "subprocess_execution",
        "goose_runtime",
        "deepagents_runtime",
        "mcp_tool_invocation",
        "patch_authority",
    ):
        if data.get(disabled) != "disabled":
            errors.append(f"{disabled} must be disabled")
    for list_field in ("changed_paths", "skipped_paths", "denied_paths", "operations"):
        if not isinstance(data.get(list_field), list):
            errors.append(f"{list_field} must be a list")
    for op_idx, op in enumerate(data.get("operations", []) if isinstance(data.get("operations"), list) else []):
        if not isinstance(op, dict):
            errors.append(f"operations[{op_idx}] must be an object")
            continue
        if not isinstance(op.get("redacted_preview"), str):
            errors.append(f"operations[{op_idx}].redacted_preview must be a string")
        if any(marker in op.get("redacted_preview", "").lower() for marker in ("supersecret", "raw_secret")):
            errors.append(f"operations[{op_idx}].redacted_preview contains unredacted secret-like content")
    digest = data.get("receipt_digest")
    if not _is_sha256(digest):
        errors.append("receipt_digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(data, digest_key="receipt_digest"):
        errors.append("receipt_digest does not match canonical receipt payload")
    return errors


def validate_setup_receipt_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_setup_receipt_artifact(data)
