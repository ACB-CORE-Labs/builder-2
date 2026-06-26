from typer.testing import CliRunner

from builder_ii.intake_cli import intake_app


def test_intake_app_help() -> None:
    result = CliRunner().invoke(intake_app, ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout
