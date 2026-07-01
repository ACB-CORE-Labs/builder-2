from pathlib import Path

from builder_ii.backends import check_health, check_serves_active_model, ensure_backend_supports_model
from builder_ii.config import Settings
from builder_ii.model_policy import (
    can_launch_with_backend,
    launch_block_reason,
    operating_profiles,
    runtime_for_alias,
)
from builder_ii.models import model_definitions


def settings_stub(alias: str = "qwen-coder") -> Settings:
    return Settings(
        core_repo=Path("/tmp/core"),
        backend="mlx-lm",
        model_tier="primary",
        model_alias=alias,
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
        temperature=0.0,
        project_root=Path("/tmp/builder-II"),
        allow_cloud_models=False,
    )


def test_every_configured_model_has_operating_profile() -> None:
    settings = settings_stub()
    aliases = {definition.alias for definition in model_definitions(settings)}
    profile_aliases = {profile.alias for profile in operating_profiles(settings)}

    assert profile_aliases == aliases


def test_profile_fields_are_public_operator_guidance() -> None:
    profiles = operating_profiles(settings_stub())

    for profile in profiles:
        assert profile.runtime
        assert profile.role
        assert profile.launch_policy
        assert profile.recommended_for
        assert profile.avoid_for


def test_qwen_coder_is_normal_mlx_lm_runtime() -> None:
    assert runtime_for_alias("qwen-coder") == "mlx-lm"
    assert can_launch_with_backend("qwen-coder", "mlx-lm") is True
    assert launch_block_reason("qwen-coder", "mlx-lm") is None


def test_gemma_fast_is_sidecar_not_mlx_lm_launch_target() -> None:
    assert runtime_for_alias("gemma-fast") == "mlx-vlm-sidecar"
    assert can_launch_with_backend("gemma-fast", "mlx-lm") is False
    assert "mlx-vlm-sidecar" in launch_block_reason("gemma-fast", "mlx-lm")


def test_heavy_lanes_remain_explicit_opt_in() -> None:
    profiles = {profile.alias: profile for profile in operating_profiles(settings_stub())}

    for alias in {"qwen-coder-14b", "qwen3-coder-heavy", "deepseek"}:
        assert profiles[alias].runtime == "mlx-lm-heavy"
        assert "explicit opt-in" in profiles[alias].launch_policy


def test_backend_support_gate_blocks_gemma_sidecar_on_mlx_lm() -> None:
    ok, message = ensure_backend_supports_model(settings_stub("gemma-fast"))

    assert ok is False
    assert "gemma-fast" in message
    assert "mlx_lm" not in message


def test_unsupported_pairing_reaches_clean_backend_refusal_path() -> None:
    health_ok, health_msg = check_health(settings_stub("gemma-fast"))
    served_ok, served_msg = check_serves_active_model(settings_stub("gemma-fast"))

    assert health_ok is True
    assert "mlx-vlm-sidecar" in health_msg
    assert served_ok is False
    assert "mlx-vlm-sidecar" in served_msg


def test_backend_support_gate_allows_qwen_default() -> None:
    ok, message = ensure_backend_supports_model(settings_stub("qwen-coder"))

    assert ok is True
    assert "qwen-coder" in message
