"""Known-limitations document pins (plan item 4.2).

docs/KNOWN_LIMITATIONS.md is generated from the completion truth matrix and must never drift
from it — the exact-equality pin here mirrors the docs/COMMAND_AUTHORITY.md pattern. The D7
verification-scope language is load-bearing: trusted local Python-with-pytest repos only, the
runner bounds invocation (never code behavior), and no surface may call it a sandbox.
"""

from __future__ import annotations

from pathlib import Path

from builder_ii.known_limitations import (
    KNOWN_LIMITATIONS_DOC_PATH,
    render_known_limitations_markdown,
)
from builder_ii.platform_completion_audit import (
    OPERATIONALLY_VERIFIED,
    REQUIRED_CAPABILITY_ROWS,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_doc_on_disk_matches_rendered_matrix_output() -> None:
    doc = (REPO_ROOT / KNOWN_LIMITATIONS_DOC_PATH).read_text(encoding="utf-8")
    assert doc == render_known_limitations_markdown(), (
        "docs/KNOWN_LIMITATIONS.md drifted from the matrix; regenerate with "
        "`uv run builder-platform known-limitations --output docs/KNOWN_LIMITATIONS.md`"
    )


def test_every_non_operational_capability_is_listed() -> None:
    text = render_known_limitations_markdown()
    for row in REQUIRED_CAPABILITY_ROWS:
        if row.state != OPERATIONALLY_VERIFIED:
            assert f"**{row.capability}**" in text, f"missing non-operational capability: {row.capability}"
        else:
            assert f"**{row.capability}**" not in text, f"verified capability listed as limitation: {row.capability}"


def test_d7_verification_scope_language_is_present() -> None:
    text = render_known_limitations_markdown()
    assert "trusted local Python-with-pytest repositories only" in text
    assert "what gets invoked" in text and "what invoked code can do" in text
    assert "not a sandbox" in text
    # The only "sandbox" mentions must be the refusals — never an affirmative claim.
    for line in text.splitlines():
        if "sandbox" in line.lower():
            assert "not a sandbox" in line or "isolation" in line, f"suspicious sandbox claim: {line}"
    assert "Container/VM isolation is post-beta" in text


def test_standing_boundaries_are_stated() -> None:
    text = render_known_limitations_markdown()
    assert "No commit or push automation" in text
    assert "No autonomous writes" in text
    assert "not cryptographic proof" in text
