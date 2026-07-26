"""Pins for the ratification-point registry -- the boundary a standing grant may never cross.

Every test here is grounded in the live command-authority registry rather than a fixture, so a
future authority change that would quietly make an ungrantable confirmation grantable fails in
this file first, by name.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from builder_ii.governance.authority import (
    CAPABILITY_FLAGS,
    MODE_HITL_ARTIFACT_REQUIRED,
    get_command_record,
)
from builder_ii.governance.ratification_points import (
    GRANTABLE_CAPABILITY_ALLOWLIST,
    GRANTABLE_KINDS,
    KIND_HUMAN_APPROVAL_MINT,
    KIND_PLAN_DIGEST_CONFIRMATION,
    KIND_PROMOTION_DECISION,
    RATIFICATION_KINDS,
    RATIFICATION_POINTS,
    RatificationPoint,
    get_ratification_point,
    grant_eligibility,
    grantable_point_ids,
    validate_ratification_point_registry,
)


def test_the_point_registry_is_structurally_valid() -> None:
    assert validate_ratification_point_registry() == []


def test_only_plan_digest_confirmation_is_ever_grantable() -> None:
    """The closed enum is the first of the two guards; widening it must be a deliberate edit here."""
    assert GRANTABLE_KINDS == (KIND_PLAN_DIGEST_CONFIRMATION,)
    assert set(GRANTABLE_KINDS) <= set(RATIFICATION_KINDS)


def test_no_hitl_confirmation_is_grantable() -> None:
    """The class-of-danger guard: minting human approval can never be delegated to a grant."""
    hitl_points = [point for point in RATIFICATION_POINTS if point.command.startswith("builder-hitl ")]
    assert hitl_points, "the HITL points must stay registered, so their refusal is pinned rather than assumed"
    for point in hitl_points:
        decision = grant_eligibility(point)
        assert not decision.eligible, f"{point.id} must never be grantable"
        assert point.kind in (KIND_HUMAN_APPROVAL_MINT, KIND_PROMOTION_DECISION)


def test_approve_patch_is_registered_and_refused_rather_than_merely_absent() -> None:
    """`builder-hitl approve-patch` carries approval_mode `none`, so absence would refuse by luck.

    Deriving eligibility from the approval mode alone would have made patch approval grantable --
    the command needs no approval *to run*, because running it is how an approval gets made. This
    test is the record of that near-miss.
    """
    point = get_ratification_point("hitl.approve_patch.patch_digest")
    assert point is not None
    record = get_command_record(point.command)
    assert record is not None
    assert record.approval_mode not in (MODE_HITL_ARTIFACT_REQUIRED,), (
        "if this changes, the approval-mode check would now catch it -- but the kind guard is what does"
    )
    assert not grant_eligibility(point).eligible


def test_the_two_setup_digest_confirmations_are_grantable_today() -> None:
    """The feature is inert unless something is actually delegable; these are the two that are."""
    assert set(grantable_point_ids()) == {
        "setup.apply.overlay_digest",
        "setup.rollback.receipt_digest",
    }


def _flags_outside_the_allowlist_with_a_live_carrier() -> list[tuple[str, str]]:
    """Every out-of-allowlist capability paired with a real command that carries it.

    Derived rather than hardcoded: `allows_shell_execution` and `allows_memory_mutation` currently
    have no carrier at all, so naming one would have pinned nothing. Promoting a command into
    either of them adds a case here automatically.
    """
    from builder_ii.governance.authority import COMMAND_AUTHORITY_REGISTRY

    pairs: list[tuple[str, str]] = []
    for flag in sorted(set(CAPABILITY_FLAGS) - GRANTABLE_CAPABILITY_ALLOWLIST):
        carrier = next((record.name for record in COMMAND_AUTHORITY_REGISTRY if getattr(record, flag, False)), None)
        if carrier is not None:
            pairs.append((flag, carrier))
    return pairs


def test_the_allowlist_is_a_strict_subset_of_the_capability_flags() -> None:
    assert GRANTABLE_CAPABILITY_ALLOWLIST < set(CAPABILITY_FLAGS)


@pytest.mark.parametrize(("flag", "command"), _flags_outside_the_allowlist_with_a_live_carrier())
def test_a_capability_outside_the_allowlist_makes_a_point_ineligible(flag: str, command: str) -> None:
    """The second guard, checked independently of the declared kind.

    The synthetic point below declares the *grantable* kind, so the only thing that can refuse it
    is the capability check -- which is exactly what this asserts.
    """
    point = RatificationPoint(
        id=f"synthetic.{flag}",
        command=command,
        kind=KIND_PLAN_DIGEST_CONFIRMATION,
        what_is_ratified="synthetic",
        consequence_of_auto="synthetic",
    )
    decision = grant_eligibility(point)
    assert not decision.eligible, f"`{command}` carries `{flag}` and must not be delegable"
    assert "outside the grantable capability set" in decision.because


def test_an_unregistered_command_is_ineligible_not_permissive() -> None:
    point = RatificationPoint(
        id="synthetic.unknown",
        command="builder-totally-fictitious-xyz",
        kind=KIND_PLAN_DIGEST_CONFIRMATION,
        what_is_ratified="synthetic",
        consequence_of_auto="synthetic",
    )
    decision = grant_eligibility(point)
    assert not decision.eligible
    assert "no command-authority record" in decision.because


def test_eligibility_is_recomputed_not_declared() -> None:
    """A point cannot carry its own answer: changing the kind changes the verdict immediately."""
    point = get_ratification_point("setup.apply.overlay_digest")
    assert point is not None
    assert grant_eligibility(point).eligible
    assert not grant_eligibility(replace(point, kind=KIND_HUMAN_APPROVAL_MINT)).eligible


@pytest.mark.parametrize("point", RATIFICATION_POINTS, ids=lambda point: point.id)
def test_every_point_states_what_it_costs_to_delegate(point: RatificationPoint) -> None:
    """A point that cannot say what granting it costs has no business offering the grant."""
    assert point.what_is_ratified.strip()
    assert point.consequence_of_auto.strip()
    assert grant_eligibility(point).because.strip()
