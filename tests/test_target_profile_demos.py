from builder_ii.target_profile_demos import (
    get_target_profile_demo,
    render_target_profile_demo,
    target_profile_demos,
    validate_target_profile_demos,
)
from builder_ii.target_profiles import target_names


def test_target_profile_demos_cover_initial_targets() -> None:
    demos = {demo.target: demo for demo in target_profile_demos()}

    assert tuple(demos) == target_names()
    assert validate_target_profile_demos() == ()


def test_each_demo_is_artifact_only_recipe() -> None:
    for demo in target_profile_demos():
        assert demo.commands
        assert demo.expected_artifacts
        assert demo.boundaries
        assert all("--output" in command for command in demo.commands)
        assert not any("start-readonly" in command for command in demo.commands)
        assert not any("run" in command.split()[0] for command in demo.commands)


def test_builder_and_core_demos_include_git_state_artifact() -> None:
    assert "builder_ii.git_state_record" in get_target_profile_demo("builder").expected_artifacts
    assert "builder_ii.git_state_record" in get_target_profile_demo("core").expected_artifacts


def test_generic_demo_uses_explicit_repo_path() -> None:
    generic = get_target_profile_demo("generic")

    assert any("--generic-repo /path/to/repo" in command for command in generic.commands)
    assert "builder_ii.git_state_record" not in generic.expected_artifacts


def test_core_demo_preserves_target_boundary() -> None:
    core = get_target_profile_demo("core")
    rendered = render_target_profile_demo(core)

    assert "CORE remains a target profile only" in rendered or "CORE is only a target profile" in rendered
    assert "CORE Workbench" in rendered
    assert "CORE runtime authority" in rendered


def test_render_demo_has_stable_sections() -> None:
    rendered = render_target_profile_demo(get_target_profile_demo("builder"))

    assert "# Target demo: builder" in rendered
    assert "## Purpose" in rendered
    assert "## Commands" in rendered
    assert "## Expected artifacts" in rendered
    assert "## Boundaries" in rendered
