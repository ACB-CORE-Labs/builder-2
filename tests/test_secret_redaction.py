"""W5.3 secret redaction."""

from __future__ import annotations

from builder_ii.secret_redaction import (
    REDACTED_MARKER,
    redact_receipt_for_storage,
    redact_structure,
    redact_text,
    token_ref,
)


def test_redact_text_strips_api_key() -> None:
    text, n = redact_text("key sk-abcdefghijklmnopqrstuvwxyz0123456789 end")
    assert n >= 1
    assert "sk-abc" not in text
    assert REDACTED_MARKER in text


def test_redact_structure_secret_fields() -> None:
    data = {"api_key": "supersecretvalue", "model": "x", "token_ref": token_ref("OPENAI_API_KEY")}
    out, n = redact_structure(data)
    assert out["api_key"] == REDACTED_MARKER
    assert out["model"] == "x"
    assert out["token_ref"].startswith("token_ref:")
    assert n >= 1


def test_redact_receipt_for_storage() -> None:
    receipt = {
        "kind": "builder_ii.model_call_receipt",
        "response_text": "hello",
        "password": "hunter2hunter2",
    }
    safe = redact_receipt_for_storage(receipt)
    assert safe["password"] == REDACTED_MARKER
    assert safe["secret_redaction"]["applied"] is True
