from typer.testing import CliRunner

from builder_ii.chain_summary_cli import chain_app


def test_chain_app_help() -> None:
    result = CliRunner().invoke(chain_app, ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout
