"""Pins for ratification policy -- the tighten-only half of the ratification lane.

The load-bearing property is that a policy **cannot** loosen, and the tests assert it twice over
because the design defends it twice: validation reports the attempt, and `effective_level` takes
`max(baseline, declared)` so the attempt could not take effect even if validation never ran.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder_ii.governance.ratification_grants import (
    build_ratification_grant,
    consult_ratification_grant,
    write_grant,
)
from builder_ii.governance.ratification_points import RATIFICATION_POINTS, get_ratification_point
from builder_ii.governance.ratification_policy import (
    LEVEL_ALWAYS_PROMPT,
    LEVEL_DELEGABLE,
    LEVEL_REQUIRE_APPROVAL_ARTIFACT,
    POLICY_LEVELS,
    RATIFICATION_POLICY_KIND,
    baseline_level,
    build_ratification_policy,
    effective_level,
    level_rank,
    load_policy,
    stricter_of,
    validate_ratification_policy_artifact,
    write_policy,
)

GRANTABLE = "setup.apply.overlay_digest"
UNGRANTABLE = "hitl.approve_patch.patch_digest"


def _point(point_id: str):
    point = get_ratification_point(point_id)
    assert point is not None
    return point


def test_the_ladder_is_ordered_weakest_first() -> None:
    assert POLICY_LEVELS == (LEVEL_DELEGABLE, LEVEL_ALWAYS_PROMPT, LEVEL_REQUIRE_APPROVAL_ARTIFACT)
    assert level_rank(LEVEL_DELEGABLE) < level_rank(LEVEL_ALWAYS_PROMPT) < level_rank(
        LEVEL_REQUIRE_APPROVAL_ARTIFACT
    )


def test_an_unknown_level_ranks_strictest_so_a_typo_fails_closed() -> None:
    assert level_rank("typo") > level_rank(LEVEL_REQUIRE_APPROVAL_ARTIFACT)
    assert stricter_of(LEVEL_DELEGABLE, "typo") == "typo"


def test_baselines_come_from_the_registry_not_from_policy() -> None:
    assert baseline_level(_point(GRANTABLE)) == LEVEL_DELEGABLE
    assert baseline_level(_point(UNGRANTABLE)) == LEVEL_ALWAYS_PROMPT


def test_no_policy_means_baseline(tmp_path: Path) -> None:
    decision = effective_level(GRANTABLE, root=tmp_path)
    assert decision.level == LEVEL_DELEGABLE
    assert "registry baseline" in decision.because


def test_policy_can_tighten_a_grantable_point(tmp_path: Path) -> None:
    write_policy(build_ratification_policy({GRANTABLE: LEVEL_ALWAYS_PROMPT}, set_by="op"), root=tmp_path)
    assert effective_level(GRANTABLE, root=tmp_path).level == LEVEL_ALWAYS_PROMPT


def test_policy_can_tighten_an_already_ungrantable_point_further(tmp_path: Path) -> None:
    """Level 1 -> 2 is the useful direction for a point that was never delegable."""
    policy = build_ratification_policy({UNGRANTABLE: LEVEL_REQUIRE_APPROVAL_ARTIFACT}, set_by="op")
    assert validate_ratification_policy_artifact(policy) == []
    write_policy(policy, root=tmp_path)
    assert effective_level(UNGRANTABLE, root=tmp_path).level == LEVEL_REQUIRE_APPROVAL_ARTIFACT


def test_validation_reports_an_attempt_to_loosen() -> None:
    policy = build_ratification_policy({UNGRANTABLE: LEVEL_DELEGABLE}, set_by="attacker")
    errors = validate_ratification_policy_artifact(policy)
    assert any("may only tighten" in error for error in errors)


def test_a_loosening_policy_cannot_take_effect_even_unvalidated(tmp_path: Path) -> None:
    """The safety must not depend on validation having been run.

    Writing the artifact straight to disk skips every check `policy-set` would have made. The
    effective level must still be the baseline, because `effective_level` takes the stricter of
    the two rather than trusting the file.
    """
    policy = build_ratification_policy({UNGRANTABLE: LEVEL_DELEGABLE}, set_by="attacker")
    write_policy(policy, root=tmp_path)
    assert effective_level(UNGRANTABLE, root=tmp_path).level == LEVEL_ALWAYS_PROMPT


def test_a_loosening_policy_cannot_resurrect_a_refused_grant(tmp_path: Path) -> None:
    """End to end: forged grant plus forged policy for a HITL point still satisfies nothing."""
    write_grant(build_ratification_grant(_point(UNGRANTABLE), granted_by="attacker"), root=tmp_path)
    write_policy(build_ratification_policy({UNGRANTABLE: LEVEL_DELEGABLE}, set_by="attacker"), root=tmp_path)
    assert not consult_ratification_grant(UNGRANTABLE, root=tmp_path).satisfied


def test_the_kill_switch_raises_every_point_at_once(tmp_path: Path) -> None:
    write_grant(build_ratification_grant(_point(GRANTABLE), granted_by="op"), root=tmp_path)
    assert consult_ratification_grant(GRANTABLE, root=tmp_path).satisfied

    write_policy(build_ratification_policy({}, set_by="op", allow_grants=False), root=tmp_path)
    decision = effective_level(GRANTABLE, root=tmp_path)
    assert decision.level == LEVEL_ALWAYS_PROMPT
    assert "allow_grants" in decision.because
    assert not consult_ratification_grant(GRANTABLE, root=tmp_path).satisfied


def test_a_stricter_per_point_level_wins_over_the_kill_switch(tmp_path: Path) -> None:
    """Both raise; the stricter must survive, not the last one applied."""
    write_policy(
        build_ratification_policy(
            {GRANTABLE: LEVEL_REQUIRE_APPROVAL_ARTIFACT}, set_by="op", allow_grants=False
        ),
        root=tmp_path,
    )
    assert effective_level(GRANTABLE, root=tmp_path).level == LEVEL_REQUIRE_APPROVAL_ARTIFACT


def test_an_unregistered_point_fails_closed(tmp_path: Path) -> None:
    decision = effective_level("nope.not.a.point", root=tmp_path)
    assert decision.level == LEVEL_REQUIRE_APPROVAL_ARTIFACT
    assert "failing closed" in decision.because


def test_a_corrupt_policy_file_is_ignored_and_cannot_loosen(tmp_path: Path) -> None:
    (tmp_path / "policy.json").write_text("{not json", encoding="utf-8")
    assert load_policy(root=tmp_path) is None
    assert effective_level(GRANTABLE, root=tmp_path).level == LEVEL_DELEGABLE
    assert effective_level(UNGRANTABLE, root=tmp_path).level == LEVEL_ALWAYS_PROMPT


def test_policy_artifact_shape_and_digest() -> None:
    policy = build_ratification_policy({GRANTABLE: LEVEL_ALWAYS_PROMPT}, set_by="op")
    assert policy["kind"] == RATIFICATION_POLICY_KIND
    assert policy["governance"]["can_loosen"] is False
    assert validate_ratification_policy_artifact(policy) == []


def test_a_tampered_policy_fails_validation(tmp_path: Path) -> None:
    policy = build_ratification_policy({GRANTABLE: LEVEL_ALWAYS_PROMPT}, set_by="op")
    path = write_policy(policy, root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["set_by"] = "someone-else"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert "policy_digest does not match artifact content" in validate_ratification_policy_artifact(payload)


def test_an_unregistered_point_in_a_policy_is_an_error() -> None:
    policy = build_ratification_policy({"nope.not.a.point": LEVEL_ALWAYS_PROMPT}, set_by="op")
    assert any("no ratification point is registered" in error for error in validate_ratification_policy_artifact(policy))


def test_an_unknown_level_in_a_policy_is_an_error() -> None:
    policy = build_ratification_policy({GRANTABLE: "super_strict"}, set_by="op")
    assert any("unknown level" in error for error in validate_ratification_policy_artifact(policy))


@pytest.mark.parametrize("point", RATIFICATION_POINTS, ids=lambda point: point.id)
def test_no_policy_can_lower_any_point_below_its_baseline(point, tmp_path: Path) -> None:
    """Swept over every registered point and every level, in one place.

    A future point added with a stricter baseline is covered the moment it is registered.
    """
    baseline = baseline_level(point)
    for level in POLICY_LEVELS:
        write_policy(build_ratification_policy({point.id: level}, set_by="op"), root=tmp_path)
        effective = effective_level(point.id, root=tmp_path).level
        assert level_rank(effective) >= level_rank(baseline), (
            f"{point.id}: policy {level!r} produced {effective!r}, weaker than baseline {baseline!r}"
        )
