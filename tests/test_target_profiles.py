from pathlib import Path
from types import SimpleNamespace

from builder_ii.target_profiles import build_target_profiles, render_target_profile, target_names, target_profile, validate_target_profiles


def _settings(tmp_path: Path):
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("core", encoding="utf-8")
    (builder / "README.md").write_text("builder", encoding="utf-8")
    (builder / "builder_ii").mkdir()
    return SimpleNamespace(core_repo=core, project_root=builder)


def test_target_names_are_stable() -> None:
    assert target_names() == ("generic", "builder", "core")


def test_profiles_resolve_repositories(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    generic = tmp_path / "generic"
    generic.mkdir()
    profiles = {profile.name: profile for profile in build_target_profiles(settings, generic_repo=generic)}

    assert profiles["generic"].repo == generic.resolve()
    assert profiles["builder"].repo == settings.project_root.resolve()
    assert profiles["core"].repo == settings.core_repo.resolve()


def test_builder_profile_stays_generic_first(tmp_path: Path) -> None:
    profile = target_profile(_settings(tmp_path), "builder")

    assert "generic-first" in " ".join(profile.principles)
    assert "builder_ii" in profile.context_defaults


def test_core_profile_is_isolated_target(tmp_path: Path) -> None:
    profile = target_profile(_settings(tmp_path), "core")

    assert "target profile" in profile.description
    assert profile.notes


def test_validate_profiles_passes_for_existing_repos(tmp_path: Path) -> None:
    assert validate_target_profiles(_settings(tmp_path)) == ()


def test_validate_profiles_reports_missing_core_repo(tmp_path: Path) -> None:
    builder = tmp_path / "builder"
    builder.mkdir()
    settings = SimpleNamespace(core_repo=tmp_path / "missing-core", project_root=builder)

    assert any("core repo missing" in error for error in validate_target_profiles(settings))


def test_render_profile_has_expected_sections(tmp_path: Path) -> None:
    rendered = render_target_profile(target_profile(_settings(tmp_path), "builder"))

    assert "# Target profile: builder" in rendered
    assert "## Repository" in rendered
    assert "## Context defaults" in rendered
    assert "## Verification hints" in rendered
    assert "## Principles" in rendered
