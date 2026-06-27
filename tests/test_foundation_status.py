from pathlib import Path


DOC = Path("docs/FOUNDATION_STATUS.md")


def _text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_foundation_status_doc_exists() -> None:
    assert DOC.exists()


def test_foundation_status_declares_generic_platform_identity() -> None:
    text = _text()

    assert "builder-II is a generic governed local agent/developer platform" in text
    assert "CORE is a target profile" in text


def test_foundation_status_covers_landed_concepts() -> None:
    text = _text()

    for phrase in (
        "operator playbook",
        "target profiles",
        "verification profiles",
        "context packs",
        "agent profiles",
        "git state records",
        "promotion records",
        "artifact index records",
        "state ledger records",
        "snapshots",
        "research adapters",
        "performance records",
        "inspection design gate",
    ):
        assert phrase in text


def test_foundation_status_avoids_forbidden_platform_language() -> None:
    text = _text().lower()

    forbidden = (
        "core cockpit",
        "core ui cockpit",
        "core runtime cockpit",
        "builder-ii is core",
        "builder-ii is the core workbench",
    )
    for phrase in forbidden:
        assert phrase not in text


def test_foundation_status_names_next_phase_as_reviewed_capability_work() -> None:
    text = _text()

    assert "The artifact-first foundation is complete" in text
    assert "carefully reviewed capability work" in text
