from builder_ii.receipt_records_cli import receipt_app


def test_receipt_app_imports() -> None:
    assert receipt_app is not None
