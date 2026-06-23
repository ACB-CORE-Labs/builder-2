from builder_ii.config import load_settings
from builder_ii.goose_setup import build_goose_config, skills_source


def test_goose_config_has_slash_commands():
    settings = load_settings()
    cfg = build_goose_config(settings)
    commands = {item["command"] for item in cfg["slash_commands"]}
    assert "explore" in commands
    assert "implement" in commands
    assert "handoff" in commands


def test_skills_exist():
    settings = load_settings()
    src = skills_source(settings)
    assert (src / "core-governed-coding" / "SKILL.md").exists()