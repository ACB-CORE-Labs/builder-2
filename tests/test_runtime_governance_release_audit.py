import re
from pathlib import Path

DOC = Path("docs/RUNTIME_GOVERNANCE_RELEASE_AUDIT.md")

def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_release_audit_document_exists() -> None:
    assert DOC.exists()


def test_release_audit_claims_generic_platform() -> None:
    text = _text()
    assert "builder-II is a generic governed local agent/developer platform" in text


def test_release_audit_denies_core_runtime_identity() -> None:
    text = _text()
    assert "builder-II is not CORE" in text
    assert "not CORE Workbench/UI" in text
    assert "not a second CORE runtime" in text
    assert "CORE is only a target profile" in text


def test_release_audit_asserts_capabilities_disabled() -> None:
    text = _text().lower()
    assert "shell execution" in text
    assert "model execution" in text
    assert "patch application" in text
    assert "autonomous writes" in text
    assert "goose runtime activation" in text
    assert "deepagents runtime" in text
    assert "rollback execution is not enabled" in text
    assert "voice/tts/stt runtime is not enabled" in text

    # It must state that everything is gated
    assert "docs" in text
    assert "tests" in text
    assert "command surface" in text
    assert "failure mode" in text
    assert "human approval boundary" in text
    assert "output artifact" in text
    assert "rollback path" in text
    assert "verification path" in text


def test_release_audit_covers_all_required_sections() -> None:
    text = _text().lower()
    
    assert "hitl command execution spec" in text
    assert "execution request/receipt artifacts" in text or "execution request" in text
    assert "hitl patch application spec" in text or "patch application" in text
    assert "rollback plan/receipt artifacts" in text or "rollback" in text
    assert "command surface audit" in text
    assert "registry closure" in text
    assert "no-runtime" in text or "no-runtime / no-authority" in text
    assert "future promotion ladder" in text


def test_release_audit_asserts_hitl_command_execution() -> None:
    text = _text()
    assert "docs/HITL_COMMAND_EXECUTION.md" in text
    assert "DESIGN_ONLY" in text


def test_release_audit_asserts_registry_closure() -> None:
    text = _text()
    assert "Registry Closure" in text
    assert "tests/test_registry_closure.py" in text


def test_release_audit_asserts_no_authority() -> None:
    text = _text()
    assert "artifact_is_authority" in text
    assert "core_workbench_coupling" in text
