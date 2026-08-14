from pathlib import Path


def test_capability_promotion_doc_exists_and_key_artifacts_mentioned() -> None:
    doc_path = Path(__file__).resolve().parent.parent / "docs" / "CAPABILITY_PROMOTION.md"
    assert doc_path.exists(), "docs/CAPABILITY_PROMOTION.md must exist"

    content = doc_path.read_text(encoding="utf-8")

    # Verify key artifacts are mentioned
    key_artifacts = [
        "command authority registry",
        "ConventionKernel platform spine",
        "governed prepare-package",
        "repo map",
        "context pack",
        "artifact index",
        "artifact chain verification",
    ]
    for artifact in key_artifacts:
        assert artifact in content, f"Missing key artifact reference in CAPABILITY_PROMOTION.md: {artifact}"


def test_capability_promotion_doc_includes_required_promotion_states() -> None:
    doc_path = Path(__file__).resolve().parent.parent / "docs" / "CAPABILITY_PROMOTION.md"
    content = doc_path.read_text(encoding="utf-8")

    required_states = [
        "artifact_only",
        "validation_only",
        "operator_managed",
        "hitl_runtime_candidate",
        "forbidden_unpromoted",
    ]
    for state in required_states:
        assert f"`{state}`" in content or state in content, f"Missing required promotion state: {state}"


def test_capability_promotion_doc_avoids_forbidden_identity_framing() -> None:
    doc_path = Path(__file__).resolve().parent.parent / "docs" / "CAPABILITY_PROMOTION.md"
    content = doc_path.read_text(encoding="utf-8")

    assert "CORE builder-II" not in content, "Forbidden global identity framing found: 'CORE builder-II'"
    assert "CORE Workbench is builder-II" not in content, (
        "Forbidden global identity framing found regarding CORE Workbench"
    )


def test_capability_promotion_doc_states_unpromoted_boundaries() -> None:
    doc_path = Path(__file__).resolve().parent.parent / "docs" / "CAPABILITY_PROMOTION.md"
    content = doc_path.read_text(encoding="utf-8")

    assert "Goose runtime start" in content, "Must mention Goose runtime start"
    assert "deepagents active delegation" in content or "Deepagents active delegation" in content, (
        "Must mention deepagents active delegation"
    )
    assert "forbidden_unpromoted" in content, "Must indicate that active runtimes are forbidden/unpromoted"


def test_capability_promotion_doc_covers_goal2_assignment_surface() -> None:
    doc_path = Path(__file__).resolve().parent.parent / "docs" / "CAPABILITY_PROMOTION.md"
    content = doc_path.read_text(encoding="utf-8")

    required_phrases = [
        "Agent assignment and orchestration v2",
        "builder-orchestration render-assignment",
        "orchestration-assignment-dry-run.json",
        "cannot execute models/tools/shell",
        "invoke Goose/deepagents/MCP",
        "digest mismatches",
    ]
    for phrase in required_phrases:
        assert phrase in content, f"Missing Goal 2 capability promotion phrase: {phrase}"
