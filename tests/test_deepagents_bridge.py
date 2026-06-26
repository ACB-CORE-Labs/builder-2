import json as json_lib
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from builder_ii import deepagents_bridge
from builder_ii.bridge_cli import bridge_app
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


def test_to_json_dict_format() -> None:
    status = deepagents_availability()
    data = status.to_json_dict()
    assert data["kind"] == "builder_ii.deepagents_smoke"
    assert data["schema_version"] == 1
    assert data["deepagents_import"] in ("PASS", "MISS", "ERROR")
    assert "deepagents_source" in data
    assert "deepagents_version" in data
    assert data["create_deep_agent"] in ("PRESENT", "MISSING")
    assert data["runtime_execution"] == "DISABLED"
    assert data["file_writes"] == "DISABLED"
    assert data["shell_execution"] == "DISABLED"
    assert data["builder_ii_dependency_mode"] == "OPTIONAL"


def test_cli_deepagents_smoke_default() -> None:
    runner = CliRunner()
    result = runner.invoke(bridge_app, ["deepagents-smoke"])
    assert result.exit_code == 0
    assert "Check" in result.stdout
    assert "Status" in result.stdout
    assert "Detail" in result.stdout


def test_cli_deepagents_smoke_json() -> None:
    runner = CliRunner()
    result = runner.invoke(bridge_app, ["deepagents-smoke", "--json"])
    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.deepagents_smoke"
    assert data["schema_version"] == 1


def test_cli_deepagents_smoke_output(tmp_path: Path) -> None:
    runner = CliRunner()
    out_file = tmp_path / "subdir" / "smoke_report.json"
    result = runner.invoke(bridge_app, ["deepagents-smoke", "--output", str(out_file)])
    assert result.exit_code == 0
    assert "kind" not in result.stdout
    assert out_file.exists()
    data = json_lib.loads(out_file.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.deepagents_smoke"


def test_cli_deepagents_smoke_both(tmp_path: Path) -> None:
    runner = CliRunner()
    out_file = tmp_path / "smoke_report2.json"
    result = runner.invoke(bridge_app, ["deepagents-smoke", "--json", "--output", str(out_file)])
    assert result.exit_code == 0
    assert out_file.exists()
    data_stdout = json_lib.loads(result.stdout)
    assert data_stdout["kind"] == "builder_ii.deepagents_smoke"
    data_file = json_lib.loads(out_file.read_text(encoding="utf-8"))
    assert data_file["kind"] == "builder_ii.deepagents_smoke"


def test_cli_deepagents_smoke_default_does_not_write(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(bridge_app, ["deepagents-smoke"])
    assert result.exit_code == 0
    assert not any(tmp_path.iterdir())
