"""W5.1 — run manifest from real envelope/receipt path."""

from __future__ import annotations

from pathlib import Path

from builder_ii.core.config import Settings
from builder_ii.core.run_manifest import run_manifest_from_receipt, validate_run_manifest
from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.routing.model_execution_gateway import ModelExecutionGateway
from builder_ii.routing.model_routing_policy import create_model_execution_policy
from builder_ii.routing.price_book import create_default_price_book


def test_run_manifest_from_stub_call(tmp_path: Path) -> None:
    settings = Settings(
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
    registry = create_model_client_registry()
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    policy = create_model_execution_policy(
        {
            "kind": "builder_ii.model_routing_recommendation",
            "recommended_candidates": [{"model_id": "gpt-4o-stub"}],
        }
    )
    gw = ModelExecutionGateway(settings, registry, policy, price_book=create_default_price_book())
    env, rec, _debited = gw.run_model_call(
        model_id="gpt-4o-stub",
        prompt="manifest binding",
        envelope_path=tmp_path / "e.json",
        receipt_path=tmp_path / "r.json",
    )
    manifest = run_manifest_from_receipt(env, rec)
    assert validate_run_manifest(manifest) == []
    assert manifest["prompt_digest"] == env["prompt_digest"]
    assert manifest["replay_declaration"] == "non-deterministic-llm-completion"
    assert "llm_completion_text" in manifest["non_deterministic_surface"]
