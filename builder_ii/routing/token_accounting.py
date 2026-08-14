"""Deterministic token accounting for governed model calls.

Provides measured, versioned token counts without requiring heavyweight
tokenizer packages by default (M1 mechanical sympathy). Optional tiktoken
support is used when installed for OpenAI-family models.

Honesty boundary:
- ``measured`` means a pinned tokenizer algorithm was applied.
- ``estimated`` is only allowed with an explicit reason code — never silent
  word-count presented as measured.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Pinned pure-Python tokenizer identity (reproducible across hosts).
TOKENIZER_WHITESPACE_V1 = "builder_ii.whitespace_v1"
TOKENIZER_WHITESPACE_VERSION = "1.0.0"

# Optional OpenAI encoding identity when tiktoken is available.
TOKENIZER_TIKTOKEN_CL100K = "tiktoken.cl100k_base"
TOKENIZER_TIKTOKEN_VERSION = "cl100k_base"

_WHITESPACE_SPLIT = re.compile(r"\s+")
_PUNCT_ATTACH = re.compile(r"([^\w\s]+)", re.UNICODE)

# OpenAI-ish model id prefixes that prefer cl100k when tiktoken is present.
_OPENAI_FAMILY_MARKERS = (
    "gpt-",
    "o3",
    "o1",
    "gpt-4o",
    "text-embedding",
)


@dataclass(frozen=True)
class TokenCountResult:
    token_count: int
    tokenizer_id: str
    tokenizer_version: str
    token_accounting: str  # "measured" | "estimated"
    estimated_reason: str | None = None


def count_tokens_whitespace_v1(text: str) -> TokenCountResult:
    """Measured tokenizer: split on whitespace after isolating punctuation.

    Empty / whitespace-only text counts as 0 tokens.
    """
    stripped = text.strip()
    if not stripped:
        return TokenCountResult(
            token_count=0,
            tokenizer_id=TOKENIZER_WHITESPACE_V1,
            tokenizer_version=TOKENIZER_WHITESPACE_VERSION,
            token_accounting="measured",
        )
    # Isolate punctuation so "hello," is two tokens: hello + ,
    spaced = _PUNCT_ATTACH.sub(r" \1 ", stripped)
    parts = [p for p in _WHITESPACE_SPLIT.split(spaced) if p]
    return TokenCountResult(
        token_count=len(parts),
        tokenizer_id=TOKENIZER_WHITESPACE_V1,
        tokenizer_version=TOKENIZER_WHITESPACE_VERSION,
        token_accounting="measured",
    )


def _try_tiktoken_cl100k(text: str) -> TokenCountResult | None:
    try:
        import tiktoken  # type: ignore[import-not-found]
    except Exception:
        return None
    try:
        enc = tiktoken.get_encoding("cl100k_base")
        n = len(enc.encode(text))
    except Exception:
        return None
    return TokenCountResult(
        token_count=n,
        tokenizer_id=TOKENIZER_TIKTOKEN_CL100K,
        tokenizer_version=TOKENIZER_TIKTOKEN_VERSION,
        token_accounting="measured",
    )


def prefer_openai_family(model_id: str) -> bool:
    mid = model_id.lower()
    return any(mid.startswith(m) or f"/{m}" in mid for m in _OPENAI_FAMILY_MARKERS)


def count_tokens(
    text: str,
    *,
    model_id: str = "",
    tokenizer_id: str | None = None,
) -> TokenCountResult:
    """Count tokens with a measured tokenizer.

    Resolution order:
    1. Explicit tokenizer_id if supported.
    2. tiktoken cl100k for OpenAI-family model ids when available.
    3. builder_ii.whitespace_v1 (always available, always measured).
    """
    if tokenizer_id == TOKENIZER_TIKTOKEN_CL100K or (
        tokenizer_id is None and model_id and prefer_openai_family(model_id)
    ):
        result = _try_tiktoken_cl100k(text)
        if result is not None:
            return result
        if tokenizer_id == TOKENIZER_TIKTOKEN_CL100K:
            # Explicit request failed — fall through to whitespace measured,
            # with estimated_reason only if we cannot measure (we always can).
            pass
    if tokenizer_id in (None, TOKENIZER_WHITESPACE_V1):
        return count_tokens_whitespace_v1(text)
    # Unknown tokenizer id — still measure with whitespace rather than invent numbers.
    base = count_tokens_whitespace_v1(text)
    return TokenCountResult(
        token_count=base.token_count,
        tokenizer_id=TOKENIZER_WHITESPACE_V1,
        tokenizer_version=TOKENIZER_WHITESPACE_VERSION,
        token_accounting="measured",
        estimated_reason=f"unknown_tokenizer_id:{tokenizer_id};used={TOKENIZER_WHITESPACE_V1}",
    )


def estimate_usd(
    *,
    input_tokens: int,
    output_tokens: int,
    input_usd_per_1k: float,
    output_usd_per_1k: float,
) -> dict[str, float]:
    """Compute USD estimates from token counts and per-1k rates."""
    if input_tokens < 0 or output_tokens < 0:
        raise ValueError("token counts must be non-negative")
    in_usd = (input_tokens / 1000.0) * float(input_usd_per_1k)
    out_usd = (output_tokens / 1000.0) * float(output_usd_per_1k)
    return {
        "estimated_usd_input": round(in_usd, 8),
        "estimated_usd_output": round(out_usd, 8),
        "estimated_usd_total": round(in_usd + out_usd, 8),
    }


def build_cost_report(
    *,
    prompt: str,
    response_text: str,
    model_id: str,
    input_usd_per_1k: float = 0.0,
    output_usd_per_1k: float = 0.0,
    currency: str = "USD",
    price_book_ref: dict[str, Any] | None = None,
    tokenizer_id: str | None = None,
) -> dict[str, Any]:
    """Build a full cost_report object for model call receipts."""
    in_tc = count_tokens(prompt, model_id=model_id, tokenizer_id=tokenizer_id)
    out_tc = count_tokens(response_text, model_id=model_id, tokenizer_id=tokenizer_id)
    # Prefer a single tokenizer identity; if they differ, keep input's and note.
    usd = estimate_usd(
        input_tokens=in_tc.token_count,
        output_tokens=out_tc.token_count,
        input_usd_per_1k=input_usd_per_1k,
        output_usd_per_1k=output_usd_per_1k,
    )
    report: dict[str, Any] = {
        "input_tokens": in_tc.token_count,
        "output_tokens": out_tc.token_count,
        "total_tokens": in_tc.token_count + out_tc.token_count,
        "token_accounting": in_tc.token_accounting,
        "tokenizer_id": in_tc.tokenizer_id,
        "tokenizer_version": in_tc.tokenizer_version,
        "currency": currency,
        **usd,
    }
    if in_tc.estimated_reason:
        report["estimated_reason"] = in_tc.estimated_reason
    if price_book_ref is not None:
        report["price_book_ref"] = price_book_ref
    return report
