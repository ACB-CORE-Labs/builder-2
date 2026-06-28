from builder_ii.model_client_registry import (
    create_model_client_registry,
    validate_model_client_registry,
)


def test_valid_model_client_registry():
    reg = create_model_client_registry()
    errors = validate_model_client_registry(reg)
    assert errors == []


def test_invalid_schema_version():
    reg = create_model_client_registry()
    reg["schema_version"] = "99.0.0"
    errors = validate_model_client_registry(reg)
    assert any("schema_version" in err for err in errors)


def test_forbidden_active_authority():
    reg = create_model_client_registry()
    reg["governance"]["network_calls"] = "ENABLED"
    errors = validate_model_client_registry(reg)
    assert any("network_calls" in err for err in errors)


def test_forbidden_secrets():
    reg = create_model_client_registry()
    reg["clients"][0]["secrets"] = {"api_key": "sk-12345"}
    errors = validate_model_client_registry(reg)
    assert any("secrets" in err for err in errors)


def test_missing_risk_classification():
    reg = create_model_client_registry()
    del reg["clients"][0]["risk_classification"]
    errors = validate_model_client_registry(reg)
    assert any("risk_classification" in err for err in errors)
