"""Gateway receipts must not silently use word-count as measured."""

from __future__ import annotations

from pathlib import Path

import pytest

from builder_ii.core.config import Settings
from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.routing.model_execution_gateway import ModelExecutionGateway, validate_model_call_receipt
from builder_ii.routing.model_routing_policy import create_model_execution_policy
from builder_ii.routing.price_book import create_default_price_book
from builder_ii.routing.token_accounting import count_tokens_whitespace_v1


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        target_repo=Path("/tmp/core"),
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
        allow_cloud_models=True,
    )


def test_stub_call_receipt_has_measured_cost(mock_settings: Settings, tmp_path: Path) -> None:
    registry = create_model_client_registry()
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    policy = create_model_execution_policy(
        {
            "kind": "builder_ii.model_routing_recommendation",
            "recommended_candidates": [{"model_id": "gpt-4o-stub"}],
        },
        max_tokens=256,
    )
    gateway = ModelExecutionGateway(mock_settings, registry, policy, price_book=create_default_price_book())
    prompt = "alpha beta gamma"
    envelope, receipt, _debited = gateway.run_model_call(
        model_id="gpt-4o-stub",
        prompt=prompt,
        envelope_path=tmp_path / "env.json",
        receipt_path=tmp_path / "rec.json",
        ledger_bound=True,
        events_dir=tmp_path / "events",
        session_id="sess-cost",
    )
    assert validate_model_call_receipt(receipt) == []
    cost = receipt["cost_report"]
    assert cost["token_accounting"] == "measured"
    assert cost["tokenizer_id"]
    assert cost["tokenizer_version"]
    expected_in = count_tokens_whitespace_v1(prompt).token_count
    assert cost["input_tokens"] == expected_in
    # Must NOT equal the old fiction of len(split())+10 for success path input only —
    # word-count of prompt is 3; measured whitespace is also 3 here, but the accounting
    # label and tokenizer identity prove the path is not the old estimated fudge.
    assert "estimated_usd_total" in cost
    assert cost.get("price_book_ref", {}).get("kind") == "builder_ii.price_book"
    assert envelope["ledger_bound"] is True
    # Ledger events written without Typer CLI
    events = list((tmp_path / "events").glob("*.json"))
    assert events, "gateway must append ledger events when ledger_bound+events_dir"


def test_receipt_validator_rejects_silent_estimated_without_reason() -> None:
    errors = validate_model_call_receipt(
        {
            "kind": "builder_ii.model_call_receipt",
            "schema_version": 1,
            "envelope_ref": {
                "kind": "builder_ii.model_call_envelope",
                "sha256": "a" * 64,
                "role": "model_call_envelope",
            },
            "response_text": "x",
            "cost_report": {
                "input_tokens": 1,
                "output_tokens": 1,
                "total_tokens": 2,
                "token_accounting": "estimated",
                # missing estimated_reason
            },
            "replay_declaration": "non-deterministic-llm-completion",
            "executes_model": True,
            "executes_tools": False,
            "executes_shell": False,
            "invokes_goose": False,
            "constructs_deepagents": False,
            "constructs_subagents": False,
            "invokes_mcp": False,
            "mutates_target_repo": False,
            "mutates_memory": False,
            "grants_authority": False,
            "artifact_is_authority": False,
            "requires_human_promotion_for_execution": True,
        }
    )
    assert any("estimated_reason" in e for e in errors)
