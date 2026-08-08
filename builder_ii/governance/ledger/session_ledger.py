"""Atomic append authority for one governed session's hash-chained event ledger.

The governed MCP server and Goose wrapper share one event chain.  Concurrent writers are
serialized with ``flock`` and each event is committed under three coupled invariants:

1. sequence/predecessor derivation happens while the exclusive lock is held;
2. sidecars and JSON event mirrors are atomically replaced from same-directory temp files;
3. a compact tail checkpoint binds the last event digest and the exact WAL byte size.

The WAL-size binding closes the crash window that matters for an O(1) tail: if a process
dies after the WAL accepted an event but before the tail advances, the next writer sees
``wal_size != checkpoint.wal_size`` and performs a full replay before choosing a sequence.
Normal appends therefore validate one tail/event plus one ``stat`` instead of replaying the
entire chain on every tool call.  Full replay remains the recovery and close-time authority.

This ledger records authority-bearing work; it never grants authority itself.
"""

from __future__ import annotations

import json
import os
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from builder_ii.core.atomic_artifacts import atomic_write_json
from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    create_event_record,
    load_event_records,
    replay_events,
    validate_event_record,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest

try:  # pragma: no cover - both supported Unix platforms have fcntl
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

_LOCK_FILENAME = ".events.lock"
_TAIL_FILENAME = ".event-tail.json"
_TAIL_KIND = "builder_ii.session_event_tail"
_TAIL_SCHEMA_VERSION = "1.0.0"


def session_dir_for(builder_root: Path, session_id: str) -> Path:
    return Path(builder_root) / "sessions" / session_id


def artifact_ref(data: dict[str, Any], path: Path, role: str) -> dict[str, Any]:
    return {
        "kind": data.get("kind"),
        "path": str(path),
        "sha256": canonical_digest(data),
        "role": role,
        "name": role.replace("_", " "),
        "required": True,
    }


def previous_event_ref(existing: list[tuple[dict[str, Any], Path]]) -> dict[str, Any] | None:
    if not existing:
        return None
    last_event, last_path = existing[-1]
    return {
        "role": "event",
        "kind": EVENT_RECORD_KIND,
        "path": str(last_path),
        "sha256": canonical_digest(last_event),
        "name": str(last_event.get("event_type", "")),
        "required": True,
    }


@contextmanager
def _exclusive_lock(handle: Any) -> Iterator[None]:
    if fcntl is None:  # pragma: no cover
        raise RuntimeError(
            "fcntl.flock is unavailable; refusing an unlocked session-ledger append because "
            "concurrent sequence derivation can fork the evidence chain"
        )
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _wal_size(events_dir: Path) -> int:
    path = events_dir / "events.wal"
    try:
        return path.stat().st_size
    except OSError:
        return 0


def _fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        try:
            os.fsync(fd)
        except OSError:
            pass
    finally:
        os.close(fd)


def _commit_event_with_wal(event: dict[str, Any], event_path: Path) -> int:
    """Append the WAL and atomically install the JSON mirror, or raise.

    ``write_event_record`` appends the WAL after writing its output path.  We point it at a
    temporary sibling, verify that the WAL actually advanced (session evidence does not accept
    the module's legacy best-effort WAL semantics), fsync the temp, then rename it into place.
    A crash after WAL append but before rename is recovered from the WAL on the next append.
    """
    event_path.parent.mkdir(parents=True, exist_ok=True)
    before = _wal_size(event_path.parent)
    temp_path = event_path.parent / f".{event_path.name}.{uuid.uuid4().hex}.tmp"
    try:
        write_event_record(event, temp_path)
        after = _wal_size(event_path.parent)
        if after <= before:
            raise OSError("session event WAL did not advance; refusing an uncommitted event")
        with temp_path.open("rb") as handle:
            os.fsync(handle.fileno())
        os.replace(temp_path, event_path)
        _fsync_directory(event_path.parent)
        return after
    except Exception:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def _tail_path(session_dir: Path) -> Path:
    return session_dir / _TAIL_FILENAME


def _tail_payload(
    *,
    session_id: str,
    event: dict[str, Any],
    event_path: Path,
    wal_size: int,
) -> dict[str, Any]:
    return {
        "kind": _TAIL_KIND,
        "schema_version": _TAIL_SCHEMA_VERSION,
        "session_id": session_id,
        "sequence": int(event["sequence"]),
        "current_stage": str(event["stage"]),
        "event_path": str(event_path),
        "event_sha256": canonical_digest(event),
        "wal_size": wal_size,
    }


def _write_tail(
    *,
    session_dir: Path,
    session_id: str,
    event: dict[str, Any],
    event_path: Path,
    wal_size: int,
) -> None:
    atomic_write_json(
        _tail_path(session_dir),
        _tail_payload(
            session_id=session_id,
            event=event,
            event_path=event_path,
            wal_size=wal_size,
        ),
    )


def _read_valid_tail(
    *, session_dir: Path, events_dir: Path, session_id: str
) -> tuple[dict[str, Any], Path, str] | None:
    path = _tail_path(session_dir)
    try:
        tail = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(tail, dict):
        return None
    if tail.get("kind") != _TAIL_KIND or tail.get("schema_version") != _TAIL_SCHEMA_VERSION:
        return None
    if tail.get("session_id") != session_id:
        return None
    sequence = tail.get("sequence")
    stage = tail.get("current_stage")
    digest = tail.get("event_sha256")
    event_path_raw = tail.get("event_path")
    wal_size = tail.get("wal_size")
    if not isinstance(sequence, int) or sequence < 1:
        return None
    if not isinstance(stage, str) or not stage:
        return None
    if not isinstance(digest, str) or len(digest) != 64:
        return None
    if not isinstance(event_path_raw, str) or not event_path_raw:
        return None
    if not isinstance(wal_size, int) or wal_size <= 0:
        return None
    if _wal_size(events_dir) != wal_size:
        # The WAL changed without the tail changing: a crash/interrupted append must replay.
        return None

    event_path = Path(event_path_raw)
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return None
    if not isinstance(event, dict):
        return None
    if event.get("session_id") != session_id or event.get("sequence") != sequence:
        return None
    if canonical_digest(event) != digest:
        return None
    if validate_event_record(event):
        return None
    return event, event_path, stage


def _recover_chain_state(
    *, session_dir: Path, events_dir: Path, session_id: str
) -> tuple[list[tuple[dict[str, Any], Path]], str]:
    """Full-replay recovery used only when no trustworthy constant-time tail exists."""
    existing = load_event_records(events_dir)
    if not existing:
        return [], "initialized"
    replay = replay_events(existing, session_id=session_id)
    if not replay.get("valid"):
        raise ValueError(f"session event chain failed recovery replay: {replay.get('errors', [])}")

    last_event, reported_path = existing[-1]
    sequence = int(last_event["sequence"])
    # WAL-backed load_event_records synthesizes a path. Recover/locate the durable JSON mirror
    # so future predecessor refs name something an operator can actually inspect.
    event_path = reported_path if reported_path.exists() else events_dir / f"{sequence:03d}_{last_event['event_type']}.json"
    if not event_path.exists():
        atomic_write_json(event_path, last_event)

    _write_tail(
        session_dir=session_dir,
        session_id=session_id,
        event=last_event,
        event_path=event_path,
        wal_size=_wal_size(events_dir),
    )
    return [(last_event, event_path)], str(replay.get("current_stage") or "initialized")


@dataclass
class SessionEventAppender:
    session_id: str
    session_dir: Path
    mcp_dir: Path
    events_dir: Path
    sequence: int
    current_stage: str
    existing: list[tuple[dict[str, Any], Path]] = field(default_factory=list)

    def write_policy_snapshot(self, policy: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        policy_path = self.mcp_dir / f"{self.sequence:03d}_policy.json"
        atomic_write_json(policy_path, policy, sort_keys=False)
        return policy_path, artifact_ref(policy, policy_path, "mcp_tool_policy")

    def write_sidecar(
        self, data: dict[str, Any], suffix: str, role: str
    ) -> tuple[Path, dict[str, Any]]:
        path = self.mcp_dir / f"{self.sequence:03d}_{suffix}.json"
        atomic_write_json(path, data, sort_keys=False)
        return path, artifact_ref(data, path, role)

    def append(
        self,
        *,
        event_id: str,
        event_type: str,
        command_surface: str,
        policy_snapshot_ref: dict[str, Any],
        subject_refs: list[dict[str, Any]] | None = None,
        message: str = "",
        decision_result: str = "recorded",
        filename: str | None = None,
    ) -> Path:
        event = create_event_record(
            event_id=event_id,
            session_id=self.session_id,
            sequence=self.sequence,
            event_type=event_type,
            stage=self.current_stage,
            subject_refs=list(subject_refs or []),
            command_surface=command_surface,
            policy_snapshot_ref=policy_snapshot_ref,
            previous_event_ref=previous_event_ref(self.existing),
            message=message,
            decision_result=decision_result,
        )
        errors = validate_event_record(event)
        if errors:
            raise ValueError(f"event validation failed: {errors}")
        event_path = self.events_dir / (filename or f"{self.sequence:03d}_{event_type}.json")
        wal_size = _commit_event_with_wal(event, event_path)
        _write_tail(
            session_dir=self.session_dir,
            session_id=self.session_id,
            event=event,
            event_path=event_path,
            wal_size=wal_size,
        )
        # Keep the appender internally coherent if a caller appends more than once while it owns
        # the lock, even though normal callers use one event per context.
        self.existing = [(event, event_path)]
        self.current_stage = str(event["stage"])
        self.sequence += 1
        return event_path


@contextmanager
def session_event_append(builder_root: Path, session_id: str) -> Iterator[SessionEventAppender]:
    """Hold the session lock across sequence derivation, sidecars, event commit and tail."""
    session_dir = session_dir_for(builder_root, session_id)
    mcp_dir = session_dir / "mcp"
    events_dir = session_dir / "events"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)

    lock_path = events_dir / _LOCK_FILENAME
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        with _exclusive_lock(lock_handle):
            tail = _read_valid_tail(
                session_dir=session_dir,
                events_dir=events_dir,
                session_id=session_id,
            )
            if tail is not None:
                last_event, last_path, current_stage = tail
                existing = [(last_event, last_path)]
            else:
                existing, current_stage = _recover_chain_state(
                    session_dir=session_dir,
                    events_dir=events_dir,
                    session_id=session_id,
                )

            sequence = int(existing[-1][0]["sequence"]) + 1 if existing else 1
            yield SessionEventAppender(
                session_id=session_id,
                session_dir=session_dir,
                mcp_dir=mcp_dir,
                events_dir=events_dir,
                sequence=sequence,
                current_stage=current_stage,
                existing=existing,
            )


def append_session_event(
    *,
    builder_root: Path,
    session_id: str,
    event_type: str,
    command_surface: str,
    policy: dict[str, Any],
    subject_refs: list[dict[str, Any]] | None = None,
    message: str = "",
    decision_result: str = "recorded",
    event_id_prefix: str = "evt",
) -> Path:
    with session_event_append(builder_root, session_id) as appender:
        _, policy_ref = appender.write_policy_snapshot(policy)
        return appender.append(
            event_id=f"{event_id_prefix}_{session_id}_{appender.sequence}",
            event_type=event_type,
            command_surface=command_surface,
            policy_snapshot_ref=policy_ref,
            subject_refs=subject_refs,
            message=message,
            decision_result=decision_result,
        )
