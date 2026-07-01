from pathlib import Path

from builder_ii.backend_state import check_backend_marker, read_backend_marker, write_backend_marker
from builder_ii.config import Settings


def settings_stub(tmp_path: Path, *, alias: str = "qwen-coder", model_id: str = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit") -> Settings:
    return Settings(
        core_repo=tmp_path / "core",
        backend="mlx-lm",
        model_tier="primary",
        model_alias=alias,
        model_primary="gemma-4-12b-4bit",
        model_fast="gemma-4-e4b-4bit",
        mlx_model_primary="mlx-community/gemma-4-12B-it-4bit",
        mlx_model_fast="mlx-community/gemma-4-e4b-it-4bit",
        mlx_model_phi="mlx-community/Phi-4-mini-reasoning-4bit",
        mlx_model_qwen=model_id,
        mlx_model_deepseek="mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
        mlx_model_llama="mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        mlx_model_codegeex="mlx-community/codegeex4-all-9b-4bit",
        mlx_model_qwen14="mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        mlx_model_qwen3_coder="mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        base_url="http://127.0.0.1:8080/v1",
        host="127.0.0.1",
        port=8080,
        temperature=0.0,
        project_root=tmp_path,
        allow_cloud_models=False,
    )


def test_backend_marker_round_trips(tmp_path: Path) -> None:
    settings = settings_stub(tmp_path)

    marker = write_backend_marker(settings)

    assert marker.model_alias == "qwen-coder"
    assert read_backend_marker(settings) == marker


def test_backend_marker_passes_matching_settings(tmp_path: Path) -> None:
    settings = settings_stub(tmp_path)
    write_backend_marker(settings)

    check = check_backend_marker(settings)

    assert check.ok is True
    assert "matches" in check.message


def test_backend_marker_fails_mismatched_model(tmp_path: Path) -> None:
    original = settings_stub(tmp_path)
    write_backend_marker(original)

    changed = settings_stub(
        tmp_path,
        alias="qwen-coder",
        model_id="mlx-community/Phi-4-mini-reasoning-4bit",
    )
    check = check_backend_marker(changed)

    assert check.ok is False
    assert "selected model" in check.message
