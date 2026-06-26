from pathlib import Path
from types import SimpleNamespace

from builder_ii import deepagents_bridge
from builder_ii.agent_profiles import agent_profile_names, get_agent_profile
from builder_ii.deepagents_bridge import (
    REQUIRED_DENIED_TOOLS,
    bridge_spec_for,
    deepagent_bridge_spec,
    deepagents_availability,
    render_bridge_prompt,
    render_bridge_spec,
    validate_bridge_spec,
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


def test_availability_does_not_require_dependency() -> None:
    status = deepagents_availability()

    assert isinstance(status.available, bool)
    assert status.detail
    assert status.dependency_mode == "optional"
    assert status.runtime_execution == "disabled"
    assert status.file_writes == "disabled"
    assert status.shell_execution == "disabled"


def test_availability_reports_missing_dependency(monkeypatch) -> None:
    monkeypatch.setattr(deepagents_bridge.importlib.util, "find_spec", lambda name: None)

    status = deepagents_availability()

    assert status.available is False
    assert status.import_status == "MISS"
    assert status.source is None
    assert status.create_deep_agent_present is False
    assert status.dependency_mode == "optional"


def test_availability_reports_present_dependency_without_enabling_runtime(monkeypatch) -> None:
    fake_module = SimpleNamespace(
        __file__="/fake/site-packages/deepagents/__init__.py",
        create_deep_agent=lambda: None,
    )
    fake_spec = SimpleNamespace(origin="/fake/site-packages/deepagents/__init__.py")

    monkeypatch.setattr(deepagents_bridge.importlib.util, "find_spec", lambda name: fake_spec)
    monkeypatch.setattr(deepagents_bridge.importlib, "import_module", lambda name: fake_module)
    monkeypatch.setattr(deepagents_bridge.metadata, "version", lambda name: "0.2.8")

    status = deepagents_availability()

    assert status.available is True
    assert status.import_status == "PASS"
    assert status.version == "0.2.8"
    assert status.source == "/fake/site-packages/deepagents/__init__.py"
    assert status.create_deep_agent_present is True
    assert status.runtime_execution == "disabled"
    assert status.file_writes == "disabled"
    assert status.shell_execution == "disabled"


def test_smoke_rows_include_authority_boundaries(monkeypatch) -> None:
    monkeypatch.setattr(deepagents_bridge.importlib.util, "find_spec", lambda name: None)

    rows = dict((check, (status, detail)) for check, status, detail in deepagents_availability().rows())

    assert rows["deepagents import"][0] == "MISS"
    assert rows["runtime execution"][0] == "DISABLED"
    assert rows["file writes"][0] == "DISABLED"
    assert rows["shell execution"][0] == "DISABLED"
    assert rows["builder-II dependency mode"][0] == "OPTIONAL"


def test_bridge_spec_disables_runtime_by_default(tmp_path: Path) -> None:
    target = target_profile(_settings(tmp_path), "builder")
    spec = deepagent_bridge_spec(get_agent_profile("patch_planner"), target)

    assert spec.name == "builder-patch-planner"
    assert spec.target == "builder"
    assert spec.runtime_enabled is False
    assert "write_file" in spec.denied_tools
    assert "execute_shell" in spec.denied_tools
    assert validate_bridge_spec(spec) == ()


def test_all_bridge_specs_enforce_required_denials(tmp_path: Path) -> None:
    target = target_profile(_settings(tmp_path), "builder")

    for name in agent_profile_names():
        spec = bridge_spec_for(name, target)
        for denied in REQUIRED_DENIED_TOOLS:
            assert denied in spec.denied_tools
        assert validate_bridge_spec(spec) == ()


def test_bridge_prompt_contains_boundary_text(tmp_path: Path) -> None:
    target = target_profile(_settings(tmp_path), "generic")
    prompt = render_bridge_prompt(get_agent_profile("code_reviewer"), target)

    assert "deepagents bridge boundary" in prompt
    assert "not runtime execution permission" in prompt
    assert "Do not write files" in prompt


def test_bridge_spec_dict_shape(tmp_path: Path) -> None:
    target = target_profile(_settings(tmp_path), "core")
    spec = bridge_spec_for("verification_planner", target)
    data = spec.as_subagent_dict()

    assert data["name"] == "core-verification-planner"
    assert data["metadata"]["target"] == "core"
    assert data["metadata"]["runtime_enabled"] is False
    assert data["metadata"]["builder_ii_bridge"] is True
    assert "prompt" in data


def test_render_bridge_spec_includes_sections(tmp_path: Path) -> None:
    target = target_profile(_settings(tmp_path), "builder")
    rendered = render_bridge_spec(bridge_spec_for("repo_mapper", target))

    assert "# deepagents bridge spec" in rendered
    assert "## Target" in rendered
    assert "## Runtime" in rendered
    assert "disabled" in rendered
    assert "## Denied tools" in rendered
