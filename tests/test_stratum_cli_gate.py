"""`builder stratum` launches the STRATUM operator console.

It now uses the `--sandbox` flag instead of `--experimental`.
"""

from __future__ import annotations

from typer.testing import CliRunner

from builder_ii.cli import app

runner = CliRunner()


class _DummyStratumApp:
    return_code = 0

    def __init__(self, *args, **kwargs):
        self.launched_kwargs = kwargs
        self.ran = False

    def run(self):
        self.ran = True


def test_stratum_launches(monkeypatch):
    built: list[_DummyStratumApp] = []

    def _factory(*args, **kwargs):
        app_instance = _DummyStratumApp(*args, **kwargs)
        built.append(app_instance)
        return app_instance

    monkeypatch.setattr("builder_ii.tui.app.StratumApp", _factory)

    result = runner.invoke(app, ["stratum"])

    assert result.exit_code == 0, result.output
    assert built[0].ran is True
    assert "stratum" in result.output.lower()
    assert "builder-stratum" in result.output.lower() or "operator console" in result.output.lower()

    result_no_guide = runner.invoke(app, ["stratum", "--no-guide"])
    assert result_no_guide.exit_code == 0, result_no_guide.output
    assert built[-1].launched_kwargs.get("skip_guide") is True
    
    result_sandbox = runner.invoke(app, ["stratum", "--sandbox"])
    assert result_sandbox.exit_code == 0, result_sandbox.output


def test_stratum_reports_a_failed_tui_instead_of_exiting_zero(monkeypatch):
    class _FailingStratumApp(_DummyStratumApp):
        return_code = 1

    monkeypatch.setattr("builder_ii.tui.app.StratumApp", _FailingStratumApp)

    result = runner.invoke(app, ["stratum"])

    assert result.exit_code == 1, (
        f"STRATUM reported return_code=1 but the launcher exited {result.exit_code}; "
        f"a crashed TUI is being reported as success"
    )
