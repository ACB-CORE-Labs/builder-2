"""T1 — the operator verb-stage journey axis.

PREPARE -> PLAN -> APPROVE -> EXECUTE -> VERIFY -> PROMOTE, each state derived from artifacts
on disk. Empty tree -> PREPARE active; a session artifact advances the journey.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.tui.app import StratumApp
from builder_ii.tui.projections.stages import project_operator_stages
from builder_ii.tui.widgets.stratum import StratumMode


def _states(artifacts_dir: Path) -> dict[str, str]:
    return {cell.verb: cell.state for cell in project_operator_stages(artifacts_dir).cells}


def test_empty_tree_makes_prepare_active(tmp_path: Path) -> None:
    view = project_operator_stages(tmp_path)
    assert view.active_verb == "PREPARE"
    states = {cell.verb: cell.state for cell in view.cells}
    assert states["PREPARE"] == "active"
    assert all(states[v] == "pending" for v in ("PLAN", "APPROVE", "EXECUTE", "VERIFY", "PROMOTE"))


def test_session_artifact_advances_journey_to_plan(tmp_path: Path) -> None:
    (tmp_path / "session.json").write_text(json.dumps({"kind": "builder_ii.session_configuration"}), encoding="utf-8")
    states = _states(tmp_path)
    assert states["PREPARE"] == "done"
    assert states["PLAN"] == "active"


def test_not_run_postflight_does_not_complete_execute(tmp_path: Path) -> None:
    """A NOT_RUN postflight record is a legitimate on-disk artifact -- the run it describes
    simply has not happened yet. EXECUTE must not show done from its mere presence."""
    (tmp_path / "postflight.json").write_text(
        json.dumps({"kind": "builder_ii.execution_postflight_record", "postflight_state": "NOT_RUN"}),
        encoding="utf-8",
    )
    states = _states(tmp_path)
    assert states["EXECUTE"] != "done", "NOT_RUN postflight record incorrectly completed EXECUTE"


def test_run_complete_postflight_completes_execute(tmp_path: Path) -> None:
    (tmp_path / "postflight.json").write_text(
        json.dumps(
            {
                "kind": "builder_ii.execution_postflight_record",
                "postflight_state": "RUN_COMPLETE",
                "performed_actions": ["did a thing"],
            }
        ),
        encoding="utf-8",
    )
    states = _states(tmp_path)
    assert states["EXECUTE"] == "done"


def test_none_artifacts_dir_is_prepare_active() -> None:
    view = project_operator_stages(None)
    assert view.active_verb == "PREPARE"


@pytest.mark.asyncio
async def test_idle_home_projects_the_journey(tmp_path: Path) -> None:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.target_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "primary"
        mock_settings.return_value.backend = "test"
        mock_settings.return_value.project_root = tmp_path

        app = StratumApp(show_splash=False, skip_guide=True)
        async with app.run_test(headless=True):
            assert app.stratum is not None
            assert app.stratum.mode == StratumMode.IDLE
            # The IDLE home renders without error and the axis projects an active verb.
            assert project_operator_stages(app.stratum.artifacts_dir).active_verb == "PREPARE"
