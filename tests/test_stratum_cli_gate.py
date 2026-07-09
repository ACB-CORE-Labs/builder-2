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


def test_stratum_launches_with_experimental_flag(monkeypatch):
    launched = {}

    class _DummyStratumApp:
        def run(self):
            launched["ran"] = True

    monkeypatch.setattr("builder_ii.tui.app.StratumApp", _DummyStratumApp)

    result = runner.invoke(app, ["stratum", "--experimental"])

    assert result.exit_code == 0, result.output
    assert launched.get("ran") is True
    assert "experimental" in result.output.lower()
