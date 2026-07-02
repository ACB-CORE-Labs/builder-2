"""Signal Rail — The right column of STRATUM.

Contains three sections:
  1. HITL Gate Indicator — always visible, pulses amber when gate is open
  2. Event Ledger (live) — tail of event_ledger events, color-coded
  3. Capability Rail — live snapshot of governance capability state
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.widgets import RichLog, Static

from builder_ii.tui.widgets.masterpiece import MechanicalSympathyHud

# ── Capability definitions ───────────────────────────────────────────

CAPABILITIES = [
    "model_exec",
    "shell_exec",
    "runtime",
    "mem_mutation",
    "source_writes",
    "target_writes",
]


# ── HITL Gate Indicator ──────────────────────────────────────────────

class HITLGateIndicator(Static):
    """Top-of-rail indicator for HITL gate status."""

    gate_open = reactive(False)
    gate_label = reactive("NO PENDING GATES")

    def render(self) -> str:
        if self.gate_open:
            return (
                "\n [bold #d29922]● HITL GATE OPEN[/]\n"
                f"   [#8b949e]{self.gate_label}[/]"
            )
        return (
            "\n [#3fb950]● ALL GATES CLEAR[/]\n"
            "   [#484f58]no pending authority[/]"
        )


# ── Capability Item ──────────────────────────────────────────────────

class CapabilityItem(Static):
    """Single capability status line."""

    state = reactive("DISABLED")

    def __init__(self, cap_name: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cap_name = cap_name

    def render(self) -> str:
        if self.state == "ACTIVE":
            glyph = "[bold #3fb950]●[/]"
            color = "#3fb950"
        elif self.state == "BLOCKED":
            glyph = "[bold #d29922]●[/]"
            color = "#d29922"
        else:
            glyph = "[#f85149]●[/]"
            color = "#f85149"
        pad = 16 - len(self.cap_name)
        return f"  {self.cap_name}{' ' * pad}{glyph} [{color}]{self.state}[/]"


# ── Signal Rail (composite) ──────────────────────────────────────────

class SignalRail(Vertical):
    """The right column of the STRATUM layout."""

    def __init__(self, artifacts_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(id="signal-rail", **kwargs)
        self.artifacts_dir = artifacts_dir
        self._gate_indicator: HITLGateIndicator | None = None
        self._ledger_log: RichLog | None = None
        self._cap_items: dict[str, CapabilityItem] = {}
        self._seen_event_files: set[str] = set()  # Track which event files we've already rendered

    def compose(self) -> ComposeResult:
        # ── HITL Gate Indicator ──
        self._gate_indicator = HITLGateIndicator(id="hitl-gate-indicator")
        yield self._gate_indicator

        # ── Event Ledger ──
        with Vertical(id="ledger-section"):
            yield Static("EVENT LEDGER", id="ledger-title")
            self._ledger_log = RichLog(
                id="ledger-log",
                highlight=True,
                markup=True,
                wrap=True,
                max_lines=200,
            )
            yield self._ledger_log

        # ── Capability Rail ──
        with Vertical(id="capability-section"):
            yield Static("CAPABILITY RAIL", id="capability-title")
            with Vertical(id="capability-list"):
                for cap in CAPABILITIES:
                    item = CapabilityItem(cap_name=cap)
                    self._cap_items[cap] = item
                    yield item

        # ── Mechanical Sympathy HUD ──
        yield MechanicalSympathyHud()

    def on_mount(self) -> None:
        self._load_initial_ledger()

    def _load_initial_ledger(self) -> None:
        """Load existing events from event directories (initial scan)."""
        if not self.artifacts_dir:
            if self._ledger_log and not self._seen_event_files:
                self._ledger_log.write("[#484f58]no events directory configured[/]")
            return

        # Look in .builder/artifacts/events/ and .builder/sessions/*/events/
        event_dirs: list[Path] = []
        events_dir = self.artifacts_dir / "events"
        if events_dir.exists():
            event_dirs.append(events_dir)

        sessions_dir = self.artifacts_dir.parent / "sessions"
        if sessions_dir.exists():
            for sess_dir in sessions_dir.iterdir():
                sess_events = sess_dir / "events"
                if sess_events.exists():
                    event_dirs.append(sess_events)

        if not event_dirs and not self._seen_event_files:
            if self._ledger_log:
                self._ledger_log.write("[#484f58]awaiting events…[/]")
            return

        new_events: list[tuple[str, str, str, str]] = []  # (ts, event_type, summary, filename)
        for edir in event_dirs:
            for path in sorted(edir.glob("*.json")):
                fname = str(path)
                if fname in self._seen_event_files:
                    continue
                try:
                    data = json.loads(path.read_text())
                    ts = data.get("timestamp", "")
                    if ts:
                        try:
                            dt = datetime.fromisoformat(ts)
                            ts_short = dt.strftime("%H:%M:%S")
                        except (ValueError, TypeError):
                            ts_short = ts[:8]
                    else:
                        ts_short = "??:??:??"

                    event_type = data.get("event_type", "unknown")
                    summary = data.get("summary", data.get("event_type", ""))
                    new_events.append((ts_short, event_type, summary, fname))
                except (json.JSONDecodeError, OSError):
                    continue

        # Render only new events
        for ts, event_type, summary, fname in new_events[-50:]:
            self._write_ledger_line(ts, event_type, summary)
            self._seen_event_files.add(fname)

    def _write_ledger_line(self, ts: str, event_type: str, summary: str) -> None:
        """Write a single color-coded event line to the ledger log."""
        if self._ledger_log is None:
            return

        # Color-code by event type
        if "fail" in event_type.lower() or "error" in event_type.lower():
            color = "#f85149"
            glyph = "✗"
        elif "gate" in event_type.lower() or "hitl" in event_type.lower():
            color = "#d29922"
            glyph = "⚡"
        elif "pass" in event_type.lower() or "verify" in event_type.lower() or "complete" in event_type.lower():
            color = "#3fb950"
            glyph = "✓"
        else:
            color = "#8b949e"
            glyph = "·"

        self._ledger_log.write(
            f"[#484f58]{ts}[/] [{color}]{glyph} {summary[:40]}[/]"
        )

    def update_gate(self, is_open: bool, label: str = "") -> None:
        """Update the HITL gate indicator."""
        if self._gate_indicator:
            self._gate_indicator.gate_open = is_open
            if label:
                self._gate_indicator.gate_label = label

    def update_capability(self, cap_name: str, state: str) -> None:
        """Update a capability state."""
        if cap_name in self._cap_items:
            self._cap_items[cap_name].state = state

    def append_event(self, ts: str, event_type: str, summary: str) -> None:
        """Append a new event to the ledger."""
        self._write_ledger_line(ts, event_type, summary)

    async def refresh_data(self) -> None:
        """Periodic refresh — reload events and capabilities."""
        self._load_initial_ledger()
