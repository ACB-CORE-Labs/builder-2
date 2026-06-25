import pytest

from builder_ii.lane_guides import get_guide, guide_names, lane_guides, render_guide


def test_expected_lane_guides_are_registered() -> None:
    assert set(guide_names()) == {
        "audit_invariants",
        "draft_patch_plan",
        "prepare_handoff",
        "probe_model_fit",
        "review_failure",
        "summarize_diff",
    }


def test_every_lane_guide_has_model_and_contract() -> None:
    for guide in lane_guides():
        assert guide.model_alias in {"phi-reasoning", "qwen-coder"}
        assert guide.use_when
        assert guide.output_contract
        assert "{context}" in guide.template


def test_render_guide_injects_context() -> None:
    prompt = render_guide("draft_patch_plan", context="Add a tiny CLI option.")

    assert "Add a tiny CLI option." in prompt
    assert "Files" in prompt
    assert "Tests" in prompt


def test_unknown_guide_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="unknown lane guide"):
        get_guide("missing")
