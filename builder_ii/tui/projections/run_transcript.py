"""Projection: one run's event ledger as a chain-aware transcript.

Observe-only. Reads the hash-chained ``builder_ii.event_record`` files a run wrote (the same
chain the governed MCP server and the deepagents lane append to) and returns an immutable
view: sequence-ordered rows plus the whole-chain verdict from the canonical validator. It
synthesizes nothing — an empty directory yields an empty view, and chain validity comes
solely from :func:`validate_event_chain_integrity`, never from a heuristic here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.governance.ledger.event_ledger import (
    load_event_records,
    validate_event_chain_integrity,
)


@dataclass(frozen=True)
class TranscriptRow:
    """One event in the transcript. ``chain_ok`` is False when the canonical validator
    implicated this row's file in a chain break."""

    sequence: int
    recorded_at: str
    event_type: str
    message: str
    stage: str
    chain_ok: bool


@dataclass(frozen=True)
class RunTranscriptView:
    """Immutable projection of a run's event chain.

    ``chain_valid`` is ``None`` when there are no events (absence, not a verdict), else the
    boolean from :func:`validate_event_chain_integrity`.
    """

    run_id: str
    events_dir: str
    rows: tuple[TranscriptRow, ...]
    event_count: int
    chain_valid: bool | None
    chain_errors: tuple[str, ...]

    @property
    def is_empty(self) -> bool:
        return self.event_count == 0


def _sequence(event: dict[str, Any]) -> int:
    seq = event.get("sequence")
    return seq if isinstance(seq, int) else 10**9


def _row(event: dict[str, Any], path: Path, broken_paths: set[str]) -> TranscriptRow:
    seq = event.get("sequence")
    return TranscriptRow(
        sequence=seq if isinstance(seq, int) else -1,
        recorded_at=str(event.get("recorded_at") or event.get("timestamp") or "—"),
        event_type=str(event.get("event_type") or "unknown"),
        message=str(event.get("message") or event.get("summary") or ""),
        stage=str(event.get("stage") or ""),
        chain_ok=str(path) not in broken_paths,
    )


def project_run_transcript(events_dir: Path, *, run_id: str | None = None) -> RunTranscriptView:
    """Project the event records under ``events_dir`` into a chain-aware transcript view."""
    resolved_run_id = run_id or events_dir.parent.name or events_dir.name
    ordered = sorted(load_event_records(events_dir), key=lambda item: _sequence(item[0]))

    if not ordered:
        return RunTranscriptView(
            run_id=resolved_run_id,
            events_dir=str(events_dir),
            rows=(),
            event_count=0,
            chain_valid=None,
            chain_errors=(),
        )

    integrity = validate_event_chain_integrity(events_dir)
    errors = tuple(str(e) for e in integrity.get("errors", []))
    # Chain-break error strings are formatted "<path>: <reason>"; map them back to rows.
    broken_paths = {err.split(":", 1)[0] for err in errors if ":" in err}
    rows = tuple(_row(event, path, broken_paths) for event, path in ordered)

    return RunTranscriptView(
        run_id=resolved_run_id,
        events_dir=str(events_dir),
        rows=rows,
        event_count=len(ordered),
        chain_valid=bool(integrity.get("valid")),
        chain_errors=errors,
    )
