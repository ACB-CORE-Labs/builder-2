from pathlib import Path

from builder_ii.routing.model_client_registry import (
    create_model_client_registry,
    dumps_model_client_registry,
    validate_model_client_registry,
    validate_model_client_registry_file,
    write_model_client_registry,
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


def test_dumps_and_write_model_client_registry(tmp_path: Path) -> None:
    reg = create_model_client_registry()
    text = dumps_model_client_registry(reg)
    assert '"kind"' in text
    out = tmp_path / "nested" / "registry.json"
    write_model_client_registry(reg, out)
    assert out.exists()
    assert validate_model_client_registry_file(out) == []


def test_validate_model_client_registry_file_edge_cases(tmp_path: Path) -> None:
    assert any("file not found" in e for e in validate_model_client_registry_file(tmp_path / "missing.json"))
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert any("invalid JSON" in e for e in validate_model_client_registry_file(bad))
    d = tmp_path / "dir"
    d.mkdir()
    assert any("failed to read file" in e for e in validate_model_client_registry_file(d))
