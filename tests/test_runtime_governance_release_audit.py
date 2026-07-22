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


def test_release_audit_covers_completed_foundation_surfaces() -> None:
    text = _text()
    required = [
        "HITL command execution spec",
        "HITL execution request/receipt artifacts",
        "HITL execution artifact CLI",
        "HITL patch application spec",
        "Rollback plan/receipt artifacts",
        "execution postflight and verification record specs",
        "Command surface audit",
        "Registry closure",
        "builder_ii/governance/hitl/hitl_execution_records.py",
        "builder_ii/hitl_execution_cli.py",
        "builder_ii/governance/hitl/hitl_patch_proposal.py",
        "builder_ii/lifecycle/candidate/rollback_artifacts.py",
        "builder_ii/lifecycle/candidate/execution_postflight_records.py",
        "builder_ii/governance/hitl/hitl_evidence_bundle.py",
        "docs/HITL_EVIDENCE_BUNDLE.md",
        "tests/test_hitl_evidence_bundle.py",
        "docs/COMMAND_SURFACE_AUDIT.md",
        "docs/ARTIFACT_INDEX.md",
    ]
    for item in required:
        assert item in text


def test_release_audit_lists_runtime_governance_artifact_kinds() -> None:
    text = _text()
    for kind in (
        "builder_ii.hitl_execution_request",
        "builder_ii.hitl_execution_receipt",
        "builder_ii.hitl_patch_proposal",
        "builder_ii.rollback_plan",
        "builder_ii.rollback_receipt",
        "builder_ii.execution_postflight_record",
        "builder_ii.execution_verification_record",
        "builder_ii.hitl_evidence_bundle",
        "builder_ii.session_workflow_plan",
    ):
        assert kind in text


def test_release_audit_asserts_capabilities_disabled() -> None:
    text = _text().lower()
    required = [
        "shell execution",
        "command execution",
        "model execution",
        "patch application",
        "autonomous writes",
        "source writes",
        "git mutation",
        "commit/push automation",
        "network/mcp execution",
        "goose runtime activation",
        "deepagents runtime",
        "rollback execution",
        "voice/tts/stt runtime",
    ]
    for item in required:
        assert item in text
    assert "not enabled" in text


def test_release_audit_asserts_no_authority() -> None:
    text = _text()
    assert "Artifact validity does not grant runtime authority." in text
    assert "artifact_is_authority" in text
    assert "core_workbench_coupling" in text
    assert "No runtime capability is promoted to `enabled`." in text


def test_release_audit_asserts_all_promotion_gates() -> None:
    text = _text().lower()
    for gate in (
        "docs",
        "tests",
        "command surface",
        "failure mode",
        "human approval boundary",
        "output artifact",
        "rollback path",
        "verification path",
    ):
        assert gate in text


def test_release_audit_names_next_safe_work_and_blocks_executor() -> None:
    text = _text()
    assert "HITL execution artifact CLI without execution" in text
    assert "execution postflight and verification record specs" in text
    assert "bounded HITL command executor" in text
    assert "must not start" in text


def test_release_audit_includes_verification_commands() -> None:
    text = _text()
    assert (
        "CORE_REPO_PATH=. uv run pytest tests/test_hitl_evidence_bundle.py tests/test_registry_closure.py tests/test_artifact_index_records.py tests/test_artifact_chain_verification.py tests/test_runtime_governance_release_audit.py -q"
        in text
    )
    assert "CORE_REPO_PATH=. uv run pytest -q" in text
    assert "git diff --check" in text
