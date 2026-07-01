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
    create_model_execution_policy,
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
    return Settings(
        core_repo=Path("/tmp/core"),
        backend="mlx-lm",
        model_tier="primary",
        model_alias="qwen-coder",
        model_primary="gemma-4-12b-4bit",
        model_fast="gemma-4-e4b-4bit",
        mlx_model_primary="mlx-community/gemma-4-12B-it-4bit",
        mlx_model_fast="mlx-community/gemma-4-e4b-it-4bit",
        mlx_model_phi="mlx-community/Phi-4-mini-reasoning-4bit",
        mlx_model_qwen="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        mlx_model_deepseek="mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
        mlx_model_llama="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        mlx_model_codegeex="mlx-community/codegeex4-all-9b-4bit",
        mlx_model_qwen14="mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        mlx_model_qwen3_coder="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        base_url="http://127.0.0.1:8080/v1",
        host="127.0.0.1",
        port=8080,
        temperature=0.7,
        project_root=Path.cwd(),
        allow_cloud_models=False,
    )

@pytest.fixture
def standard_registry() -> dict:
    return create_model_client_registry()

@pytest.fixture
def standard_execution_policy() -> dict:
    dummy_rec = {
        "kind": "builder_ii.model_routing_recommendation",
        "recommended_candidates": [
            {"model_id": "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"},
            {"model_id": "gpt-4o-stub"}
        ]
    }
    return create_model_execution_policy(dummy_rec, max_tokens=16384)

def test_secret_scanner() -> None:
    # Standard prompt is clean
    assert scan_for_secrets("Write a python quicksort function.") == []

    # API key detections
    assert len(scan_for_secrets("My OpenAI key is sk-1234567890abcdef1234567890abcdef")) > 0
    assert len(scan_for_secrets("Authorization: Bearer 1234567890abcdef")) > 0
    assert len(scan_for_secrets("token = 'ghp_abcdefghijklmnopqrstuvwxyz0123456789'")) > 0

def test_model_execution_fails_on_disabled_model(
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_execution_policy)
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
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    # Enable gpt-4o-stub
    for client in standard_registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True

    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_execution_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError) as exc:
        gateway.run_model_call(
            model_id="gpt-4o-stub",
            prompt="Hello",
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    assert "disabled by environment configuration" in str(exc.value)

def test_model_execution_succeeds_on_authorized_cloud(
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    # Enable gpt-4o-stub and allow cloud models
    for client in standard_registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True

    # mock_settings is a frozen dataclass, so we must recreate it to set allow_cloud_models
    mock_settings = Settings(**{**mock_settings.__dict__, "allow_cloud_models": True})

    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_execution_policy)
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

def test_model_execution_fails_on_local_offline_network(
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    for client in standard_registry["clients"]:
        if client["model_id"] == "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit":
            client["risk_classification"] = "local_offline"

    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_execution_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError) as exc:
        gateway.run_model_call(
            model_id="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            prompt="Hello",
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    assert "cannot perform network calls" in str(exc.value)

def test_model_execution_fails_on_max_tokens_registry_limit(
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_execution_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError) as exc:
        gateway.run_model_call(
            model_id="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            prompt="Hello",
            max_tokens=99999,
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    assert "exceeds client registry limit" in str(exc.value)

def test_model_execution_fails_on_max_tokens_policy_limit(
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    standard_execution_policy["max_tokens"] = 100
    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_execution_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError) as exc:
        gateway.run_model_call(
            model_id="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            prompt="Hello",
            max_tokens=500,
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    assert "exceeds execution policy limit" in str(exc.value)

def test_model_execution_fails_on_unauthorized_model_in_policy(
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    standard_execution_policy["allowed_models"] = ["mlx-community/Phi-3.5-mini-instruct-4bit"]
    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_execution_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with pytest.raises(ValueError) as exc:
        gateway.run_model_call(
            model_id="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            prompt="Hello",
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    assert "not authorized by the execution policy" in str(exc.value)

def test_cli_commands(mock_settings, standard_registry, standard_execution_policy, tmp_path) -> None:
    runner = CliRunner()
    
    for client in standard_registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    
    reg_path = tmp_path / "registry.json"
    pol_path = tmp_path / "policy.json"
    reg_path.write_text(json_lib.dumps(standard_registry), encoding="utf-8")
    pol_path.write_text(json_lib.dumps(standard_execution_policy), encoding="utf-8")

    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with patch("builder_ii.model_cli.load_settings") as mock_load:
        # Recreate settings to enable cloud
        settings_mock = Settings(**{**mock_settings.__dict__, "allow_cloud_models": True})
        mock_load.return_value = settings_mock

        # Call requires session-id
        result_call_no_session = runner.invoke(model_app, [
            "call",
            "--model", "gpt-4o-stub",
            "--prompt", "What is the capital of France?",
            "--registry", str(reg_path),
            "--execution-policy", str(pol_path),
            "--output-envelope", str(envelope_path),
            "--output-receipt", str(receipt_path)
        ])
        assert result_call_no_session.exit_code != 0
        assert "Must specify --session-id" in result_call_no_session.output

        # Call with session-id
        result = runner.invoke(model_app, [
            "call",
            "--model", "gpt-4o-stub",
            "--prompt", "What is the capital of France?",
            "--registry", str(reg_path),
            "--execution-policy", str(pol_path),
            "--session-id", "test-session",
            "--output-envelope", str(envelope_path),
            "--output-receipt", str(receipt_path)
        ])
        assert result.exit_code == 0, result.output

        # Standalone call
        result_standalone = runner.invoke(model_app, [
            "standalone-call",
            "--model", "gpt-4o-stub",
            "--prompt", "What is the capital of France?",
            "--registry", str(reg_path),
            "--execution-policy", str(pol_path),
            "--output-envelope", str(envelope_path),
            "--output-receipt", str(receipt_path)
        ])
        assert result_standalone.exit_code == 0, result_standalone.output

        # Validate receipt command
        result_val = runner.invoke(model_app, [
            "validate-receipt",
            str(receipt_path)
        ])
        assert result_val.exit_code == 0, result_val.output


# ── Network semantics ─────────────────────────────────────────────────────────

def test_envelope_network_semantics_local_network(
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    """local_network risk: envelope + authority_boundary + governance must declare network enabled."""
    from unittest.mock import patch as _patch
    from builder_ii.direct_chat import DirectChatResult
    stub_result = DirectChatResult(ok=True, content="Paris", endpoint="http://x", model_id="m")
    gateway = ModelExecutionGateway(mock_settings, standard_registry, standard_execution_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"

    with _patch("builder_ii.model_execution_gateway.run_direct_chat", return_value=stub_result):
        envelope, receipt = gateway.run_model_call(
            model_id="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
            prompt="Capital of France?",
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )

    assert envelope["performs_network_calls"] is True
    assert envelope["authority_boundary"]["performs_network_calls"] is True
    assert envelope["governance"]["network_calls"] == "ENABLED_UNDER_ENVELOPE"
    assert receipt["authority_boundary"]["performs_network_calls"] is True
    assert receipt["governance"]["network_calls"] == "ENABLED_UNDER_ENVELOPE"
    env_errors = validate_model_call_envelope(envelope)
    assert env_errors == [], f"Envelope validation errors: {env_errors}"


def test_envelope_network_semantics_cloud_external(
    mock_settings, standard_registry, standard_execution_policy, tmp_path
) -> None:
    """cloud_external risk: envelope must declare network enabled when cloud models are allowed."""
    for client in standard_registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    cloud_settings = Settings(**{**mock_settings.__dict__, "allow_cloud_models": True})
    gateway = ModelExecutionGateway(cloud_settings, standard_registry, standard_execution_policy)
    envelope_path = tmp_path / "envelope.json"
    receipt_path = tmp_path / "receipt.json"
    envelope, receipt = gateway.run_model_call(
        model_id="gpt-4o-stub",
        prompt="Capital of France?",
        envelope_path=envelope_path,
        receipt_path=receipt_path,
    )
    assert envelope["performs_network_calls"] is True
    assert envelope["authority_boundary"]["performs_network_calls"] is True
    assert envelope["governance"]["network_calls"] == "ENABLED_UNDER_ENVELOPE"
    env_errors = validate_model_call_envelope(envelope)
    assert env_errors == [], f"Envelope validation errors: {env_errors}"


# ── Execution policy authority claims ─────────────────────────────────────────

def test_execution_policy_does_not_claim_grants_authority(standard_execution_policy) -> None:
    assert standard_execution_policy.get("grants_authority") is False

def test_execution_policy_artifact_is_not_authority(standard_execution_policy) -> None:
    gov = standard_execution_policy.get("governance", {})
    assert gov.get("artifact_is_authority") is False

def test_execution_policy_requires_human_promotion(standard_execution_policy) -> None:
    assert standard_execution_policy.get("requires_human_promotion_for_execution") is True

def test_execution_policy_governance_model_execution_is_under_envelope(standard_execution_policy) -> None:
    gov = standard_execution_policy.get("governance", {})
    assert gov.get("model_execution") == "ENABLED_UNDER_ENVELOPE"
