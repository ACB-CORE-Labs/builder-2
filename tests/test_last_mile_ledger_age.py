"""Ledger-tail age labeling (audit F6): recorded history must say it is history.

The last-mile HUD echoes the newest on-disk event next to a capability panel that says
model_exec DISABLED. Without an age, a days-old "Model call executed: ..." line reads as
this-session activity and the flagship screen contradicts itself. The tail therefore
carries a compact age suffix; the empty case stays the honest absence marker.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from builder_ii.tui.projections.last_mile import _format_event_age, project_last_mile_hud


def _write_event(artifacts: Path, name: str, message: str, age_seconds: float) -> None:
    events = artifacts / "events"
    events.mkdir(parents=True, exist_ok=True)
    path = events / name
    path.write_text(json.dumps({"event_type": "model_call", "message": message}), encoding="utf-8")
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))


def test_format_event_age_buckets() -> None:
    assert _format_event_age(0) == "now"
    assert _format_event_age(59) == "now"
    assert _format_event_age(60) == "1m ago"
    assert _format_event_age(3599) == "59m ago"
    assert _format_event_age(7200) == "2h ago"
    assert _format_event_age(172800) == "2d ago"
    assert _format_event_age(-5) == "now"


def test_stale_event_carries_age_suffix(tmp_path: Path) -> None:
    artifacts = tmp_path / ".builder" / "artifacts"
    _write_event(artifacts, "old.json", "Model call executed: stub", age_seconds=2 * 3600 + 30)
    view = project_last_mile_hud(artifacts)
    assert view.ledger_tail.endswith("· 2h ago"), view.ledger_tail
    assert "Model call executed: stub" in view.ledger_tail


def test_fresh_event_reads_now(tmp_path: Path) -> None:
    artifacts = tmp_path / ".builder" / "artifacts"
    _write_event(artifacts, "fresh.json", "candidate_accepted", age_seconds=0)
    view = project_last_mile_hud(artifacts)
    assert view.ledger_tail.endswith("· now"), view.ledger_tail


def test_absence_marker_unchanged(tmp_path: Path) -> None:
    artifacts = tmp_path / ".builder" / "artifacts"
    artifacts.mkdir(parents=True)
    view = project_last_mile_hud(artifacts)
    assert view.ledger_tail == "—"
