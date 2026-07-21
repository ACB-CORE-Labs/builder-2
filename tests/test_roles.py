import pytest

from builder_ii.governance.authority.roles import builder_roles, get_role, role_names, validate_roles
from builder_ii.lifecycle.setup.lane_guides import guide_names


def test_expected_roles_are_registered() -> None:
    assert set(role_names()) == {
        "diff_summarizer",
        "failure_reviewer",
        "handoff_scribe",
        "invariant_auditor",
        "lane_router",
        "patch_planner",
    }


def test_roles_reference_known_lane_guides() -> None:
    known_guides = set(guide_names())

    for role in builder_roles():
        assert role.lane_guides
        assert set(role.lane_guides) <= known_guides


def test_roles_stay_on_validated_default_model_aliases() -> None:
    for role in builder_roles():
        assert role.model_alias in {"phi-reasoning", "qwen-coder"}


def test_roles_have_authority_boundaries_and_output_contracts() -> None:
    for role in builder_roles():
        assert role.purpose
        assert role.authority
        assert role.forbidden
        assert role.escalation
        assert role.output_contract


def test_validate_roles_is_clean() -> None:
    assert validate_roles() == ()


def test_unknown_role_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="unknown role"):
        get_role("missing")
