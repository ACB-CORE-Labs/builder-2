"""STRATUM guide / walkthrough honesty and opt-out tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.stratum_guide import (
    WALKTHROUGH_STEPS,
    dismiss_guide,
    is_guide_skipped,
    normalize_composed_command,
    should_auto_open_guide,
    walkthrough_lines,
)


def test_normalize_composed_command_avoids_double_builder_prefix() -> None:
    assert normalize_composed_command("builder-platform matrix") == "builder-platform matrix"
    assert normalize_composed_command("uv run builder-session prepare-package generic -o .builder/session").startswith(
        "uv run "
    )
    assert normalize_composed_command("builder hitl status") == "builder hitl status"
    assert normalize_composed_command("verify plan") == "builder verify plan"


def test_walkthrough_commands_are_nonempty_and_named() -> None:
    assert len(WALKTHROUGH_STEPS) >= 5
    for step in WALKTHROUGH_STEPS:
        assert step.title
        assert step.why
        if step.command:
            assert "builder" in step.command or step.command.startswith("uv ")


def test_guide_dismiss_and_skip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRATUM_SKIP_GUIDE", raising=False)
    assert is_guide_skipped(project_root=tmp_path) is False
    path = dismiss_guide(tmp_path)
    assert path.is_file()
    assert is_guide_skipped(project_root=tmp_path) is True
    assert should_auto_open_guide(project_root=tmp_path, artifacts_dir=tmp_path / "missing") is False


def test_auto_open_when_artifacts_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRATUM_SKIP_GUIDE", raising=False)
    arts = tmp_path / "artifacts"
    arts.mkdir()
    assert should_auto_open_guide(project_root=tmp_path, artifacts_dir=arts) is True
    (arts / "x.json").write_text("{}", encoding="utf-8")
    assert should_auto_open_guide(project_root=tmp_path, artifacts_dir=arts) is False


def test_env_skip_guide(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATUM_SKIP_GUIDE", "1")
    assert is_guide_skipped(project_root=tmp_path) is True
    assert should_auto_open_guide(project_root=tmp_path, artifacts_dir=None, force_show=False) is False


def test_force_show_overrides_dismiss(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STRATUM_SKIP_GUIDE", raising=False)
    dismiss_guide(tmp_path)
    assert should_auto_open_guide(project_root=tmp_path, artifacts_dir=None, force_show=True) is True


def test_walkthrough_lines_include_opt_out() -> None:
    text = "\n".join(walkthrough_lines())
    assert "STRATUM_SKIP_GUIDE" in text
    assert "--no-guide" in text
    assert "prepare-package" in text


@pytest.mark.asyncio
async def test_stratum_app_accepts_guide_flags() -> None:
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        root = Path("/tmp/stratum-guide-test-root")
        mock_settings.return_value.core_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "TIER_0"
        mock_settings.return_value.project_root = root
        mock_settings.return_value.backend = "test"
        from builder_ii.tui.app import StratumApp

        app = StratumApp(skip_guide=True)
        assert app._force_skip_guide is True
        app2 = StratumApp(show_guide=True)
        assert app2._force_show_guide is True


def test_walkthrough_prepare_matches_session_cli_shape() -> None:
    """Step 4 command must match builder-session prepare-package TARGET -o DIR shape."""
    step = next(s for s in WALKTHROUGH_STEPS if "prepare package" in s.title.lower())
    assert step.command is not None
    assert "builder-session prepare-package" in step.command
    assert " -o " in step.command or " -o." in step.command
