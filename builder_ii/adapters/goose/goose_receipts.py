from __future__ import annotations

import hashlib
import json as json_lib
import re
from typing import Any

GOOSE_LAUNCH_RECEIPT_KIND = "builder_ii.goose_launch_receipt"
GOOSE_CLOSE_RECEIPT_KIND = "builder_ii.goose_close_receipt"
NO_MUTATION_POSTFLIGHT_KIND = "builder_ii.no_mutation_postflight"
GOOSE_LAUNCH_RECEIPT_SCHEMA_VERSION = 2
SCHEMA_VERSION = 1
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_goose_launch_receipt(
    session_id: str,
    target_profile: str,
    agent_profile: str,
    pid: int,
    start_time: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    content = {
        "kind": GOOSE_LAUNCH_RECEIPT_KIND,
        "schema_version": GOOSE_LAUNCH_RECEIPT_SCHEMA_VERSION,
        "session_id": session_id,
        "target_profile": target_profile,
        "agent_profile": agent_profile,
        "pid": pid,
        "start_time": start_time,
    }
    if not isinstance(evidence, dict) or not evidence:
        raise ValueError("Goose launch receipt v2 requires explicit runtime evidence")
    content["evidence"] = evidence
    content["digest"] = _digest(content)
    return content


def validate_goose_launch_receipt(receipt: Any) -> list[str]:
    """Validate the versioned, digest-bound Goose launch contract."""
    if not isinstance(receipt, dict):
        return ["Goose launch receipt must be a JSON object"]
    errors: list[str] = []
    if receipt.get("kind") != GOOSE_LAUNCH_RECEIPT_KIND:
        errors.append(f"kind must be {GOOSE_LAUNCH_RECEIPT_KIND}")
    if receipt.get("schema_version") != GOOSE_LAUNCH_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GOOSE_LAUNCH_RECEIPT_SCHEMA_VERSION}")
    required = ("session_id", "target_profile", "agent_profile", "pid", "start_time", "evidence", "digest")
    for key in required:
        if key not in receipt:
            errors.append(f"missing required field: {key}")
    for key in ("session_id", "target_profile", "agent_profile", "start_time"):
        if not isinstance(receipt.get(key), str) or not receipt[key]:
            errors.append(f"{key} must be a non-empty string")
    if not isinstance(receipt.get("pid"), int) or receipt["pid"] <= 0:
        errors.append("pid must be a positive integer")
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        errors.append("evidence must be a non-empty object")
    elif "runtime" not in evidence and "goose_compatibility" not in evidence:
        errors.append("evidence must identify the admitted runtime")
    supplied_digest = receipt.get("digest")
    if not isinstance(supplied_digest, str) or not _SHA256_RE.fullmatch(supplied_digest):
        errors.append("digest must be a SHA-256 hex digest")
    else:
        content = dict(receipt)
        content.pop("digest", None)
        if _digest(content) != supplied_digest:
            errors.append("digest does not match receipt content")
    return errors


def validate_no_mutation_postflight(postflight: Any) -> list[str]:
    """Validate Goose target-state evidence without treating it as authority."""
    if not isinstance(postflight, dict):
        return ["Goose postflight must be a JSON object"]
    errors: list[str] = []
    if postflight.get("kind") != NO_MUTATION_POSTFLIGHT_KIND:
        errors.append(f"kind must be {NO_MUTATION_POSTFLIGHT_KIND}")
    if postflight.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    for key in ("session_id", "target_root", "start_time", "end_time"):
        if not isinstance(postflight.get(key), str) or not postflight[key]:
            errors.append(f"{key} must be a non-empty string")
    if not isinstance(postflight.get("files_checked"), int) or postflight["files_checked"] < 0:
        errors.append("files_checked must be a non-negative integer")
    for key in ("mutations_detected", "approved_mutations", "unexplained_mutations"):
        value = postflight.get(key)
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            errors.append(f"{key} must be a list of strings")
    if postflight.get("mutation_mode") not in {
        "no_mutation",
        "approved_hitl_patch",
        "approved_hitl_rollback",
    }:
        errors.append("mutation_mode is invalid")
    unexplained = postflight.get("unexplained_mutations")
    if isinstance(unexplained, list) and postflight.get("valid") is not (len(unexplained) == 0):
        errors.append("valid must equal whether unexplained_mutations is empty")
    detected = postflight.get("mutations_detected")
    approved = postflight.get("approved_mutations")
    if all(isinstance(value, list) and all(isinstance(item, str) for item in value) for value in (detected, approved, unexplained)):
        assert isinstance(detected, list)
        assert isinstance(approved, list)
        assert isinstance(unexplained, list)
        if any(len(value) != len(set(value)) for value in (detected, approved, unexplained)):
            errors.append("mutation lists must not contain duplicates")
        if set(approved) & set(unexplained):
            errors.append("approved_mutations and unexplained_mutations must be disjoint")
        if set(detected) != set(approved) | set(unexplained):
            errors.append("detected mutations must be exactly partitioned into approved and unexplained mutations")
    mode = postflight.get("mutation_mode")
    evidence = postflight.get("approved_mutation_evidence")
    patch_evidence = postflight.get("approved_patch_evidence")
    if mode == "no_mutation":
        if approved:
            errors.append("no_mutation mode must not contain approved mutations")
        if evidence is not None or patch_evidence is not None:
            errors.append("no_mutation mode must not contain approval evidence")
    elif mode in {"approved_hitl_patch", "approved_hitl_rollback"}:
        if not isinstance(evidence, dict) or not evidence:
            errors.append("approved mutation mode requires approved_mutation_evidence")
        if mode == "approved_hitl_patch" and patch_evidence != evidence:
            errors.append("approved_hitl_patch mode must mirror approved evidence in approved_patch_evidence")
        if mode == "approved_hitl_rollback" and patch_evidence is not None:
            errors.append("approved_hitl_rollback mode must not claim approved_patch_evidence")
    supplied_digest = postflight.get("digest")
    if not isinstance(supplied_digest, str) or not _SHA256_RE.fullmatch(supplied_digest):
        errors.append("digest must be a SHA-256 hex digest")
    else:
        content = dict(postflight)
        content.pop("digest", None)
        if _digest(content) != supplied_digest:
            errors.append("digest does not match postflight content")
    return errors


def create_no_mutation_postflight(
    session_id: str,
    target_root: str,
    start_time: str,
    end_time: str,
    files_checked: int,
    mutations_detected: list[str],
    approved_mutations: list[str] | None = None,
    unexplained_mutations: list[str] | None = None,
    approved_patch_evidence: dict[str, Any] | None = None,
    *,
    mutation_mode: str | None = None,
    approved_mutation_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if mutation_mode is None:
        mutation_mode = "approved_hitl_patch" if approved_patch_evidence else "no_mutation"
    if mutation_mode not in {"no_mutation", "approved_hitl_patch", "approved_hitl_rollback"}:
        raise ValueError("mutation_mode must be no_mutation, approved_hitl_patch, or approved_hitl_rollback")
    if approved_mutation_evidence is None:
        approved_mutation_evidence = approved_patch_evidence
    content = {
        "kind": NO_MUTATION_POSTFLIGHT_KIND,
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "target_root": target_root,
        "start_time": start_time,
        "end_time": end_time,
        "files_checked": files_checked,
        "mutations_detected": mutations_detected,
        "approved_mutations": list(approved_mutations or []),
        "unexplained_mutations": list(unexplained_mutations if unexplained_mutations is not None else mutations_detected),
        "approved_mutation_evidence": approved_mutation_evidence,
        "approved_patch_evidence": (
            approved_mutation_evidence if mutation_mode == "approved_hitl_patch" else None
        ),
        "mutation_mode": mutation_mode,
        "valid": len(unexplained_mutations if unexplained_mutations is not None else mutations_detected) == 0,
    }
    content["digest"] = _digest(content)
    return content


def create_goose_close_receipt(
    session_id: str,
    launch_receipt_digest: str,
    postflight_digest: str,
    transcript_path: str,
    transcript_digest: str,
    end_time: str,
    exit_code: int,
) -> dict[str, Any]:
    content = {
        "kind": GOOSE_CLOSE_RECEIPT_KIND,
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "launch_receipt_digest": launch_receipt_digest,
        "postflight_digest": postflight_digest,
        "transcript_path": transcript_path,
        "transcript_digest": transcript_digest,
        "end_time": end_time,
        "exit_code": exit_code,
    }
    content["digest"] = _digest(content)
    return content


def validate_goose_close_receipt(receipt: Any) -> list[str]:
    """Validate the digest-bound Goose close contract."""
    if not isinstance(receipt, dict):
        return ["Goose close receipt must be a JSON object"]
    errors: list[str] = []
    if receipt.get("kind") != GOOSE_CLOSE_RECEIPT_KIND:
        errors.append(f"kind must be {GOOSE_CLOSE_RECEIPT_KIND}")
    if receipt.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    for key in ("session_id", "transcript_path", "end_time"):
        if not isinstance(receipt.get(key), str) or not receipt[key]:
            errors.append(f"{key} must be a non-empty string")
    for key in ("launch_receipt_digest", "postflight_digest", "transcript_digest"):
        value = receipt.get(key)
        if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
            errors.append(f"{key} must be a SHA-256 hex digest")
    if not isinstance(receipt.get("exit_code"), int):
        errors.append("exit_code must be an integer")
    supplied_digest = receipt.get("digest")
    if not isinstance(supplied_digest, str) or not _SHA256_RE.fullmatch(supplied_digest):
        errors.append("digest must be a SHA-256 hex digest")
    else:
        content = dict(receipt)
        content.pop("digest", None)
        if _digest(content) != supplied_digest:
            errors.append("digest does not match receipt content")
    return errors
