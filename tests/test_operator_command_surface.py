from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner

from builder_ii.session_cli import session_app

ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = ROOT / "docs" / "OPERATOR_COMMAND_SURFACE.md"


def test_operator_command_surface_doc_exists_and_preserves_identity():
    assert DOC_PATH.exists(), "OPERATOR_COMMAND_SURFACE.md must exist"
    content = DOC_PATH.read_text(encoding="utf-8")

    required_identity = [
        "generic governed local agent/developer platform",
        "not CORE Workbench",
        "not CORE UI/UX",
        "not a second CORE runtime",
        "CORE is only a target profile",
    ]
    for phrase in required_identity:
        assert phrase in content, f"Missing identity phrase: {phrase}"


def test_operator_command_surface_doc_forbidden_terms():
    content = DOC_PATH.read_text(encoding="utf-8")
    forbidden = [
        "CORE cockpit",
        "CORE Workbench identity",
        "CORE runtime cockpit",
    ]
    for term in forbidden:
        assert term not in content, f"Forbidden term found: {term}"


def test_operator_command_surface_doc_names_profiles_and_lane():
    content = DOC_PATH.read_text(encoding="utf-8")
    required = [
        "`generic`",
        "`builder`",
        "`core`",
        "builder-session prepare-package",
        "builder-session validate-prepare-package",
        "builder-session summarize-prepare-package",
    ]
    for phrase in required:
        assert phrase in content, f"Missing profile or lane phrase: {phrase}"


def test_operator_command_surface_doc_references_related_docs():
    content = DOC_PATH.read_text(encoding="utf-8")
    required_docs = [
        "OPERATOR_QUICKSTART.md",
        "GOVERNED_PREPARE_PACKAGE.md",
        "VALIDATE_PREPARE_PACKAGE.md",
        "PREPARE_PACKAGE_SUMMARY.md",
    ]
    for doc in required_docs:
        assert doc in content, f"Missing doc reference: {doc}"


def test_operator_command_surface_doc_command_groups():
    content = DOC_PATH.read_text(encoding="utf-8")
    groups = [
        "Discovery / Inspection",
        "Session Preparation",
        "Package Validation",
        "Package Summarization",
        "Handoff / Notes",
        "Verification Planning",
        "Assignment / Orchestration",
        "HITL Request / Receipt / Evidence",
        "Optional Deepagents Readiness",
    ]
    for group in groups:
        assert group in content, f"Missing command group: {group}"


def test_operator_command_surface_doc_runtime_boundary_and_non_authoritative_claims():
    content = DOC_PATH.read_text(encoding="utf-8")
    required_boundaries = [
        "no target-repo execution",
        "no shell execution",
        "no subprocess-backed authority",
        "no Goose activation",
        "no deepagents activation/delegation",
        "no model/runtime execution",
        "no target-repo writes",
        "no Deephaven changes",
        "no CORE Workbench/UI coupling",
        "no conversion of planned verification into completed evidence",
        "summary artifacts are not authoritative",
        "planned verification commands do not imply or constitute executed verification",
    ]
    for phrase in required_boundaries:
        assert phrase in content, f"Missing boundary phrase: {phrase}"


def test_operator_command_surface_doc_covers_goal2_assignment_commands():
    content = DOC_PATH.read_text(encoding="utf-8")
    required = [
        "builder-orchestration render-assignment",
        "builder-orchestration validate",
        "builder-orchestration dry-run",
        "planned bindings, denied capabilities, required promotions, expected evidence, and handoff expectations",
        "no execution, authorization, promotion, or verification evidence",
    ]
    for phrase in required:
        assert phrase in content, f"Missing Goal 2 operator surface phrase: {phrase}"


def test_operator_command_surface_doc_covers_deepagents_actual_commands():
    content = DOC_PATH.read_text(encoding="utf-8")
    required = [
        "builder-deepagents policy",
        "builder-deepagents validate",
        "builder-deepagents readiness",
        "builder-deepagents validate-readiness",
        "builder-deepagents forge",
        "builder-deepagents delegate",
        "builder-deepagents work-plan",
        "builder-deepagents validate-work-artifact",
        "builder-deepagents execution-candidate",
        "builder-deepagents backend-readiness",
        "builder-deepagents approve-candidate",
        "builder-deepagents run-approved",
        "builder-deepagents replay-run",
        "builder-deepagents evidence-bundle",
        "builder-deepagents resume-approved",
    ]
    for phrase in required:
        assert phrase in content, f"Missing deepagents command phrase: {phrase}"
    assert "builder-deepagents check-readiness" not in content


def test_session_cli_command_surface_discoverability():
    runner = CliRunner()
    for cmd in ["command-surface", "operator-surface"]:
        result = runner.invoke(session_app, [cmd])
        assert result.exit_code == 0, result.output
        assert "docs/OPERATOR_COMMAND_SURFACE.md" in result.output
        assert "builder-session prepare-package" in result.output


def test_cli_identity_coherence():
    import builder_ii
    from builder_ii.cli import app

    doc = getattr(builder_ii, "__doc__", None) or ""
    if doc:
        assert "Generic governed platform" in doc
        assert "CORE builder-II" not in doc

    assert "Generic governed platform" in app.info.help
    assert "CORE builder-II" not in app.info.help
    assert "Local CORE coding platform" not in app.info.help
