from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.wrp_cli import wrp_app

runner = CliRunner()


def test_wrp_cli_classify_and_validate(tmp_path: Path) -> None:
    out = tmp_path / "clf.json"
    result = runner.invoke(wrp_app, ["classify", "--text", "implement a validator", "-o", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    result = runner.invoke(wrp_app, ["validate", str(out)])
    assert result.exit_code == 0, result.output


def test_wrp_cli_score_classifier() -> None:
    result = runner.invoke(wrp_app, ["score-classifier"])
    assert result.exit_code == 0, result.output


def test_wrp_cli_gate_and_route(tmp_path: Path) -> None:
    result = runner.invoke(
        wrp_app,
        ["gate", "--tool", "shell", "--domain", "local_workspace", "-o", str(tmp_path / "gate.json")],
    )
    assert result.exit_code == 0, result.output
    result = runner.invoke(wrp_app, ["route", "--text", "fix the digest mismatch", "-o", str(tmp_path / "r.json")])
    assert result.exit_code == 0, result.output
