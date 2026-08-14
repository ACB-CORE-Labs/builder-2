import hashlib
import json
from typing import Any


def canonical_json(value: Any, ensure_ascii: bool = True) -> str:
    """Serialise deterministically: sorted keys, no incidental whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ensure_ascii)

def canonical_digest(value: Any, ensure_ascii: bool = True) -> str:
    """Canonical SHA-256 digest of a JSON-serializable value."""
    return hashlib.sha256(canonical_json(value, ensure_ascii=ensure_ascii).encode("utf-8")).hexdigest()
