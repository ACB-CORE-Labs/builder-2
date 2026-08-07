"""One append-point for a governed session's hash-chained event ledger.

Three writers now share a session's ``events/`` directory: the governed MCP server's tool-call
path, its gated-apply path, and the Goose runtime harness's lifecycle events. Each one had
grown its own copy of the same six-step shape -- load the tail, derive ``sequence`` from its
length, build a ``previous_event_ref`` from the last record, replay for the current stage,
validate, write -- and each copy computed ``sequence = len(existing) + 1`` outside any critical
section.

That is a chain fork waiting for contention. Two writers that read the same tail both mint
sequence *n*, both point ``previous_event_ref`` at the same predecessor, and the ledger now has
two branches from one parent -- which is indistinguishable, after the fact, from tampering. The
same shape already forked the TUI audit ledger once; `tui_audit_ledger.append_run_to_index`
carries the measurement and the lock that fixed it. This module does not re-learn that lesson:
:func:`session_event_append` holds an exclusive ``flock`` across read-tail-then-append, so the
whole derive-and-write is one critical section.

Note that the obvious concurrency test passes without the lock -- the window only opens under
real contention, which is exactly why the lock is structural here rather than left to callers.

This is a ledger, not authority. It records what a governed lane did; it grants nothing, and
``artifact != authority`` holds unchanged.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator

from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    create_event_record,
    load_event_records,
    replay_events,
    validate_event_record,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest

try:  # pragma: no cover - both macOS and Linux have fcntl
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

_LOCK_FILENAME = ".events.lock"


def session_dir_for(builder_root: Path, session_id: str) -> Path:
    """The session root the run cockpit tails: ``<builder_root>/sessions/<session_id>``."""
    return Path(builder_root) / "sessions" / session_id


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def artifact_ref(data: dict[str, Any], path: Path, role: str) -> dict[str, Any]:
    """A digest-bound reference to an artifact on disk, in the shape event records expect."""
    return {
        "kind": data.get("kind"),
        "path": str(path),
        "sha256": canonical_digest(data),
        "role": role,
        "name": role.replace("_", " "),
        "required": True,
    }


def previous_event_ref(existing: list[tuple[dict[str, Any], Path]]) -> dict[str, Any] | None:
    """Bind the tail record so each link commits to its predecessor, or None for a first event."""
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
    """Hold an exclusive advisory lock for the whole read-tail-then-append critical section."""
    if fcntl is None:  # pragma: no cover - both supported platforms have fcntl
        raise RuntimeError(
            "fcntl.flock is unavailable on this platform; refusing to append to a session event "
            "ledger unlocked, because concurrent appends fork the chain and the fork is "
            "indistinguishable from tampering"
        )
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    try:
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass
class SessionEventAppender:
    """The state a caller needs to write its sidecar artifacts at the sequence it will use.

    Sidecar files (policy snapshot, call envelope, execution receipt) are named by ``sequence``
    and must be written *before* the event that references them -- so the sequence is exposed
    rather than hidden, and the whole span stays inside the lock.
    """

    session_id: str
    session_dir: Path
    mcp_dir: Path
    events_dir: Path
    sequence: int
    current_stage: str
    existing: list[tuple[dict[str, Any], Path]] = field(default_factory=list)

    def write_policy_snapshot(self, policy: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        """Write this event's policy snapshot and return its path plus a digest-bound ref."""
        policy_path = self.mcp_dir / f"{self.sequence:03d}_policy.json"
        _write_json(policy_path, policy)
        return policy_path, artifact_ref(policy, policy_path, "mcp_tool_policy")

    def write_sidecar(self, data: dict[str, Any], suffix: str, role: str) -> tuple[Path, dict[str, Any]]:
        """Write a sequence-named sidecar artifact and return its path plus a digest-bound ref."""
        path = self.mcp_dir / f"{self.sequence:03d}_{suffix}.json"
        _write_json(path, data)
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
        """Validate and write one chained event at this appender's sequence."""
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
        write_event_record(event, event_path)
        return event_path


@contextmanager
def session_event_append(builder_root: Path, session_id: str) -> Iterator[SessionEventAppender]:
    """Hold the session's append lock and yield the appender for the next sequence.

    Everything a writer does between reading the tail and writing its event belongs inside this
    block -- deriving the sequence, writing sequence-named sidecars, and appending the record --
    because that whole span is what concurrent writers would otherwise interleave.
    """
    session_dir = session_dir_for(builder_root, session_id)
    mcp_dir = session_dir / "mcp"
    events_dir = session_dir / "events"
    mcp_dir.mkdir(parents=True, exist_ok=True)
    events_dir.mkdir(parents=True, exist_ok=True)

    lock_path = events_dir / _LOCK_FILENAME
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        with _exclusive_lock(lock_handle):
            existing = load_event_records(events_dir)
            current_stage = "initialized"
            if existing:
                replay = replay_events(existing, session_id=session_id)
                if replay.get("valid"):
                    current_stage = str(replay.get("current_stage") or "initialized")

            yield SessionEventAppender(
                session_id=session_id,
                session_dir=session_dir,
                mcp_dir=mcp_dir,
                events_dir=events_dir,
                sequence=len(existing) + 1,
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
    """Append one chained lifecycle event, snapshotting the policy it ran under.

    The convenience path for writers with no sequence-named sidecars of their own (the Goose
    runtime harness's start/close events). Writers that must place sidecars at the same sequence
    use :func:`session_event_append` directly.
    """
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
