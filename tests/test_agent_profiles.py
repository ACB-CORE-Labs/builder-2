from pathlib import Path
from types import SimpleNamespace

from builder_ii.agent_profiles import (
    agent_profile_names,
    agent_profiles,
    get_agent_profile,
    profiles_for_target,
    render_agent_profile,
    validate_agent_profiles,
)
from builder_ii.target_profiles import target_profile


def _settings(tmp_path: Path):
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("core", encoding="utf-8")
    (builder / "README.md").write_text("builder", encoding="utf-8")
    return SimpleNamespace(core_repo=core, project_root=builder)


def test_agent_profile_names_are_generic_base_profiles() -> None:
    assert agent_profile_names() == (
        "repo_mapper",
        "context_planner",
        "code_reviewer",
        "patch_planner",
        "verification_planner",
        "handoff_scribe",
    )


def test_all_profiles_forbid_shell_and_mutation_by_default() -> None:
    for profile in agent_profiles():
        assert "execute_shell" in profile.forbidden_tools
        assert "commit" in profile.forbidden_tools
        assert "push" in profile.forbidden_tools


def test_all_profiles_support_all_initial_targets() -> None:
    for profile in agent_profiles():
        assert profile.compatible_targets == ("generic", "builder", "core")


def test_profiles_for_target_returns_generic_profiles() -> None:
    assert {profile.name for profile in profiles_for_target("builder")} == set(agent_profile_names())
    assert {profile.name for profile in profiles_for_target("core")} == set(agent_profile_names())


def test_validate_agent_profiles_passes() -> None:
    assert validate_agent_profiles() == ()


def test_patch_planner_is_proposal_only() -> None:
    profile = get_agent_profile("patch_planner")

    assert profile.authority == "proposal_only"
    assert "applying patches" in profile.hitl_required_for
    assert "write_file" in profile.forbidden_tools


def test_render_agent_profile_without_target() -> None:
    rendered = render_agent_profile(get_agent_profile("repo_mapper"))

    assert "# Agent profile: repo_mapper" in rendered
    assert "## Authority" in rendered
    assert "## Output contract" in rendered


def test_render_agent_profile_with_target(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rendered = render_agent_profile(get_agent_profile("code_reviewer"), target_profile(settings, "builder"))

    assert "# Agent profile: code_reviewer" in rendered
    assert "## Selected target" in rendered
    assert "`builder`" in rendered
    assert "## Target principles" in rendered
