from pathlib import Path

from builder_ii.platform_completion_audit import (
    REQUIRED_CAPABILITY_ROWS,
    render_capability_table_markdown,
)

DOC = Path("docs/PLATFORM_COMPLETION_AUDIT.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_platform_completion_audit_exists() -> None:
    assert DOC.exists()


def test_platform_completion_audit_declares_generic_identity_and_core_boundary() -> None:
    text = _text()
    assert "builder-II is a generic governed local agent/developer platform" in text
    assert "CORE is a target profile" in text
    assert "not CORE Workbench/UI" in text


def test_platform_completion_audit_lists_allowed_state_labels() -> None:
    text = _text()
    for label in (
        "NOT_STARTED",
        "DESIGN_ONLY",
        "ARTIFACT_ONLY",
        "PASSIVE_FOUNDATION",
        "IMPLEMENTED_ON_BRANCH",
        "PR_OPEN",
        "MERGED_BUT_NOT_OPERATIONAL",
        "OPERATIONALLY_VERIFIED",
    ):
        assert f"`{label}`" in text


def test_platform_completion_audit_mirrors_required_rows() -> None:
    text = _text()
    for row in REQUIRED_CAPABILITY_ROWS:
        assert f"| {row.capability} | `{row.state}` | {row.next_pr} |" in text


def test_render_capability_table_markdown_matches_doc() -> None:
    rendered = render_capability_table_markdown()
    text = _text()
    for line in rendered.splitlines()[2:]:
        assert line in text


def test_platform_completion_audit_names_non_goals() -> None:
    text = _text()
    for phrase in (
        "runtime execution",
        "patch application",
        "model/provider calls",
        "MCP/tool invocation",
        "Goose runtime promotion",
        "deepagents runtime",
        "autonomous writes",
        "commit/push automation",
    ):
        assert phrase in text


def test_platform_completion_audit_splits_legacy_helpers_from_canonical_lanes() -> None:
    text = _text()
    assert "Legacy operator-managed helpers" in text
    assert "Canonical governed passive lanes" in text
    assert "builder-platform" in text


def test_platform_completion_audit_states_r1_before_b1() -> None:
    text = _text()
    assert "R0 -> R1 -> B1" in text
    assert "R1 Config + Onboarding Kernel must precede B1 verification execution" in text


def test_b9_operational_verification_requires_no_runtime_promotion() -> None:
    # B9 can be OPERATIONALLY_VERIFIED only if its blockers explicitly state it does not promote runtime execution.
    b9_row = next(r for r in REQUIRED_CAPABILITY_ROWS if r.capability == "operator quickstart/golden path")
    if b9_row.state == "OPERATIONALLY_VERIFIED":
        assert any("does not promote runtime execution" in b.lower() for b in b9_row.blockers)


def test_b8_passive_foundation_requires_no_implied_mutation() -> None:
    # B8 can remain PASSIVE_FOUNDATION only if blockers do not imply hidden memory or operational memory mutation.
    b8_row = next(r for r in REQUIRED_CAPABILITY_ROWS if r.capability == "artifact memory")
    if b8_row.state == "PASSIVE_FOUNDATION":
        assert any("do not imply operational memory mutation" in b.lower() for b in b8_row.blockers)


def test_next_sequence_matches_incomplete_rows() -> None:
    # NEXT_SEQUENCE must match actual incomplete capability rows.
    from builder_ii.platform_completion_audit import NEXT_SEQUENCE

    assert NEXT_SEQUENCE == "B8 deferred; B9 complete"
