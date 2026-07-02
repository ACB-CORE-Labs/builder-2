from __future__ import annotations

import importlib
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


REQUIRED_MODULES = [
    "builder_ii.profile_resolution",
    "builder_ii.session_workflow",
    "builder_ii.goose_readonly_session",
    "builder_ii.verification_profile_reports",
    "builder_ii.handoff_notes",
    "builder_ii.deepagents_bridge_readiness",
    "builder_ii.artifact_index_records",
    "builder_ii.artifact_chain_verification",
]


REQUIRED_DOC_PHRASES = [
    "generic governed local agent/developer platform",
    "not CORE Workbench",
    "CORE remains a target profile only",
    "builder_ii.session_workflow_plan",
    "builder_ii.goose_readonly_session_plan",
    "builder_ii.verification_profile_report",
    "builder_ii.handoff_note",
    "builder_ii.deepagents_bridge_readiness_report",
    "no autonomous source writes by default",
    "no shell execution by default",
    "no deepagents hard dependency",
    "no Deephaven changes",
    "artifact index and chain verification",
]


REQUIRED_ARTIFACT_KIND_STRINGS = [
    "builder_ii.session_workflow_plan",
    "builder_ii.goose_readonly_session_plan",
    "builder_ii.verification_profile_report",
    "builder_ii.handoff_note",
    "builder_ii.deepagents_bridge_readiness_report",
]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_platform_release_audit_doc_exists_and_states_boundary():
    doc = _read("docs/BUILDER_PLATFORM_RELEASE_AUDIT.md")

    for phrase in REQUIRED_DOC_PHRASES:
        assert phrase in doc


def test_release_modules_import_without_runtime_activation():
    for module_name in REQUIRED_MODULES:
        importlib.import_module(module_name)


def test_release_artifact_kinds_are_declared_in_source():
    source_paths = [
        "builder_ii/session_workflow.py",
        "builder_ii/goose_readonly_session.py",
        "builder_ii/verification_profile_reports.py",
        "builder_ii/handoff_notes.py",
        "builder_ii/deepagents_bridge_readiness.py",
    ]
    joined = "\n".join(_read(path) for path in source_paths)

    for kind in REQUIRED_ARTIFACT_KIND_STRINGS:
        assert kind in joined


def test_release_artifact_kinds_are_registry_visible():
    registry_sources = (
        _read("builder_ii/artifact_index_records.py") + "\n" + _read("builder_ii/artifact_chain_verification.py")
    )

    expected_registry_tokens = [
        "SESSION_WORKFLOW_PLAN_KIND",
        "GOOSE_READONLY_SESSION_PLAN_KIND",
        "VERIFICATION_PROFILE_REPORT_KIND",
        "HANDOFF_NOTE_KIND",
        "DEEPAGENTS",
    ]

    for token in expected_registry_tokens:
        assert token in registry_sources


def test_reference_carrying_handoff_notes_remain_chain_visible():
    chain_source = _read("builder_ii/artifact_chain_verification.py")

    assert "elif kind == HANDOFF_NOTE_KIND" in chain_source
    assert "session_ref" in chain_source
    assert "goose_readonly_session_ref" in chain_source
    assert "verification_report_ref" in chain_source
    assert "verification_evidence_refs" in chain_source


def test_deepagents_readiness_remains_optional_and_non_executing():
    source = _read("builder_ii/deepagents_bridge_readiness.py")
    doc = _read("docs/DEEPAGENTS_BRIDGE_READINESS.md")
    combined = source + "\n" + doc

    forbidden_runtime_tokens = [
        "subprocess",
        "os.system",
        "Popen",
        "from deepagents",
        "import deepagents",
    ]

    for token in forbidden_runtime_tokens:
        assert token not in source

    required_boundary_phrases = [
        "readiness",
        "runtime authority",
        "shell",
    ]

    for phrase in required_boundary_phrases:
        assert phrase.lower() in combined.lower()

    assert "optional" in combined.lower()
    assert "not required" in combined.lower() or "absent" in combined.lower()


def test_command_surface_audit_covers_registered_scripts():
    pyproject = tomllib.loads(_read("pyproject.toml"))
    scripts = pyproject.get("project", {}).get("scripts", {})
    audit = _read("docs/COMMAND_SURFACE_AUDIT.md")

    missing = sorted(script for script in scripts if script not in audit)
    assert missing == []


def test_release_audit_does_not_claim_core_workbench_identity():
    docs = "\n".join(
        _read(path)
        for path in [
            "docs/BUILDER_PLATFORM_RELEASE_AUDIT.md",
            "docs/PROJECT_OVERVIEW.md",
            "docs/COMMAND_SURFACE_AUDIT.md",
        ]
        if (ROOT / path).exists()
    )

    forbidden_identity_claims = [
        "builder-II is CORE Workbench",
        "builder-II is the CORE UI",
        "builder-II is a CORE runtime",
        "CORE cockpit",
        "CORE runtime cockpit",
    ]

    for phrase in forbidden_identity_claims:
        assert phrase not in docs
