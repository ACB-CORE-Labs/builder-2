from builder_ii.routing.routing import suite_for_module


def test_algebra_routes_to_algebra():
    assert suite_for_module("algebra/versor.py") == "algebra"


def test_vault_routes_to_teaching():
    assert suite_for_module("vault/store.py") == "teaching"


def test_unknown_routes_to_smoke():
    assert suite_for_module("misc/foo.py") == "smoke"
