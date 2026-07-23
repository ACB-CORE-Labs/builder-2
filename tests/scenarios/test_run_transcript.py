"""T2a — live ledger transcript projection + widget.

The projection is pure and chain-aware; the widget tails one run's ``event_record`` chain,
appends only unseen records, shows an honest empty state, and marks a chain break explicitly.
Fixtures write event JSON directly (no WAL) so ``load_event_records`` globs the real files and
tampering is deterministic.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from textual.app import App, ComposeResult

from builder_ii.governance.ledger.event_ledger import EVENT_RECORD_KIND, create_event_record
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.tui.projections.run_transcript import project_run_transcript
from builder_ii.tui.widgets.transcript import RunTranscript

_POLICY_REF = {
    "role": "policy",
    "kind": "builder_ii.mcp_tool_policy",
    "path": "policy.json",
    "sha256": "0" * 64,
    "name": "policy",
    "required": True,
}


def _write_chain(events_dir: Path, count: int, session_id: str = "run_x") -> None:
    """Write ``count`` correctly hash-chained event records as plain JSON (no WAL)."""
    events_dir.mkdir(parents=True, exist_ok=True)
    prev_event: dict | None = None
    prev_path: Path | None = None
    for seq in range(1, count + 1):
        prev_ref = None
        if prev_event is not None and prev_path is not None:
            prev_ref = {
                "role": "event",
                "kind": EVENT_RECORD_KIND,
                "path": str(prev_path),
                "sha256": canonical_digest(prev_event),
                "name": "prev",
                "required": True,
            }
        event = create_event_record(
            event_id=f"evt_{session_id}_{seq}",
            session_id=session_id,
            sequence=seq,
            event_type="mcp_call_executed",
            stage="initialized",
            subject_refs=[],
            command_surface="test",
            policy_snapshot_ref=dict(_POLICY_REF),
            previous_event_ref=prev_ref,
            message=f"event {seq}",
        )
        path = events_dir / f"{seq:03d}_event.json"
        path.write_text(json.dumps(event, indent=2), encoding="utf-8")
        prev_event, prev_path = event, path


class _HostApp(App[None]):
    def __init__(self, widget: RunTranscript) -> None:
        super().__init__()
        self._widget = widget

    def compose(self) -> ComposeResult:
        yield self._widget


# ── projection ───────────────────────────────────────────────────────────────


def test_projection_empty_dir_is_absence_not_a_verdict(tmp_path: Path) -> None:
    view = project_run_transcript(tmp_path / "missing" / "events", run_id="none")
    assert view.is_empty
    assert view.event_count == 0
    assert view.chain_valid is None
    assert view.rows == ()


def test_projection_valid_chain_is_ordered_and_valid(tmp_path: Path) -> None:
    events = tmp_path / "events"
    _write_chain(events, 3)
    view = project_run_transcript(events, run_id="run_x")
    assert view.event_count == 3
    assert view.chain_valid is True
    assert view.chain_errors == ()
    assert [row.sequence for row in view.rows] == [1, 2, 3]
    assert all(row.chain_ok for row in view.rows)
    assert view.rows[0].event_type == "mcp_call_executed"


def test_projection_marks_a_broken_link(tmp_path: Path) -> None:
    events = tmp_path / "events"
    _write_chain(events, 2)
    tampered = events / "002_event.json"
    data = json.loads(tampered.read_text(encoding="utf-8"))
    data["previous_event_sha256"] = "f" * 64
    tampered.write_text(json.dumps(data, indent=2), encoding="utf-8")

    view = project_run_transcript(events)
    assert view.chain_valid is False
    assert view.chain_errors
    by_seq = {row.sequence: row for row in view.rows}
    assert by_seq[1].chain_ok is True
    assert by_seq[2].chain_ok is False


# ── widget ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_widget_shows_honest_empty_state(tmp_path: Path) -> None:
    widget = RunTranscript(events_dir=tmp_path / "events", run_id="empty_run")
    async with _HostApp(widget).run_test(headless=True):
        assert widget._empty_written is True
        assert widget._seen == set()


@pytest.mark.asyncio
async def test_widget_tails_a_valid_chain(tmp_path: Path) -> None:
    events = tmp_path / "events"
    _write_chain(events, 2)
    widget = RunTranscript(events_dir=events, run_id="run_x")
    async with _HostApp(widget).run_test(headless=True):
        assert widget._seen == {1, 2}
        view = widget.project()
        assert view is not None and view.chain_valid is True


@pytest.mark.asyncio
async def test_widget_set_run_switches_and_resets_tail(tmp_path: Path) -> None:
    run_a = tmp_path / "a" / "events"
    run_b = tmp_path / "b" / "events"
    _write_chain(run_a, 2, "a")
    _write_chain(run_b, 3, "b")
    widget = RunTranscript(events_dir=run_a, run_id="a")
    async with _HostApp(widget).run_test(headless=True):
        assert widget._seen == {1, 2}
        widget.set_run(run_b, "b")
        assert widget._seen == {1, 2, 3}
        view = widget.project()
        assert view is not None and view.run_id == "b"
