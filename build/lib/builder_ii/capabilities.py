from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from builder_ii.backends import _without_v1_suffix, check_serves_active_model
from builder_ii.config import Settings

GateResult = Literal["PASS", "WARN", "FAIL", "UNSUPPORTED", "SKIP"]


@dataclass(frozen=True)
class CapabilityGate:
    name: str
    result: GateResult
    details: str

    @property
    def ok(self) -> bool:
        return self.result in {"PASS", "WARN", "UNSUPPORTED", "SKIP"}


def chat_completions_url(settings: Settings) -> str:
    return f"{_without_v1_suffix(settings.base_url)}/v1/chat/completions"


def served_model_gate(settings: Settings, timeout: float = 3.0) -> CapabilityGate:
    ok, message = check_serves_active_model(settings, timeout=timeout)
    return CapabilityGate("served model", "PASS" if ok else "FAIL", message)


def chat_smoke_gate(settings: Settings, timeout: float = 60.0) -> CapabilityGate:
    url = chat_completions_url(settings)
    payload = {
        "model": settings.active_model_id,
        "messages": [
            {
                "role": "system",
                "content": "You are a local smoke-test responder. Reply with exactly: builder-chat-smoke-ok",
            },
            {"role": "user", "content": "Reply now."},
        ],
        "max_tokens": 16,
        "temperature": 0,
    }
    try:
        response = httpx.post(url, json=payload, timeout=timeout)
    except httpx.HTTPError as exc:
        return CapabilityGate("chat smoke", "FAIL", f"{url} unreachable: {exc}")

    if response.status_code != 200:
        return CapabilityGate("chat smoke", "FAIL", f"HTTP {response.status_code} from {url}")

    try:
        body = response.json()
    except ValueError:
        return CapabilityGate("chat smoke", "FAIL", f"{url} returned non-JSON response")

    choices = body.get("choices") if isinstance(body, dict) else None
    if not isinstance(choices, list) or not choices:
        return CapabilityGate("chat smoke", "FAIL", f"{url} returned no choices")

    first = choices[0]
    content = ""
    if isinstance(first, dict):
        message = first.get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            content = message["content"].strip()
        elif isinstance(first.get("text"), str):
            content = first["text"].strip()

    if not content:
        return CapabilityGate("chat smoke", "FAIL", f"{url} returned empty content")

    return CapabilityGate("chat smoke", "PASS", f"{url} responded with text")


def tool_support_gate(settings: Settings) -> CapabilityGate:
    if settings.backend == "mlx-lm":
        return CapabilityGate(
            "tool support",
            "UNSUPPORTED",
            "local mlx-lm Goose tool execution is not validated; keep sessions review/planning-only",
        )
    return CapabilityGate(
        "tool support",
        "WARN",
        f"tool execution gate is unverified for backend={settings.backend}",
    )


def capability_gates(settings: Settings, *, run_chat_smoke: bool = False) -> list[CapabilityGate]:
    gates = [served_model_gate(settings)]
    if run_chat_smoke:
        gates.append(chat_smoke_gate(settings))
    else:
        gates.append(CapabilityGate("chat smoke", "SKIP", "pass --chat to run a live completion smoke"))
    gates.append(tool_support_gate(settings))
    return gates
