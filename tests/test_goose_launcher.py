from pathlib import Path

from builder_ii.config import Settings, load_settings
from builder_ii.goose_launcher import goose_env, goose_status, recipe_path


def _settings_with_base_url(base_url: str) -> Settings:
    existing_root = Path.cwd()
    return Settings(
        core_repo=existing_root,
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
        base_url=base_url,
        host="127.0.0.1",
        port=8080,
        temperature=0.0,
        project_root=existing_root,
    )


def test_goose_status_is_string():
    assert isinstance(goose_status(), str)


def test_goose_env_openai_provider():
    settings = load_settings()
    env = goose_env(settings)
    if settings.backend == "ollama":
        assert env["GOOSE_PROVIDER"] == "ollama"
    else:
        assert env["GOOSE_PROVIDER"] == "openai"
    assert env["GOOSE_TEMPERATURE"] == "0.0"
    assert env["GOOSE_MODEL"] == settings.active_model_id
    assert env["BUILDER_MODEL_ALIAS"] == settings.model_alias


def test_goose_openai_host_is_server_root_not_v1_path():
    settings = _settings_with_base_url("http://127.0.0.1:8080/v1")

    env = goose_env(settings)

    assert env["OPENAI_HOST"] == "http://127.0.0.1:8080"


def test_goose_openai_host_keeps_root_url_unchanged():
    settings = _settings_with_base_url("http://127.0.0.1:8080")

    env = goose_env(settings)

    assert env["OPENAI_HOST"] == "http://127.0.0.1:8080"


def test_recipe_exists():
    settings = load_settings()
    assert recipe_path(settings).exists()


def test_platform_recipe_exists():
    from builder_ii.model_router import plan_session

    settings = load_settings()
    assert recipe_path(settings, plan_session("orchestrator")).exists()
