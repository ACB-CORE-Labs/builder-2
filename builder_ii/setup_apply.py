from __future__ import annotations

import hashlib
import json as json_lib
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from builder_ii.config_schema import digest_jsonable
from builder_ii.setup_overlay import validate_setup_overlay_plan_artifact
from builder_ii.setup_receipt import finalize_setup_receipt, write_setup_receipt
from builder_ii.setup_rollback import validate_setup_rollback_snapshot_artifact

SUPPORTED_OPERATIONS = {"create", "replace", "merge", "mkdir", "no-op"}
UNSAFE_CONFLICTS = {
    "unsafe_path_traversal",
    "outside_declared_setup_scopes",
    "symlink_path",
    "parent_symlink",
    "parent_not_directory",
    "directory_file_conflict",
    "file_directory_conflict",
}
SECRET_MARKERS = ("secret", "token", "api_key", "apikey", "password", "credential", "bearer")


class SetupApplyError(ValueError):
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


def _redact_node(node: Any) -> Any:
    if isinstance(node, dict):
        redacted: dict[Any, Any] = {}
        for key, value in node.items():
            if isinstance(key, str) and any(marker in key.lower() for marker in SECRET_MARKERS):
                redacted[key] = "<redacted>"
            else:
                redacted[key] = _redact_node(value)
        return redacted
    if isinstance(node, list):
        return [_redact_node(item) for item in node]
    return node


def _redact_lines(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if any(marker in lower for marker in SECRET_MARKERS):
            if "=" in line:
                lines.append(line.split("=", 1)[0].strip() + "=<redacted>")
            elif ":" in line:
                lines.append(line.split(":", 1)[0].strip() + ": <redacted>")
            else:
                lines.append("<redacted-secret-line>")
        else:
            lines.append(line)
    return "\n".join(lines)


def _redact(text: str, limit: int = 800) -> str:
    """Redact secret-ish content for previews/receipts.

    Marker matching is structural, not line-oriented: if `text` parses as YAML/JSON
    to a dict or list, every key matching SECRET_MARKERS has its *entire subtree*
    collapsed, so a nested `api_key: {value: sk-...}` cannot leak through an
    unmarked descendant line. Non-mapping content (e.g. `.env`-style `KEY=value`
    text, which is not valid YAML mapping syntax) falls back to the original
    line-oriented redaction.
    """
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        parsed = None
    if isinstance(parsed, (dict, list)) and parsed:
        out = yaml.safe_dump(_redact_node(parsed), sort_keys=False, default_flow_style=False, allow_unicode=True)
    else:
        out = _redact_lines(text)
    return out[:limit] + ("\n<truncated>" if len(out) > limit else "")


def _content_text(change: dict[str, Any]) -> str:
    meta = change.get("metadata")
    if isinstance(meta, (dict, list)) and meta:
        return json_lib.dumps(meta, indent=2, sort_keys=True) + "\n"
    return str(change.get("redacted_preview", ""))


def _merge_fragment_and_keys(change: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    metadata = change.get("metadata")
    if not isinstance(metadata, dict):
        return None, []
    fragment = metadata.get("merge_fragment")
    fragment = fragment if isinstance(fragment, dict) and fragment else None
    raw_keys = metadata.get("overlay_keys")
    keys = [key for key in raw_keys if isinstance(key, str) and key] if isinstance(raw_keys, list) else []
    return fragment, keys


def _has_dotted_path(node: Any, dotted_key: str) -> bool:
    current = node
    for part in dotted_key.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _merge_preflight_reasons(change: dict[str, Any], target: Path) -> list[str]:
    reasons: list[str] = []
    fragment, keys = _merge_fragment_and_keys(change)
    if fragment is None:
        reasons.append("merge requires metadata.merge_fragment to be a non-empty object")
    if not keys:
        reasons.append("merge requires metadata.overlay_keys to be a non-empty list of strings")
    if fragment is not None and keys:
        missing = [key for key in keys if not _has_dotted_path(fragment, key)]
        if missing:
            reasons.append("merge_fragment missing declared overlay_keys: " + ", ".join(sorted(missing)))
    if target.is_dir():
        reasons.append("merge target is a directory")
        return reasons
    if target.is_file():
        try:
            existing_text = target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            reasons.append("merge target is not valid UTF-8 text")
            return reasons
        try:
            existing = yaml.safe_load(existing_text) if existing_text.strip() else {}
        except yaml.YAMLError:
            # Never interpolate the parser exception: it may echo the offending
            # line, which can itself contain the operator's secret.
            reasons.append("merge target is not valid YAML")
            return reasons
        if existing is not None and not isinstance(existing, dict):
            reasons.append("merge target YAML root is not a mapping")
    return reasons


def _count_nested_keys(node: Any) -> int:
    if isinstance(node, dict):
        return sum(1 + _count_nested_keys(value) for value in node.values())
    if isinstance(node, list):
        return sum(_count_nested_keys(item) for item in node)
    return 0


def _count_preserved_keys(existing: dict[str, Any], fragment: dict[str, Any]) -> int:
    """Count keys in `existing` whose subtree the merge fragment does not touch."""
    total = 0
    for key, value in existing.items():
        if key in fragment:
            if isinstance(value, dict) and isinstance(fragment[key], dict):
                total += _count_preserved_keys(value, fragment[key])
            continue
        total += 1 + _count_nested_keys(value)
    return total


def _deep_merge(existing: dict[str, Any], fragment: dict[str, Any]) -> dict[str, Any]:
    """Merge `fragment` into a copy of `existing`, recursing only into shared dict keys.

    Every key/value in `existing` that `fragment` does not name is left untouched,
    including keys nested arbitrarily deep and keys whose name never appears in
    SECRET_MARKERS. Preservation here is structural (path-based), independent of
    the secret-redaction logic above.
    """
    merged = dict(existing)
    for key, value in fragment.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _merge_yaml_target(change: dict[str, Any], target: Path) -> tuple[str, bool, dict[str, Any]]:
    fragment, keys = _merge_fragment_and_keys(change)
    assert fragment is not None  # preflight already denied the change otherwise
    existing_text = target.read_text(encoding="utf-8") if target.is_file() else ""
    existing = yaml.safe_load(existing_text) if existing_text.strip() else {}
    if not isinstance(existing, dict):
        existing = {}
    merged = _deep_merge(existing, fragment)
    merged_text = yaml.safe_dump(merged, sort_keys=False, default_flow_style=False, allow_unicode=True)
    fields = {
        "merge_keys_written": sorted(keys),
        "merge_keys_preserved_count": _count_preserved_keys(existing, fragment),
    }
    return merged_text, merged_text == existing_text, fields


def _atomic_write_text(target: Path, text: str) -> None:
    fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp:
            tmp.write(text)
            tmp.flush()
            os.fsync(tmp.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def _inside(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_target(change: dict[str, Any], overlay: dict[str, Any], *, operation: str) -> list[str]:
    errors: list[str] = []
    target = Path(str(change.get("target_path", "")))
    if not target.is_absolute():
        errors.append("target path is not absolute")
    if any(part == ".." for part in target.parts):
        errors.append("target path contains traversal")
    if change.get("path_traversal_rejected") is True:
        errors.append("overlay rejected path traversal")
    if change.get("conflict_classification") in UNSAFE_CONFLICTS:
        errors.append(f"unsafe conflict: {change.get('conflict_classification')}")
    scopes = overlay.get("path_policy", {}).get("declared_setup_scopes", {})
    roots = [Path(str(value)).resolve(strict=False) for value in scopes.values() if isinstance(value, str) and value]
    resolved = target.resolve(strict=False)
    if not roots or not any(_inside(resolved, root) for root in roots):
        errors.append("target path outside declared setup scopes")
    builder_root = Path(str(overlay.get("builder_repo_canonical_path", ""))).resolve(strict=False)
    artifact_root = Path(str(overlay.get("artifact_root_canonical_path", ""))).resolve(strict=False)
    if (
        operation != "no-op"
        and builder_root
        and _inside(resolved, builder_root)
        and not _inside(resolved, artifact_root)
    ):
        errors.append("source repo mutation is disabled except declared artifact-root setup metadata")
    if target.is_symlink() or target.parent.is_symlink():
        errors.append("unsafe symlink target or parent")
    return errors


def _preflight_filesystem_conflicts(target: Path, *, operation: str) -> list[str]:
    errors: list[str] = []
    if operation == "no-op":
        return errors
    if target.parent.exists() and not target.parent.is_dir():
        errors.append("target parent exists but is not a directory")
    if operation == "create" and target.exists():
        errors.append("create target already exists")
    if operation == "replace":
        if not target.exists():
            errors.append("replace target is missing")
        elif target.is_dir():
            errors.append("replace target is a directory")
    if operation == "mkdir" and target.exists() and not target.is_dir():
        errors.append("mkdir target exists and is not a directory")
    return errors


def _base_receipt(
    overlay: dict[str, Any],
    snapshot: dict[str, Any],
    approve_digest: str,
    approval_mode: str = "explicit_digest_bound_cli_flag",
) -> dict[str, Any]:
    basis = {
        "overlay": overlay.get("overlay_plan_digest"),
        "snapshot": snapshot.get("snapshot_digest"),
        "approval": approve_digest,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "receipt_id": digest_jsonable(basis, digest_key="receipt_id"),
        "timestamp": basis["ts"],
        "setup_plan_digest": overlay["setup_plan_ref"]["digest"],
        "overlay_plan_digest": overlay["overlay_plan_digest"],
        "rollback_snapshot_digest": snapshot["snapshot_digest"],
        "approval_digest": approve_digest,
        "approval_mode": approval_mode,
        "operation_attempted": "setup_apply",
        "operation_result": "pending",
        "changed_paths": [],
        "skipped_paths": [],
        "denied_paths": [],
        "operations": [],
    }


def apply_setup_overlay(
    overlay: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    approve_digest: str,
    receipt_output: Path | None = None,
    approval_mode: str = "explicit_digest_bound_cli_flag",
) -> dict[str, Any]:
    errors = validate_setup_overlay_plan_artifact(overlay) + validate_setup_rollback_snapshot_artifact(snapshot)
    if approve_digest != overlay.get("overlay_plan_digest"):
        errors.append("approve digest does not match overlay_plan_digest")
    if snapshot.get("overlay_plan_digest") != overlay.get("overlay_plan_digest"):
        errors.append("rollback snapshot overlay digest does not match overlay")
    if snapshot.get("setup_plan_digest") != overlay.get("setup_plan_ref", {}).get("digest"):
        errors.append("rollback snapshot setup plan digest does not match overlay setup plan digest")
    receipt = (
        _base_receipt(overlay, snapshot, approve_digest if isinstance(approve_digest, str) else "", approval_mode)
        if isinstance(overlay, dict) and isinstance(snapshot, dict) and overlay.get("setup_plan_ref")
        else None
    )
    if errors:
        if receipt is not None:
            receipt["operation_result"] = "denied"
            receipt["denied_paths"] = ["<artifact>" for _ in errors]
            receipt["operations"] = [
                {
                    "change_id": "artifact_validation",
                    "operation_type": "validate",
                    "result": "denied",
                    "reason": error,
                    "before_digest": "",
                    "after_digest": "",
                    "redacted_preview": "",
                }
                for error in errors
            ]
            finalized = finalize_setup_receipt(receipt)
            if receipt_output is not None:
                write_setup_receipt(finalized, receipt_output)
            raise SetupApplyError("setup apply denied: " + "; ".join(errors), finalized)
        raise SetupApplyError("setup apply denied: " + "; ".join(errors))

    snapshot_paths = set(snapshot.get("target_paths_covered", []))
    declared_paths = {change.get("target_path") for change in overlay.get("planned_changes", [])}
    if snapshot_paths != declared_paths:
        receipt["operation_result"] = "denied"
        receipt["denied_paths"] = sorted(str(path) for path in declared_paths ^ snapshot_paths)
        finalized = finalize_setup_receipt(receipt)
        if receipt_output is not None:
            write_setup_receipt(finalized, receipt_output)
        raise SetupApplyError(
            "setup apply denied: rollback snapshot target paths do not match declared changes", finalized
        )

    try:
        preflight: list[tuple[dict[str, Any], Path, str, str]] = []
        for change in overlay["planned_changes"]:
            target = Path(change["target_path"])
            operation = str(change["operation_type"])
            reasons = []
            if change.get("planned_only") is not True:
                reasons.append("change is not planned_only")
            reasons.extend(_safe_target(change, overlay, operation=operation))
            if operation not in SUPPORTED_OPERATIONS:
                reasons.append(f"unsupported operation: {operation}")
            else:
                reasons.extend(_preflight_filesystem_conflicts(target, operation=operation))
                if operation == "merge":
                    reasons.extend(_merge_preflight_reasons(change, target))
            if operation in {"replace", "merge"} and str(target) not in snapshot_paths:
                reasons.append(f"{operation} requires rollback snapshot coverage")
            before = _digest_path(target)
            text = _content_text(change)
            op_record = {
                "change_id": change["change_id"],
                "target_path": str(target),
                "operation_type": operation,
                "before_digest": before,
                "after_digest": before,
                "redacted_preview": _redact(text),
                "result": "pending",
                "reason": "",
            }
            if reasons:
                op_record["result"] = "denied"
                op_record["reason"] = "; ".join(reasons)
                receipt["denied_paths"].append(str(target))
                receipt["operations"].append(op_record)
            preflight.append((change, target, operation, text))
        if receipt["denied_paths"]:
            receipt["denied_paths"] = sorted(set(receipt["denied_paths"]))
            receipt["operation_result"] = "denied"
            finalized = finalize_setup_receipt(receipt)
            if receipt_output is not None:
                write_setup_receipt(finalized, receipt_output)
            raise SetupApplyError("setup apply denied for one or more planned changes", finalized)

        for change, target, operation, text in preflight:
            before = _digest_path(target)
            op_record = {
                "change_id": change["change_id"],
                "target_path": str(target),
                "operation_type": operation,
                "before_digest": before,
                "after_digest": before,
                "redacted_preview": _redact(text),
                "result": "pending",
                "reason": "",
            }
            if operation == "no-op":
                op_record["result"] = "skipped_no_op"
                receipt["skipped_paths"].append(str(target))
                receipt["operations"].append(op_record)
                continue
            if operation == "mkdir":
                target.mkdir(parents=True, exist_ok=True)
            elif operation == "merge":
                merged_text, unchanged, merge_fields = _merge_yaml_target(change, target)
                op_record["redacted_preview"] = _redact(merged_text)
                op_record.update(merge_fields)
                if unchanged:
                    op_record["result"] = "skipped_no_op"
                    op_record["reason"] = "merge output identical to existing content"
                    receipt["skipped_paths"].append(str(target))
                    receipt["operations"].append(op_record)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_text(target, merged_text)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                _atomic_write_text(target, text)
            op_record["after_digest"] = _digest_path(target)
            op_record["result"] = "changed"
            receipt["changed_paths"].append(str(target))
            receipt["operations"].append(op_record)
        receipt["changed_paths"] = sorted(set(receipt["changed_paths"]))
        receipt["skipped_paths"] = sorted(set(receipt["skipped_paths"]))
        receipt["denied_paths"] = sorted(set(receipt["denied_paths"]))
        receipt["operation_result"] = "denied" if receipt["denied_paths"] else "applied"
        finalized = finalize_setup_receipt(receipt)
        if receipt_output is not None:
            write_setup_receipt(finalized, receipt_output)
        if receipt["denied_paths"]:
            raise SetupApplyError("setup apply denied for one or more planned changes", finalized)
        return finalized
    except Exception as exc:
        if isinstance(exc, SetupApplyError):
            raise
        receipt["operation_result"] = "failed"
        receipt["operations"].append(
            {
                "change_id": "apply_failure",
                "operation_type": "failure",
                "result": "failed",
                "reason": str(exc),
                "before_digest": "",
                "after_digest": "",
                "redacted_preview": "",
            }
        )
        finalized = finalize_setup_receipt(receipt)
        if receipt_output is not None:
            write_setup_receipt(finalized, receipt_output)
        raise SetupApplyError("setup apply failed: " + str(exc), finalized) from exc
