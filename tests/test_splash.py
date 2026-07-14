"""Splash hero path resolution and hold timing constants."""

from __future__ import annotations

from pathlib import Path

from builder_ii.tui.widgets.splash import (
    HERO_RELATIVE,
    SPLASH_HOLD_SECONDS,
    load_hero_renderable,
    resolve_hero_path,
)


def test_splash_hold_is_about_three_seconds() -> None:
    assert 2.5 <= SPLASH_HOLD_SECONDS <= 4.0


def test_resolve_hero_from_repo() -> None:
    repo = Path(__file__).resolve().parents[1]
    path = resolve_hero_path(repo)
    assert path is not None
    assert path.name == "builder-ii-splash-hero.jpeg"
    assert path.is_file()


def test_load_hero_renderable() -> None:
    repo = Path(__file__).resolve().parents[1]
    path = repo / HERO_RELATIVE
    assert path.is_file()
    renderable = load_hero_renderable(path)
    assert renderable is not None


def test_resolve_missing_project_root_falls_back_to_package(tmp_path: Path) -> None:
    """Explicit root without image still falls back to package/cwd so splash works."""
    assert not (tmp_path / HERO_RELATIVE).is_file()
    path = resolve_hero_path(tmp_path)
    # Package layout or cwd should still locate the repo hero in this worktree.
    assert path is not None
    assert path.is_file()
