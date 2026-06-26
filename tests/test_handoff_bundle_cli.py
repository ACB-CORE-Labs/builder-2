from typer.testing import CliRunner

from builder_ii.handoff_bundle_cli import handoff_app


def test_handoff_bundle_app_help() -> None:
    result = CliRunner().invoke(handoff_app, ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout
