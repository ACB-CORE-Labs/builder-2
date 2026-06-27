from __future__ import annotations

import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.session_cli import session_app
from builder_ii.goose_projection import GOOSE_PROJECTION_KIND
from builder_ii.session_config import SESSION_CONFIG_KIND

runner = CliRunner()


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def test_goose_projection_cli_stdout(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    config_path = tmp_path / "session-config.json"
    config_result = runner.invoke(
        session_app,
        ["config", "generic", "--repo-path", str(repo), "--task", "project Goose", "--output", str(config_path)],
    )
    assert config_result.exit_code == 0
    assert json_lib.loads(config_path.read_text(encoding="utf-8"))["kind"] == SESSION_CONFIG_KIND

    projection_result = runner.invoke(session_app, ["goose-projection", str(config_path)])

    assert projection_result.exit_code == 0
    projection = json_lib.loads(projection_result.output)
    assert projection["kind"] == GOOSE_PROJECTION_KIND
    assert projection["projection_state"] == "PLANNED_ONLY"
    assert projection["governance"]["goose_runtime_start"] == "DISABLED"
    assert projection["goose_native_surface"]["env"]["GOOSE_MODEL"]


def test_goose_projection_cli_output_and_validate(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    config_path = tmp_path / "session-config.json"
    projection_path = tmp_path / "goose-projection.json"
    config_result = runner.invoke(session_app, ["config", "generic", "--repo-path", str(repo), "--output", str(config_path)])
    assert config_result.exit_code == 0

    projection_result = runner.invoke(
        session_app,
        ["goose-projection", str(config_path), "--output", str(projection_path)],
    )
    assert projection_result.exit_code == 0
    assert projection_path.exists()
    assert "Goose projection written" in projection_result.stdout

    validate_result = runner.invoke(session_app, ["validate-goose-projection", str(projection_path)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout
