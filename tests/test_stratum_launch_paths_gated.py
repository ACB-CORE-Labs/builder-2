"""H8 — every way to launch STRATUM must consult command authority first.

The 2026-07-19 TUI/UX red-team audit (docs/audits/TUI_UX_RED_TEAM_MASTERY_AUDIT.md, finding H8)
found that `builder-platform tui` and `python -m builder_ii.tui` constructed StratumApp directly,
skipping the enforce_command_authority gate that `builder stratum` and `builder-stratum` both call.
This file pins two things: a structural scan so a *future* fifth entrypoint cannot silently
reintroduce the gap, and a behavioral test per known entrypoint proving a denial actually stops
construction rather than merely being logged or ignored.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from builder_ii.cli import app as root_app
from builder_ii.cli.platform_status_cli import platform_app
from builder_ii.cli.stratum_cli import stratum_app
from builder_ii.governance.authority import CommandAuthorityError

runner = CliRunner()

_REPO_ROOT = Path(__file__).resolve().parent.parent
_BUILDER_II = _REPO_ROOT / "builder_ii"
_CONSTRUCTION = re.compile(r"StratumApp\s*\(")
_CLASS_DEF = re.compile(r"class\s+StratumApp\s*\(")


def _files_constructing_stratum_app() -> list[Path]:
    hits: list[Path] = []
    for path in sorted(_BUILDER_II.rglob("*.py")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if _CONSTRUCTION.search(line) and not _CLASS_DEF.search(line):
                hits.append(path)
                break
    return hits


def test_every_stratum_app_construction_site_gates_on_command_authority() -> None:
    """Every place under builder_ii/ that constructs StratumApp(...) must also reference
    enforce_command_authority somewhere in the same file. A coarse per-file check, not full
    control-flow proof, but it is exactly the shape of the H8 gap: two files built the app
    with zero reference to the gate anywhere in the file at all."""
    sites = _files_constructing_stratum_app()
    assert sites, "no StratumApp construction sites found -- the scan itself is broken"
    ungated = [p for p in sites if "enforce_command_authority" not in p.read_text(encoding="utf-8")]
    assert not ungated, f"StratumApp constructed without an authority gate in: {[str(p) for p in ungated]}"


def _deny_authority(monkeypatch: pytest.MonkeyPatch, calls: list[str]) -> None:
    def _raise(name: str, *_args: object, **_kwargs: object) -> None:
        calls.append(name)
        raise CommandAuthorityError("denied for test")

    monkeypatch.setattr("builder_ii.governance.authority.enforce_command_authority", _raise)


class _RecordingStratumApp:
    """Stands in for StratumApp; records construction attempts without launching a real TUI."""

    return_code = 0

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.constructed_with = (args, kwargs)

    def run(self) -> int:
        return self.return_code


def test_builder_stratum_refuses_before_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    constructed: list[object] = []
    _deny_authority(monkeypatch, calls)
    monkeypatch.setattr(
        "builder_ii.tui.app.StratumApp",
        lambda *a, **kw: constructed.append((a, kw)) or _RecordingStratumApp(*a, **kw),
    )

    result = runner.invoke(root_app, ["stratum"])

    assert result.exit_code != 0
    assert calls == ["builder stratum"]
    assert constructed == [], "StratumApp was constructed despite a denied authority check"


def test_builder_stratum_console_script_refuses_before_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    constructed: list[object] = []
    _deny_authority(monkeypatch, calls)
    monkeypatch.setattr(
        "builder_ii.tui.app.StratumApp",
        lambda *a, **kw: constructed.append((a, kw)) or _RecordingStratumApp(*a, **kw),
    )

    result = runner.invoke(stratum_app, [])

    assert result.exit_code != 0
    assert calls == ["builder stratum"]
    assert constructed == [], "StratumApp was constructed despite a denied authority check"


def test_builder_platform_tui_refuses_before_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    """H8: builder-platform tui previously built StratumApp with zero authority check at all."""
    calls: list[str] = []
    constructed: list[object] = []
    _deny_authority(monkeypatch, calls)
    monkeypatch.setattr(
        "builder_ii.tui.app.StratumApp",
        lambda *a, **kw: constructed.append((a, kw)) or _RecordingStratumApp(*a, **kw),
    )

    result = runner.invoke(platform_app, ["tui"])

    assert result.exit_code != 0
    assert calls, "builder-platform tui never called enforce_command_authority"
    assert constructed == [], "StratumApp was constructed despite a denied authority check"


def test_python_dash_m_tui_refuses_before_construction(monkeypatch: pytest.MonkeyPatch) -> None:
    """H8: python -m builder_ii.tui previously built StratumApp with zero authority check at all."""
    calls: list[str] = []
    constructed: list[object] = []
    _deny_authority(monkeypatch, calls)
    monkeypatch.setattr(
        "builder_ii.tui.app.StratumApp",
        lambda *a, **kw: constructed.append((a, kw)) or _RecordingStratumApp(*a, **kw),
    )

    from builder_ii.tui.__main__ import main

    with pytest.raises(CommandAuthorityError):
        main()

    assert calls, "python -m builder_ii.tui never called enforce_command_authority"
    assert constructed == [], "StratumApp was constructed despite a denied authority check"
