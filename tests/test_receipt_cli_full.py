from typer.testing import CliRunner

from builder_ii.receipt_records_cli import receipt_app


def test_receipt_cli_help() -> None:
    result = CliRunner().invoke(receipt_app, ["--help"])

    assert result.exit_code == 0
    assert "record" in result.stdout
    assert "validate" in result.stdout
