from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "GOVERNED_SESSION_BOOTSTRAP.md"


def _doc() -> str:
    return DOC.read_text(encoding="utf-8")


def test_governed_session_bootstrap_doc_exists():
    assert DOC.exists()


def test_bootstrap_doc_preserves_builder_ii_boundary():
    doc = _doc()

    required = [
        "generic governed local agent/developer platform",
        "not CORE Workbench",
        "not CORE UI/UX",
        "not a second CORE runtime",
        "CORE is only a target profile",
    ]

    for phrase in required:
        assert phrase in doc


def test_bootstrap_doc_names_the_artifact_chain():
    doc = _doc()

    required = [
        "target repo",
        "target profile",
        "session workflow plan",
        "Goose read-only session plan",
        "verification profile report",
        "handoff note",
        "optional deepagents readiness report",
    ]

    for phrase in required:
        assert phrase in doc


def test_bootstrap_doc_states_allowed_and_forbidden_operations():
    doc = _doc()

    allowed = [
        "inspect repository metadata",
        "resolve profiles",
        "render plans",
        "write explicit artifact files",
        "validate artifacts",
    ]

    forbidden = [
        "shell execution against the target repo",
        "autonomous source writes",
        "model/runtime execution",
        "deepagents delegation",
        "Goose activation",
        "Deephaven changes",
        "hidden authority escalation",
    ]

    for phrase in allowed + forbidden:
        assert phrase in doc


def test_bootstrap_doc_includes_copyable_command_blocks():
    doc = _doc()

    expected_commands = [
        "builder-session plan",
        "builder-session validate",
        "builder-session goose-readonly-plan",
        "builder-session validate-goose-readonly-plan",
    ]

    for command in expected_commands:
        assert command in doc

    bash_blocks = re.findall(r"```bash\n(.*?)\n```", doc, flags=re.DOTALL)
    assert len(bash_blocks) >= 4


def test_bootstrap_doc_keeps_deepagents_optional():
    doc = _doc()

    required = [
        "must remain optional",
        "make deepagents a hard dependency",
        "import deepagents at module import time",
        "delegate to agents",
        "grant runtime authority",
    ]

    for phrase in required:
        assert phrase in doc


def test_bootstrap_doc_completion_criteria_are_governed():
    doc = _doc()

    required = [
        "all generated artifacts validate",
        "no runtime authority has been granted",
        "future execution remains HITL-gated",
        "target profile remains explicit",
        "CORE-specific behavior is scoped to the `core` target profile only",
    ]

    for phrase in required:
        assert phrase in doc
