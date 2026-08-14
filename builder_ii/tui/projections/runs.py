"""Projection: the roster of runs on disk (T2b).

Observe-only. A "run" is a session with an event ledger under
``.builder/sessions/<id>/events/`` -- the same ledgers the governed MCP server (G1/G3) and
other governed lanes append to. Each row carries the run id, event count, last event, and the
whole-chain verdict from the canonical validator. Ordered most-recent first. Synthesizes
nothing: no sessions dir, or no ledgered runs, yields an empty roster.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from builder_ii.governance.ledger.event_ledger import (
    load_event_records,
    validate_event_chain_integrity,
)


@dataclass(frozen=True)
class RunRow:
    run_id: str
    events_dir: str
    event_count: int
    last_event_type: str
    last_recorded_at: str
    chain_valid: bool | None


@dataclass(frozen=True)
class RunRosterView:
    rows: tuple[RunRow, ...]

    @property
    def is_empty(self) -> bool:
        return not self.rows


def _sessions_root(builder_root: Path | None) -> Path | None:
    if builder_root is None:
        return None
    root = builder_root / "sessions"
    return root if root.is_dir() else None


def _sequence(event: dict) -> int:
    seq = event.get("sequence")
    return seq if isinstance(seq, int) else 10**9


def project_run_roster(builder_root: Path | None) -> RunRosterView:
    """Scan ``<builder_root>/sessions/*/events`` for ledgered runs, most-recent first."""
    root = _sessions_root(builder_root)
    if root is None:
        return RunRosterView(rows=())

    rows: list[RunRow] = []
    for session_dir in sorted(root.iterdir()):
        events_dir = session_dir / "events"
        if not events_dir.is_dir():
            continue
        records = load_event_records(events_dir)
        if not records:
            continue  # only sessions that actually have a ledger are runs
        ordered = sorted(records, key=lambda item: _sequence(item[0]))
        last = ordered[-1][0]
        integrity = validate_event_chain_integrity(events_dir)
        rows.append(
            RunRow(
                run_id=session_dir.name,
                events_dir=str(events_dir),
                event_count=len(ordered),
                last_event_type=str(last.get("event_type") or ""),
                last_recorded_at=str(last.get("recorded_at") or ""),
                chain_valid=bool(integrity.get("valid")),
            )
        )

    # ISO timestamps sort lexically; most-recent first, then run id for stability.
    rows.sort(key=lambda r: (r.last_recorded_at, r.run_id), reverse=True)
    return RunRosterView(rows=tuple(rows))
