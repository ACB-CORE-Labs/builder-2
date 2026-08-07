"""Pins for the shared golden path and the `builder onboard` walkthrough.

The stage table used to exist twice -- as predicates in `get_onboarding_state` and as a literal
list inside `builder course` -- and the copies had already drifted. The first test here is the
anti-drift pin; the rest cover the walkthrough that reads from the same table.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from builder_ii.cli.main import app
from builder_ii.governance.ratification_grants import RATIFICATION_ROOT_ENV
from builder_ii.governance.ratification_points import grantable_point_ids
from builder_ii.lifecycle.setup.user_onboarding_next import (
    GOLDEN_PATH,
    READY_STAGE,
    READY_STATE,
    current_stage,
    get_onboarding_state,
)

runner = CliRunner()

GRANTABLE = "setup.apply.overlay_digest"


@pytest.fixture()
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An empty project directory, with the ratification store isolated inside it."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(RATIFICATION_ROOT_ENV, str(tmp_path / "ratification"))
    return tmp_path


def _satisfy_through(root: Path, count: int) -> None:
    """Create the filesystem markers for the first ``count`` stages, in order."""
    artifacts = root / ".builder" / "artifacts"
    markers = [
        lambda: (root / ".env").write_text("", encoding="utf-8"),
        lambda: (artifacts / "setup-plan.json").write_text("{}", encoding="utf-8"),
        lambda: (artifacts / "setup-receipt.json").write_text("{}", encoding="utf-8"),
        lambda: (root / ".builder" / "session" / "pkg.json").write_text("{}", encoding="utf-8"),
    ]
    artifacts.mkdir(parents=True, exist_ok=True)
    (root / ".builder" / "session").mkdir(parents=True, exist_ok=True)
    for marker in markers[:count]:
        marker()


def test_the_course_renders_from_the_shared_table_rather_than_a_transcription(project: Path) -> None:
    """Every title `builder course` prints must come from GOLDEN_PATH, so the two cannot drift."""
    result = runner.invoke(app, ["course"])
    assert result.exit_code == 0, result.output
    for stage in (*GOLDEN_PATH, READY_STAGE):
        assert stage.title in result.output


def test_each_stage_becomes_current_as_its_predecessor_is_satisfied(tmp_path: Path) -> None:
    for index, stage in enumerate(GOLDEN_PATH):
        _satisfy_through(tmp_path, index)
        assert current_stage(tmp_path).state == stage.state
    _satisfy_through(tmp_path, len(GOLDEN_PATH))
    assert current_stage(tmp_path).state == READY_STATE


def test_get_onboarding_state_keeps_its_reported_shape(tmp_path: Path) -> None:
    """`builder next` and the operator report both read these four keys."""
    state = get_onboarding_state(tmp_path)
    assert set(state) == {"title", "description", "safe_command", "state"}
    assert state["state"] == GOLDEN_PATH[0].state


def test_onboard_describes_every_point_and_writes_nothing_with_no_prompt(project: Path) -> None:
    result = runner.invoke(app, ["onboard", "--no-prompt"])
    assert result.exit_code == 0, result.output

    from builder_ii.governance.ratification_points import RATIFICATION_POINTS

    for point in RATIFICATION_POINTS:
        assert point.id in result.output
    assert not (project / "ratification").exists(), "--no-prompt must not write"


def _answers(*, accept_first: bool = False) -> str:
    """One answer per delegable point, sized from the live registry.

    Hardcoding the count made these tests a tripwire on the number of grantable points rather
    than on the behaviour they describe: registering a new one exhausted the supplied stdin and
    aborted the walkthrough mid-prompt. The set of points is exactly what `builder onboard`
    iterates, so deriving the answers from it keeps the assertions about grants, not arithmetic.
    """
    count = len(grantable_point_ids())
    assert count, "the walkthrough is inert unless something is delegable"
    first = "y" if accept_first else "n"
    return "\n".join([first] + ["n"] * (count - 1)) + "\n"


def test_onboard_names_which_confirmations_can_never_be_delegated(project: Path) -> None:
    """The trust-building half: the walkthrough has to say what it will not let you turn off."""
    result = runner.invoke(app, ["onboard", "--no-prompt"])
    assert "delegable:  NO" in result.output
    assert "human_approval_mint" in result.output


def test_onboard_writes_a_grant_only_for_an_accepted_prompt(project: Path) -> None:
    """Every delegable point is offered; accepting only the first yields exactly one grant."""
    result = runner.invoke(app, ["onboard", "--granted-by", "op"], input=_answers(accept_first=True))
    assert result.exit_code == 0, result.output

    grants = list((project / "ratification" / "grants").glob("*.json"))
    assert len(grants) == 1
    grant = json.loads(grants[0].read_text(encoding="utf-8"))
    assert grant["point_id"] == GRANTABLE
    assert grant["granted_by"] == "op"
    assert "Delegated 1 confirmation(s)." in result.output


def test_onboard_declining_everything_writes_no_grants(project: Path) -> None:
    result = runner.invoke(app, ["onboard", "--granted-by", "op"], input=_answers())
    assert result.exit_code == 0, result.output
    assert "Delegated nothing." in result.output
    assert not list((project / "ratification").glob("grants/*.json"))


def test_onboard_reports_a_grant_already_in_force(project: Path) -> None:
    runner.invoke(app, ["onboard", "--granted-by", "op"], input=_answers(accept_first=True))
    again = runner.invoke(app, ["onboard", "--no-prompt"])
    assert "already in force" in again.output


def test_onboard_points_at_the_current_stage_command(project: Path) -> None:
    result = runner.invoke(app, ["onboard", "--no-prompt"])
    assert GOLDEN_PATH[0].safe_command in result.output
    assert "builder-govern trace" in result.output, "the walkthrough must hand over the audit surface"
