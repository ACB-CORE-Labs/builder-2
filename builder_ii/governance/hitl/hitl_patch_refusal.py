"""Passive HITL patch refusal artifact — RECORDED_ONLY, not authority.

kind: builder_ii.hitl_patch_refusal

Records that an operator refused a bound patch proposal. Does not apply,
approve, roll back, or grant authority. Complements approve-patch: reject is
non-approval, not a promotion-bridge rejection-record.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

HITL_PATCH_REFUSAL_KIND = "builder_ii.hitl_patch_refusal"
HITL_PATCH_REFUSAL_SCHEMA_VERSION = 1


def _digest(data: dict[str, Any]) -> str:
    raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_hitl_patch_refusal(
    proposal: dict[str, Any],
    *,
    proposal_path: str | Path,
    rationale: str,
    refused_by: str = "operator",
) -> dict[str, Any]:
    """Mint a passive refusal bound to a proposal path and patch digest when present."""
    patch_digest = proposal.get("patch_digest") or proposal.get("digest") or ""
    if not isinstance(patch_digest, str):
        patch_digest = ""
    record: dict[str, Any] = {
        "kind": HITL_PATCH_REFUSAL_KIND,
        "schema_version": HITL_PATCH_REFUSAL_SCHEMA_VERSION,
        "record_state": "REFUSED_ONLY",
        "proposal_path": str(proposal_path),
        "proposal_kind": str(proposal.get("kind") or ""),
        "patch_digest": patch_digest,
        "rationale": rationale,
        "refused_by": refused_by,
        "grants_authority": False,
        "artifact_is_authority": False,
        "executes_patch": False,
        "mutates_source": False,
        "governance": {
            "capability_state": "hitl_patch_refusal",
            "artifact_is_authority": False,
            "independent_observer": False,
        },
    }
    record["digest"] = _digest({k: v for k, v in record.items() if k != "digest"})
    return record


def validate_hitl_patch_refusal(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["hitl patch refusal must be a JSON object"]
    if data.get("kind") != HITL_PATCH_REFUSAL_KIND:
        errors.append(f"kind must be {HITL_PATCH_REFUSAL_KIND}")
    if data.get("schema_version") != HITL_PATCH_REFUSAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_PATCH_REFUSAL_SCHEMA_VERSION}")
    if data.get("record_state") != "REFUSED_ONLY":
        errors.append("record_state must be REFUSED_ONLY")
    if not isinstance(data.get("proposal_path"), str) or not data.get("proposal_path"):
        errors.append("proposal_path must be a non-empty string")
    if not isinstance(data.get("rationale"), str) or not str(data.get("rationale")).strip():
        errors.append("rationale must be a non-empty string")
    if data.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if data.get("executes_patch") is not False:
        errors.append("executes_patch must be false")
    if data.get("mutates_source") is not False:
        errors.append("mutates_source must be false")
    return errors


def write_hitl_patch_refusal(record: dict[str, Any], output: Path) -> None:
    errors = validate_hitl_patch_refusal(record)
    if errors:
        raise ValueError(f"invalid hitl patch refusal: {'; '.join(errors)}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
