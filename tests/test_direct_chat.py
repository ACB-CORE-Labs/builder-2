from pathlib import Path

from builder_ii.config import Settings
from builder_ii.direct_chat import (
    EMPTY_SANITIZED_OUTPUT_MESSAGE,
    build_direct_chat_payload,
    run_direct_chat,
    sanitize_direct_output,
)


class ResponseStub:
    status_code = 200

    def json(self) -> object:
        return {"choices": [{"message": {"content": "ok"}}]}


class ThinkOnlyResponseStub:
    status_code = 200

    def json(self) -> object:
        return {"choices": [{"message": {"content": "<think>private scratchpad</think>"}}]}


def settings_stub() -> Settings:
    return Settings(
        core_repo=Path("/tmp/core"),
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
        project_root=Path("/tmp/builder-II"),
    )


def test_direct_chat_payload_has_no_tool_fields() -> None:
    payload = build_direct_chat_payload(settings_stub(), prompt="summarize this failure")

    assert payload["model"] == "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"
    assert payload["messages"][1]["content"] == "summarize this failure"
    assert payload["max_tokens"] == 256
    assert "stop" in payload
    assert "<|im_end|>" in payload["stop"]
    assert "tools" not in payload
    assert "tool_choice" not in payload
    assert "functions" not in payload


def test_direct_chat_posts_plain_payload(monkeypatch) -> None:
    seen = {}

    def fake_post(url, json, timeout):
        seen["url"] = url
        seen["json"] = json
        return ResponseStub()

    monkeypatch.setattr("builder_ii.direct_chat.httpx.post", fake_post)

    result = run_direct_chat(settings_stub(), prompt="check this", max_tokens=32)

    assert result.ok is True
    assert result.content == "ok"
    assert seen["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert "tools" not in seen["json"]
    assert "tool_choice" not in seen["json"]


def test_direct_chat_returns_public_message_when_sanitized_empty(monkeypatch) -> None:
    def fake_post(url, json, timeout):
        return ThinkOnlyResponseStub()

    monkeypatch.setattr("builder_ii.direct_chat.httpx.post", fake_post)

    result = run_direct_chat(settings_stub(), prompt="check this")

    assert result.ok is True
    assert result.content == EMPTY_SANITIZED_OUTPUT_MESSAGE


def test_sanitize_direct_output_removes_think_blocks_and_stop_markers() -> None:
    raw = "<think>private scratchpad</think>Final answer.<|im_end|><|assistant|>more"

    assert sanitize_direct_output(raw) == "Final answer."
