from __future__ import annotations

import hashlib
import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.config_schema import digest_jsonable
from builder_ii.setup_receipt import validate_setup_receipt_artifact
from builder_ii.setup_rollback import validate_setup_rollback_snapshot_artifact
from builder_ii.setup_rollback_receipt import finalize_setup_rollback_receipt, write_setup_rollback_receipt


class SetupRollbackError(ValueError):
    def __init__(self, message: str, receipt: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.receipt = receipt


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _digest_path(path: Path) -> str:
    if path.is_symlink():
        return _sha256_bytes(f"symlink:{path.readlink()}".encode())
    if path.is_file():
        return _sha256_bytes(path.read_bytes())
    if path.is_dir():
        return _sha256_bytes(f"directory:{path}".encode())
    return _sha256_bytes(f"missing:{path}".encode())


def _base_receipt(setup_receipt: dict[str, Any], snapshot: dict[str, Any], approve_digest: str) -> dict[str, Any]:
    ts = datetime.now(timezone.utc).isoformat()
    basis = {"setup_receipt": setup_receipt.get("receipt_digest"), "snapshot": snapshot.get("snapshot_digest"), "approval": approve_digest, "ts": ts}
    return {
        "rollback_receipt_id": digest_jsonable(basis, digest_key="rollback_receipt_id"),
        "timestamp": ts,
        "setup_receipt_digest": str(setup_receipt.get("receipt_digest", "")),
        "setup_plan_digest": str(setup_receipt.get("setup_plan_digest", "")),
        "overlay_plan_digest": str(setup_receipt.get("overlay_plan_digest", "")),
        "rollback_snapshot_digest": str(snapshot.get("snapshot_digest", "")),
        "approval_digest": approve_digest,
        "approval_mode": "explicit_digest_bound_cli_flag",
        "operation_attempted": "setup_rollback",
        "rollback_result": "pending",
        "deleted_paths": [],
        "restored_paths": [],
        "skipped_paths": [],
        "denied_paths": [],
        "operations": [],
    }


def _path_error(path_text: str) -> str | None:
    path = Path(path_text)
    if not path.is_absolute() or any(part == ".." for part in path.parts):
        return "path traversal or non-absolute path denied"
    if path.is_symlink() or path.parent.is_symlink():
        return "unsafe symlink target or symlink parent"
    return None


def _preflight_state(path: Path, state: dict[str, Any]) -> str | None:
    prior = state.get("prior_existence_state")
    if prior == "missing":
        if path.exists() and path.is_dir() and any(path.iterdir()):
            return "prior state missing but target is a non-empty directory"
        if path.exists() and not path.is_file() and not path.is_dir():
            return "prior state missing but target is neither file nor directory"
        return None
    if prior == "directory":
        if path.exists() and not path.is_dir():
            return "prior state directory but target exists and is not a directory"
        return None
    if prior == "file":
        if state.get("raw_content_included") is not True or not isinstance(state.get("raw_prior_content"), str):
            return "manual_restore_required: raw prior content is unavailable"
        return None
    if prior == "symlink":
        return "manual_restore_required: prior symlink is unsupported"
    return "manual_restore_required: prior state is unsupported"


def execute_setup_rollback(setup_receipt: dict[str, Any], snapshot: dict[str, Any], *, approve_digest: str, receipt_output: Path | None = None) -> dict[str, Any]:
    errors = validate_setup_receipt_artifact(setup_receipt) + validate_setup_rollback_snapshot_artifact(snapshot)
    receipt = _base_receipt(setup_receipt if isinstance(setup_receipt, dict) else {}, snapshot if isinstance(snapshot, dict) else {}, approve_digest if isinstance(approve_digest, str) else "")
    if setup_receipt.get("setup_apply_executed") is not True:
        errors.append("setup receipt setup_apply_executed must be true")
    if setup_receipt.get("rollback_executed") is not False:
        errors.append("setup receipt rollback_executed must be false")
    if setup_receipt.get("operation_attempted") != "setup_apply":
        errors.append("setup receipt operation_attempted must be setup_apply")
    if setup_receipt.get("operation_result") != "applied":
        errors.append("setup receipt operation_result must be applied")
    if approve_digest != setup_receipt.get("receipt_digest"):
        errors.append("approve digest does not match setup receipt digest")
    if setup_receipt.get("setup_plan_digest") != snapshot.get("setup_plan_digest"):
        errors.append("receipt/snapshot setup plan digest mismatch")
    if setup_receipt.get("overlay_plan_digest") != snapshot.get("overlay_plan_digest"):
        errors.append("receipt/snapshot overlay plan digest mismatch")
    if setup_receipt.get("rollback_snapshot_digest") != snapshot.get("snapshot_digest"):
        errors.append("setup receipt rollback snapshot digest does not match supplied snapshot digest")

    changed = set(setup_receipt.get("changed_paths", []) if isinstance(setup_receipt.get("changed_paths"), list) else [])
    skipped = set(setup_receipt.get("skipped_paths", []) if isinstance(setup_receipt.get("skipped_paths"), list) else [])
    states = {state.get("target_path"): state for state in snapshot.get("target_path_states", []) if isinstance(state, dict)}
    covered = set(states)
    if not changed <= covered:
        errors.append("changed path not covered by snapshot")
    if not skipped <= covered:
        errors.append("skipped path not covered by snapshot")
    if errors:
        receipt["rollback_result"] = "denied"
        receipt["denied_paths"] = sorted(changed - covered) or ["<artifact>"]
        receipt["operations"] = [{"target_path": path, "operation_type": "preflight", "result": "denied", "reason": "; ".join(errors), "before_digest": "", "after_digest": ""} for path in receipt["denied_paths"]]
        finalized = finalize_setup_rollback_receipt(receipt)
        if receipt_output is not None:
            write_setup_rollback_receipt(finalized, receipt_output)
        raise SetupRollbackError("setup rollback denied: " + "; ".join(errors), finalized)

    plans: list[tuple[Path, dict[str, Any], str]] = []
    for path_text in sorted(changed):
        reason = _path_error(path_text)
        state = states[path_text]
        path = Path(path_text)
        if reason is None:
            reason = _preflight_state(path, state)
        op = {"target_path": path_text, "operation_type": "rollback", "before_digest": _digest_path(path), "after_digest": _digest_path(path), "result": "pending", "reason": ""}
        if reason is not None:
            op["result"] = "denied"
            op["reason"] = reason
            receipt["denied_paths"].append(path_text)
        receipt["operations"].append(op)
        plans.append((path, state, str(state.get("prior_existence_state"))))
    for path_text in sorted(skipped):
        receipt["skipped_paths"].append(path_text)
        receipt["operations"].append({"target_path": path_text, "operation_type": "no-op", "before_digest": _digest_path(Path(path_text)), "after_digest": _digest_path(Path(path_text)), "result": "skipped_no_op", "reason": "setup apply skipped this path"})
    if receipt["denied_paths"]:
        receipt["rollback_result"] = "denied"
        receipt["deleted_paths"] = []
        receipt["restored_paths"] = []
        receipt["denied_paths"] = sorted(set(receipt["denied_paths"]))
        finalized = finalize_setup_rollback_receipt(receipt)
        if receipt_output is not None:
            write_setup_rollback_receipt(finalized, receipt_output)
        raise SetupRollbackError("setup rollback denied for one or more changed paths", finalized)

    try:
        for idx, (path, state, prior) in enumerate(plans):
            if prior == "missing":
                if path.is_file():
                    path.unlink()
                elif path.is_dir():
                    path.rmdir()
                receipt["deleted_paths"].append(str(path))
            elif prior == "directory":
                path.mkdir(parents=True, exist_ok=True)
                receipt["restored_paths"].append(str(path))
            elif prior == "file":
                raw = str(state["raw_prior_content"]).encode("utf-8")
                if _sha256_bytes(raw) != state.get("prior_content_digest"):
                    raise SetupRollbackError("raw prior content digest mismatch")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(raw)
                receipt["restored_paths"].append(str(path))
            receipt["operations"][idx]["after_digest"] = _digest_path(path)
            receipt["operations"][idx]["result"] = "rolled_back"
        receipt["rollback_result"] = "rolled_back"
        finalized = finalize_setup_rollback_receipt(receipt)
        if receipt_output is not None:
            write_setup_rollback_receipt(finalized, receipt_output)
        return finalized
    except Exception as exc:
        if isinstance(exc, SetupRollbackError):
            raise
        receipt["rollback_result"] = "failed"
        receipt["operations"].append({"target_path": "<rollback>", "operation_type": "failure", "result": "failed", "reason": str(exc), "before_digest": "", "after_digest": ""})
        finalized = finalize_setup_rollback_receipt(receipt)
        if receipt_output is not None:
            write_setup_rollback_receipt(finalized, receipt_output)
        raise SetupRollbackError("setup rollback failed: " + str(exc), finalized) from exc
