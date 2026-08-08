from __future__ import annotations

import hashlib
import json as json_lib
from typing import Any

GOOSE_LAUNCH_RECEIPT_KIND = "builder_ii.goose_launch_receipt"
GOOSE_CLOSE_RECEIPT_KIND = "builder_ii.goose_close_receipt"
NO_MUTATION_POSTFLIGHT_KIND = "builder_ii.no_mutation_postflight"
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
) -> dict[str, Any]:
    content = {
        "kind": GOOSE_LAUNCH_RECEIPT_KIND,
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "target_profile": target_profile,
        "agent_profile": agent_profile,
        "pid": pid,
        "start_time": start_time,
    }
    content["digest"] = _digest(content)
    return content


def bind_goose_launch_receipt_dispatch(
    receipt: dict[str, Any],
    *,
    plan_path: str,
    plan_sha256: str,
    authorization_path: str,
    authorization_sha256: str,
    consumption_path: str,
    decision_mode: str,
    grant_digest: str | None,
) -> dict[str, Any]:
    """Return the same launch receipt rebound to the dispatch evidence that preceded spawn.

    The original digest is discarded and recomputed over the expanded receipt. This keeps
    ``builder-govern trace``-style consumers from having to correlate a launch to a grant by
    filename convention or timing.
    """
    content = {key: value for key, value in receipt.items() if key != "digest"}
    content["dispatch_evidence"] = {
        "plan_ref": {
            "path": plan_path,
            "sha256": plan_sha256,
        },
        "authorization_ref": {
            "path": authorization_path,
            "sha256": authorization_sha256,
        },
        "consumption_path": consumption_path,
        "decision_mode": decision_mode,
        "grant_digest": grant_digest,
    }
    content["digest"] = _digest(content)
    return content


def create_no_mutation_postflight(
    session_id: str,
    target_root: str,
    start_time: str,
    end_time: str,
    files_checked: int,
    mutations_detected: list[str],
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
        "valid": len(mutations_detected) == 0,
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
