"""Shared runtime event append helper for gateway/seam (not CLI-only).

Appends hash-chained builder_ii.event_record entries under a session events dir.
"""

from __future__ import annotations

import os
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

try:  # macOS and Linux both provide fcntl.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

from builder_ii.governance.ledger.event_ledger import (
    create_event_record,
    load_event_records,
    replay_events,
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


def open_directory_nofollow(path: Path, *, create: bool = True) -> int:
    """Open/create an absolute directory one component at a time without following symlinks."""
    absolute = path.absolute()
    parts = absolute.parts
    if not parts or parts[0] != absolute.anchor:
        raise ValueError(f"event directory must be absolute: {path}")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(absolute.anchor, flags)
    try:
        for part in parts[1:]:
            if create:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=fd)
                except FileExistsError:
                    pass
            next_fd = os.open(part, flags, dir_fd=fd)
            info = os.fstat(next_fd)
            if not stat.S_ISDIR(info.st_mode):
                os.close(next_fd)
                raise ValueError(f"event namespace component is not a directory: {path}")
            os.close(fd)
            fd = next_fd
        return fd
    except Exception:
        os.close(fd)
        raise


@contextmanager
def _locked_events_dir(events_dir: Path) -> Iterator[int]:
    if fcntl is None:  # pragma: no cover
        raise RuntimeError("fcntl.flock is unavailable; refusing unlocked lifecycle append")
    directory_fd = open_directory_nofollow(events_dir)
    existing_flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        lock_fd = os.open(".runtime-event.lock", existing_flags, dir_fd=directory_fd)
    except FileNotFoundError:
        try:
            lock_fd = os.open(
                ".runtime-event.lock",
                os.O_CREAT | os.O_EXCL | os.O_RDWR,
                0o600,
                dir_fd=directory_fd,
            )
        except FileExistsError:
            lock_fd = os.open(".runtime-event.lock", existing_flags, dir_fd=directory_fd)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        yield directory_fd
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)
        os.close(directory_fd)


def _write_event_exclusive(
    *, events_dir: Path, directory_fd: int, filename: str, record: dict[str, Any]
) -> None:
    """Write the sole canonical JSON event while the caller holds the append lock."""
    wal_path = events_dir / "events.wal"
    if wal_path.is_symlink():
        raise ValueError(f"event WAL must not be a symlink: {wal_path}")
    from builder_ii.governance.ledger.event_ledger import dumps_event_record
    if wal_path.exists():
        raise ValueError(
            f"legacy event WAL must be reconciled and retired before canonical append: {wal_path}"
        )
    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_NOFOLLOW", 0)
    output_fd = os.open(filename, flags, 0o600, dir_fd=directory_fd)
    try:
        payload = dumps_event_record(record).encode("utf-8")
        with os.fdopen(output_fd, "wb", closefd=False) as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
    finally:
        os.close(output_fd)


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
    with _locked_events_dir(events_dir) as directory_fd:
        existing = sorted(
            load_event_records(events_dir),
            key=lambda item: (
                item[0].get("sequence") if isinstance(item[0].get("sequence"), int) else 10**9,
                str(item[1]),
            ),
        )
        replay = replay_events(existing, session_id=session_id)
        if existing and not replay.get("valid"):
            raise ValueError("refusing to append to invalid runtime event chain: " + "; ".join(replay["errors"]))
        sequence = int(existing[-1][0]["sequence"]) + 1 if existing else 1
        current_stage = stage or "initialized"
        if existing and stage is None:
            last = existing[-1][0]
            if isinstance(last.get("stage"), str) and last["stage"]:
                current_stage = str(last["stage"])

        event_id = f"evt_rt_{uuid.uuid4().hex}_{sequence}_{event_type}"
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
        filename = f"{sequence:03d}_{event_type}.json"
        _write_event_exclusive(
            events_dir=events_dir,
            directory_fd=directory_fd,
            filename=filename,
            record=record,
        )
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
