from typer.testing import CliRunner

from builder_ii.promotion_readiness_cli import promotion_app


def test_promotion_readiness_app_help() -> None:
    result = CliRunner().invoke(promotion_app, ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout
