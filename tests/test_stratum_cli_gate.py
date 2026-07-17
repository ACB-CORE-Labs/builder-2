"""`builder stratum` refuses to launch without `--experimental` (plan item 3.13 / D5).

The gate exists because STRATUM is a pre-release surface, not because of any single unfinished
widget. What is true of it today: command tier evaluation is real; no chain digest is displayed,
because none is reachable; HITL approve/reject are constitutive refusals rather than pending
features; and the HITL diff viewer is still a mockup. It must not launch by default.
"""

from __future__ import annotations

from typer.testing import CliRunner

from builder_ii.cli import app

runner = CliRunner()


def test_stratum_refuses_without_experimental_flag():
    result = runner.invoke(app, ["stratum"])

    assert result.exit_code == 1
    assert "--experimental" in result.output
    assert "experimental" in result.output.lower()


class _DummyStratumApp:
    """Stands in for StratumApp, modelling the part of Textual's contract the launcher reads.

    `return_code` is not padding. A real `App` always carries it, and it is the *only* channel by
    which Textual reports that the app failed -- it catches an unhandled `on_mount` exception,
    prints the traceback, and returns from `run()` normally. A fake without it cannot distinguish a
    launcher that propagates the code from one that discards it, which is exactly how every launch
    site came to call a bare `app.run()` and report success for a crashed TUI while this lane
    stayed green.
    """

    return_code = 0

    def __init__(self, *args, **kwargs):
        self.launched_kwargs = kwargs
        self.ran = False

    def run(self):
        self.ran = True


def test_stratum_launches_with_experimental_flag(monkeypatch):
    built: list[_DummyStratumApp] = []

    def _factory(*args, **kwargs):
        app_instance = _DummyStratumApp(*args, **kwargs)
        built.append(app_instance)
        return app_instance

    monkeypatch.setattr("builder_ii.tui.app.StratumApp", _factory)

    result = runner.invoke(app, ["stratum", "--experimental"])

    assert result.exit_code == 0, result.output
    assert built[0].ran is True
    assert "stratum" in result.output.lower()
    assert "builder-stratum" in result.output.lower() or "operator console" in result.output.lower()

    result_no_guide = runner.invoke(app, ["stratum", "--experimental", "--no-guide"])
    assert result_no_guide.exit_code == 0, result_no_guide.output
    assert built[-1].launched_kwargs.get("skip_guide") is True


def test_stratum_reports_a_failed_tui_instead_of_exiting_zero(monkeypatch):
    """A STRATUM that failed must not be reported to the shell as a success.

    Textual signals failure only through `App.return_code`; `run()` returns normally either way.
    Every launcher discarded it, so `builder stratum` exited `0` for a TUI that crashed on mount --
    a false green for anything scripting the surface. The lane above cannot see this: its dummy
    always succeeds, so it passes whether or not the code is propagated.
    """

    class _FailingStratumApp(_DummyStratumApp):
        return_code = 1

    monkeypatch.setattr("builder_ii.tui.app.StratumApp", _FailingStratumApp)

    result = runner.invoke(app, ["stratum", "--experimental"])

    assert result.exit_code == 1, (
        f"STRATUM reported return_code=1 but the launcher exited {result.exit_code}; "
        f"a crashed TUI is being reported as success"
    )
