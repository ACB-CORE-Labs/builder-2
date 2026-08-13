from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "plan" / "OPEN_SOURCE_V1_COMPLETION_PLAN.md"


def test_superseded_execution_candidate_plan_is_explicitly_disposed() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "docs/plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md" in text
    assert not (ROOT / "docs/plan/PASSIVE_EXECUTION_CANDIDATE_MANIFEST_RFC.md").exists()
    assert (ROOT / "docs/HITL_VERIFICATION_CANDIDATE.md").exists()


def test_current_candidate_surface_remains_non_authoritative() -> None:
    text = (ROOT / "docs/HITL_VERIFICATION_CANDIDATE.md").read_text(encoding="utf-8").lower()
    assert "candidate" in text
    assert "authority" in text


def test_roadmap_lists_current_candidate_surface_without_activation() -> None:
    text = (ROOT / "docs/ROADMAP.md").read_text(encoding="utf-8")
    assert "docs/HITL_VERIFICATION_CANDIDATE.md" in text
    assert "not runtime activation" in text.lower()
