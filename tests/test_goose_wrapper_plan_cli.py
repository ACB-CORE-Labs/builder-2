from __future__ import annotations

import json as json_lib
from pathlib import Path

from builder_ii.session_cli import session_app
from typer.testing import CliRunner

from builder_ii.adapters.goose.goose_projection import GOOSE_PROJECTION_KIND
from builder_ii.adapters.goose.goose_wrapper_plan import GOOSE_WRAPPER_PLAN_KIND

runner = CliRunner()


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def _write_projection(tmp_path: Path) -> Path:
    repo = _generic_repo(tmp_path)
    config_path = tmp_path / "session-config.json"
    projection_path = tmp_path / "goose-projection.json"
    config_result = runner.invoke(
        session_app, ["config", "generic", "--repo-path", str(repo), "--output", str(config_path)]
    )
    assert config_result.exit_code == 0
    projection_result = runner.invoke(
        session_app, ["goose-projection", str(config_path), "--output", str(projection_path)]
    )
    assert projection_result.exit_code == 0
    assert json_lib.loads(projection_path.read_text(encoding="utf-8"))["kind"] == GOOSE_PROJECTION_KIND
    return projection_path


def test_goose_wrapper_plan_cli_stdout(tmp_path: Path) -> None:
    projection_path = _write_projection(tmp_path)
    result = runner.invoke(session_app, ["goose-wrapper-plan", str(projection_path)])

    assert result.exit_code == 0
    plan = json_lib.loads(result.output)
    assert plan["kind"] == GOOSE_WRAPPER_PLAN_KIND
    assert plan["operator_launch"]["executes_now"] is False
    assert plan["operator_launch"]["requires_operator_execution"] is True
    assert plan["governance"]["goose_runtime_start"] == "DISABLED"


def test_goose_wrapper_plan_cli_output_and_validate(tmp_path: Path) -> None:
    projection_path = _write_projection(tmp_path)
    wrapper_path = tmp_path / "goose-wrapper-plan.json"
    result = runner.invoke(session_app, ["goose-wrapper-plan", str(projection_path), "--output", str(wrapper_path)])

    assert result.exit_code == 0
    assert wrapper_path.exists()
    assert "Goose wrapper plan written" in result.stdout

    validate_result = runner.invoke(session_app, ["validate-goose-wrapper-plan", str(wrapper_path)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout
