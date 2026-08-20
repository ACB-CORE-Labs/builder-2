from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

import builder_ii.cli.mcp_cli as mcp_cli
from builder_ii.cli.mcp_cli import mcp_app


def test_serve_passes_target_config_and_artifact_identities_separately(tmp_path: Path, monkeypatch) -> None:
    target_root = tmp_path / "target"
    project_root = tmp_path / "builder-platform"
    builder_root = tmp_path / "artifacts"
    target_root.mkdir()
    project_root.mkdir()
    captured: dict[str, object] = {}

    class FakeServer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def serve_stdio(self):
            captured["served"] = True

    monkeypatch.chdir(target_root)
    monkeypatch.setenv("BUILDER_MCP_SESSION_ID", "cli-identity")
    monkeypatch.setenv("BUILDER_MCP_TARGET_PROFILE", "core")
    monkeypatch.setenv("BUILDER_MCP_PROJECT_ROOT", str(project_root))
    monkeypatch.setattr(mcp_cli, "enforce_command_authority", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("builder_ii.adapters.mcp.server.GovernedMcpServer", FakeServer)

    result = CliRunner().invoke(mcp_app, ["serve", "--builder-root", str(builder_root)])

    assert result.exit_code == 0, result.output
    assert captured == {
        "session_id": "cli-identity",
        "builder_root": builder_root,
        "target_root": target_root,
        "target_name": "core",
        "config_root": project_root,
        "allow_artifact_root_inside_target": False,
        "served": True,
    }


def test_serve_defaults_to_canonical_target_artifact_namespace(tmp_path: Path, monkeypatch) -> None:
    target_root = tmp_path / "target"
    target_root.mkdir()
    captured: dict[str, object] = {}

    class FakeServer:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def serve_stdio(self):
            captured["served"] = True

    monkeypatch.chdir(target_root)
    monkeypatch.delenv("BUILDER_ARTIFACT_ROOT", raising=False)
    monkeypatch.delenv("CORE_ARTIFACT_ROOT", raising=False)
    monkeypatch.setattr(mcp_cli, "enforce_command_authority", lambda *_args, **_kwargs: None)
    monkeypatch.setattr("builder_ii.adapters.mcp.server.GovernedMcpServer", FakeServer)

    result = CliRunner().invoke(mcp_app, ["serve"])

    assert result.exit_code == 0, result.output
    assert captured["builder_root"] == (target_root / ".builder" / "artifacts").resolve()
    assert captured["target_root"] == target_root.resolve()
    assert captured["allow_artifact_root_inside_target"] is False
    assert captured["served"] is True
