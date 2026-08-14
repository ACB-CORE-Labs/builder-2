"""W5.1 — run-manifest replay harness.

Re-derives deterministic digests from a run_manifest + envelope/receipt and
flags **only** the LLM completion as non-deterministic. Does not re-invoke models.
"""

from __future__ import annotations

import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.core.run_manifest import RUN_MANIFEST_KIND, validate_run_manifest

REPLAY_REPORT_KIND = "builder_ii.run_replay_report"
REPLAY_REPORT_SCHEMA_VERSION = 1


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replay_from_manifest(
    manifest: dict[str, Any],
    *,
    envelope: dict[str, Any] | None = None,
    receipt: dict[str, Any] | None = None,
    envelope_path: Path | None = None,
    receipt_path: Path | None = None,
) -> dict[str, Any]:
    """Validate deterministic surfaces; never re-executes a model."""
    errors = validate_run_manifest(manifest)
    if errors:
        raise ValueError("invalid run_manifest: " + "; ".join(errors))

    checks: list[dict[str, Any]] = []
    all_ok = True

    # Re-derive manifest digest excluding its own digest field.
    expected_manifest_digest = _digest({k: v for k, v in manifest.items() if k != "digest"})
    md_ok = expected_manifest_digest == manifest.get("digest")
    checks.append(
        {
            "surface": "manifest_digest",
            "deterministic": True,
            "ok": md_ok,
            "expected": expected_manifest_digest,
            "observed": manifest.get("digest"),
        }
    )
    all_ok = all_ok and md_ok

    if envelope is not None:
        env_ok = envelope.get("prompt_digest") == manifest.get("prompt_digest")
        checks.append(
            {
                "surface": "prompt_digest_vs_envelope",
                "deterministic": True,
                "ok": env_ok,
                "expected": manifest.get("prompt_digest"),
                "observed": envelope.get("prompt_digest"),
            }
        )
        all_ok = all_ok and env_ok
        if envelope.get("digest") and manifest.get("envelope_digest"):
            ed_ok = envelope.get("digest") == manifest.get("envelope_digest")
            checks.append(
                {
                    "surface": "envelope_digest",
                    "deterministic": True,
                    "ok": ed_ok,
                    "expected": manifest.get("envelope_digest"),
                    "observed": envelope.get("digest"),
                }
            )
            all_ok = all_ok and ed_ok

    if receipt is not None:
        if receipt.get("digest") and manifest.get("receipt_digest"):
            rd_ok = receipt.get("digest") == manifest.get("receipt_digest")
            checks.append(
                {
                    "surface": "receipt_digest",
                    "deterministic": True,
                    "ok": rd_ok,
                    "expected": manifest.get("receipt_digest"),
                    "observed": receipt.get("digest"),
                }
            )
            all_ok = all_ok and rd_ok
        # Explicit non-deterministic surface declaration
        checks.append(
            {
                "surface": "llm_completion_text",
                "deterministic": False,
                "ok": True,
                "declaration": "non-deterministic-llm-completion",
                "observed_len": len(str(receipt.get("response_text") or "")),
            }
        )

    if envelope_path is not None and envelope_path.is_file() and manifest.get("envelope_digest"):
        file_sha = _file_digest(envelope_path)
        # File may include full envelope JSON; compare when envelope provided
        if envelope is not None and envelope.get("digest"):
            path_ok = envelope.get("digest") == manifest.get("envelope_digest")
        else:
            path_ok = True  # path presence recorded; content check needs envelope
        checks.append(
            {
                "surface": "envelope_path_present",
                "deterministic": True,
                "ok": path_ok,
                "path": str(envelope_path),
                "file_sha256": file_sha,
            }
        )

    if receipt_path is not None and receipt_path.is_file():
        checks.append(
            {
                "surface": "receipt_path_present",
                "deterministic": True,
                "ok": True,
                "path": str(receipt_path),
                "file_sha256": _file_digest(receipt_path),
            }
        )

    report: dict[str, Any] = {
        "kind": REPLAY_REPORT_KIND,
        "schema_version": REPLAY_REPORT_SCHEMA_VERSION,
        "report_state": "RECONSTRUCTED_ONLY",
        "manifest_kind": RUN_MANIFEST_KIND,
        "manifest_digest": manifest.get("digest"),
        "model_id": manifest.get("model_id"),
        "tokenizer_id": manifest.get("tokenizer_id"),
        "tokenizer_version": manifest.get("tokenizer_version"),
        "checks": checks,
        "deterministic_ok": all_ok,
        "replay_declaration": "non-deterministic-llm-completion",
        "executes_model": False,
        "reinvokes_provider": False,
        "grants_authority": False,
        "artifact_is_authority": False,
    }
    report["digest"] = _digest({k: v for k, v in report.items() if k != "digest"})
    return report


def validate_run_replay_report(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["run_replay_report must be a JSON object"]
    if record.get("kind") != REPLAY_REPORT_KIND:
        errors.append(f"kind must be {REPLAY_REPORT_KIND}")
    if record.get("schema_version") != REPLAY_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REPLAY_REPORT_SCHEMA_VERSION}")
    if record.get("executes_model") is not False:
        errors.append("executes_model must be false")
    if record.get("reinvokes_provider") is not False:
        errors.append("reinvokes_provider must be false")
    if record.get("grants_authority") is not False:
        errors.append("grants_authority must be false")
    if not isinstance(record.get("checks"), list):
        errors.append("checks must be a list")
    return errors
