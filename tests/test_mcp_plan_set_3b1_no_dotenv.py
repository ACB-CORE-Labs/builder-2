from __future__ import annotations

import os
from pathlib import Path

from builder_ii.adapters.mcp.server import GovernedMcpServer


def test_prepare_service_does_not_load_target_or_config_root_dotenv(tmp_path: Path, monkeypatch) -> None:
    target_root = tmp_path / "target"
    config_root = tmp_path / "builder-config"
    builder_root = tmp_path / "artifacts"
    target_root.mkdir()
    config_root.mkdir()

    target_key = "BUILDER_3B1_TARGET_DOTENV_SENTINEL"
    config_key = "BUILDER_3B1_CONFIG_DOTENV_SENTINEL"
    (target_root / ".env").write_text(f"{target_key}=target-secret\n", encoding="utf-8")
    (config_root / ".env").write_text(f"{config_key}=config-secret\n", encoding="utf-8")
    monkeypatch.delenv(target_key, raising=False)
    monkeypatch.delenv(config_key, raising=False)

    server = GovernedMcpServer(
        session_id="no-dotenv",
        builder_root=builder_root,
        target_root=target_root,
        target_name="generic",
        config_root=config_root,
    )
    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "prepare_package", "arguments": {"task": "prepare safely"}},
        }
    )

    assert response is not None
    assert response["result"]["isError"] is False, response
    assert os.environ.get(target_key) is None
    assert os.environ.get(config_key) is None
