"""T2b — run roster projection + the STRATUM run cockpit.

The roster lists ledgered runs under .builder/sessions; the cockpit (mode RUN_COCKPIT, key
`l`) renders it and mounts a live transcript of the selected run. Observe-only. Fixtures
write event JSON directly (no WAL) so the roster/transcript read the real files.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.governance.ledger.event_ledger import EVENT_RECORD_KIND, create_event_record
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.tui.app import StratumApp
from builder_ii.tui.projections.runs import project_run_roster
from builder_ii.tui.widgets.stratum import StratumMode

_POLICY_REF = {
    "role": "policy",
    "kind": "builder_ii.mcp_tool_policy",
    "path": "policy.json",
    "sha256": "0" * 64,
    "name": "policy",
    "required": True,
}


def _write_run(builder_root: Path, run_id: str, count: int, event_type: str = "mcp_call_executed") -> None:
    events_dir = builder_root / "sessions" / run_id / "events"
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
            event_id=f"evt_{run_id}_{seq}",
            session_id=run_id,
            sequence=seq,
            event_type=event_type,
            stage="initialized",
            subject_refs=[],
            command_surface="test",
            policy_snapshot_ref=dict(_POLICY_REF),
            previous_event_ref=prev_ref,
            message=f"{run_id} event {seq}",
        )
        path = events_dir / f"{seq:03d}_event.json"
        path.write_text(json.dumps(event, indent=2), encoding="utf-8")
        prev_event, prev_path = event, path


# ── roster projection ────────────────────────────────────────────────────────


def test_roster_empty_when_no_sessions(tmp_path: Path) -> None:
    assert project_run_roster(tmp_path / ".builder").is_empty
    assert project_run_roster(None).is_empty


def test_roster_lists_only_ledgered_runs_with_chain_verdict(tmp_path: Path) -> None:
    builder_root = tmp_path / ".builder"
    _write_run(builder_root, "run-a", 2)
    _write_run(builder_root, "run-b", 3)
    # A session dir with no events is not a run.
    (builder_root / "sessions" / "empty" / "events").mkdir(parents=True)

    view = project_run_roster(builder_root)
    ids = {r.run_id for r in view.rows}
    assert ids == {"run-a", "run-b"}
    by_id = {r.run_id: r for r in view.rows}
    assert by_id["run-b"].event_count == 3
    assert all(r.chain_valid is True for r in view.rows)


# ── cockpit widget ───────────────────────────────────────────────────────────


def _app_at(root: Path) -> StratumApp:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.target_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "primary"
        mock_settings.return_value.backend = "test"
        mock_settings.return_value.project_root = root
        return StratumApp(show_splash=False, skip_guide=True)


@pytest.mark.asyncio
async def test_l_key_opens_run_cockpit_and_binds_transcript(tmp_path: Path) -> None:
    builder_root = tmp_path / ".builder"
    _write_run(builder_root, "run-older", 2)
    _write_run(builder_root, "run-newer", 2)

    app = _app_at(tmp_path)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("l")
        await pilot.pause()
        assert app.stratum is not None
        assert app.stratum.mode == StratumMode.RUN_COCKPIT
        # The mounted transcript is shown and bound to a run.
        transcript = app.stratum._run_transcript
        assert transcript is not None
        assert transcript.display is True
        assert transcript.project() is not None


@pytest.mark.asyncio
async def test_cockpit_next_run_changes_selection(tmp_path: Path) -> None:
    builder_root = tmp_path / ".builder"
    _write_run(builder_root, "run-1", 1)
    _write_run(builder_root, "run-2", 1)

    app = _app_at(tmp_path)
    async with app.run_test(headless=True) as pilot:
        await pilot.press("l")
        await pilot.pause()
        assert app.stratum is not None
        first = app.stratum._selected_run_index
        await pilot.press("full_stop")  # "." -> next run
        await pilot.pause()
        assert app.stratum._selected_run_index == first + 1
