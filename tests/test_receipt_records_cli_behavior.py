from builder_ii.receipt_records_cli import receipt_app
from typer.testing import CliRunner


def test_receipt_cli_bad_status() -> None:
    result = CliRunner().invoke(
        receipt_app, ["record", "missing.json", "--status", "maybe", "--recorded-by", "operator"]
    )

    assert result.exit_code == 1
    assert "status must be passed, failed, or blocked" in result.stdout
