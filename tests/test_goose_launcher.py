from pathlib import Path

from builder_ii.config import Settings, load_settings
from builder_ii.goose_launcher import (
    derive_goose_environment,
    goose_env,
    goose_status,
    launch_goose_session,
    recipe_path,
)


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
        allow_cloud_models=False,
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


def test_goose_env_mlx_lm_backend():
    settings = Settings(
        core_repo=Path.cwd(),
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
        temperature=0.0,
        project_root=Path.cwd(),
        allow_cloud_models=False,
    )

    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy-secret-key"}):
        env, report = derive_goose_environment(settings)
        assert env["GOOSE_PROVIDER"] == "openai"
        assert env["GOOSE_PROVIDER__TYPE"] == "openai"
        assert env["GOOSE_MODEL"] == "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
        assert env["GOOSE_PROVIDER__HOST"] == "http://127.0.0.1:8080"
        assert env["OPENAI_HOST"] == "http://127.0.0.1:8080"
        assert report["key_present"] == "yes"
        assert "dummy-secret-key" not in report.values()


def test_goose_env_groq_backend():
    settings = Settings(
        core_repo=Path.cwd(),
        backend="groq",
        model_tier="primary",
        model_alias="groq-llama",
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
        project_root=Path.cwd(),
        allow_cloud_models=True,
    )

    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"GROQ_API_KEY": "groq-secret"}):
        env, report = derive_goose_environment(settings)
        assert env["GOOSE_PROVIDER"] == "openai"
        assert env["GOOSE_PROVIDER__TYPE"] == "openai"
        assert env["GOOSE_PROVIDER__HOST"] == "https://api.groq.com/openai"
        assert env["GOOSE_PROVIDER__API_KEY"] == "groq-secret"
        assert env["OPENAI_HOST"] == "https://api.groq.com/openai"
        assert env["OPENAI_API_KEY"] == "groq-secret"
        assert report["key_present"] == "yes"
        assert "groq-secret" not in report.values()


def test_goose_env_xai_backend():
    settings = Settings(
        core_repo=Path.cwd(),
        backend="xai",
        model_tier="primary",
        model_alias="grok-beta",
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
        project_root=Path.cwd(),
        allow_cloud_models=True,
    )

    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"XAI_API_KEY": "xai-secret"}):
        env, report = derive_goose_environment(settings)
        assert env["GOOSE_PROVIDER"] == "openai"
        assert env["GOOSE_PROVIDER__TYPE"] == "openai"
        assert env["GOOSE_PROVIDER__HOST"] == "https://api.x.ai"
        assert env["GOOSE_PROVIDER__API_KEY"] == "xai-secret"
        assert env["OPENAI_HOST"] == "https://api.x.ai"
        assert env["OPENAI_API_KEY"] == "xai-secret"
        assert report["key_present"] == "yes"
        assert "xai-secret" not in report.values()


def test_goose_env_openai_backend():
    settings = Settings(
        core_repo=Path.cwd(),
        backend="openai",
        model_tier="primary",
        model_alias="gpt-4o",
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
        base_url="https://api.openai.com/v1",
        host="api.openai.com",
        port=443,
        temperature=0.0,
        project_root=Path.cwd(),
        allow_cloud_models=True,
    )

    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"OPENAI_API_KEY": "openai-secret"}):
        env, report = derive_goose_environment(settings)
        assert env["GOOSE_PROVIDER"] == "openai"
        assert env["GOOSE_PROVIDER__TYPE"] == "openai"
        assert env["GOOSE_PROVIDER__HOST"] == "https://api.openai.com"
        assert env["GOOSE_PROVIDER__API_KEY"] == "openai-secret"
        assert env["OPENAI_HOST"] == "https://api.openai.com"
        assert env["OPENAI_API_KEY"] == "openai-secret"
        assert report["key_present"] == "yes"
        assert "openai-secret" not in report.values()


def test_goose_env_anthropic_backend():
    settings = Settings(
        core_repo=Path.cwd(),
        backend="anthropic",
        model_tier="primary",
        model_alias="claude-sonnet-5",
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
        base_url="https://api.anthropic.com/v1",
        host="api.anthropic.com",
        port=443,
        temperature=0.0,
        project_root=Path.cwd(),
        allow_cloud_models=True,
    )

    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "anthropic-secret"}):
        env, report = derive_goose_environment(settings)
        assert env["GOOSE_PROVIDER"] == "anthropic"
        assert env["GOOSE_PROVIDER__TYPE"] == "anthropic"
        assert env["GOOSE_PROVIDER__API_KEY"] == "anthropic-secret"
        assert env["ANTHROPIC_API_KEY"] == "anthropic-secret"
        assert report["key_present"] == "yes"
        assert "anthropic-secret" not in report.values()


def test_missing_provider_or_key_raises_error():
    settings = Settings(
        core_repo=Path.cwd(),
        backend="openai",
        model_tier="primary",
        model_alias="gpt-4o",
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
        base_url="https://api.openai.com/v1",
        host="api.openai.com",
        port=443,
        temperature=0.0,
        project_root=Path.cwd(),
        allow_cloud_models=True,
    )

    import os
    from unittest.mock import patch

    import pytest

    with patch.dict(os.environ, {"OPENAI_API_KEY": ""}, clear=True):
        with patch("builder_ii.goose_launcher.find_goose_binary", return_value="/usr/local/bin/goose"):
            with pytest.raises(ValueError) as exc:
                launch_goose_session(settings)
            assert "No Goose provider could be derived from builder-II settings" in str(exc.value)


def test_stratum_action_launch_goose_uses_adapter():
    from unittest.mock import MagicMock, patch

    from builder_ii.tui.app import StratumApp

    app = StratumApp()
    app.settings = Settings(
        core_repo=Path.cwd(),
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
        temperature=0.0,
        project_root=Path.cwd(),
        allow_cloud_models=False,
    )

    mock_proc = MagicMock()
    mock_proc.wait.return_value = 0

    with (
        patch("builder_ii.tui.app.StratumApp.suspend"),
        patch("builtins.print"),
        patch("builtins.input"),
        patch("builder_ii.goose_launcher.find_goose_binary", return_value="/usr/local/bin/goose"),
        patch("builder_ii.goose_launcher.launch_goose_session", return_value=mock_proc) as mock_launch_session,
    ):
        app.action_launch_goose()
        mock_launch_session.assert_called_once_with(app.settings)
