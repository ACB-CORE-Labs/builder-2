"""P6 Maker exchange package: artifact_digests must match real file SHA-256 when set.

Prevents false integrity claims (digest theater). Empty maps (prior-wave style)
remain valid; non-empty maps must equal hashlib.sha256(file_bytes).hexdigest().
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from builder_ii.wrp.exchange import validate_maker_candidate_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "artifacts/wrp_exchange/mastery/P6/maker_candidate_manifest.json"


def test_p6_maker_manifest_exists_and_validates() -> None:
    assert MANIFEST_PATH.is_file(), f"missing Maker package: {MANIFEST_PATH}"
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    errors = validate_maker_candidate_manifest(data)
    assert errors == [], errors
    assert data.get("self_certified") is False
    assert data.get("requires_governor_cert") is True
    assert data.get("grants_authority") is False
    assert data.get("wave") == "P6"


def test_p6_maker_artifact_digests_match_file_bytes() -> None:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    digests = data.get("artifact_digests")
    assert isinstance(digests, dict)
    # Non-empty for this wave — integrity claim must be real.
    assert digests, "P6 package claims file digests; map must not be empty"
    for rel, claimed in digests.items():
        path = REPO_ROOT / rel
        assert path.is_file(), f"digest path missing: {rel}"
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        assert actual == claimed, f"false digest for {rel}: file={actual} claimed={claimed}"
        assert isinstance(claimed, str) and len(claimed) == 64
