import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli import app
from builder_ii.config import load_settings
from builder_ii.goose_setup import (
    SETUP_REDIRECT_KIND,
    build_goose_config,
    legacy_setup_redirect_payload,
    skills_source,
)

runner = CliRunner()


def test_goose_config_has_slash_commands():
    settings = load_settings()
    cfg = build_goose_config(settings)
    commands = {item["command"] for item in cfg["slash_commands"]}
    assert "explore" in commands
    assert "implement" in commands
    assert "review" in commands
    assert "verify" in commands
    assert "plan" in commands
    assert "platform" in commands
    assert "coding" in commands
    assert "handoff" not in commands


def test_skills_exist():
    settings = load_settings()
    src = skills_source(settings)
    assert (src / "core-governed-coding" / "SKILL.md").exists()


def test_legacy_setup_redirect_payload_is_passive() -> None:
    payload = legacy_setup_redirect_payload(load_settings())
    assert payload["kind"] == SETUP_REDIRECT_KIND
    assert any(row["surface"] == "builder setup" for row in payload["legacy_setup_surfaces"])
    assert any(command.startswith("builder-setup plan") for command in payload["governed_setup_commands"])


def test_builder_setup_fails_closed_without_writes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    target = tmp_path / "target"
    home.mkdir()
    target.mkdir()
    env = {
        "HOME": str(home),
        "BUILDER_TARGET_REPO": str(target),
        "CORE_REPO_PATH": str(target),
    }

    result = runner.invoke(app, ["setup"], env=env)

    assert result.exit_code == 1, result.output
    assert "Legacy `builder setup` is disabled in R1.4." in result.output
    assert "builder-setup plan" in result.output
    assert "builder-setup apply" in result.output
    assert not (home / ".config" / "goose" / "config.yaml").exists()
    assert not (target / ".goosehints").exists()
    assert not (target / ".agents" / "skills").exists()


def test_builder_config_reports_redirect_metadata_without_writes(tmp_path: Path) -> None:
    home = tmp_path / "home"
    target = tmp_path / "target"
    home.mkdir()
    target.mkdir()
    env = {
        "HOME": str(home),
        "BUILDER_TARGET_REPO": str(target),
        "CORE_REPO_PATH": str(target),
    }

    result = runner.invoke(app, ["config"], env=env)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["kind"] == SETUP_REDIRECT_KIND
    assert payload["settings"]["target_repo"] == str(target.resolve())
    assert not (home / ".config" / "goose" / "config.yaml").exists()


def test_goose_setup_module_remains_passive_source() -> None:
    source = Path("builder_ii/goose_setup.py").read_text(encoding="utf-8")
    assert "import subprocess" not in source
    assert "write_text(" not in source
    assert "copytree(" not in source
