"""Shared runtime event append helper for gateway/seam (not CLI-only).

Appends hash-chained builder_ii.event_record entries under a session events dir.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from builder_ii.governance.ledger.event_ledger import (
    create_event_record,
    load_event_records,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import artifact_ref, canonical_digest


def _previous_event_ref(existing: list[tuple[dict[str, Any], Path]]) -> dict[str, Any] | None:
    if not existing:
        return None
    last_event, last_path = existing[-1]
    return {
        "role": "event",
        "kind": last_event.get("kind"),
        "path": str(last_path),
        "sha256": canonical_digest(last_event),
        "name": str(last_event.get("event_type", "")),
        "required": True,
    }


def append_runtime_event(
    *,
    events_dir: Path,
    session_id: str,
    event_type: str,
    message: str,
    command_surface: str,
    subject_refs: list[dict[str, Any]] | None = None,
    stage: str | None = None,
    policy_snapshot_ref: dict[str, Any] | None = None,
    decision_result: str = "recorded",
) -> dict[str, Any]:
    """Append one hash-chained event record. Returns the written event."""
    events_dir.mkdir(parents=True, exist_ok=True)
    existing = load_event_records(events_dir)
    # load_event_records may return unsorted if mixed; sort by sequence
    existing = sorted(
        existing,
        key=lambda item: (
            item[0].get("sequence") if isinstance(item[0].get("sequence"), int) else 10**9,
            str(item[1]),
        ),
    )
    sequence = len(existing) + 1
    current_stage = stage or "initialized"
    if existing and stage is None:
        last = existing[-1][0]
        if isinstance(last.get("stage"), str) and last["stage"]:
            current_stage = str(last["stage"])

    event_id = f"evt_rt_{int(time.time())}_{sequence}_{event_type}"
    prev = _previous_event_ref(existing)
    policy_ref = policy_snapshot_ref or {
        "role": "policy_snapshot",
        "kind": "builder_ii.runtime_policy_snapshot",
        "sha256": "0" * 64,
        "path": str(events_dir / "implicit_runtime_policy.json"),
        "name": "implicit_runtime",
        "required": False,
    }
    record = create_event_record(
        event_id=event_id,
        session_id=session_id,
        sequence=sequence,
        event_type=event_type,
        stage=current_stage,
        subject_refs=list(subject_refs or []),
        command_surface=command_surface,
        policy_snapshot_ref=policy_ref,
        previous_event_ref=prev,
        message=message,
        decision_result=decision_result,
    )
    out_path = events_dir / f"{sequence:03d}_{event_type}.json"
    write_event_record(record, out_path)
    return record


def append_model_call_event(
    *,
    events_dir: Path,
    session_id: str,
    event_type: str,
    envelope: dict[str, Any],
    receipt: dict[str, Any],
    envelope_path: Path,
    receipt_path: Path,
    command_surface: str,
    message: str,
) -> dict[str, Any]:
    env_ref = artifact_ref(
        envelope,
        path=envelope_path,
        role="model_call_envelope",
        name="model_call_envelope",
    )
    rec_ref = artifact_ref(
        receipt,
        path=receipt_path,
        role="model_call_receipt",
        name="model_call_receipt",
    )
    return append_runtime_event(
        events_dir=events_dir,
        session_id=session_id,
        event_type=event_type,
        message=message,
        command_surface=command_surface,
        subject_refs=[env_ref, rec_ref],
        decision_result="executed" if event_type == "model_call_executed" else "failed",
    )
