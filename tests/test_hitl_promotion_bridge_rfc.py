from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / "docs" / "plan" / "OPEN_SOURCE_V1_COMPLETION_PLAN.md"


def test_superseded_hitl_promotion_plan_is_explicitly_disposed() -> None:
    text = PLAN.read_text(encoding="utf-8")
    assert "docs/plan/PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md" in text
    assert "obsolete, shipped, superseded, or deferred plan documents" in text
    assert not (ROOT / "docs/plan/PASSIVE_HITL_PROMOTION_BRIDGE_RFC.md").exists()
    assert (ROOT / "docs/HITL_PROMOTION_ARTIFACTS.md").exists()


def test_current_hitl_promotion_surface_preserves_passive_boundary() -> None:
    text = (ROOT / "docs/HITL_PROMOTION_ARTIFACTS.md").read_text(encoding="utf-8").lower()
    assert "approval" in text
    assert "execution" in text
