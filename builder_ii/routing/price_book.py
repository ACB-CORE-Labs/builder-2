"""Governed price-book artifact for model cost metering.

kind: builder_ii.price_book

RECORDED_ONLY / policy-bound — never grants authority. Used by the model
execution gateway to attach measured-token USD estimates to receipts.
"""

from __future__ import annotations

import hashlib
import json as json_lib
import re
from pathlib import Path
from typing import Any

from builder_ii.routing.model_client_registry import KNOWN_MODEL_IDS
from builder_ii.routing.token_accounting import TOKENIZER_WHITESPACE_V1, TOKENIZER_WHITESPACE_VERSION

PRICE_BOOK_KIND = "builder_ii.price_book"
PRICE_BOOK_SCHEMA_VERSION = 1

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

ALLOWED_LATENCY_CLASSES = frozenset({"local", "low", "medium", "high", "unknown"})
ALLOWED_COST_CLASSES = frozenset({"free_local", "low", "medium", "high", "placeholder"})


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _default_governance() -> dict[str, Any]:
    return {
        "capability_state": "price_book",
        "model_execution": "DISABLED",
        "runtime_execution": "DISABLED",
        "network_calls": "DISABLED",
        "shell_execution": "DISABLED",
        "provider_calls": "DISABLED",
        "artifact_is_authority": False,
        "grants_authority": False,
        "core_workbench_coupling": "NONE",
    }


def _entry(
    *,
    model_id: str,
    input_usd_per_1k: float,
    output_usd_per_1k: float,
    cost_class: str,
    latency_class: str,
    context_window: int,
    tool_use: bool,
    tokenizer_id: str = TOKENIZER_WHITESPACE_V1,
    tokenizer_version: str = TOKENIZER_WHITESPACE_VERSION,
    currency: str = "USD",
    effective_from: str = "2026-07-01",
) -> dict[str, Any]:
    return {
        "model_id": model_id,
        "input_usd_per_1k": float(input_usd_per_1k),
        "output_usd_per_1k": float(output_usd_per_1k),
        "currency": currency,
        "cost_class": cost_class,
        "latency_class": latency_class,
        "context_window": int(context_window),
        "tool_use": bool(tool_use),
        "tokenizer_id": tokenizer_id,
        "tokenizer_version": tokenizer_version,
        "effective_from": effective_from,
    }


def create_default_price_book() -> dict[str, Any]:
    """Create a default price book covering known registry models.

    Local MLX models are free ($0). Stub/cloud placeholders use conservative
    list-price style numbers for ranking/savings estimates only — not billing.
    """
    entries: list[dict[str, Any]] = []

    # Local MLX free_local
    mlx_models = [
        ("mlx-community/Phi-4-mini-reasoning-4bit", 128000, True),
        ("mlx-community/Qwen2.5-Coder-7B-Instruct-4bit", 32768, True),
        ("mlx-community/gemma-4-e4b-it-4bit", 8192, False),
        ("mlx-community/gemma-4-12B-it-4bit", 8192, False),
        ("mlx-community/Meta-Llama-3.1-8B-Instruct-4bit", 128000, True),
        ("mlx-community/codegeex4-all-9b-4bit", 32768, True),
        ("mlx-community/Qwen2.5-Coder-14B-Instruct-4bit", 32768, True),
        ("mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit", 32768, True),
        ("mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit", 32768, True),
    ]
    for mid, ctx, tools in mlx_models:
        entries.append(
            _entry(
                model_id=mid,
                input_usd_per_1k=0.0,
                output_usd_per_1k=0.0,
                cost_class="free_local",
                latency_class="local",
                context_window=ctx,
                tool_use=tools,
            )
        )

    # Stub / cloud placeholder rates (advisory ranking only)
    cloud_specs: list[tuple[str, float, float, str, str, int, bool]] = [
        ("gpt-4o-stub", 0.0025, 0.01, "placeholder", "low", 128000, True),
        ("gpt-4o", 0.0025, 0.01, "high", "medium", 128000, True),
        ("gpt-5.5", 0.005, 0.015, "high", "medium", 200000, True),
        ("gpt-5.5-pro", 0.01, 0.03, "high", "high", 200000, True),
        ("gpt-5.4", 0.003, 0.012, "high", "medium", 128000, True),
        ("gpt-5.4-mini", 0.0004, 0.0016, "medium", "low", 128000, True),
        ("gpt-5.4-nano", 0.0001, 0.0004, "low", "low", 128000, True),
        ("gpt-5.3-codex", 0.003, 0.012, "high", "medium", 128000, True),
        ("o3", 0.01, 0.04, "high", "high", 200000, True),
        ("llama-3.3-70b-versatile", 0.00059, 0.00079, "medium", "low", 128000, True),
        ("mixtral-8x7b-32768", 0.00024, 0.00024, "low", "low", 32768, True),
        ("llama-3.1-8b-instant", 0.00005, 0.00008, "low", "low", 128000, True),
        ("openai/gpt-oss-20b", 0.0001, 0.0002, "low", "low", 8192, False),
        ("openai/gpt-oss-120b", 0.0005, 0.001, "medium", "medium", 8192, False),
        ("meta-llama/llama-4-scout-17b-16e-instruct", 0.00011, 0.00034, "low", "low", 128000, True),
        ("qwen/qwen3-32b", 0.0002, 0.0006, "medium", "medium", 32768, True),
        ("moonshotai/kimi-k2-instruct-0905", 0.0006, 0.0025, "medium", "medium", 128000, True),
        ("grok-2-1212", 0.002, 0.01, "high", "medium", 131072, True),
        ("grok-beta", 0.005, 0.015, "high", "medium", 131072, True),
        ("grok-4.3", 0.003, 0.015, "high", "medium", 131072, True),
        ("grok-build-0.1", 0.001, 0.004, "medium", "low", 131072, True),
        ("grok-4.1-fast", 0.0005, 0.002, "low", "low", 131072, True),
        ("google/gemini-1.5-pro", 0.00125, 0.005, "high", "medium", 1000000, True),
        ("google/gemini-1.5-flash", 0.000075, 0.0003, "low", "low", 1000000, True),
        ("google/gemini-1.0-ultra", 0.002, 0.008, "high", "high", 32768, True),
        ("google/gemini-3.5-flash", 0.0001, 0.0004, "low", "low", 1000000, True),
        ("google/gemini-3.1-pro-preview", 0.00125, 0.005, "high", "medium", 1000000, True),
        ("google/gemini-3.1-flash-lite", 0.00005, 0.0002, "low", "low", 1000000, True),
        ("google/gemini-3-flash-preview", 0.0001, 0.0004, "low", "low", 1000000, True),
        ("claude-fable-5", 0.003, 0.015, "high", "medium", 200000, True),
        ("claude-opus-4-8", 0.015, 0.075, "high", "high", 200000, True),
        ("claude-opus-4-7", 0.015, 0.075, "high", "high", 200000, True),
        ("claude-opus-4-6", 0.015, 0.075, "high", "high", 200000, True),
        ("claude-sonnet-5", 0.003, 0.015, "high", "medium", 200000, True),
        ("claude-sonnet-4-6", 0.003, 0.015, "high", "medium", 200000, True),
        ("claude-sonnet-4-5", 0.003, 0.015, "high", "medium", 200000, True),
        ("claude-haiku-4-5-20251001", 0.0008, 0.004, "medium", "low", 200000, True),
        ("gemma4:e4b", 0.0, 0.0, "free_local", "local", 8192, False),
        ("gemma4:e2b", 0.0, 0.0, "free_local", "local", 8192, False),
        ("qwen3.5:2b", 0.0, 0.0, "free_local", "local", 32768, True),
        ("qwen3.5:0.8b", 0.0, 0.0, "free_local", "local", 32768, False),
        ("ibm/granite4.1:3b", 0.0, 0.0, "free_local", "local", 8192, False),
    ]
    for mid, inn, out, cc, lat, ctx, tools in cloud_specs:
        entries.append(
            _entry(
                model_id=mid,
                input_usd_per_1k=inn,
                output_usd_per_1k=out,
                cost_class=cc,
                latency_class=lat,
                context_window=ctx,
                tool_use=tools,
            )
        )

    # Sort for determinism
    entries.sort(key=lambda e: e["model_id"])

    book: dict[str, Any] = {
        "kind": PRICE_BOOK_KIND,
        "schema_version": PRICE_BOOK_SCHEMA_VERSION,
        "price_book_state": "RECORDED_ONLY",
        "book_name": "default_builder_ii_price_book",
        "currency_default": "USD",
        "entries": entries,
        "executes_model": False,
        "grants_authority": False,
        "requires_human_promotion_for_execution": True,
        "artifact_is_authority": False,
        "governance": _default_governance(),
    }
    book["digest"] = _digest({k: v for k, v in book.items() if k != "digest"})
    return book


def dumps_price_book(book: dict[str, Any]) -> str:
    return json_lib.dumps(book, indent=2, sort_keys=True) + "\n"


def write_price_book(book: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_price_book(book), encoding="utf-8")


def lookup_price_entry(book: dict[str, Any], model_id: str) -> dict[str, Any] | None:
    entries = book.get("entries")
    if not isinstance(entries, list):
        return None
    for entry in entries:
        if isinstance(entry, dict) and entry.get("model_id") == model_id:
            return entry
    return None


def price_book_ref(book: dict[str, Any], *, path: Path | None = None) -> dict[str, Any]:
    digest = book.get("digest")
    if not isinstance(digest, str) or not _SHA256_RE.match(digest):
        digest = _digest({k: v for k, v in book.items() if k != "digest"})
    ref: dict[str, Any] = {
        "kind": PRICE_BOOK_KIND,
        "sha256": digest,
        "role": "price_book",
        "required": True,
    }
    if path is not None:
        ref["path"] = str(path)
    return ref


def validate_price_book(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["price book must be a JSON object"]
    if record.get("kind") != PRICE_BOOK_KIND:
        errors.append(f"kind must be {PRICE_BOOK_KIND}")
    if record.get("schema_version") != PRICE_BOOK_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PRICE_BOOK_SCHEMA_VERSION}")
    if record.get("price_book_state") != "RECORDED_ONLY":
        errors.append("price_book_state must be RECORDED_ONLY")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if record.get("requires_human_promotion_for_execution") is not True:
        errors.append("requires_human_promotion_for_execution must be true")

    entries = record.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        return errors

    seen: set[str] = set()
    for idx, entry in enumerate(entries):
        prefix = f"entries[{idx}]"
        if not isinstance(entry, dict):
            errors.append(f"{prefix} must be an object")
            continue
        mid = entry.get("model_id")
        if not isinstance(mid, str) or not mid:
            errors.append(f"{prefix}.model_id must be a non-empty string")
        elif mid in seen:
            errors.append(f"{prefix}.model_id '{mid}' is not unique")
        else:
            seen.add(mid)
            if mid not in KNOWN_MODEL_IDS:
                errors.append(f"{prefix}.model_id '{mid}' is unknown")
        for rate_field in ("input_usd_per_1k", "output_usd_per_1k"):
            val = entry.get(rate_field)
            if not isinstance(val, (int, float)) or isinstance(val, bool) or val < 0:
                errors.append(f"{prefix}.{rate_field} must be a non-negative number")
        if entry.get("currency") != "USD" and not isinstance(entry.get("currency"), str):
            errors.append(f"{prefix}.currency must be a non-empty string")
        cc = entry.get("cost_class")
        if cc not in ALLOWED_COST_CLASSES:
            errors.append(f"{prefix}.cost_class invalid; must be one of {sorted(ALLOWED_COST_CLASSES)}")
        lat = entry.get("latency_class")
        if lat not in ALLOWED_LATENCY_CLASSES:
            errors.append(f"{prefix}.latency_class invalid; must be one of {sorted(ALLOWED_LATENCY_CLASSES)}")
        ctx = entry.get("context_window")
        if not isinstance(ctx, int) or ctx <= 0:
            errors.append(f"{prefix}.context_window must be a positive integer")
        if not isinstance(entry.get("tool_use"), bool):
            errors.append(f"{prefix}.tool_use must be a boolean")
        if not isinstance(entry.get("tokenizer_id"), str) or not entry.get("tokenizer_id"):
            errors.append(f"{prefix}.tokenizer_id must be a non-empty string")
        if not isinstance(entry.get("tokenizer_version"), str) or not entry.get("tokenizer_version"):
            errors.append(f"{prefix}.tokenizer_version must be a non-empty string")

    gov = record.get("governance")
    if not isinstance(gov, dict):
        errors.append("governance must be an object")
    else:
        if gov.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if gov.get("grants_authority") is not False:
            errors.append("governance.grants_authority must be false")

    digest = record.get("digest")
    if digest is not None:
        if not isinstance(digest, str) or not _SHA256_RE.match(digest):
            errors.append("digest must be a 64-char hex SHA-256 when present")
        else:
            expected = _digest({k: v for k, v in record.items() if k != "digest"})
            if digest != expected:
                errors.append("digest does not match canonical payload")

    return errors


def validate_price_book_file(path: Path) -> list[str]:
    if not path.is_file():
        return [f"file not found or not a file: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_price_book(data)
