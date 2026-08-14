"""W5.1 — run manifest binding for replay declaration honesty.

kind: builder_ii.run_manifest

Binds deterministic identity of a model call (model, params, digests, tokenizer)
so a replay harness can re-derive envelopes and flag only the LLM completion.
"""

from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

RUN_MANIFEST_KIND = "builder_ii.run_manifest"
RUN_MANIFEST_SCHEMA_VERSION = 1


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def create_run_manifest(
    *,
    model_id: str,
    model_version: str = "unspecified",
    params: dict[str, Any] | None = None,
    prompt_digest: str,
    context_digest: str | None = None,
    tokenizer_id: str,
    tokenizer_version: str,
    seed: int | None = None,
    envelope_digest: str | None = None,
    receipt_digest: str | None = None,
) -> dict[str, Any]:
    if not isinstance(prompt_digest, str) or len(prompt_digest) != 64:
        raise ValueError("prompt_digest must be a 64-char hex digest")
    manifest: dict[str, Any] = {
        "kind": RUN_MANIFEST_KIND,
        "schema_version": RUN_MANIFEST_SCHEMA_VERSION,
        "manifest_state": "RECORDED_ONLY",
        "model_id": model_id,
        "model_version": model_version,
        "params": dict(params or {}),
        "prompt_digest": prompt_digest,
        "context_digest": context_digest,
        "tokenizer_id": tokenizer_id,
        "tokenizer_version": tokenizer_version,
        "seed": seed,
        "envelope_digest": envelope_digest,
        "receipt_digest": receipt_digest,
        "replay_declaration": "non-deterministic-llm-completion",
        "deterministic_surface": [
            "prompt_digest",
            "params",
            "model_id",
            "tokenizer_id",
            "tokenizer_version",
        ],
        "non_deterministic_surface": ["llm_completion_text"],
        "executes_model": False,
        "grants_authority": False,
        "artifact_is_authority": False,
    }
    manifest["digest"] = _digest({k: v for k, v in manifest.items() if k != "digest"})
    return manifest


def validate_run_manifest(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["run manifest must be a JSON object"]
    if record.get("kind") != RUN_MANIFEST_KIND:
        errors.append(f"kind must be {RUN_MANIFEST_KIND}")
    if record.get("schema_version") != RUN_MANIFEST_SCHEMA_VERSION:
        errors.append(f"schema_version must be {RUN_MANIFEST_SCHEMA_VERSION}")
    if record.get("manifest_state") != "RECORDED_ONLY":
        errors.append("manifest_state must be RECORDED_ONLY")
    if record.get("replay_declaration") != "non-deterministic-llm-completion":
        errors.append("replay_declaration must be non-deterministic-llm-completion")
    if not isinstance(record.get("prompt_digest"), str) or len(record["prompt_digest"]) != 64:
        errors.append("prompt_digest must be a 64-char hex digest")
    if not isinstance(record.get("tokenizer_id"), str) or not record.get("tokenizer_id"):
        errors.append("tokenizer_id must be a non-empty string")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if record.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    return errors


def write_run_manifest(manifest: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json_lib.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_manifest_from_receipt(envelope: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    cost = receipt.get("cost_report") if isinstance(receipt.get("cost_report"), dict) else {}
    return create_run_manifest(
        model_id=str(envelope.get("model_id") or ""),
        model_version=str(envelope.get("provider_id") or "unspecified"),
        params={
            "max_tokens": envelope.get("max_tokens"),
            "temperature": envelope.get("temperature"),
        },
        prompt_digest=str(envelope.get("prompt_digest") or ""),
        tokenizer_id=str(cost.get("tokenizer_id") or "unknown"),
        tokenizer_version=str(cost.get("tokenizer_version") or "unknown"),
        envelope_digest=envelope.get("digest"),
        receipt_digest=receipt.get("digest"),
    )
