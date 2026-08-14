"""W2.1 — real OpenAI-compatible cloud chat adapters.

Invokes cloud endpoints behind existing governance gates (caller must enforce
``allow_cloud_models`` + approval + budget). Secrets are resolved from env via
token refs only — never written into artifacts.

CI and offline tests inject a transport callable; production uses httpx.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import httpx

from builder_ii.routing.direct_chat import (
    DEFAULT_DIRECT_SYSTEM_PROMPT,
    DirectChatResult,
    _extract_content,
    build_direct_chat_payload,
)
from builder_ii.validation.secret_redaction import TOKEN_REF_PREFIX, is_token_ref, token_ref

# provider_id → (base_url_env, api_key_env, default_base_url)
_PROVIDER_ENDPOINTS: dict[str, tuple[str, str, str]] = {
    "groq_provider": ("GROQ_BASE_URL", "GROQ_API_KEY", "https://api.groq.com/openai/v1"),
    "xai_provider": ("XAI_BASE_URL", "XAI_API_KEY", "https://api.x.ai/v1"),
    "openai_provider": ("OPENAI_BASE_URL", "OPENAI_API_KEY", "https://api.openai.com/v1"),
    "openai_compat_provider": (
        "OPENAI_COMPAT_BASE_URL",
        "OPENAI_COMPAT_API_KEY",
        "http://127.0.0.1:8000/v1",
    ),
    "google_provider": (
        "GOOGLE_OPENAI_COMPAT_BASE_URL",
        "GOOGLE_API_KEY",
        "https://generativelanguage.googleapis.com/v1beta/openai",
    ),
    "anthropic_provider": (
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_API_KEY",
        "https://api.anthropic.com/v1",
    ),
}


@dataclass(frozen=True)
class CloudEndpoint:
    provider_id: str
    base_url: str
    api_key_env: str
    api_key_token_ref: str
    chat_completions_url: str


Transport = Callable[[str, dict[str, str], dict[str, Any], float], DirectChatResult]


def resolve_cloud_endpoint(client_record: Mapping[str, Any]) -> CloudEndpoint:
    """Resolve base URL + API key *env name* from a registry client record."""
    provider_id = str(client_record.get("provider_id") or "")
    endpoint_kind = str(client_record.get("endpoint_kind") or "")
    if endpoint_kind not in {"openai_compatible_cloud", "cloud_stub"}:
        raise ValueError(
            f"cloud adapter requires openai_compatible_cloud or cloud_stub; got {endpoint_kind!r}"
        )

    base_env, key_env, default_base = _PROVIDER_ENDPOINTS.get(
        provider_id,
        ("CLOUD_OPENAI_BASE_URL", "CLOUD_OPENAI_API_KEY", "https://api.openai.com/v1"),
    )
    # Prefer secret_ref_names from registry when present.
    refs = client_record.get("secret_ref_names")
    if isinstance(refs, list) and refs:
        first = str(refs[0])
        if first.endswith("_REF"):
            # OPENAI_API_KEY_REF → OPENAI_API_KEY
            key_env = first[: -len("_REF")] if first.endswith("_REF") else first
        elif is_token_ref(first):
            key_env = first[len(TOKEN_REF_PREFIX) :] if first.startswith(TOKEN_REF_PREFIX) else first

    base_url = os.environ.get(base_env, default_base).rstrip("/")
    return CloudEndpoint(
        provider_id=provider_id or "unknown_cloud",
        base_url=base_url,
        api_key_env=key_env,
        api_key_token_ref=token_ref(key_env),
        chat_completions_url=f"{base_url}/chat/completions",
    )


def _load_api_key(env_name: str) -> str:
    value = os.environ.get(env_name, "").strip()
    if not value:
        raise ValueError(
            f"cloud API key missing: set env {env_name} (artifacts store only {token_ref(env_name)})"
        )
    return value


def _default_httpx_transport(
    url: str, headers: dict[str, str], payload: dict[str, Any], timeout: float
) -> DirectChatResult:
    model_id = str(payload.get("model") or "unknown")
    try:
        response = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        return DirectChatResult(False, "", url, model_id, error=f"{url} unreachable: {exc}")
    if response.status_code != 200:
        return DirectChatResult(
            False,
            "",
            url,
            model_id,
            status_code=response.status_code,
            error=f"HTTP {response.status_code} from {url}",
        )
    try:
        body = response.json()
    except ValueError:
        return DirectChatResult(
            False, "", url, model_id, status_code=response.status_code, error="non-JSON response"
        )
    content = _extract_content(body)
    if not content:
        return DirectChatResult(
            True, "", url, model_id, status_code=response.status_code, error="empty model content"
        )
    return DirectChatResult(True, content, url, model_id, status_code=response.status_code)


def run_cloud_chat(
    *,
    client_record: Mapping[str, Any],
    prompt: str,
    system_prompt: str = DEFAULT_DIRECT_SYSTEM_PROMPT,
    max_tokens: int = 256,
    temperature: float | None = 0.0,
    timeout: float = 120.0,
    transport: Transport | None = None,
) -> tuple[DirectChatResult, dict[str, Any]]:
    """Execute one cloud chat completion. Returns (result, egress_record).

    ``egress_record`` is safe for ledgers (token refs only; no raw keys).
    """
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    endpoint = resolve_cloud_endpoint(client_record)
    model_id = str(client_record.get("model_id") or "")
    if not model_id:
        raise ValueError("client_record.model_id required")

    # Stub cloud providers never hit the network — local synthetic response.
    if client_record.get("endpoint_kind") == "cloud_stub" or client_record.get("provider_id") in (
        "openai_stub_provider",
        "anthropic_stub_provider",
    ):
        text = f"Mocked cloud stub response for model '{model_id}' to: {prompt[:30]}..."
        result = DirectChatResult(True, text, "cloud_stub://local", model_id, status_code=200)
        egress = {
            "kind": "builder_ii.cloud_egress_record",
            "provider_id": endpoint.provider_id,
            "endpoint_kind": "cloud_stub",
            "url": "cloud_stub://local",
            "model_id": model_id,
            "api_key_token_ref": endpoint.api_key_token_ref,
            "performs_network": False,
            "status_code": 200,
            "grants_authority": False,
        }
        return result, egress

    api_key = _load_api_key(endpoint.api_key_env)
    resolved_temp = 0.0 if temperature is None else float(temperature)

    # Minimal Settings-like object for payload builder
    class _S:
        active_model_id = model_id
        temperature = resolved_temp

    payload = build_direct_chat_payload(
        _S(),  # type: ignore[arg-type]
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=resolved_temp,
        override_model_id=model_id,
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    xport = transport or _default_httpx_transport
    result = xport(endpoint.chat_completions_url, headers, payload, timeout)
    egress = {
        "kind": "builder_ii.cloud_egress_record",
        "provider_id": endpoint.provider_id,
        "endpoint_kind": "openai_compatible_cloud",
        "url": endpoint.chat_completions_url,
        "model_id": model_id,
        "api_key_token_ref": endpoint.api_key_token_ref,
        "performs_network": True,
        "status_code": result.status_code,
        "ok": result.ok,
        "grants_authority": False,
        # Never include Authorization or raw key
    }
    return result, egress
