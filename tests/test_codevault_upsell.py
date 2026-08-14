"""CodeVault upsell fires only on genuine open-core fallback paths."""

from __future__ import annotations

from pathlib import Path

from builder_ii.cli import code_vault_cli
from builder_ii.core.codevault_upsell import (
    CODEVAULT_CLI_UPGRADE_MESSAGE,
    format_context_scale_upsell,
)
from builder_ii.core.repo_map import create_repo_map


def test_cli_message_keeps_live_voice_and_has_upgrade_pointer() -> None:
    msg = code_vault_cli.CODE_VAULT_UPGRADE_MESSAGE
    assert "CodeVault is not installed" in msg
    assert "separately licensed" in msg
    assert "Upgrade to CodeVault" in format_context_scale_upsell() or "upgrade" in msg.lower()
    assert CODEVAULT_CLI_UPGRADE_MESSAGE in msg or msg == CODEVAULT_CLI_UPGRADE_MESSAGE


def test_codevault_url_env(monkeypatch) -> None:
    monkeypatch.setenv("CODEVAULT_URL", "https://example.test/codevault")
    assert "https://example.test/codevault" in format_context_scale_upsell()


def test_repo_map_upsell_only_when_truncated(tmp_path: Path) -> None:
    (tmp_path / "ok.py").write_text("x = 1\n", encoding="utf-8")
    normal = create_repo_map(str(tmp_path), target_name="builder", max_file_bytes=10_000)
    assert normal["truncated"] is False
    assert normal.get("upgrade_hint") is None

    (tmp_path / "huge.py").write_text("x" * 5000, encoding="utf-8")
    truncated = create_repo_map(str(tmp_path), target_name="builder", max_file_bytes=100)
    assert truncated["truncated"] is True
    assert truncated.get("upgrade_hint") is not None
    assert "Upgrade to CodeVault" in truncated["upgrade_hint"]
