from builder_ii.preflight_cli import preflight_app


def test_preflight_app_imports() -> None:
    assert preflight_app is not None
