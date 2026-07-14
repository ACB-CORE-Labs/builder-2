"""P6 vLLM research profile — stub interface, never default runtime."""

from __future__ import annotations

import pytest

from builder_ii.wrp.vllm_profile import (
    DEFAULT_RESEARCH_PROFILE,
    VLLM_ENV,
    VLLM_ENV_VALUE,
    BackendUnavailableError,
    StubVllmClient,
    profile_status,
    research_profile,
    resolve_vllm_client,
    vllm_opt_in_enabled,
)


@pytest.fixture(autouse=True)
def _clear_vllm_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(VLLM_ENV, raising=False)


def test_default_research_profile_not_runtime() -> None:
    p = DEFAULT_RESEARCH_PROFILE
    assert p.is_default_runtime is False
    assert p.grants_authority is False
    assert p.name
    data = p.to_jsonable()
    assert data["is_default_runtime"] is False


def test_research_profile_overrides_cannot_inflate() -> None:
    p = research_profile(overrides={"model_id": "custom/test", "is_default_runtime": True})
    assert p.model_id == "custom/test"
    assert p.is_default_runtime is False
    assert p.grants_authority is False


def test_research_profile_rejects_unknown_field() -> None:
    with pytest.raises(ValueError, match="unknown"):
        research_profile(overrides={"not_a_field": 1})


def test_stub_complete_fail_closed_without_env() -> None:
    client = StubVllmClient()
    with pytest.raises(BackendUnavailableError, match="opt-in only"):
        client.complete("hello")


def test_stub_complete_fail_closed_with_env_no_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VLLM_ENV, VLLM_ENV_VALUE)
    client = StubVllmClient()
    with pytest.raises(BackendUnavailableError, match="not injected"):
        client.complete("hello", max_tokens=8)


def test_resolve_vllm_client_default_is_stub() -> None:
    client = resolve_vllm_client()
    assert isinstance(client, StubVllmClient)
    assert client.name == "vllm_stub"


def test_resolve_injected_requires_opt_in() -> None:
    class Fake:
        name = "fake"

        def complete(self, prompt: str, *, max_tokens: int = 64) -> dict:
            return {"text": prompt, "max_tokens": max_tokens}

    with pytest.raises(BackendUnavailableError, match="refused without"):
        resolve_vllm_client(client=Fake())  # type: ignore[arg-type]


def test_resolve_injected_with_opt_in(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(VLLM_ENV, VLLM_ENV_VALUE)

    class Fake:
        name = "fake"

        def complete(self, prompt: str, *, max_tokens: int = 64) -> dict:
            return {"text": f"echo:{prompt}", "max_tokens": max_tokens}

    client = resolve_vllm_client(client=Fake())  # type: ignore[arg-type]
    assert client.complete("hi")["text"] == "echo:hi"


def test_profile_status_shape() -> None:
    status = profile_status()
    assert status["default_runtime"] is False
    assert status["grants_authority"] is False
    assert status["engine_started"] is False
    assert status["opt_in_enabled"] is False
    assert status["profile"]["name"] == DEFAULT_RESEARCH_PROFILE.name
    assert vllm_opt_in_enabled() is False
