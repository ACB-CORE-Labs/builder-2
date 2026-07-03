from pathlib import Path

from builder_ii.platform_status_cli import platform_app
from typer.testing import CliRunner

from builder_ii.platform_completion_audit import (
    REQUIRED_CAPABILITY_ROWS,
    render_capability_table_markdown,
    render_docs_audit_jsonable,
    scan_docs_for_false_completion,
)

runner = CliRunner()


def test_docs_do_not_claim_operational_completion_for_non_operational_capabilities() -> None:
    report = render_docs_audit_jsonable(Path("."))
    assert report["valid"] is True, report["violations"]


def test_audit_docs_cli_passes_repository_docs() -> None:
    result = runner.invoke(platform_app, ["audit-docs"])
    assert result.exit_code == 0, result.output
    assert '"valid": true' in result.output


def test_audit_docs_fails_closed_on_false_completion_claim(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    (tmp_path / "README.md").write_text("# bad\n", encoding="utf-8")
    (docs / "bad.md").write_text("tool registry is complete and operational.\n", encoding="utf-8")

    violations = scan_docs_for_false_completion(tmp_path)
    assert violations
    assert violations[0].path == "docs/bad.md"
    assert "tool registry" in violations[0].reason


def test_readme_no_longer_says_model_routing_is_only_an_rfc() -> None:
    text = Path("README.md").read_text(encoding="utf-8")
    assert "Model routing policy artifact (RFC exists, artifact not yet built)" not in text
    assert "Passive model client registry and routing policy via `builder-model-policy`" in text
    assert "Model/provider execution gateway" in text


def test_platform_completion_audit_table_matches_matrix_source() -> None:
    doc = Path("docs/PLATFORM_COMPLETION_AUDIT.md").read_text(encoding="utf-8")
    for row in REQUIRED_CAPABILITY_ROWS:
        assert f"| {row.capability} | `{row.state}` | {row.next_pr} |" in doc
    rendered = render_capability_table_markdown()
    for line in rendered.splitlines()[2:]:
        assert line in doc


def test_truth_report_promoted_capabilities_match_matrix() -> None:
    report = Path("docs/BUILDER_II_COMPLETION_TRUTH_REPORT.md").read_text(encoding="utf-8")
    promoted = (
        "HITL patch application",
        "rollback execution",
        "HITL-approved verification execution",
        "model/provider execution",
        "command authority as runtime gate",
        "deepagents runtime/subagents",
        "config schema",
        "setup receipt + rollback artifact",
    )
    by_capability = {row.capability: row for row in REQUIRED_CAPABILITY_ROWS}
    stale_phrases = (
        "Setup apply, receipts, rollback, migration tooling, and runtime authority are still missing",
        "rollback execution, ledger event, and replay binding are missing",
    )
    for phrase in stale_phrases:
        assert phrase not in report

    for capability in promoted:
        row = by_capability[capability]
        assert f"| {capability} | {row.state} |" in report


def test_docs_state_corrected_sequence() -> None:
    for path in (
        Path("docs/PLATFORM_COMPLETION_AUDIT.md"),
        Path("docs/FOUNDATION_STATUS.md"),
        Path("docs/ROADMAP.md"),
    ):
        text = path.read_text(encoding="utf-8")
        assert "R0 -> R1 -> B1" in text
        assert "R1 Config + Onboarding Kernel must precede B1 verification execution" in text
