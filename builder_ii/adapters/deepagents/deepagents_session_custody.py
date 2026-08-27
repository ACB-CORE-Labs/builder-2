"""Canonical persisted custody for governed Deep Agents session lifecycle evidence.

This adapter writes only beneath an already-admitted Builder-II artifact root.
Receipt and envelope files are persisted and revalidated before hash-linked
lifecycle events refer to them.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    validate_deepagents_runtime_envelope,
    validate_deepagents_subagent_execution_receipt,
    validate_deepagents_work_plan,
)
from builder_ii.governance.ledger.event_ledger import load_event_records, validate_event_chain_integrity
from builder_ii.governance.ledger.workflow_records import artifact_ref
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


def _validate_identity(value: dict[str, Any], session_id: str, label: str) -> None:
    if value.get("session_id") != session_id:
        raise ValueError(f"{label} session_id does not match governed run")


def _load_json(path: Path, label: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        if path.is_symlink() or not path.is_file():
            return None, [f"{label} is missing or is a symlink"]
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{label} is unreadable: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{label} must be a JSON object"]
    return value, []


def validate_deepagents_session_custody(artifact_root: Path, session_id: str) -> list[str]:
    """Independently reconstruct the canonical Deep Agents lifecycle artifacts and events."""
    try:
        session_dir = deepagents_session_dir(artifact_root, session_id)
        directory_fd = open_directory_nofollow(session_dir, create=False)
        os.close(directory_fd)
    except (OSError, ValueError) as exc:
        return [f"canonical Deep Agents session namespace is invalid: {exc}"]

    errors: list[str] = []
    plan_path = session_dir / "work_plan.json"
    envelope_path = session_dir / "envelope.json"
    receipt_path = session_dir / "receipt.json"

    plan, plan_errors = _load_json(plan_path, "canonical Deep Agents work plan")
    envelope, env_errors = _load_json(envelope_path, "canonical Deep Agents runtime envelope")
    errors.extend(plan_errors)
    errors.extend(env_errors)

    if plan is not None:
        errors.extend(validate_deepagents_work_plan(plan))
        if plan.get("session_id") and plan.get("session_id") != session_id:
            errors.append("canonical Deep Agents work plan session_id does not match run")

    if envelope is not None:
        errors.extend(validate_deepagents_runtime_envelope(envelope))
        if envelope.get("session_id") != session_id:
            errors.append("canonical Deep Agents runtime envelope session_id does not match run")

    events_dir = session_dir.parent / "events"
    integrity = validate_event_chain_integrity(events_dir)
    if not integrity.get("valid"):
        errors.extend(str(error) for error in integrity.get("errors", []))

    events = [event for event, _ in load_event_records(events_dir)]
    if plan is not None and envelope is not None:
        start_matches = [
            (event, ref)
            for event in events
            if event.get("event_type") == "deepagents_runtime_started"
            for ref in event.get("subject_refs", [])
            if isinstance(ref, dict)
            and ref.get("role") == "deepagents_work_plan"
            and ref.get("path") == str(plan_path)
        ]
        if len(start_matches) != 1:
            errors.append(f"{plan_path}: expected exactly one deepagents_runtime_started binding")
        elif (
            start_matches[0][0].get("session_id") != session_id
            or start_matches[0][1].get("kind") != plan.get("kind")
            or start_matches[0][1].get("sha256")
            != artifact_ref(plan, path=plan_path, role="deepagents_work_plan")["sha256"]
        ):
            errors.append(f"{plan_path}: deepagents_runtime_started binding does not match canonical custody")

    if receipt_path.exists() or receipt_path.is_symlink():
        receipt, rec_errors = _load_json(receipt_path, "canonical Deep Agents execution receipt")
        errors.extend(rec_errors)
        if receipt is not None:
            errors.extend(validate_deepagents_subagent_execution_receipt(receipt))
            if receipt.get("session_id") and receipt.get("session_id") != session_id:
                errors.append("canonical Deep Agents receipt session_id does not match run")

            exec_events = [
                event
                for event in events
                if event.get("event_type") in ("deepagents_runtime_executed", "deepagents_runtime_failed")
            ]
            if len(exec_events) != 1:
                errors.append("canonical Deep Agents custody requires exactly one terminal execution event")

    return list(dict.fromkeys(errors))


def persist_deepagents_start(
    *,
    artifact_root: Path,
    session_id: str,
    work_plan: dict[str, Any],
    envelope: dict[str, Any],
) -> dict[str, Any]:
    """Persist and event-bind a governed Deep Agents delegation start."""
    plan_errors = validate_deepagents_work_plan(work_plan)
    env_errors = validate_deepagents_runtime_envelope(envelope)
    errors = [*plan_errors, *env_errors]
    if errors:
        raise ValueError("invalid Deep Agents start custody: " + "; ".join(errors))

    _validate_identity(envelope, session_id, "Deep Agents runtime envelope")

    session_dir = deepagents_session_dir(artifact_root, session_id)
    plan_path = session_dir / "work_plan.json"
    envelope_path = session_dir / "envelope.json"

    _require_new((plan_path, envelope_path))
    _persist_new_json(plan_path, work_plan)
    _persist_new_json(envelope_path, envelope)

    return append_runtime_event(
        events_dir=session_dir.parent / "events",
        session_id=session_id,
        event_type="deepagents_runtime_started",
        message="Governed Deep Agents delegation started",
        command_surface="builder delegate",
        subject_refs=[
            artifact_ref(
                work_plan,
                path=plan_path,
                role="deepagents_work_plan",
                name="governed work plan",
            ),
            artifact_ref(
                envelope,
                path=envelope_path,
                role="deepagents_runtime_envelope",
                name="runtime envelope",
            ),
        ],
        decision_result="executed",
    )


def persist_deepagents_execution(
    *,
    artifact_root: Path,
    session_id: str,
    execution_receipt: dict[str, Any],
    success: bool = True,
) -> dict[str, Any]:
    """Persist and event-bind a governed Deep Agents delegation execution outcome."""
    receipt_errors = validate_deepagents_subagent_execution_receipt(execution_receipt)
    if receipt_errors:
        raise ValueError("invalid Deep Agents execution receipt: " + "; ".join(receipt_errors))

    if execution_receipt.get("session_id") and execution_receipt.get("session_id") != session_id:
        raise ValueError("Deep Agents execution receipt session_id does not match governed run")

    session_dir = deepagents_session_dir(artifact_root, session_id)
    receipt_path = session_dir / "receipt.json"

    _require_new((receipt_path,))
    _persist_new_json(receipt_path, execution_receipt)

    event_type = "deepagents_runtime_executed" if success else "deepagents_runtime_failed"
    message = "Governed Deep Agents delegation completed" if success else "Governed Deep Agents delegation failed"

    return append_runtime_event(
        events_dir=session_dir.parent / "events",
        session_id=session_id,
        event_type=event_type,
        message=message,
        command_surface="builder delegate",
        subject_refs=[
            artifact_ref(
                execution_receipt,
                path=receipt_path,
                role="deepagents_execution_receipt",
                name="execution receipt",
            ),
        ],
        decision_result="executed" if success else "failed",
    )
