from __future__ import annotations

import hashlib
import json as json_lib
from typing import Any

GOOSE_LAUNCH_RECEIPT_KIND = "builder_ii.goose_launch_receipt"
GOOSE_CLOSE_RECEIPT_KIND = "builder_ii.goose_close_receipt"
NO_MUTATION_POSTFLIGHT_KIND = "builder_ii.no_mutation_postflight"
GOOSE_LAUNCH_RECEIPT_SCHEMA_VERSION = 2
SCHEMA_VERSION = 1


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
    evidence = receipt.get("evidence")
    if not isinstance(evidence, dict) or not evidence:
        errors.append("evidence must be a non-empty object")
    elif "runtime" not in evidence and "goose_compatibility" not in evidence:
        errors.append("evidence must identify the admitted runtime")
    supplied_digest = receipt.get("digest")
    if isinstance(supplied_digest, str):
        content = dict(receipt)
        content.pop("digest", None)
        if _digest(content) != supplied_digest:
            errors.append("digest does not match receipt content")
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
) -> dict[str, Any]:
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
        "approved_patch_evidence": approved_patch_evidence,
        "mutation_mode": "approved_hitl_patch" if approved_patch_evidence else "no_mutation",
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
