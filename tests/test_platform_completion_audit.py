from pathlib import Path

DOC = Path("docs/PLATFORM_COMPLETION_AUDIT.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_platform_completion_audit_exists() -> None:
    assert DOC.exists()


def test_generic_first_and_target_profile() -> None:
    text = _text()
    assert "builder-II" in text
    assert "generic-first" in text
    assert "CORE" in text
    assert "target profile" in text
    assert "not CORE Workbench/UI" in text


def test_lists_completed_artifacts() -> None:
    text = _text()
    completed_artifacts = [
        "target profiles",
        "verification profiles",
        "context pack records",
        "agent profile records",
        "explicit git state records",
        "command proposal records",
        "approval records",
        "preflight records",
        "receipt records",
        "handoff bundles",
        "intake records",
        "artifact index",
        "chain verification",
        "promotion readiness",
        "promotion decisions",
        "state ledger",
        "snapshots",
        "research adapters",
        "performance measurements",
        "readonly inspection promotion spec",
        "readonly inspection reports",
        "readonly inspection promotion wiring",
    ]
    for artifact in completed_artifacts:
        assert artifact in text


def test_lists_not_yet_promoted_capabilities() -> None:
    text = _text()
    not_yet_promoted = [
        "shell execution",
        "model execution",
        "patch application",
        "commit/push automation",
        "Goose runtime activation",
        "deepagents runtime",
        "MCP execution",
        "arbitrary repository traversal",
        "content capture",
        "voice/TTS/STT",
        "CORE Workbench/UI coupling",
    ]
    for cap in not_yet_promoted:
        assert cap in text


def test_readonly_inspection_report_only_runtime_candidate() -> None:
    text = _text()
    assert "read-only inspection report" in text
    assert "only current runtime-candidate capability" in text


def test_does_not_claim_active_or_enabled_features() -> None:
    text = _text().lower()
    assert "no autonomous writes" in text
    assert "shell execution is disabled" in text
    assert "model execution is disabled" in text
    assert "deepagents runtime is disabled" in text
    assert "goose runtime is disabled" in text


def test_release_verification_checklist_names_current_commands() -> None:
    text = _text()
    expected_commands = [
        "uv run pytest -q",
        "builder-index validate",
        "builder-chain verify",
        "builder-promotion record",
        "builder-promotion-decision record",
        "builder-state-index validate",
        "builder-snapshot validate",
        "builder-inspect report",
        "builder-inspect validate",
    ]
    for command in expected_commands:
        assert command in text
