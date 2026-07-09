from __future__ import annotations

import hashlib
import json as json_lib
import os
from pathlib import Path
from typing import Any

import yaml

from builder_ii.config_schema import CAPABILITY_DEFAULTS, attach_digest, digest_jsonable
from builder_ii.setup_overlay import (
    validate_setup_overlay_plan_artifact,
)

SETUP_ROLLBACK_SNAPSHOT_KIND = "builder_ii.setup_rollback_snapshot"
SETUP_ROLLBACK_SNAPSHOT_SCHEMA_VERSION = 1

_SECRET_MARKERS = ("secret", "token", "api_key", "apikey", "password", "credential", "bearer")

# See setup_apply._MERGE_PREVIEW_WITHHELD. Redaction recognises key NAMES, not credentials, so no
# preview of an operator-owned file is safe to embed in a governed artifact.
_MERGE_PREVIEW_WITHHELD = (
    "<withheld: a merge target may hold operator credentials under keys redaction cannot recognise; "
    "see prior_content_digest and prior_content_size_bytes>"
)
_EXISTENCE_STATES = {"missing", "file", "directory", "symlink", "unsupported"}
_STORAGE_POLICIES = {
    "not_stored_missing_file_marker_only",
    "not_stored_directory_marker_only",
    "not_stored_symlink_marker_only",
    "not_stored_unsupported_path_marker_only",
    "digest_size_redacted_preview_only_future_secure_snapshot_required",
}


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _redact_node(node: Any) -> tuple[Any, bool]:
    if isinstance(node, dict):
        result: dict[Any, Any] = {}
        redacted_any = False
        for key, value in node.items():
            if isinstance(key, str) and any(marker in key.lower() for marker in _SECRET_MARKERS):
                result[key] = "<redacted>"
                redacted_any = True
            else:
                child, child_redacted = _redact_node(value)
                result[key] = child
                redacted_any = redacted_any or child_redacted
        return result, redacted_any
    if isinstance(node, list):
        results = []
        redacted_any = False
        for item in node:
            child, child_redacted = _redact_node(item)
            results.append(child)
            redacted_any = redacted_any or child_redacted
        return results, redacted_any
    return node, False


def _redact_lines(text: str) -> tuple[str, bool]:
    redacted = False
    lines: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if any(marker in lower for marker in _SECRET_MARKERS):
            redacted = True
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                lines.append(f"{key}=<redacted>")
            elif ":" in line:
                key = line.split(":", 1)[0].strip()
                lines.append(f"{key}: <redacted>")
            else:
                lines.append("<redacted-secret-line>")
        else:
            lines.append(line)
    return "\n".join(lines), redacted


def _redact_text(text: str, *, limit: int = 800) -> tuple[str, str]:
    """Redact secret-ish prior content for the rollback snapshot preview.

    Same structural-vs-line-oriented split as `setup_apply._redact`: a parsed
    YAML/JSON mapping or list gets secret-marker keys collapsed at every depth;
    anything else (e.g. `.env`-style `KEY=value` text) falls back to line
    scanning. Kept independently in this module rather than imported from
    `setup_apply` — each `setup_*` artifact module in this codebase is
    self-contained and independently auditable.
    """
    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        parsed = None
    if isinstance(parsed, (dict, list)) and parsed:
        redacted_node, redacted = _redact_node(parsed)
        preview = yaml.safe_dump(redacted_node, sort_keys=False, default_flow_style=False, allow_unicode=True)
    else:
        preview, redacted = _redact_lines(text)
    if len(preview) > limit:
        preview = preview[:limit] + "\n<truncated>"
    return preview, "redacted_secret_like_content" if redacted else "not_secret_like"


def _future_rollback_operation(state: str, change_operation: str) -> str:
    if change_operation == "no-op":
        return "none"
    if state == "missing":
        return "delete_future_created_path"
    if state == "file":
        return "restore_prior_file_from_future_secure_snapshot"
    if state == "directory":
        return "restore_prior_directory_state_or_delete_future_created_children"
    if state == "symlink":
        return "manual_review_required_for_prior_symlink"
    return "manual_review_required_for_unsupported_path"


def _snapshot_path(path: Path, *, change: dict[str, Any]) -> dict[str, Any]:
    base = {
        "target_path": os.path.abspath(str(path)),
        "change_ids": [change["change_id"]],
        "change_kinds": [change["change_kind"]],
        "planned_operation_types": [change["operation_type"]],
        "missing_file_marker": False,
        "directory_marker": False,
        "symlink_marker": False,
        "unsupported_path_marker": False,
        "prior_content_digest": "",
        "prior_content_size_bytes": 0,
        "prior_redacted_preview": "",
        "secret_redaction_state": "not_read",
        "raw_content_included": False,
        "snapshot_only": True,
        "artifact_is_authority": False,
    }
    operation = str(change["operation_type"])
    try:
        if path.is_symlink():
            return {
                **base,
                "prior_existence_state": "symlink",
                "symlink_marker": True,
                "prior_content_storage_policy": "not_stored_symlink_marker_only",
                "future_rollback_operation_needed": _future_rollback_operation("symlink", operation),
                "path_notes": ["prior path is a symlink; rollback requires manual review"],
            }
        if not path.exists():
            return {
                **base,
                "prior_existence_state": "missing",
                "missing_file_marker": True,
                "prior_content_storage_policy": "not_stored_missing_file_marker_only",
                "future_rollback_operation_needed": _future_rollback_operation("missing", operation),
                "path_notes": ["prior path does not exist"],
            }
        if path.is_dir():
            return {
                **base,
                "prior_existence_state": "directory",
                "directory_marker": True,
                "prior_content_storage_policy": "not_stored_directory_marker_only",
                "future_rollback_operation_needed": _future_rollback_operation("directory", operation),
                "path_notes": ["prior path is a directory; file content is not embedded"],
            }
        if path.is_file():
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            if operation == "merge":
                # A merge target is, by declaration, a file builder-II does not own and which may
                # hold operator credentials. Marker-based redaction only elides values under key
                # names it recognises, so an unrecognised one (`openai_key`, `session_cookie`, ...)
                # would be copied verbatim into this snapshot. The digest and size below identify
                # the prior file without reproducing any of it.
                preview, redaction_state = (_MERGE_PREVIEW_WITHHELD, "withheld_merge_target_may_contain_credentials")
            else:
                preview, redaction_state = _redact_text(text)
            return {
                **base,
                "prior_existence_state": "file",
                "prior_content_digest": _sha256_bytes(raw),
                "prior_content_size_bytes": len(raw),
                "prior_redacted_preview": preview,
                "prior_content_storage_policy": "digest_size_redacted_preview_only_future_secure_snapshot_required",
                "secret_redaction_state": redaction_state,
                "future_rollback_operation_needed": _future_rollback_operation("file", operation),
                "path_notes": [
                    "raw content is not embedded; future apply must store secure prior content before mutation"
                ],
            }
    except OSError as exc:
        return {
            **base,
            "prior_existence_state": "unsupported",
            "unsupported_path_marker": True,
            "prior_content_storage_policy": "not_stored_unsupported_path_marker_only",
            "future_rollback_operation_needed": _future_rollback_operation("unsupported", operation),
            "path_notes": [f"path could not be inspected safely: {exc}"],
        }
    return {
        **base,
        "prior_existence_state": "unsupported",
        "unsupported_path_marker": True,
        "prior_content_storage_policy": "not_stored_unsupported_path_marker_only",
        "future_rollback_operation_needed": _future_rollback_operation("unsupported", operation),
        "path_notes": ["prior path is neither file, directory, symlink, nor missing"],
    }


def _merge_duplicate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    for record in records:
        path = record["target_path"]
        if path not in by_path:
            by_path[path] = record
            continue
        existing = by_path[path]
        existing["change_ids"] = sorted(set(existing["change_ids"]) | set(record["change_ids"]))
        existing["change_kinds"] = sorted(set(existing["change_kinds"]) | set(record["change_kinds"]))
        existing["planned_operation_types"] = sorted(
            set(existing["planned_operation_types"]) | set(record["planned_operation_types"])
        )
        if existing["future_rollback_operation_needed"] == "none":
            existing["future_rollback_operation_needed"] = record["future_rollback_operation_needed"]
    return [by_path[path] for path in sorted(by_path)]


def _no_mutation_proof() -> dict[str, bool]:
    return {
        "snapshot_generation_performs_writes": False,
        "target_repo_writes": False,
        "goose_config_writes": False,
        "goosehints_writes": False,
        "skill_copy": False,
        "recipe_installation_writes": False,
        "runtime_start": False,
        "model_calls": False,
        "shell_execution": False,
        "mcp_tool_invocation": False,
        "patch_application": False,
        "deepagents_construction": False,
        "setup_apply": False,
        "setup_rollback_execution": False,
        "only_explicit_output_artifact_may_be_written_by_cli": True,
    }


def create_setup_rollback_snapshot(overlay_plan: dict[str, Any]) -> dict[str, Any]:
    overlay_errors = validate_setup_overlay_plan_artifact(overlay_plan)
    if overlay_errors:
        raise ValueError("invalid setup overlay plan: " + "; ".join(overlay_errors))

    records = _merge_duplicate_records(
        [_snapshot_path(Path(change["target_path"]), change=change) for change in overlay_plan["planned_changes"]]
    )
    snapshot_basis = {
        "setup_plan_digest": overlay_plan["setup_plan_ref"]["digest"],
        "overlay_plan_digest": overlay_plan["overlay_plan_digest"],
        "target_path_states": records,
    }
    snapshot_id = digest_jsonable(snapshot_basis, digest_key="snapshot_id")
    snapshot = {
        "kind": SETUP_ROLLBACK_SNAPSHOT_KIND,
        "schema_version": SETUP_ROLLBACK_SNAPSHOT_SCHEMA_VERSION,
        "artifact_is_authority": False,
        "snapshot_only": True,
        "setup_plan_digest": overlay_plan["setup_plan_ref"]["digest"],
        "overlay_plan_digest": overlay_plan["overlay_plan_digest"],
        "snapshot_id": snapshot_id,
        "target_paths_covered": [record["target_path"] for record in records],
        "target_path_states": records,
        "prior_content_default_storage_policy": (
            "normal_json_artifact_records_digest_size_and_redacted_preview_only; "
            "future apply must create secure external prior-content storage before mutation"
        ),
        "secret_policy": {
            "raw_secrets_stored_in_json": False,
            "raw_prior_content_stored_in_json": False,
            "redacted_preview_only": True,
        },
        "no_mutation_proof": _no_mutation_proof(),
        "governance": {
            "artifact_is_authority": False,
            **CAPABILITY_DEFAULTS,
            "setup_apply": "disabled",
            "setup_rollback_execution": "disabled",
        },
    }
    return attach_digest(snapshot, digest_key="snapshot_digest")


def dumps_setup_rollback_snapshot(snapshot: dict[str, Any]) -> str:
    return json_lib.dumps(snapshot, indent=2, sort_keys=True) + "\n"


def write_setup_rollback_snapshot(snapshot: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_setup_rollback_snapshot(snapshot), encoding="utf-8")


def validate_setup_rollback_snapshot_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["setup rollback snapshot artifact must be a JSON object"]
    if data.get("kind") != SETUP_ROLLBACK_SNAPSHOT_KIND:
        errors.append(f"kind must be {SETUP_ROLLBACK_SNAPSHOT_KIND}")
    if data.get("schema_version") != SETUP_ROLLBACK_SNAPSHOT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {SETUP_ROLLBACK_SNAPSHOT_SCHEMA_VERSION}")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false or NOT_AUTHORIZED")
    if data.get("snapshot_only") is not True:
        errors.append("snapshot_only must be true")
    for digest_field in ("setup_plan_digest", "overlay_plan_digest", "snapshot_id"):
        if not _is_sha256(data.get(digest_field)):
            errors.append(f"{digest_field} must be a SHA-256 hex string")

    paths = data.get("target_paths_covered")
    states = data.get("target_path_states")
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        errors.append("target_paths_covered must be a list of strings")
    if not isinstance(states, list) or not states:
        errors.append("target_path_states must be a non-empty list")
    else:
        state_paths: list[str] = []
        for idx, state in enumerate(states):
            if not isinstance(state, dict):
                errors.append(f"target_path_states[{idx}] must be an object")
                continue
            path = state.get("target_path")
            if not isinstance(path, str) or not Path(path).is_absolute():
                errors.append(f"target_path_states[{idx}].target_path must be absolute")
            else:
                state_paths.append(path)
            existence = state.get("prior_existence_state")
            if existence not in _EXISTENCE_STATES:
                errors.append(f"target_path_states[{idx}].prior_existence_state is unsupported")
            storage_policy = state.get("prior_content_storage_policy")
            if storage_policy not in _STORAGE_POLICIES:
                errors.append(f"target_path_states[{idx}].prior_content_storage_policy is unsupported")
            if state.get("raw_content_included") is not False:
                errors.append(f"target_path_states[{idx}].raw_content_included must be false or NOT_AUTHORIZED")
            if state.get("snapshot_only") is not True:
                errors.append(f"target_path_states[{idx}].snapshot_only must be true")
            if state.get("artifact_is_authority") is not False:
                errors.append(f"target_path_states[{idx}].artifact_is_authority must be false or NOT_AUTHORIZED")
            for marker in (
                "missing_file_marker",
                "directory_marker",
                "symlink_marker",
                "unsupported_path_marker",
            ):
                if not isinstance(state.get(marker), bool):
                    errors.append(f"target_path_states[{idx}].{marker} must be boolean")
            if existence == "file":
                if not _is_sha256(state.get("prior_content_digest")):
                    errors.append(f"target_path_states[{idx}].prior_content_digest must be SHA-256 for files")
                if not isinstance(state.get("prior_redacted_preview"), str):
                    errors.append(f"target_path_states[{idx}].prior_redacted_preview must be a string")
            if not isinstance(state.get("future_rollback_operation_needed"), str):
                errors.append(f"target_path_states[{idx}].future_rollback_operation_needed must be a string")
        if isinstance(paths, list) and sorted(paths) != sorted(state_paths):
            errors.append("target_paths_covered must match target_path_states target paths")

    secret_policy = data.get("secret_policy")
    if not isinstance(secret_policy, dict):
        errors.append("secret_policy must be an object")
    else:
        if secret_policy.get("raw_secrets_stored_in_json") is not False:
            errors.append("secret_policy.raw_secrets_stored_in_json must be false or NOT_AUTHORIZED")
        if secret_policy.get("raw_prior_content_stored_in_json") is not False:
            errors.append("secret_policy.raw_prior_content_stored_in_json must be false or NOT_AUTHORIZED")
        if secret_policy.get("redacted_preview_only") is not True:
            errors.append("secret_policy.redacted_preview_only must be true")

    proof = data.get("no_mutation_proof")
    if not isinstance(proof, dict):
        errors.append("no_mutation_proof must be an object")
    else:
        for key, value in proof.items():
            if key == "only_explicit_output_artifact_may_be_written_by_cli":
                if value is not True:
                    errors.append(f"no_mutation_proof.{key} must be true")
            elif value is not False:
                errors.append(f"no_mutation_proof.{key} must be false or NOT_AUTHORIZED")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    elif governance.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")

    digest = data.get("snapshot_digest")
    if not _is_sha256(digest):
        errors.append("snapshot_digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(data, digest_key="snapshot_digest"):
        errors.append("snapshot_digest does not match canonical snapshot payload")
    return errors


def validate_setup_rollback_snapshot_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_setup_rollback_snapshot_artifact(data)
