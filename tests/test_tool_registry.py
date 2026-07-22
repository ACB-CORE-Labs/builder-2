from pathlib import Path

from builder_ii.core.tool_registry import check_tool, missing_required_tools, tool_registry, tools_by_tier


def test_registry_contains_tier_one_and_tier_two_tools() -> None:
    names = {tool.name for tool in tool_registry()}

    assert {"repomix", "serena", "semgrep", "ruff", "rg", "tea"} <= names
    assert {"aider", "ast-grep", "promptfoo"} <= names


def test_required_tools_have_install_guidance() -> None:
    required = [tool for tool in tool_registry() if tool.required]

    assert required
    for tool in required:
        assert tool.install
        assert tool.integration


def test_notes_default_is_plain_markdown_vault() -> None:
    notes = {tool.name: tool for tool in tools_by_tier("notes")}

    assert notes["markdown-vault"].required is True
    assert notes["markdown-vault"].command is None
    assert notes["markdown-vault"].open_source is True
    assert notes["obsidian"].open_source is False
    assert notes["logseq"].open_source is True
    assert notes["zettlr"].open_source is True


def test_commandless_required_markdown_vault_is_available() -> None:
    tool = next(tool for tool in tool_registry() if tool.name == "markdown-vault")
    check = check_tool(tool)

    assert check.status == "installed"


def test_missing_required_tools_only_reports_required_entries() -> None:
    for check in missing_required_tools():
        assert check.tool.required is True
        assert check.status == "missing"


def test_install_tools_script_exposes_expected_modes() -> None:
    script = Path("scripts/install-tools.sh")
    text = script.read_text(encoding="utf-8")

    assert "required|tier1|tier2|notes|all|status" in text
    assert "install_required" in text
    assert "install_tier1" in text
    assert "install_tier2" in text
    assert "install_notes" in text
    assert "show_status" in text


def test_install_tools_script_is_command_aware() -> None:
    text = Path("scripts/install-tools.sh").read_text(encoding="utf-8")

    assert "brew_install_cmd ruff ruff" in text
    assert "brew_install_cmd ripgrep rg" in text
    assert "brew_install_cmd fd fd" in text
    assert "uv_tool_install_cmd pre-commit pre-commit" in text
    assert "npm_global_install_cmd promptfoo promptfoo" in text
