"""Passive ledger records for the HITL patch apply/rollback lane (plan item 1.6).

The apply and rollback executors are governed mutations, but until now they left no
append-only ledger trace: a receipt was written into the output directory and nothing
recorded *that an apply/rollback event occurred* as a first-class, independently
verifiable artifact. This module adds that trace.

Doctrine and shape: this is a ``PASSIVE_INDEX_ONLY`` record modeled on
``verification_execution_ledger.py`` — it binds the digests of the governing chain
(proposal/approval/verification-receipt/apply-receipt for an apply; rollback
plan/approval/receipt for a rollback) into ``subject_refs`` plus a ``chain_digest``,
self-digests, and validates. It grants no authority and executes nothing (**artifact !=
authority**): it is evidence that a governed event happened, emitted *after* the mutation
the executor already performed and gated. It is deliberately NOT folded into
``event_ledger.py`` — that ledger is coupled to the workflow-orchestrator stage machine
(a closed ``EVENT_TYPES`` set and ``WORKFLOW_STAGE_ORDER`` replay); a patch apply is not a
workflow stage transition, so forcing it there would corrupt a pinned subsystem.

The record is written to the builder-side output directory, never into the target repo —
writing into the tree being patched would dirty it and corrupt the post-apply drift
fingerprint the rollback lane depends on.
"""

from __future__ import annotations

import hashlib
import json as json_lib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest, digest_jsonable

HITL_PATCH_LEDGER_RECORD_KIND = "builder_ii.hitl_patch_ledger_record"
HITL_PATCH_LEDGER_RECORD_SCHEMA_VERSION = 1
HITL_PATCH_LEDGER_RECORD_STATE = "PASSIVE_INDEX_ONLY"

EVENT_PATCH_APPLIED = "patch_applied"
EVENT_PATCH_ROLLED_BACK = "patch_rolled_back"
_EVENT_TYPES = {EVENT_PATCH_APPLIED, EVENT_PATCH_ROLLED_BACK}

_DIGEST_KEY = "hitl_patch_ledger_record_digest"


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _is_non_empty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_sha256_hex(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _default_governance() -> dict[str, Any]:
    return {
        "capability_state": "hitl_patch_ledger_record",
        "runtime_execution": "DISABLED",
        "model_execution": "DISABLED",
        "shell_execution": "DISABLED",
        "source_writes": "DISABLED EXCEPT EXPLICIT LEDGER ARTIFACT OUTPUT PATH",
        "target_repo_writes": "DISABLED",
        "memory_mutation": "DISABLED",
        "goose_runtime_start": "DISABLED",
        "deepagents_runtime": "DISABLED",
        "mcp_execution": "DISABLED",
        "artifact_is_authority": False,
        "grants_runtime_authority": False,
        "grants_action_authority": False,
        "core_workbench_coupling": "NONE",
    }


def hitl_patch_ledger_subject_ref(*, role: str, kind: str, path: Path) -> dict[str, Any]:
    """Build one ``subject_refs`` entry, hashing the on-disk artifact so the ledger record
    binds exactly the bytes that governed the event. The file must exist at call time
    (every governing artifact is written before emission)."""
    return {
        "role": role,
        "kind": kind,
        "path": str(path),
        "sha256": _file_sha256(path),
        "required": True,
    }


def _chain_digest(*, event_type: str, patch_digest: str, pre_head: str, subject_refs: list[dict[str, Any]]) -> str:
    return digest_jsonable(
        {
            "event_type": event_type,
            "patch_digest": patch_digest,
            "pre_head": pre_head,
            "subject_digests": {
                str(ref.get("role", "")): str(ref.get("sha256", ""))
                for ref in sorted(subject_refs, key=lambda ref: str(ref.get("role", "")))
            },
        }
    )


def create_hitl_patch_ledger_record(
    *,
    event_type: str,
    target: dict[str, Any],
    patch_digest: str,
    pre_head: str,
    subject_refs: list[dict[str, Any]],
    recorded_at: str | None = None,
) -> dict[str, Any]:
    """Assemble a self-digested, self-validated patch-ledger record.

    Never raises on a malformed input: like ``create_verification_execution_ledger_record``,
    a failed self-validation is embedded as ``errors``/``valid=false`` on the returned record
    rather than raised, so a successful mutation is never stranded without a ledger trace.
    """
    chain_digest = _chain_digest(
        event_type=event_type,
        patch_digest=patch_digest,
        pre_head=pre_head,
        subject_refs=subject_refs,
    )
    record: dict[str, Any] = {
        "kind": HITL_PATCH_LEDGER_RECORD_KIND,
        "schema_version": HITL_PATCH_LEDGER_RECORD_SCHEMA_VERSION,
        "ledger_record_state": HITL_PATCH_LEDGER_RECORD_STATE,
        "event_type": event_type,
        "recorded_at": recorded_at or _utc_now(),
        "target": {"name": target.get("name", ""), "repo": str(target.get("repo", ""))},
        "patch_digest": patch_digest,
        "pre_head": pre_head,
        "chain_digest": chain_digest,
        "subject_refs": list(subject_refs),
        "executes_model": False,
        "executes_shell": False,
        "invokes_goose": False,
        "constructs_deepagents": False,
        "invokes_mcp": False,
        "mutates_target_repo": False,
        "governance": _default_governance(),
        "errors": [],
        "valid": True,
    }
    record = attach_digest(record, digest_key=_DIGEST_KEY)
    errors = validate_hitl_patch_ledger_record(record)
    if errors:
        record["errors"] = errors
        record["valid"] = False
        record = attach_digest(record, digest_key=_DIGEST_KEY)
    return record


def dumps_hitl_patch_ledger_record(record: dict[str, Any]) -> str:
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_hitl_patch_ledger_record(record: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_hitl_patch_ledger_record(record), encoding="utf-8")


def validate_hitl_patch_ledger_record(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["hitl patch ledger record must be a JSON object"]
    if record.get("kind") != HITL_PATCH_LEDGER_RECORD_KIND:
        errors.append(f"kind must be {HITL_PATCH_LEDGER_RECORD_KIND}")
    if record.get("schema_version") != HITL_PATCH_LEDGER_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {HITL_PATCH_LEDGER_RECORD_SCHEMA_VERSION}")
    if record.get("ledger_record_state") != HITL_PATCH_LEDGER_RECORD_STATE:
        errors.append(f"ledger_record_state must be {HITL_PATCH_LEDGER_RECORD_STATE}")
    if record.get("event_type") not in _EVENT_TYPES:
        errors.append(f"event_type must be one of: {', '.join(sorted(_EVENT_TYPES))}")
    if not _is_non_empty_string(record.get("recorded_at")):
        errors.append("recorded_at must be a non-empty string")
    if not _is_sha256_hex(record.get("patch_digest")):
        errors.append("patch_digest must be a SHA-256 hex digest")
    if not _is_sha256_hex(record.get("pre_head")) and not _is_non_empty_string(record.get("pre_head")):
        errors.append("pre_head must be a non-empty string")
    if not _is_sha256_hex(record.get("chain_digest")):
        errors.append("chain_digest must be a SHA-256 hex digest")

    target = record.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if not _is_non_empty_string(target.get("name")):
            errors.append("target.name must be a non-empty string")
        if not _is_non_empty_string(target.get("repo")):
            errors.append("target.repo must be a non-empty string")

    refs = record.get("subject_refs")
    if not isinstance(refs, list) or not refs:
        errors.append("subject_refs must be a non-empty list")
    else:
        for index, ref in enumerate(refs):
            if not isinstance(ref, dict):
                errors.append(f"subject_refs[{index}] must be an object")
                continue
            for key in ("role", "kind", "path"):
                if not _is_non_empty_string(ref.get(key)):
                    errors.append(f"subject_refs[{index}].{key} must be a non-empty string")
            if not _is_sha256_hex(ref.get("sha256")):
                errors.append(f"subject_refs[{index}].sha256 must be a SHA-256 hex digest")
            if ref.get("required") is not True:
                errors.append(f"subject_refs[{index}].required must be true")

    # chain_digest must be recomputable from the bound subject digests: the record cannot
    # claim a chain it does not actually bind.
    if isinstance(refs, list) and _is_sha256_hex(record.get("chain_digest")):
        expected_chain = _chain_digest(
            event_type=str(record.get("event_type", "")),
            patch_digest=str(record.get("patch_digest", "")),
            pre_head=str(record.get("pre_head", "")),
            subject_refs=[ref for ref in refs if isinstance(ref, dict)],
        )
        if record.get("chain_digest") != expected_chain:
            errors.append("chain_digest does not match event_type/patch_digest/pre_head/subject_refs")

    for key in (
        "executes_model",
        "executes_shell",
        "invokes_goose",
        "constructs_deepagents",
        "invokes_mcp",
        "mutates_target_repo",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false or NOT_AUTHORIZED")

    governance = record.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "model_execution",
            "shell_execution",
            "target_repo_writes",
            "memory_mutation",
            "goose_runtime_start",
            "deepagents_runtime",
            "mcp_execution",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("source_writes") != "DISABLED EXCEPT EXPLICIT LEDGER ARTIFACT OUTPUT PATH":
            errors.append(
                "governance.source_writes must be DISABLED or NOT_AUTHORIZED EXCEPT EXPLICIT LEDGER ARTIFACT OUTPUT PATH"
            )
        for key in ("artifact_is_authority", "grants_runtime_authority", "grants_action_authority"):
            if governance.get(key) is not False:
                errors.append(f"governance.{key} must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    artifact_errors = record.get("errors")
    if not isinstance(artifact_errors, list) or not all(isinstance(item, str) for item in artifact_errors):
        errors.append("errors must be a list of strings")
    valid = record.get("valid")
    if not isinstance(valid, bool):
        errors.append("valid must be a boolean")
    elif valid is True and artifact_errors:
        errors.append("errors must be empty when valid is true")
    elif valid is False and not artifact_errors:
        errors.append("errors must be non-empty when valid is false")

    digest = record.get(_DIGEST_KEY)
    if not _is_sha256_hex(digest):
        errors.append(f"{_DIGEST_KEY} must be a SHA-256 hex string")
    elif digest != digest_jsonable(record, digest_key=_DIGEST_KEY):
        errors.append(f"{_DIGEST_KEY} drift detected")
    return list(dict.fromkeys(errors))


def validate_hitl_patch_ledger_record_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid json: {exc}"]
    return validate_hitl_patch_ledger_record(data)
