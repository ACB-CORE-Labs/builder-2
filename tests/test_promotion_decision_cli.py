from typer.testing import CliRunner

from builder_ii.promotion_decision_cli import promotion_decision_app


def test_promotion_decision_app_help() -> None:
    result = CliRunner().invoke(promotion_decision_app, ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout
