"""V.4 CORE target profile isolation (catalog + doctor; not Workbench)."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from builder_ii.cli.targets_cli import targets_app
from builder_ii.target_profiles import (
    target_profile,
    validate_target_profile_artifact,
)
from builder_ii.targets.core import (
    core_profile_block,
    doctor_core_profile,
    validate_core_profile_block,
)

runner = CliRunner()


def _settings(tmp_path: Path):
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("core", encoding="utf-8")
    (core / "AGENTS.md").write_text("agents", encoding="utf-8")
    (builder / "README.md").write_text("builder", encoding="utf-8")
    (builder / "builder_ii").mkdir()
    return SimpleNamespace(target_repo=core, project_root=builder)


def test_core_profile_block_valid() -> None:
    block = core_profile_block()
    assert validate_core_profile_block(block) == []
    assert block["workbench_coupling"] == "NONE"
    assert block["grants_runtime_authority"] is False
    assert block["platform_identity"] is False
    assert block["semgrep_executed_by_profile"] is False
    assert block["isolation"] == "CORE_TARGET_ONLY"
    assert any(i["id"] == "versor_condition" for i in block["invariants"])
    assert "preferred_context" in block["safe_file_path_categories"]
    assert block["verification_routing_defaults"]["routes_generic_platform"] is False


def test_core_artifact_includes_core_profile(tmp_path: Path) -> None:
    profile = target_profile(_settings(tmp_path), "core")
    art = profile.to_artifact_dict()
    assert "core_profile" in art
    assert validate_target_profile_artifact(art) == []
    assert art["core_profile"]["workbench_coupling"] == "NONE"
    assert art["governance"]["core_workbench_coupling"] == "NONE"


def test_builder_artifact_has_no_core_profile(tmp_path: Path) -> None:
    profile = target_profile(_settings(tmp_path), "builder")
    art = profile.to_artifact_dict()
    assert "core_profile" not in art
    assert validate_target_profile_artifact(art) == []


def test_core_profile_rejected_on_generic(tmp_path: Path) -> None:
    profile = target_profile(_settings(tmp_path), "generic", generic_repo=tmp_path)
    art = profile.to_artifact_dict()
    art["core_profile"] = core_profile_block()
    errors = validate_target_profile_artifact(art)
    assert any("only valid on the core" in e for e in errors)


def test_doctor_core_profile_ok(tmp_path: Path) -> None:
    report = doctor_core_profile(_settings(tmp_path))
    assert report["ok"] is True
    assert report["target"] == "core"
    assert report["semgrep_executed"] is False
    assert report["workbench_coupling"] == "NONE"
    assert report["grants_runtime_authority"] is False


def test_render_show_core_includes_v4_sections(tmp_path: Path) -> None:
    from builder_ii.target_profiles import render_target_profile

    rendered = render_target_profile(target_profile(_settings(tmp_path), "core"))
    assert "## CORE profile (V.4 isolation)" in rendered
    assert "### Invariants" in rendered
    assert "### Semgrep rules catalog" in rendered
    assert "versor_condition" in rendered


def test_cli_show_core() -> None:
    result = runner.invoke(targets_app, ["show", "core"])
    assert result.exit_code == 0
    assert "CORE profile (V.4 isolation)" in result.stdout
    assert "workbench_coupling" in result.stdout


def test_cli_doctor_core(tmp_path: Path) -> None:
    out = tmp_path / "doctor.json"
    result = runner.invoke(targets_app, ["doctor", "core", "-o", str(out)])
    assert result.exit_code == 0, result.stdout
    assert out.is_file()
    data = json_lib.loads(out.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["semgrep_executed"] is False


def test_cli_doctor_rejects_non_core() -> None:
    result = runner.invoke(targets_app, ["doctor", "builder"])
    assert result.exit_code == 2
