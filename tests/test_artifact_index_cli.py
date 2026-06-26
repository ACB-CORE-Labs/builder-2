from typer.testing import CliRunner

from builder_ii.artifact_index_cli import index_app


def test_artifact_index_app_help() -> None:
    result = CliRunner().invoke(index_app, ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout
