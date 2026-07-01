import json as json_lib
from pathlib import Path
import pytest
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from builder_ii.config import Settings
from builder_ii.model_client_registry import (
    create_model_client_registry,
)
from builder_ii.model_routing_policy import (
    create_model_routing_policy,
)
from builder_ii.model_execution_gateway import (
    ModelExecutionGateway,
    validate_model_call_envelope,
    validate_model_call_receipt,
    validate_model_call_receipt_file,
    scan_for_secrets,
)
from builder_ii.model_cli import model_app

@pytest.fixture
def mock_settings() -> Settings:
    s = MagicMock(spec=Settings)
    s.allow_cloud_models = False
    s.temperature = 0.7
    s.active_model_id = "gpt-4o-stub"
    return s

@pytest.fixture
def standard_registry() -> dict:
    return create_model_client_registry()

@pytest.fixture
def standard_policy() -> dict:
    return create_model_routing_policy()

def test_secret_scanner() -> None:
    # Standard prompt is clean
    assert scan_for_secrets("Write a python quicksort function.") == []

    # API key detections
    assert len(scan_for_secrets("My OpenAI key is sk-1234567890abcdef1234567890abcdef")) > 0
    assert len(scan_for_secrets("Authorization: Bearer 1234567890abcdef")) > 0
    assert len(scan_for_secrets("token = 'ghp_abcdefghijklmnopqrstuvwxyz0123456789'")) > 0

def test_model_execution_fails_on_disabled_model(
    mock_settings, standard_registry, standard_policy, tmp_path
) -> None:
    # gpt-4o-stub is disabled by default in _default_client_records()
    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError) as exc:
        gateway.run_model_call(
            model_id="gpt-4o-stub",
            prompt="Hello",
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    assert "disabled" in str(exc.value)

def test_model_execution_fails_on_unauthorized_cloud(
    mock_settings, standard_registry, standard_policy, tmp_path
) -> None:
    # Enable gpt-4o-stub
    for client in standard_registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True

    # Cloud models are disabled in mock_settings
    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError) as exc:
        gateway.run_model_call(
            model_id="gpt-4o-stub",
            prompt="Hello",
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    assert "Cloud/external model calls are disabled" in str(exc.value)

def test_model_execution_succeeds_on_authorized_cloud(
    mock_settings, standard_registry, standard_policy, tmp_path
) -> None:
    # Enable gpt-4o-stub and allow cloud models
    for client in standard_registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    mock_settings.allow_cloud_models = True

    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    envelope, receipt = gateway.run_model_call(
        model_id="gpt-4o-stub",
        prompt="Tell me a joke",
        envelope_path=envelope_path,
        receipt_path=receipt_path,
    )

    assert envelope_path.is_file()
    assert receipt_path.is_file()

    assert validate_model_call_envelope(envelope) == []
    assert validate_model_call_receipt(receipt) == []
    assert receipt["replay_declaration"] == "non-deterministic-llm-completion"
    assert "Mocked stub response" in receipt["response_text"]

def test_model_execution_fails_on_secret_leak(
    mock_settings, standard_registry, standard_policy, tmp_path
) -> None:
    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError) as exc:
        gateway.run_model_call(
            model_id="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            prompt="Here is my secret token: sk-abcdefghijklmnopqrstuvwxyz0123456789",
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    assert "leak detected" in str(exc.value)

def test_cli_commands(standard_registry, standard_policy, tmp_path) -> None:
    runner = CliRunner()
    
    # Write registry and policy
    # Enable gpt-4o-stub in custom registry to test
    for client in standard_registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    
    reg_path = tmp_path / "registry.json"
    pol_path = tmp_path / "policy.json"
    reg_path.write_text(json_lib.dumps(standard_registry), encoding="utf-8")
    pol_path.write_text(json_lib.dumps(standard_policy), encoding="utf-8")

    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    # Call with allow_cloud_models patched in Settings load
    with patch("builder_ii.model_cli.load_settings") as mock_load:
        settings_mock = MagicMock(spec=Settings)
        settings_mock.allow_cloud_models = True
        mock_load.return_value = settings_mock

        result = runner.invoke(model_app, [
            "call",
            "--model", "gpt-4o-stub",
            "--prompt", "What is the capital of France?",
            "--registry", str(reg_path),
            "--policy", str(pol_path),
            "--output-envelope", str(envelope_path),
            "--output-receipt", str(receipt_path)
        ])
        assert result.exit_code == 0, result.output
        assert envelope_path.is_file()
        assert receipt_path.is_file()

        # Validate receipt command
        result_val = runner.invoke(model_app, [
            "validate-receipt",
            str(receipt_path)
        ])
        assert result_val.exit_code == 0, result_val.output
