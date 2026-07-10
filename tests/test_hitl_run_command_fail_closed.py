from pathlib import Path

import pytest
from typer.testing import CliRunner

from builder_ii.cli.hitl_execution_cli import hitl_app
from builder_ii.hitl_command_runner import RunCommandDisabledError, execute_hitl_command

runner = CliRunner()


def test_execute_hitl_command_is_fail_closed(tmp_path: Path) -> None:
    with pytest.raises(RunCommandDisabledError, match="fail-closed"):
        execute_hitl_command(
            request_path=tmp_path / "req.json",
            proposal_path=tmp_path / "prop.json",
            approval_path=tmp_path / "app.json",
            output_dir=tmp_path / "out",
        )


def test_run_command_cli_points_to_run_approved(tmp_path: Path) -> None:
    req = tmp_path / "req.json"
    prop = tmp_path / "prop.json"
    app = tmp_path / "app.json"
    for path in (req, prop, app):
        path.write_text("{}", encoding="utf-8")

    result = runner.invoke(
        hitl_app,
        [
            "run-command",
            "--request",
            str(req),
            "--proposal",
            str(prop),
            "--approval",
            str(app),
            "--output-dir",
            str(tmp_path / "out"),
        ],
    )
    assert result.exit_code == 2
    assert "builder-verify run-approved" in result.output
    assert "fail-closed" in result.output
