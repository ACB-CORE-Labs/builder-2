"""Live, chain-aware transcript of one run's event ledger (T2a).

Observe-only: it tails the ``event_record`` chain a run wrote and appends new records as they
land — the streaming-run view a frontier console has, but sourced entirely from a ledger the
run itself produced. It never dispatches, writes, or synthesizes progress: an empty run shows
an honest empty state, and a chain break is rendered explicitly rather than hidden.

This widget is mountable on its own (and unit-tested that way); the run cockpit (T2b) embeds
it against a selected run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.widgets import RichLog, Static

from builder_ii.tui.projections.render import bold_themed, themed
from builder_ii.tui.projections.run_transcript import (
    RunTranscriptView,
    TranscriptRow,
    project_run_transcript,
)


def _event_glyph(event_type: str) -> str:
    et = event_type.lower()
    if any(k in et for k in ("fail", "error", "deny", "denied", "refus")):
        return themed("fail", "✗")
    if any(k in et for k in ("gate", "hitl", "approv", "reject")):
        return themed("warn", "⚡")
    if any(k in et for k in ("model", "llm", "mcp", "tool", "inference")):
        return themed("accent", "•")
    if any(k in et for k in ("pass", "verify", "complete", "executed", "recorded")):
        return themed("pass", "✓")
    return themed("hint", "·")


def _short_time(recorded_at: str) -> str:
    """HH:MM:SS from an ISO timestamp, without parsing (deterministic, no clock read)."""
    if "T" in recorded_at:
        return recorded_at.split("T", 1)[1].replace("Z", "")[:8]
    return recorded_at[:8]


class RunTranscript(Vertical):
    """A RichLog that tails one run's hash-chained event ledger. Observe-only."""

    def __init__(
        self, events_dir: Path | None = None, run_id: str | None = None, **kwargs: Any
    ) -> None:
        super().__init__(id="run-transcript", **kwargs)
        self._events_dir = events_dir
        self._run_id = run_id
        self._log: RichLog | None = None
        self._title: Static | None = None
        self._seen: set[int] = set()
        self._empty_written = False
        self._last_chain_valid: bool | None = None

    def compose(self) -> ComposeResult:
        self._title = Static(self._title_text(None), id="run-transcript-title")
        yield self._title
        self._log = RichLog(
            id="run-transcript-log", highlight=True, markup=True, wrap=True, max_lines=500
        )
        yield self._log

    def on_mount(self) -> None:
        self.refresh_from_disk()

    def set_run(self, events_dir: Path, run_id: str | None = None) -> None:
        """Point the transcript at a different run and reset the tail."""
        self._events_dir = events_dir
        self._run_id = run_id
        self._seen.clear()
        self._empty_written = False
        self._last_chain_valid = None
        if self._log is not None:
            self._log.clear()
        self.refresh_from_disk()

    def project(self) -> RunTranscriptView | None:
        if self._events_dir is None:
            return None
        return project_run_transcript(self._events_dir, run_id=self._run_id)

    def refresh_from_disk(self) -> None:
        """Re-project and append only records not yet shown; mark chain breaks explicitly."""
        if self._log is None:
            return
        view = self.project()
        if self._title is not None:
            self._title.update(self._title_text(view))

        if view is None or view.is_empty:
            if not self._empty_written:
                self._log.write(themed("dim", "  awaiting events…"))
                self._empty_written = True
            return

        if self._empty_written:
            self._log.clear()
            self._empty_written = False

        for row in view.rows:
            if row.sequence in self._seen:
                continue
            self._seen.add(row.sequence)
            self._log.write(self._line(row))

        if view.chain_valid is False and self._last_chain_valid is not False:
            self._log.write(bold_themed("fail", "  ✗ chain integrity broken — see validator errors"))
        self._last_chain_valid = view.chain_valid

    def _line(self, row: TranscriptRow) -> str:
        seq = themed("dim", f"{row.sequence:>3}")
        ts = themed("dim", _short_time(row.recorded_at))
        glyph = _event_glyph(row.event_type)
        etype = themed("bold", row.event_type[:18])
        marker = "" if row.chain_ok else themed("fail", " ✗chain")
        message = themed("hint", row.message[:60]) if row.message else ""
        return f"  {seq} {ts} {glyph} {etype}{marker}  {message}"

    def _title_text(self, view: RunTranscriptView | None) -> str:
        run_id = (view.run_id if view else self._run_id) or "—"
        if view is None:
            state = ""
        elif view.chain_valid is None:
            state = themed("dim", "  no events")
        elif view.chain_valid:
            state = themed("pass", f"  ✓ chain valid · {view.event_count}")
        else:
            state = themed("fail", f"  ✗ chain broken · {view.event_count}")
        return f"{bold_themed('active', 'TRANSCRIPT')} {themed('hint', run_id)}{state}"
