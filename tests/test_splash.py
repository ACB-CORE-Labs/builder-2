"""Splash hero path resolution and native/terminal mode flags."""

from __future__ import annotations

from pathlib import Path

from builder_ii.tui.widgets.splash import (
    HERO_RELATIVE,
    SPLASH_HOLD_SECONDS,
    _native_splash_allowed,
    _want_terminal_image,
    load_hero_renderable,
    resolve_hero_path,
)


def test_splash_hold_is_brief() -> None:
    assert 2.5 <= SPLASH_HOLD_SECONDS <= 5.0


def test_resolve_hero_from_repo() -> None:
    repo = Path(__file__).resolve().parents[1]
    path = resolve_hero_path(repo)
    assert path is not None
    assert path.name == "builder-ii-splash-hero.jpeg"
    assert path.is_file()


def test_terminal_image_opt_in_only(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("BUILDER_SPLASH_TERMINAL_IMAGE", raising=False)
    assert _want_terminal_image() is False
    path = resolve_hero_path(Path(__file__).resolve().parents[1])
    assert path is not None
    # Default: no terminal pixel mosaic
    assert load_hero_renderable(path) is None
    monkeypatch.setenv("BUILDER_SPLASH_TERMINAL_IMAGE", "1")
    assert _want_terminal_image() is True


def test_native_allowed_respects_env(monkeypatch) -> None:
    monkeypatch.setenv("BUILDER_SPLASH_NATIVE", "0")
    assert _native_splash_allowed() is False


def test_resolve_missing_project_root_falls_back_to_package(tmp_path: Path) -> None:
    assert not (tmp_path / HERO_RELATIVE).is_file()
    path = resolve_hero_path(tmp_path)
    assert path is not None
    assert path.is_file()
