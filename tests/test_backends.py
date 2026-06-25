from __future__ import annotations

from pathlib import Path

from builder_ii.backends import check_serves_active_model, health_url
from builder_ii.config import Settings


class _Response:
    def __init__(self, status_code: int, payload: object) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> object:
        return self._payload


def _settings(*, backend: str, base_url: str = "http://127.0.0.1:8080/v1") -> Settings:
    return Settings(
        core_repo=Path("/tmp/core"),
        backend=backend,
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
        project_root=Path("/tmp/builder-II"),
    )


def test_mlx_lm_health_url_uses_openai_v1_models_endpoint() -> None:
    settings = _settings(backend="mlx-lm")

    assert health_url(settings, "/v1/models") == "http://127.0.0.1:8080/v1/models"


def test_rapid_mlx_health_url_keeps_legacy_models_endpoint() -> None:
    settings = _settings(backend="rapid-mlx")

    assert health_url(settings, "/models") == "http://127.0.0.1:8080/models"


def test_check_serves_active_model_passes_matching_mlx_model(monkeypatch) -> None:
    settings = _settings(backend="mlx-lm")

    def fake_get(url: str, timeout: float) -> _Response:
        return _Response(200, {"data": [{"id": settings.active_model_id}]})

    monkeypatch.setattr("builder_ii.backends.httpx.get", fake_get)

    ok, message = check_serves_active_model(settings)

    assert ok is True
    assert settings.active_model_id in message


def test_check_serves_active_model_fails_mismatched_mlx_model(monkeypatch) -> None:
    settings = _settings(backend="mlx-lm")

    def fake_get(url: str, timeout: float) -> _Response:
        return _Response(200, {"data": [{"id": "mlx-community/Phi-4-mini-reasoning-4bit"}]})

    monkeypatch.setattr("builder_ii.backends.httpx.get", fake_get)

    ok, message = check_serves_active_model(settings)

    assert ok is False
    assert "selected model" in message
    assert "Phi-4-mini-reasoning" in message


def test_check_serves_active_model_skips_non_mlx_backend() -> None:
    settings = _settings(backend="rapid-mlx")

    ok, message = check_serves_active_model(settings)

    assert ok is True
    assert "skipped" in message
