"""STRATUM dispatching a governed run: task in, streamed run out.

This is the loop the whole lane exists to create -- the operator states a task and watches it
happen -- so what these tests defend is that gaining the ability to *start* work did not cost any
of the honesty the console had while it could only compose.

Three claims, in order of how badly it would matter if they broke:

1. Authority is evaluated before anything is minted or spawned.
2. Where no standing grant covers the dispatch, the operator is asked, and the confirmation names
   the manifest digest and the exact argv -- not a summary of them.
3. Where a grant does cover it, the run proceeds and the grant is named and ledgered, so an
   operator can see what answered for them.

No test here spawns a real process: the dispatch primitive is replaced by a recorder, and what is
asserted is the argv that *would* have run.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from builder_ii.governance.ratification_grants import (
    RATIFICATION_ROOT_ENV,
    build_ratification_grant,
    write_grant,
)
from builder_ii.governance.ratification_points import get_ratification_point
from builder_ii.tui.app import StratumApp
from builder_ii.tui.widgets.cli_passthrough import ConfirmScreen
from builder_ii.tui.widgets.stratum import StratumMode
from builder_ii.tui.widgets.task_entry import TaskEntryScreen

POINT = "stratum.dispatch.goose_run"


def _app(tmp_path: Path) -> StratumApp:
    app = StratumApp(show_splash=False, skip_guide=True)
    app.artifacts_dir = tmp_path / ".builder" / "artifacts"
    app.artifacts_dir.mkdir(parents=True, exist_ok=True)
    return app


@pytest.fixture
def settings_patch(tmp_path: Path) -> Any:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.target_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "primary"
        mock_settings.return_value.project_root = tmp_path
        yield mock_settings


@pytest.fixture
def grant_root(tmp_path: Path, monkeypatch: Any) -> Path:
    """Point the ratification store at tmp_path so no test reads the operator's real grants."""
    root = tmp_path / "ratification"
    monkeypatch.setenv(RATIFICATION_ROOT_ENV, str(root))
    return root


@pytest.mark.asyncio
async def test_authority_denial_stops_before_anything_is_minted_or_spawned(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    """Fail closed first: a denied console must not even write a manifest."""
    from builder_ii.governance.authority import CommandAuthorityError

    app = _app(tmp_path)
    spawned: list[tuple[str, ...]] = []

    async with app.run_test() as pilot:
        with patch(
            "builder_ii.governance.authority.enforce_command_authority",
            side_effect=CommandAuthorityError("denied for test"),
        ):
            with patch.object(app, "_dispatch_governed_run", lambda *a, **k: spawned.append(a)):
                app.action_run_governed_task()
                await pilot.pause()

        assert spawned == []
        assert not isinstance(app.screen, TaskEntryScreen)
        assert not (tmp_path / ".builder" / "goose").exists()


@pytest.mark.asyncio
async def test_without_a_grant_the_operator_is_asked_and_told_what_will_run(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    app = _app(tmp_path)
    spawned: list[tuple[Any, ...]] = []

    async with app.run_test() as pilot:
        with patch.object(app, "_dispatch_governed_run", lambda *a, **k: spawned.append(a)):
            app._on_governed_task_entered("map the hitl lane")
            await pilot.pause()

            # A confirmation, not a dispatch.
            assert isinstance(app.screen, ConfirmScreen), f"expected ConfirmScreen, got {type(app.screen)}"
            assert spawned == []

            body = " ".join(str(node.render()) for node in app.screen.query("Static"))
            assert "map the hitl lane" in body
            # The exact command, not a description of it: an operator confirming a dispatch is
            # entitled to see the argv, and a digest that binds which manifest it will read.
            assert "run-governed" in body
            assert "--manifest" in body
            manifest = tmp_path / ".builder" / "goose" / "stratum-governed-run.json"
            assert manifest.exists()
            assert app._manifest_digest(manifest) in body


@pytest.mark.asyncio
async def test_declining_the_confirmation_dispatches_nothing(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    app = _app(tmp_path)
    spawned: list[tuple[Any, ...]] = []

    async with app.run_test() as pilot:
        with patch.object(app, "_dispatch_governed_run", lambda *a, **k: spawned.append(a)):
            app._on_governed_task_entered("map the hitl lane")
            await pilot.pause()
            app._on_governed_dispatch_confirm(False)
            await pilot.pause()

        assert spawned == []


@pytest.mark.asyncio
async def test_confirming_dispatches_the_exact_fixed_argv(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    """Fixed argv through the module entry point -- never a shell string, never a guess."""
    import sys

    app = _app(tmp_path)
    spawned: list[tuple[Any, ...]] = []

    async with app.run_test() as pilot:
        with patch.object(app, "_dispatch_governed_run", lambda *a, **k: spawned.append(a)):
            app._on_governed_task_entered("map the hitl lane")
            await pilot.pause()
            app._on_governed_dispatch_confirm(True)
            await pilot.pause()

        assert len(spawned) == 1
        argv = spawned[0][0]
        manifest = tmp_path / ".builder" / "goose" / "stratum-governed-run.json"
        assert argv == (
            sys.executable,
            "-m",
            "builder_ii.cli.goose_cli",
            "run-governed",
            "--manifest",
            str(manifest),
            "--task",
            "map the hitl lane",
        )


@pytest.mark.asyncio
async def test_a_standing_grant_dispatches_without_asking_and_names_the_grant(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    """The operator-configured pause: granted means proceed, and say what allowed it."""
    point = get_ratification_point(POINT)
    assert point is not None
    grant = build_ratification_grant(point, granted_by="operator")
    write_grant(grant, root=grant_root)

    app = _app(tmp_path)
    spawned: list[tuple[Any, ...]] = []
    notices: list[str] = []

    async with app.run_test() as pilot:
        with patch.object(app, "_dispatch_governed_run", lambda *a, **k: spawned.append(a)):
            with patch.object(app, "notify", lambda msg, **k: notices.append(str(msg))):
                app._on_governed_task_entered("map the hitl lane")
                await pilot.pause()

        # No confirmation was raised, and the run went out.
        assert not isinstance(app.screen, ConfirmScreen)
        assert len(spawned) == 1
        # The operator is told which grant answered for them -- an auto-ratified action that
        # cannot be traced back to what allowed it would be the feature doing less governance.
        assert any(grant["grant_digest"][:12] in note for note in notices), notices


@pytest.mark.asyncio
async def test_an_auto_ratified_dispatch_is_recorded_on_the_ratification_ledger(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    from builder_ii.governance.ledger.ratification_ledger import (
        EVENT_AUTO_ACCEPTED,
        read_ratification_events,
    )

    point = get_ratification_point(POINT)
    assert point is not None
    grant = build_ratification_grant(point, granted_by="operator")
    write_grant(grant, root=grant_root)

    app = _app(tmp_path)
    async with app.run_test() as pilot:
        with patch.object(app, "_dispatch_governed_run", lambda *a, **k: None):
            app._on_governed_task_entered("map the hitl lane")
            await pilot.pause()

    entries = [e for e in read_ratification_events(grant_root) if e["event"] == EVENT_AUTO_ACCEPTED]
    assert len(entries) == 1
    assert entries[0]["point_id"] == POINT
    assert entries[0]["grant_digest"] == grant["grant_digest"]


@pytest.mark.asyncio
async def test_a_prompted_dispatch_is_recorded_as_manual(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    """Same emission either way: the prompted branch is ledgered too, just not as auto."""
    from builder_ii.governance.ledger.ratification_ledger import (
        EVENT_MANUAL_RATIFIED,
        read_ratification_events,
    )

    app = _app(tmp_path)
    async with app.run_test() as pilot:
        with patch.object(app, "_dispatch_governed_run", lambda *a, **k: None):
            app._on_governed_task_entered("map the hitl lane")
            await pilot.pause()
            app._on_governed_dispatch_confirm(True)
            await pilot.pause()

    entries = [e for e in read_ratification_events(grant_root) if e["event"] == EVENT_MANUAL_RATIFIED]
    assert len(entries) == 1
    assert entries[0]["point_id"] == POINT


@pytest.mark.asyncio
async def test_an_empty_task_dispatches_nothing(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    app = _app(tmp_path)
    spawned: list[tuple[Any, ...]] = []

    async with app.run_test() as pilot:
        with patch.object(app, "_dispatch_governed_run", lambda *a, **k: spawned.append(a)):
            app._on_governed_task_entered(None)
            app._on_governed_task_entered("   ")
            await pilot.pause()

        assert spawned == []


@pytest.mark.asyncio
async def test_dispatch_switches_to_the_cockpit_so_the_run_is_watchable(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    """Starting work and then having to go find it would rebuild the invisible run."""
    app = _app(tmp_path)
    manifest = tmp_path / "m.json"

    async with app.run_test() as pilot:
        with patch("subprocess.Popen", lambda *a, **k: _FakeProc()):
            app._dispatch_governed_run(("x",), manifest, "a task")
            await pilot.pause()

        assert app.stratum is not None
        assert app.stratum.mode == StratumMode.RUN_COCKPIT
        # The handle is kept so a later Stop verb has something to signal; disk stays the
        # source of truth for what ran.
        assert str(manifest) in app._live_runs


@pytest.mark.asyncio
async def test_a_failed_spawn_is_reported_rather_than_claimed_as_started(
    tmp_path: Path, settings_patch: Any, grant_root: Path
) -> None:
    """A console that says "dispatched" for a process that never existed is the old lie."""
    app = _app(tmp_path)
    errors: list[str] = []

    async with app.run_test() as pilot:
        def _raise(*a: Any, **k: Any) -> Any:
            raise OSError("no such executable")

        with patch("subprocess.Popen", _raise):
            with patch.object(app, "notify", lambda msg, **k: errors.append(str(msg))):
                app._dispatch_governed_run(("x",), tmp_path / "m.json", "a task")
                await pilot.pause()

    assert any("could not start" in e for e in errors), errors
    assert app._live_runs == {}


class _FakeProc:
    def __init__(self) -> None:
        self.pid = 1234

    def poll(self) -> int | None:
        return None
