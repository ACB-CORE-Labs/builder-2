"""Signal Rail — right column of STRATUM.

  1. HITL Gate Indicator
  2. Event Ledger (tail of disk events)
  3. Capability Rail
  4. Mechanical Sympathy HUD
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

from builder_ii.tui.projections.gates import scan_pending_hitl
from builder_ii.tui.projections.render import bold_themed, themed
from builder_ii.tui.widgets.masterpiece import MechanicalSympathyHud

CAPABILITIES = [
    "model_exec",
    "shell_exec",
    "runtime",
    "mem_mutation",
    "source_writes",
    "target_writes",
]


class HITLGateIndicator(Static):
    gate_open = reactive(False)
    gate_label = reactive("NO PENDING GATES")

    def render(self) -> str:
        if self.gate_open:
            return (
                f"\n {bold_themed('warn', '● HITL GATE OPEN')}\n"
                f"   {themed('hint', self.gate_label)}"
            )
        return (
            f"\n {themed('pass', '● ALL GATES CLEAR')}\n"
            f"   {themed('dim', 'no pending authority')}"
        )


class CapabilityItem(Static):
    state = reactive("DISABLED")

    def __init__(self, cap_name: str, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.cap_name = cap_name

    def render(self) -> str:
        if self.state == "ACTIVE":
            glyph = bold_themed("pass", "●")
            token = "pass"
        elif self.state == "BLOCKED":
            glyph = bold_themed("warn", "●")
            token = "warn"
        else:
            glyph = themed("fail", "●")
            token = "fail"
        pad = 16 - len(self.cap_name)
        return f"  {self.cap_name}{' ' * pad}{glyph} {themed(token, self.state)}"


class SignalRail(Vertical):
    def __init__(self, artifacts_dir: Path | None = None, **kwargs: Any) -> None:
        super().__init__(id="signal-rail", **kwargs)
        self.artifacts_dir = artifacts_dir
        self._gate_indicator: HITLGateIndicator | None = None
        self._ledger_log: RichLog | None = None
        self._cap_items: dict[str, CapabilityItem] = {}
        self._seen_event_files: set[str] = set()
        self._empty_hint_written = False

    def compose(self) -> ComposeResult:
        self._gate_indicator = HITLGateIndicator(id="hitl-gate-indicator")
        yield self._gate_indicator

        with Vertical(id="ledger-section"):
            yield Static("EVENTS", id="ledger-title")
            self._ledger_log = RichLog(
                id="ledger-log",
                highlight=True,
                markup=True,
                wrap=True,
                max_lines=200,
            )
            yield self._ledger_log

        with Vertical(id="capability-section"):
            yield Static("CAPABILITIES", id="capability-title")
            with Vertical(id="capability-list"):
                for cap in CAPABILITIES:
                    item = CapabilityItem(cap_name=cap)
                    self._cap_items[cap] = item
                    yield item

        yield MechanicalSympathyHud()

    def on_mount(self) -> None:
        self._load_initial_ledger()
        self._refresh_hitl_gate()
        self._apply_default_capabilities()

    def _apply_default_capabilities(self) -> None:
        """Honest defaults: STRATUM surface itself grants no execution caps."""
        for cap in CAPABILITIES:
            self.update_capability(cap, "DISABLED")

    def _refresh_hitl_gate(self) -> None:
        open_, label = scan_pending_hitl(self.artifacts_dir)
        self.update_gate(open_, label)

    def _load_initial_ledger(self) -> None:
        if not self.artifacts_dir:
            if self._ledger_log and not self._seen_event_files and not self._empty_hint_written:
                self._ledger_log.write(themed("dim", "no events directory configured"))
                self._empty_hint_written = True
            return

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
            if self._ledger_log and not self._empty_hint_written:
                self._ledger_log.write(themed("dim", "awaiting events…"))
                self._empty_hint_written = True
            return

        new_events: list[tuple[str, str, str, str]] = []
        for edir in event_dirs:
            for path in sorted(edir.glob("*.json")):
                fname = str(path)
                if fname in self._seen_event_files:
                    continue
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                    ts = data.get("timestamp", "")
                    if ts:
                        try:
                            dt = datetime.fromisoformat(ts)
                            ts_short = dt.strftime("%H:%M:%S")
                        except (ValueError, TypeError):
                            ts_short = str(ts)[:8]
                    else:
                        ts_short = "??:??:??"

                    event_type = str(data.get("event_type", "unknown"))
                    summary = str(data.get("summary", data.get("event_type", "")))
                    new_events.append((ts_short, event_type, summary, fname))
                except (json.JSONDecodeError, OSError):
                    continue

        for ts, event_type, summary, fname in new_events[-50:]:
            self._write_ledger_line(ts, event_type, summary)
            self._seen_event_files.add(fname)

    def _write_ledger_line(self, ts: str, event_type: str, summary: str) -> None:
        if self._ledger_log is None:
            return
        et = event_type.lower()
        if "fail" in et or "error" in et:
            glyph = themed("fail", "✗")
        elif "gate" in et or "hitl" in et:
            glyph = themed("warn", "⚡")
        elif "pass" in et or "verify" in et or "complete" in et:
            glyph = themed("pass", "✓")
        else:
            glyph = themed("hint", "·")

        self._ledger_log.write(f"{themed('dim', ts)} {glyph} {themed('hint', summary[:40])}")

    def update_gate(self, is_open: bool, label: str = "") -> None:
        if self._gate_indicator:
            self._gate_indicator.gate_open = is_open
            if label:
                self._gate_indicator.gate_label = label

    def update_capability(self, cap_name: str, state: str) -> None:
        if cap_name in self._cap_items:
            self._cap_items[cap_name].state = state

    def append_event(self, ts: str, event_type: str, summary: str) -> None:
        self._write_ledger_line(ts, event_type, summary)

    async def refresh_data(self) -> None:
        self._load_initial_ledger()
        self._refresh_hitl_gate()
