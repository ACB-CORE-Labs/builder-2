from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import httpx

from builder_ii.core.config import Settings
from builder_ii.governance.authority.capabilities import chat_completions_url

DEFAULT_DIRECT_SYSTEM_PROMPT = (
    "You are a local builder-II review/probe model. "
    "Do not claim to edit files, run tools, or inspect hidden state. "
    "Return only the final answer. Do not include hidden reasoning, chain-of-thought, or think tags. "
    "Answer only from the provided prompt and clearly state uncertainty."
)

EMPTY_SANITIZED_OUTPUT_MESSAGE = (
    "The local model returned no public final answer after direct-ask sanitization. "
    "This usually means it emitted only hidden reasoning or stopped before a final response. "
    "Retry with a more explicit prompt or use qwen-coder for this direct ask."
)

_DIRECT_STOP_TOKENS = ("<|end|>", "<|assistant|>", "<|user|>", "<|im_end|>", "</s>")
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class DirectChatResult:
    ok: bool
    content: str
    endpoint: str
    model_id: str
    status_code: int | None = None
    error: str | None = None


def build_direct_chat_payload(
    settings: Settings,
    *,
    prompt: str,
    system_prompt: str = DEFAULT_DIRECT_SYSTEM_PROMPT,
    max_tokens: int = 256,
    temperature: float | None = None,
    override_model_id: str | None = None,
) -> dict[str, Any]:
    if not prompt.strip():
        raise ValueError("prompt must not be empty")
    if max_tokens <= 0:
        raise ValueError("max_tokens must be positive")

    payload: dict[str, Any] = {
        "model": override_model_id if override_model_id is not None else settings.active_model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
        "temperature": settings.temperature if temperature is None else temperature,
        "stop": list(_DIRECT_STOP_TOKENS),
    }
    return payload


def sanitize_direct_output(text: str) -> str:
    cleaned = text.strip()
    cleaned = _THINK_BLOCK_RE.sub("", cleaned).strip()

    open_think = cleaned.lower().find("<think>")
    if open_think >= 0:
        cleaned = cleaned[:open_think].strip()

    for token in _DIRECT_STOP_TOKENS:
        marker = cleaned.find(token)
        if marker >= 0:
            cleaned = cleaned[:marker].strip()

    return cleaned


def _extract_content(body: object) -> str:
    if not isinstance(body, dict):
        return ""
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return sanitize_direct_output(message["content"])
    text = first.get("text")
    if isinstance(text, str):
        return sanitize_direct_output(text)
    return ""


def run_direct_chat(
    settings: Settings,
    *,
    prompt: str,
    system_prompt: str = DEFAULT_DIRECT_SYSTEM_PROMPT,
    max_tokens: int = 256,
    timeout: float = 120.0,
    temperature: float | None = None,
    override_model_id: str | None = None,
) -> DirectChatResult:
    url = chat_completions_url(settings)
    payload = build_direct_chat_payload(
        settings,
        prompt=prompt,
        system_prompt=system_prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        override_model_id=override_model_id,
    )

    try:
        response = httpx.post(url, json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        return DirectChatResult(False, "", url, settings.active_model_id, error=f"{url} unreachable: {exc}")

    if response.status_code != 200:
        return DirectChatResult(
            False,
            "",
            url,
            settings.active_model_id,
            status_code=response.status_code,
            error=f"HTTP {response.status_code} from {url}",
        )

    try:
        body = response.json()
    except ValueError:
        return DirectChatResult(
            False, "", url, settings.active_model_id, status_code=response.status_code, error="non-JSON response"
        )

    content = _extract_content(body)
    if not content:
        return DirectChatResult(
            True, EMPTY_SANITIZED_OUTPUT_MESSAGE, url, settings.active_model_id, status_code=response.status_code
        )

    return DirectChatResult(True, content, url, settings.active_model_id, status_code=response.status_code)
