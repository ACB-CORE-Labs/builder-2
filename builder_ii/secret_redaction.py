"""W5.3 — secret-boundary redaction for receipts, ledgers, and artifacts.

Extends prompt secret *denial* with structure-safe redaction for stored
surfaces: raw secrets never land in digests/receipts/ledger messages.
Token refs (env names) are preserved; values are replaced with token markers.
"""

from __future__ import annotations

import copy
import re
from typing import Any

# Patterns that match secret *values* in free text (redact, don't only deny).
_SECRET_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"sk-[a-zA-Z0-9_]{20,}", re.IGNORECASE),
    re.compile(r"gsk_[a-zA-Z0-9_]{20,}", re.IGNORECASE),
    re.compile(r"xai-[a-zA-Z0-9_]{20,}", re.IGNORECASE),
    re.compile(r"AIza[a-zA-Z0-9_\-]{30,}"),
    re.compile(r"ghp_[a-zA-Z0-9]{30,}"),
    re.compile(r"github_pat_[a-zA-Z0-9_]{20,}", re.IGNORECASE),
    re.compile(r"(?i)bearer\s+[a-zA-Z0-9_\-\.\~]{10,}"),
    re.compile(
        r"(?i)(?:api[_-]?key|apikey|secret|password|token|credential)\s*[:=]\s*[\"']?([a-zA-Z0-9_\-\.]{8,})[\"']?"
    ),
)

REDACTED_MARKER = "<redacted:secret>"
TOKEN_REF_PREFIX = "token_ref:"

# Field names whose values are always treated as secret payloads when string.
_SECRET_FIELD_NAMES = frozenset(
    {
        "api_key",
        "apikey",
        "api-key",
        "secret",
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "auth_header",
        "credential",
        "credentials",
        "private_key",
        "client_secret",
    }
)


def scan_secret_patterns(text: str) -> list[str]:
    """Return human-readable match descriptions (empty if clean)."""
    if not isinstance(text, str) or not text:
        return []
    hits: list[str] = []
    for pattern in _SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            hits.append(f"secret_pattern:{pattern.pattern}")
    return hits


def redact_text(text: str) -> tuple[str, int]:
    """Redact secret-like substrings. Returns (redacted_text, replacement_count)."""
    if not isinstance(text, str) or not text:
        return text, 0
    out = text
    count = 0
    for pattern in _SECRET_VALUE_PATTERNS:
        out, n = pattern.subn(REDACTED_MARKER, out)
        count += n
    return out, count


def is_token_ref(value: str) -> bool:
    """True when value is an explicit token reference (env name / ref), not a raw secret."""
    if not isinstance(value, str):
        return False
    if value.startswith(TOKEN_REF_PREFIX):
        return True
    # Env-style refs used by registry secret_ref_names
    if value.endswith("_REF") or value.endswith("_API_KEY_REF"):
        return True
    if re.fullmatch(r"[A-Z][A-Z0-9_]{2,}", value) and (
        "KEY" in value or "TOKEN" in value or "SECRET" in value
    ):
        return True
    return False


def redact_structure(obj: Any, *, _depth: int = 0) -> tuple[Any, int]:
    """Deep-copy structure with secret field values and matching substrings redacted.

    Returns (redacted_copy, total_redaction_count). Does not mutate input.
    """
    if _depth > 40:
        return obj, 0
    if isinstance(obj, str):
        return redact_text(obj)
    if isinstance(obj, list):
        total = 0
        out_list: list[Any] = []
        for item in obj:
            red, n = redact_structure(item, _depth=_depth + 1)
            out_list.append(red)
            total += n
        return out_list, total
    if isinstance(obj, dict):
        total = 0
        out: dict[str, Any] = {}
        for key, value in obj.items():
            key_l = str(key).lower().replace("-", "_")
            if key_l in _SECRET_FIELD_NAMES and isinstance(value, str):
                if is_token_ref(value):
                    out[key] = value
                else:
                    out[key] = REDACTED_MARKER
                    total += 1
                continue
            red, n = redact_structure(value, _depth=_depth + 1)
            out[key] = red
            total += n
        return out, total
    # ints, bools, None, etc.
    return copy.deepcopy(obj) if not isinstance(obj, (int, float, bool, type(None))) else obj, 0


def token_ref(env_name: str) -> str:
    """Build a non-secret token reference string for artifacts."""
    name = env_name.strip()
    if not name:
        raise ValueError("env_name must be non-empty")
    if name.startswith(TOKEN_REF_PREFIX):
        return name
    return f"{TOKEN_REF_PREFIX}{name}"


def redact_receipt_for_storage(receipt: dict[str, Any]) -> dict[str, Any]:
    """Return a storage-safe receipt copy (response/error surfaces redacted)."""
    redacted, count = redact_structure(receipt)
    if isinstance(redacted, dict):
        redacted = {
            **redacted,
            "secret_redaction": {
                "applied": count > 0,
                "replacement_count": count,
                "marker": REDACTED_MARKER,
                "grants_authority": False,
            },
        }
    return redacted  # type: ignore[return-value]
