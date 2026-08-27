"""Canonical persisted custody for governed Deep Agents session lifecycle evidence.

This adapter manages the canonical Deep Agents namespace beneath an admitted
Builder-II artifact root: ``sessions/<session_id>/deepagents/``.

Enforces strict builder-II epistemological invariants:
1. Projection evidence (e.g. PROJECTED_ONLY) is NEVER accepted as execution evidence.
2. End-to-end cryptographic and structural cross-binding:
   work_plan ↔ candidate ↔ approval ↔ run_envelope ↔ receipt ↔ event ledger.
3. Monotonic, hash-chained lifecycle events with exact subject references.
4. Fail-closed no-follow directory traversal and exclusive file creation.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from builder_ii.adapters.deepagents.deepagents_execution import (
    _DIGEST_KEYS,
    DEEPAGENTS_RUN_ENVELOPE_KIND,
    _digest_jsonable,
    validate_deepagents_checkpoint,
    validate_deepagents_execution_approval,
    validate_deepagents_execution_candidate,
    validate_deepagents_execution_receipt,
    validate_deepagents_run_envelope,
)
from builder_ii.adapters.deepagents.deepagents_runtime import (
    DEEPAGENTS_RUNTIME_ENVELOPE_KIND,
)
from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    validate_deepagents_runtime_envelope,
    validate_deepagents_work_plan,
)
from builder_ii.governance.ledger.event_ledger import load_event_records, validate_event_chain_integrity
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.lifecycle.candidate.runtime_event_append import (
    append_runtime_event,
    open_directory_nofollow,
)

_SESSION_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


def _validate_session_id(session_id: str) -> None:
    if not _SESSION_ID_RE.fullmatch(session_id):
        raise ValueError("invalid canonical Deep Agents session identity")


def deepagents_session_dir(artifact_root: Path, session_id: str) -> Path:
    _validate_session_id(session_id)
    normalized_root = Path(os.path.abspath(artifact_root))
    return normalized_root / "sessions" / session_id / "deepagents"


def _persist_new_json(path: Path, value: dict[str, Any]) -> None:
    parent_fd = open_directory_nofollow(path.parent)
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        output_fd = os.open(path.name, flags, 0o600, dir_fd=parent_fd)
        try:
            payload = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")
            with os.fdopen(output_fd, "wb", closefd=False) as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            os.close(output_fd)
    finally:
        os.close(parent_fd)


def _require_new(paths: tuple[Path, ...]) -> None:
    existing = [path for path in paths if path.exists() or path.is_symlink()]
    if existing:
        raise FileExistsError(
            "refusing to overwrite existing canonical Deep Agents evidence: "
            + ", ".join(str(path) for path in existing)
        )


def _load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        if path.is_symlink():
            return None, [f"{label} must not be a symlink"]
        if not path.is_file():
            return None, [f"{label} is missing or not a regular file"]
        raw = path.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{label} is unreadable: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{label} must be a JSON object"]
    return value, []


def _validate_identity(value: dict[str, Any], session_id: str, label: str) -> None:
    if value.get("session_id") != session_id:
        raise ValueError(f"{label} session_id does not match governed run")


def _artifact_digest(value: dict[str, Any] | None) -> str:
    if not isinstance(value, dict):
        return ""
    for k in _DIGEST_KEYS:
        if k in value and isinstance(value[k], str) and len(value[k]) == 64:
            return value[k]
    return canonical_digest(value)


def _custody_artifact_ref(
    data: dict[str, Any],
    *,
    path: str | Path,
    role: str,
    name: str = "",
    required: bool = True,
) -> dict[str, Any]:
    return {
        "role": role,
        "kind": str(data.get("kind", "")),
        "path": str(path),
        "sha256": _artifact_digest(data),
        "name": name,
        "required": required,
    }


def _ref_digest_matches(ref: Any, actual_value: dict[str, Any] | None) -> bool:
    if not isinstance(ref, dict) or not isinstance(actual_value, dict):
        return False
    ref_sha = ref.get("sha256")
    if not ref_sha:
        return False
    candidates = {
        canonical_digest(actual_value),
        _digest_jsonable(actual_value),
        *(actual_value[k] for k in _DIGEST_KEYS if k in actual_value and isinstance(actual_value[k], str)),
    }
    return ref_sha in candidates


def validate_deepagents_session_custody(artifact_root: Path, session_id: str) -> list[str]:
    """Independently reconstruct the exact canonical Deep Agents lifecycle artifacts and events."""
    try:
        session_dir = deepagents_session_dir(artifact_root, session_id)
        directory_fd = open_directory_nofollow(session_dir, create=False)
        os.close(directory_fd)
    except (OSError, ValueError) as exc:
        return [f"canonical Deep Agents session namespace is invalid: {exc}"]

    errors: list[str] = []
    plan_path = session_dir / "work_plan.json"
    envelope_path = session_dir / "envelope.json"
    candidate_path = session_dir / "candidate.json"
    approval_path = session_dir / "approval.json"
    receipt_path = session_dir / "receipt.json"
    checkpoint_path = session_dir / "checkpoint.json"

    plan, plan_errors = _load_json(plan_path, "canonical Deep Agents work plan")
    envelope, env_errors = _load_json(envelope_path, "canonical Deep Agents run envelope")
    errors.extend(plan_errors)
    errors.extend(env_errors)

    if plan is not None:
        errors.extend(validate_deepagents_work_plan(plan))
        if plan.get("session_id") and plan.get("session_id") != session_id:
            errors.append("canonical Deep Agents work plan session_id does not match run")

    candidate: dict[str, Any] | None = None
    if candidate_path.exists() or candidate_path.is_symlink():
        candidate, cand_errors = _load_json(candidate_path, "canonical Deep Agents candidate")
        errors.extend(cand_errors)
        if candidate is not None:
            errors.extend(validate_deepagents_execution_candidate(candidate))
            if candidate.get("session_id") and candidate.get("session_id") != session_id:
                errors.append("canonical Deep Agents candidate session_id does not match run")
            if plan is not None and not _ref_digest_matches(candidate.get("work_plan_ref"), plan):
                errors.append("candidate work_plan_ref does not match canonical work_plan digest")

    approval: dict[str, Any] | None = None
    if approval_path.exists() or approval_path.is_symlink():
        approval, app_errors = _load_json(approval_path, "canonical Deep Agents approval")
        errors.extend(app_errors)
        if approval is not None:
            errors.extend(validate_deepagents_execution_approval(approval))
            if approval.get("session_id") and approval.get("session_id") != session_id:
                errors.append("canonical Deep Agents approval session_id does not match run")
            if candidate is not None and not _ref_digest_matches(approval.get("candidate_ref"), candidate):
                errors.append("approval candidate_ref does not match canonical candidate digest")

    if envelope is not None:
        env_kind = envelope.get("kind")
        if env_kind == DEEPAGENTS_RUN_ENVELOPE_KIND:
            errors.extend(validate_deepagents_run_envelope(envelope))
            if candidate is not None and not _ref_digest_matches(envelope.get("candidate_ref"), candidate):
                errors.append("envelope candidate_ref does not match canonical candidate digest")
            if approval is not None and not _ref_digest_matches(envelope.get("approval_ref"), approval):
                errors.append("envelope approval_ref does not match canonical approval digest")
        elif env_kind == DEEPAGENTS_RUNTIME_ENVELOPE_KIND:
            errors.extend(validate_deepagents_runtime_envelope(envelope))
            if plan is not None and not _ref_digest_matches(envelope.get("work_plan_ref"), plan):
                errors.append("envelope work_plan_ref does not match canonical work_plan digest")
        else:
            errors.append(f"unknown Deep Agents envelope kind: {env_kind}")

        if envelope.get("session_id") != session_id:
            errors.append("canonical Deep Agents run envelope session_id does not match run")

    events_dir = session_dir.parent / "events"
    integrity = validate_event_chain_integrity(events_dir)
    if not integrity.get("valid"):
        errors.extend(str(error) for error in integrity.get("errors", []))

    events = [event for event, _ in load_event_records(events_dir)]

    if plan is not None and envelope is not None:
        start_matches = [event for event in events if event.get("event_type") == "deepagents_runtime_started"]
        if len(start_matches) != 1:
            errors.append("canonical Deep Agents custody requires exactly one deepagents_runtime_started event")
        else:
            start_event = start_matches[0]
            if start_event.get("session_id") != session_id:
                errors.append("deepagents_runtime_started session_id does not match run")
            if start_event.get("command_surface") != "builder delegate":
                errors.append("deepagents_runtime_started command_surface must be 'builder delegate'")

            subject_refs = start_event.get("subject_refs", [])
            plan_refs = [
                ref
                for ref in subject_refs
                if isinstance(ref, dict)
                and ref.get("role") in ("deepagents_work_plan", "work_plan")
                and ref.get("path") == str(plan_path)
            ]
            if len(plan_refs) != 1 or not _ref_digest_matches(plan_refs[0], plan):
                errors.append(
                    f"{plan_path}: deepagents_runtime_started binding does not match canonical work plan digest"
                )

            env_refs = [
                ref
                for ref in subject_refs
                if isinstance(ref, dict)
                and ref.get("role") in ("deepagents_run_envelope", "deepagents_runtime_envelope", "run_envelope")
                and ref.get("path") == str(envelope_path)
            ]
            if len(env_refs) != 1 or not _ref_digest_matches(env_refs[0], envelope):
                errors.append(
                    f"{envelope_path}: deepagents_runtime_started binding does not match canonical envelope digest"
                )

    if receipt_path.exists() or receipt_path.is_symlink():
        receipt, rec_errors = _load_json(receipt_path, "canonical Deep Agents execution receipt")
        errors.extend(rec_errors)
        if receipt is not None:
            rec_kind = receipt.get("kind")
            rec_state = receipt.get("receipt_state")

            if rec_state == "PROJECTED_ONLY" or rec_kind == "builder_ii.deepagents_subagent_execution_receipt":
                errors.append("PROJECTED_ONLY subagent receipt must not be promoted to execution receipt")
            else:
                errors.extend(validate_deepagents_execution_receipt(receipt))
                if receipt.get("session_id") != session_id:
                    errors.append("canonical Deep Agents receipt session_id does not match run")

                if envelope is not None and not _ref_digest_matches(receipt.get("envelope_ref"), envelope):
                    errors.append("receipt envelope_ref does not match canonical envelope digest")

                checkpoint: dict[str, Any] | None = None
                if checkpoint_path.exists() or checkpoint_path.is_symlink():
                    checkpoint, chk_errors = _load_json(checkpoint_path, "canonical Deep Agents checkpoint")
                    errors.extend(chk_errors)
                    if checkpoint is not None:
                        errors.extend(validate_deepagents_checkpoint(checkpoint))
                        if not _ref_digest_matches(receipt.get("checkpoint_ref"), checkpoint):
                            errors.append("receipt checkpoint_ref does not match canonical checkpoint digest")

                exec_events = [
                    event
                    for event in events
                    if event.get("event_type")
                    in (
                        "deepagents_runtime_executed",
                        "deepagents_runtime_failed",
                        "deepagents_runtime_interrupted",
                    )
                ]
                if len(exec_events) != 1:
                    errors.append("canonical Deep Agents custody requires exactly one terminal execution event")
                else:
                    exec_event = exec_events[0]
                    if exec_event.get("session_id") != session_id:
                        errors.append("terminal execution event session_id does not match run")
                    rec_matches = [
                        ref
                        for ref in exec_event.get("subject_refs", [])
                        if isinstance(ref, dict)
                        and ref.get("role") in ("deepagents_execution_receipt", "execution_receipt")
                        and ref.get("path") == str(receipt_path)
                    ]
                    if len(rec_matches) != 1 or not _ref_digest_matches(rec_matches[0], receipt):
                        errors.append(f"{receipt_path}: terminal execution event does not bind exact receipt digest")

    return list(dict.fromkeys(errors))


def persist_deepagents_start(
    *,
    artifact_root: Path,
    session_id: str,
    work_plan: dict[str, Any],
    envelope: dict[str, Any],
    candidate: dict[str, Any] | None = None,
    approval: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist and event-bind a governed Deep Agents delegation start."""
    plan_errors = validate_deepagents_work_plan(work_plan)
    env_kind = envelope.get("kind")
    if env_kind == DEEPAGENTS_RUN_ENVELOPE_KIND:
        env_errors = validate_deepagents_run_envelope(envelope)
    elif env_kind == DEEPAGENTS_RUNTIME_ENVELOPE_KIND:
        env_errors = validate_deepagents_runtime_envelope(envelope)
    else:
        env_errors = [f"invalid envelope kind: {env_kind}"]

    errors = [*plan_errors, *env_errors]

    cand_errors: list[str] = []
    if candidate is not None:
        cand_errors = validate_deepagents_execution_candidate(candidate)
        errors.extend(cand_errors)

    app_errors: list[str] = []
    if approval is not None:
        app_errors = validate_deepagents_execution_approval(approval)
        errors.extend(app_errors)

    if errors:
        raise ValueError("invalid Deep Agents start custody: " + "; ".join(errors))

    _validate_identity(envelope, session_id, "Deep Agents run envelope")

    session_dir = deepagents_session_dir(artifact_root, session_id)
    plan_path = session_dir / "work_plan.json"
    envelope_path = session_dir / "envelope.json"
    candidate_path = session_dir / "candidate.json"
    approval_path = session_dir / "approval.json"

    to_persist = [(plan_path, work_plan), (envelope_path, envelope)]
    if candidate is not None:
        to_persist.append((candidate_path, candidate))
    if approval is not None:
        to_persist.append((approval_path, approval))

    _require_new(tuple(p for p, _ in to_persist))
    for p, val in to_persist:
        _persist_new_json(p, val)

    subject_refs = [
        _custody_artifact_ref(
            work_plan,
            path=plan_path,
            role="deepagents_work_plan",
            name="governed work plan",
        ),
        _custody_artifact_ref(
            envelope,
            path=envelope_path,
            role="deepagents_run_envelope"
            if env_kind == DEEPAGENTS_RUN_ENVELOPE_KIND
            else "deepagents_runtime_envelope",
            name="run envelope",
        ),
    ]
    if candidate is not None:
        subject_refs.append(
            _custody_artifact_ref(
                candidate,
                path=candidate_path,
                role="deepagents_execution_candidate",
                name="execution candidate",
            )
        )
    if approval is not None:
        subject_refs.append(
            _custody_artifact_ref(
                approval,
                path=approval_path,
                role="deepagents_execution_approval",
                name="execution approval",
            )
        )

    return append_runtime_event(
        events_dir=session_dir.parent / "events",
        session_id=session_id,
        event_type="deepagents_runtime_started",
        message="Governed Deep Agents delegation started",
        command_surface="builder delegate",
        subject_refs=subject_refs,
        decision_result="executed",
    )


def persist_deepagents_execution(
    *,
    artifact_root: Path,
    session_id: str,
    execution_receipt: dict[str, Any],
    checkpoint: dict[str, Any] | None = None,
    success: bool = True,
) -> dict[str, Any]:
    """Persist and event-bind a governed Deep Agents delegation execution outcome.

    Refuses PROJECTED_ONLY subagent receipts.
    """
    rec_state = execution_receipt.get("receipt_state")
    rec_kind = execution_receipt.get("kind")
    if rec_state == "PROJECTED_ONLY" or rec_kind == "builder_ii.deepagents_subagent_execution_receipt":
        raise ValueError("PROJECTED_ONLY receipt cannot be persisted as runtime execution evidence")

    receipt_errors = validate_deepagents_execution_receipt(execution_receipt)
    if receipt_errors:
        raise ValueError("invalid Deep Agents execution receipt: " + "; ".join(receipt_errors))

    if execution_receipt.get("session_id") and execution_receipt.get("session_id") != session_id:
        raise ValueError("Deep Agents execution receipt session_id does not match governed run")

    chk_errors: list[str] = []
    if checkpoint is not None:
        chk_errors = validate_deepagents_checkpoint(checkpoint)
        if chk_errors:
            raise ValueError("invalid Deep Agents checkpoint: " + "; ".join(chk_errors))

    session_dir = deepagents_session_dir(artifact_root, session_id)
    receipt_path = session_dir / "receipt.json"
    checkpoint_path = session_dir / "checkpoint.json"

    to_persist = [(receipt_path, execution_receipt)]
    if checkpoint is not None:
        to_persist.append((checkpoint_path, checkpoint))

    _require_new(tuple(p for p, _ in to_persist))
    for p, val in to_persist:
        _persist_new_json(p, val)

    if rec_state == "CHECKPOINTED":
        event_type = "deepagents_runtime_interrupted"
        decision_result = "interrupted"
        message = "Governed Deep Agents delegation checkpointed on interrupt"
    elif rec_state == "FAILED" or not success:
        event_type = "deepagents_runtime_failed"
        decision_result = "failed"
        message = "Governed Deep Agents delegation failed"
    else:
        event_type = "deepagents_runtime_executed"
        decision_result = "executed"
        message = "Governed Deep Agents delegation completed"

    subject_refs = [
        _custody_artifact_ref(
            execution_receipt,
            path=receipt_path,
            role="deepagents_execution_receipt",
            name="execution receipt",
        ),
    ]
    if checkpoint is not None:
        subject_refs.append(
            _custody_artifact_ref(
                checkpoint,
                path=checkpoint_path,
                role="deepagents_checkpoint",
                name="execution checkpoint",
            )
        )

    return append_runtime_event(
        events_dir=session_dir.parent / "events",
        session_id=session_id,
        event_type=event_type,
        message=message,
        command_surface="builder delegate",
        subject_refs=subject_refs,
        decision_result=decision_result,
    )
