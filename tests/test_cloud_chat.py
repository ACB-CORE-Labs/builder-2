"""W2.1 cloud adapters (transport-injected; no network)."""

from __future__ import annotations

from builder_ii.adapters.openai_compat.cloud_chat import resolve_cloud_endpoint, run_cloud_chat
from builder_ii.routing.direct_chat import DirectChatResult


def test_stub_cloud_no_network() -> None:
    client = {
        "provider_id": "openai_stub_provider",
        "endpoint_kind": "cloud_stub",
        "model_id": "gpt-4o-stub",
        "secret_ref_names": ["OPENAI_API_KEY_REF"],
    }
    result, egress = run_cloud_chat(client_record=client, prompt="hello cloud")
    assert result.ok
    assert "Mocked" in result.content
    assert egress["performs_network"] is False
    assert "api_key_token_ref" in egress
    assert "sk-" not in str(egress)


def test_openai_compatible_uses_injected_transport(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_API_KEY", "test-key-not-a-real-secret-value-xx")
    client = {
        "provider_id": "groq_provider",
        "endpoint_kind": "openai_compatible_cloud",
        "model_id": "llama-3.1-8b-instant",
        "secret_ref_names": ["GROQ_API_KEY_REF"],
    }
    ep = resolve_cloud_endpoint(client)
    assert "chat/completions" in ep.chat_completions_url

    def transport(url, headers, payload, timeout):
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")
        assert payload["model"] == "llama-3.1-8b-instant"
        return DirectChatResult(True, "hi from transport", url, "llama-3.1-8b-instant", status_code=200)

    result, egress = run_cloud_chat(client_record=client, prompt="ping", transport=transport)
    assert result.ok
    assert result.content == "hi from transport"
    assert egress["performs_network"] is True
    assert "Bearer" not in str(egress)
