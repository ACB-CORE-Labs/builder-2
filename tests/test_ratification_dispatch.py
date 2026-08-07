"""Where the human pause lands for a governed dispatch, and the record that it happened.

The governance claim this file defends is the one that makes grant-aware dispatch honest: a
standing grant relocates the *pause*, never the emission. Auto-ratified work produces the same
artifacts, receipts and events as prompted work, plus the digest of the grant that scheduled it.
If that ever stops being true, the feature has become a way to do less governance rather than the
same governance with the friction where the operator wants it.

Note on "expired": grants have no TTL as built. A grant lives until something invalidates it --
explicit revocation, a policy raise, or the owning command's authority tightening -- so the tests
below express staleness through those channels rather than inventing an expiry the model does not
have.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from builder_ii.governance.ledger.ratification_ledger import (
    EVENT_AUTO_ACCEPTED,
    EVENT_MANUAL_RATIFIED,
    read_ratification_events,
)
from builder_ii.governance.ratification_dispatch import (
    STATUS_APPROVAL_ARTIFACT_REQUIRED,
    STATUS_AUTO,
    STATUS_PROMPT,
    record_auto_ratified,
    record_manual_ratified,
    resolve_dispatch_ratification,
)
from builder_ii.governance.ratification_grants import (
    build_ratification_grant,
    build_ratification_revocation,
    write_grant,
    write_revocation,
)
from builder_ii.governance.ratification_points import get_ratification_point
from builder_ii.governance.ratification_policy import (
    LEVEL_ALWAYS_PROMPT,
    LEVEL_REQUIRE_APPROVAL_ARTIFACT,
    build_ratification_policy,
    write_policy,
)

DISPATCH = "stratum.dispatch.goose_run"
UNGRANTABLE = "hitl.approve_patch.patch_digest"


def _grant(root: Path, point_id: str = DISPATCH, *, granted_by: str = "operator") -> dict[str, Any]:
    point = get_ratification_point(point_id)
    assert point is not None
    grant = build_ratification_grant(point, granted_by=granted_by)
    write_grant(grant, root=root)
    return grant


# --- resolution -------------------------------------------------------------------------


def test_with_no_grant_the_operator_is_asked(tmp_path: Path) -> None:
    resolution = resolve_dispatch_ratification(DISPATCH, root=tmp_path)
    assert resolution.status == STATUS_PROMPT
    assert not resolution.is_auto
    # The reason is surfaced verbatim at the prompt, so it must name a fact.
    assert resolution.because.strip()


def test_with_a_standing_grant_the_dispatch_proceeds(tmp_path: Path) -> None:
    grant = _grant(tmp_path)
    resolution = resolve_dispatch_ratification(DISPATCH, root=tmp_path)

    assert resolution.status == STATUS_AUTO
    assert resolution.is_auto
    # The grant is named, so an auto-ratified action can be traced back to what scheduled it.
    assert resolution.grant_digest == grant["grant_digest"]
    assert resolution.granted_by == "operator"


def test_a_grant_covers_only_its_own_point(tmp_path: Path) -> None:
    _grant(tmp_path, DISPATCH)
    assert resolve_dispatch_ratification("stratum.dispatch.prepare_package", root=tmp_path).status == (
        STATUS_PROMPT
    )


def test_a_revoked_grant_returns_the_prompt(tmp_path: Path) -> None:
    grant = _grant(tmp_path)
    assert resolve_dispatch_ratification(DISPATCH, root=tmp_path).is_auto

    write_revocation(
        build_ratification_revocation(grant, revoked_by="operator", reason="no longer wanted"),
        root=tmp_path,
    )

    resolution = resolve_dispatch_ratification(DISPATCH, root=tmp_path)
    assert resolution.status == STATUS_PROMPT
    assert not resolution.is_auto


def test_a_policy_raise_overrides_a_live_grant(tmp_path: Path) -> None:
    """Tighten-only means policy can subtract a grant's effect but never add one."""
    _grant(tmp_path)
    write_policy(
        build_ratification_policy(levels={DISPATCH: LEVEL_ALWAYS_PROMPT}, set_by="operator"),
        root=tmp_path,
    )

    resolution = resolve_dispatch_ratification(DISPATCH, root=tmp_path)
    assert resolution.status == STATUS_PROMPT


def test_the_strictest_policy_level_refuses_and_names_the_remedy(tmp_path: Path) -> None:
    _grant(tmp_path)
    write_policy(
        build_ratification_policy(
            levels={DISPATCH: LEVEL_REQUIRE_APPROVAL_ARTIFACT}, set_by="operator"
        ),
        root=tmp_path,
    )

    resolution = resolve_dispatch_ratification(DISPATCH, root=tmp_path)
    assert resolution.status == STATUS_APPROVAL_ARTIFACT_REQUIRED
    # A refusal that does not say how to proceed is a dead end.
    assert "builder-govern approve" in resolution.because


def test_grants_disabled_wholesale_returns_every_dispatch_to_the_prompt(tmp_path: Path) -> None:
    _grant(tmp_path)
    write_policy(
        build_ratification_policy(levels={}, set_by="operator", allow_grants=False),
        root=tmp_path,
    )
    assert resolve_dispatch_ratification(DISPATCH, root=tmp_path).status != STATUS_AUTO


def test_an_ungrantable_point_is_never_auto_even_with_a_grant_file_present(tmp_path: Path) -> None:
    """Patch approval is the decision itself; a grant file must not be able to satisfy it."""
    point = get_ratification_point(UNGRANTABLE)
    assert point is not None
    write_grant(build_ratification_grant(point, granted_by="forged"), root=tmp_path)

    resolution = resolve_dispatch_ratification(UNGRANTABLE, root=tmp_path)
    assert resolution.status == STATUS_PROMPT


def test_an_unregistered_point_prompts_rather_than_assuming(tmp_path: Path) -> None:
    """A typo in a point id must not be the thing that skips a confirmation."""
    resolution = resolve_dispatch_ratification("stratum.dispatch.nonexistent", root=tmp_path)
    assert resolution.status == STATUS_PROMPT
    assert "no ratification point" in resolution.because


def test_resolution_writes_nothing(tmp_path: Path) -> None:
    """A console resolves before it decides whether to raise a dialog; that must be a pure read."""
    _grant(tmp_path)
    before = {p for p in tmp_path.rglob("*") if p.is_file()}

    resolve_dispatch_ratification(DISPATCH, root=tmp_path)

    assert {p for p in tmp_path.rglob("*") if p.is_file()} == before


# --- recording --------------------------------------------------------------------------


def test_an_auto_ratified_dispatch_is_ledgered_with_its_grant(tmp_path: Path) -> None:
    grant = _grant(tmp_path)
    resolution = resolve_dispatch_ratification(DISPATCH, root=tmp_path)

    record_auto_ratified(resolution, actor="stratum", root=tmp_path)

    entries = read_ratification_events(tmp_path)
    auto = [e for e in entries if e["event"] == EVENT_AUTO_ACCEPTED]
    assert len(auto) == 1
    assert auto[0]["point_id"] == DISPATCH
    assert auto[0]["grant_digest"] == grant["grant_digest"]
    assert auto[0]["command"] == "builder-goose run-governed"


def test_a_prompted_dispatch_is_ledgered_as_manual(tmp_path: Path) -> None:
    record_manual_ratified(DISPATCH, actor="stratum", because="operator confirmed", root=tmp_path)

    entries = read_ratification_events(tmp_path)
    manual = [e for e in entries if e["event"] == EVENT_MANUAL_RATIFIED]
    assert len(manual) == 1
    assert manual[0]["grant_digest"] in (None, "")


def test_auto_acceptance_cannot_be_recorded_for_a_decision_that_was_not_auto(tmp_path: Path) -> None:
    """`auto_accepted` and `manual_ratified` must keep meaning different things."""
    import pytest

    resolution = resolve_dispatch_ratification(DISPATCH, root=tmp_path)
    assert resolution.status == STATUS_PROMPT

    with pytest.raises(ValueError, match="only an AUTO resolution"):
        record_auto_ratified(resolution, actor="stratum", root=tmp_path)

    assert read_ratification_events(tmp_path) == []


def test_one_dispatch_records_exactly_one_ledger_line(tmp_path: Path) -> None:
    """Double-recording would make the ledger overcount the decisions actually taken."""
    _grant(tmp_path)
    resolution = resolve_dispatch_ratification(DISPATCH, root=tmp_path)

    record_auto_ratified(resolution, actor="stratum", root=tmp_path)

    assert len(read_ratification_events(tmp_path)) == 1


# --- the non-regression invariant --------------------------------------------------------


def test_auto_ratification_relocates_the_pause_and_nothing_else(tmp_path: Path) -> None:
    """The load-bearing claim: granting changes who was asked, not what was recorded.

    Both branches produce a ledger entry naming the same point and command, with the same
    governance framing. The only differences are the event name -- which is the *point* of having
    two -- and the grant digest an auto-acceptance additionally carries, which makes the
    auto-ratified path strictly *more* traceable than the prompted one, never less.
    """
    prompted_root = tmp_path / "prompted"
    granted_root = tmp_path / "granted"
    prompted_root.mkdir()
    granted_root.mkdir()

    prompted = resolve_dispatch_ratification(DISPATCH, root=prompted_root)
    assert prompted.status == STATUS_PROMPT
    record_manual_ratified(DISPATCH, actor="stratum", because=prompted.because, root=prompted_root)

    _grant(granted_root)
    auto = resolve_dispatch_ratification(DISPATCH, root=granted_root)
    assert auto.status == STATUS_AUTO
    record_auto_ratified(auto, actor="stratum", root=granted_root)

    [manual_entry] = read_ratification_events(prompted_root)
    [auto_entry] = read_ratification_events(granted_root)

    # Same decision, same subject, same actor: one ledger line either way.
    assert manual_entry["point_id"] == auto_entry["point_id"] == DISPATCH
    assert manual_entry["command"] == auto_entry["command"] == "builder-goose run-governed"
    assert manual_entry["actor"] == auto_entry["actor"] == "stratum"

    # The differences are exactly the two that should differ.
    assert manual_entry["event"] == EVENT_MANUAL_RATIFIED
    assert auto_entry["event"] == EVENT_AUTO_ACCEPTED
    assert auto_entry["grant_digest"]
    assert not manual_entry.get("grant_digest")

    # Both are chained records with the same shape; neither is a lighter-weight entry.
    assert set(manual_entry) == set(auto_entry)
