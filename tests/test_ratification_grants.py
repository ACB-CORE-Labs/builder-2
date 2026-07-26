"""Pins for standing ratification grants: digest binding, revocation, and consult-time eligibility.

The load-bearing test in this file is
:func:`test_a_grant_claiming_eligibility_it_never_had_still_does_not_satisfy` -- everything else
guards the ordinary paths, but that one pins the property the whole design rests on: what the
artifact claims about its own eligibility is never what gets read.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder_ii.governance.ratification_grants import (
    RATIFICATION_GRANT_KIND,
    RATIFICATION_ROOT_ENV,
    build_ratification_grant,
    build_ratification_revocation,
    consult_ratification_grant,
    grants_dir,
    resolve_ratification_root,
    validate_ratification_grant_artifact,
    validate_ratification_grant_file,
    validate_ratification_revocation_artifact,
    write_grant,
    write_revocation,
)
from builder_ii.governance.ratification_points import get_ratification_point

GRANTABLE = "setup.apply.overlay_digest"
UNGRANTABLE = "hitl.approve_patch.patch_digest"


def _point(point_id: str = GRANTABLE):
    point = get_ratification_point(point_id)
    assert point is not None
    return point


def test_a_fresh_store_satisfies_nothing(tmp_path: Path) -> None:
    """Absence is never an implicit grant, and the reason says which fact decided it."""
    consultation = consult_ratification_grant(GRANTABLE, root=tmp_path)
    assert not consultation.satisfied
    assert "no valid unrevoked standing grant" in consultation.because


def test_a_written_grant_satisfies_its_own_point_only(tmp_path: Path) -> None:
    write_grant(build_ratification_grant(_point(), granted_by="op"), root=tmp_path)
    assert consult_ratification_grant(GRANTABLE, root=tmp_path).satisfied
    assert not consult_ratification_grant("setup.rollback.receipt_digest", root=tmp_path).satisfied


def test_an_ungrantable_point_is_refused_even_with_a_grant_file_present(tmp_path: Path) -> None:
    """Hand-writing a grant file for a HITL confirmation must buy nothing at all."""
    forged = build_ratification_grant(_point(UNGRANTABLE), granted_by="attacker")
    write_grant(forged, root=tmp_path)

    consultation = consult_ratification_grant(UNGRANTABLE, root=tmp_path)
    assert not consultation.satisfied
    assert "not grant-eligible" in consultation.because


def test_a_grant_claiming_eligibility_it_never_had_still_does_not_satisfy(tmp_path: Path) -> None:
    """`eligibility_at_grant` is a recorded receipt, never the thing consulted.

    This is the property that makes the recorded block safe to keep: an edited grant that asserts
    it was eligible is consulted against the live registry anyway, and refused there.
    """
    forged = build_ratification_grant(_point(UNGRANTABLE), granted_by="attacker")
    forged["eligibility_at_grant"] = {"eligible": True, "because": "trust me"}
    # Re-digest so the artifact is internally consistent: the tampering must be defeated by the
    # design, not merely by a digest mismatch.
    from builder_ii.core.config_schema import attach_digest

    forged.pop("grant_digest")
    forged = attach_digest(forged, digest_key="grant_digest")
    assert validate_ratification_grant_artifact(forged) == [], "the forged artifact is internally valid"

    write_grant(forged, root=tmp_path)
    assert not consult_ratification_grant(UNGRANTABLE, root=tmp_path).satisfied


def test_a_tampered_grant_fails_validation_and_is_ignored(tmp_path: Path) -> None:
    grant = build_ratification_grant(_point(), granted_by="op")
    path = write_grant(grant, root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["granted_by"] = "someone-else"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_ratification_grant_file(path) == ["grant_digest does not match artifact content"]
    assert not consult_ratification_grant(GRANTABLE, root=tmp_path).satisfied


def test_revocation_stops_a_grant_and_keeps_the_grant_file(tmp_path: Path) -> None:
    grant = build_ratification_grant(_point(), granted_by="op")
    grant_path = write_grant(grant, root=tmp_path)
    assert consult_ratification_grant(GRANTABLE, root=tmp_path).satisfied

    write_revocation(
        build_ratification_revocation(grant, revoked_by="op", reason="rotating"),
        root=tmp_path,
    )
    assert not consult_ratification_grant(GRANTABLE, root=tmp_path).satisfied
    assert grant_path.exists(), "revocation is additive; the history of what was delegated stays readable"


def test_a_tampered_revocation_does_not_revoke(tmp_path: Path) -> None:
    """A revocation must be as digest-bound as the grant it withdraws, in both directions."""
    grant = build_ratification_grant(_point(), granted_by="op")
    write_grant(grant, root=tmp_path)
    revocation = build_ratification_revocation(grant, revoked_by="op", reason="rotating")
    path = write_revocation(revocation, root=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["reason"] = "edited after the fact"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert validate_ratification_revocation_artifact(payload)
    assert consult_ratification_grant(GRANTABLE, root=tmp_path).satisfied


def test_the_newest_grant_wins_when_several_are_on_file(tmp_path: Path) -> None:
    write_grant(build_ratification_grant(_point(), granted_by="first", created_at="2020-01-01T00:00:00+00:00"), root=tmp_path)
    newest = build_ratification_grant(_point(), granted_by="second", created_at="2030-01-01T00:00:00+00:00")
    write_grant(newest, root=tmp_path)

    consultation = consult_ratification_grant(GRANTABLE, root=tmp_path)
    assert consultation.satisfied
    assert consultation.granted_by == "second"


def test_an_unregistered_point_is_reported_not_silently_unsatisfied(tmp_path: Path) -> None:
    consultation = consult_ratification_grant("nope.not.a.point", root=tmp_path)
    assert not consultation.satisfied
    assert "no ratification point is registered" in consultation.because


def test_grant_artifact_shape(tmp_path: Path) -> None:
    grant = build_ratification_grant(_point(), granted_by="op")
    assert grant["kind"] == RATIFICATION_GRANT_KIND
    assert grant["governance"]["artifact_is_authority"] is False
    assert grant["governance"]["originates_approval"] is False
    assert validate_ratification_grant_artifact(grant) == []


def test_a_grant_for_an_unregistered_point_fails_validation() -> None:
    grant = build_ratification_grant(_point(), granted_by="op")
    grant["point_id"] = "nope.not.a.point"
    assert any("no ratification point registered" in error for error in validate_ratification_grant_artifact(grant))


def test_the_store_root_resolves_from_argument_then_env_then_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(RATIFICATION_ROOT_ENV, raising=False)
    assert resolve_ratification_root(None) == Path(".builder") / "artifacts" / "ratification"
    monkeypatch.setenv(RATIFICATION_ROOT_ENV, str(tmp_path / "from-env"))
    assert resolve_ratification_root(None) == tmp_path / "from-env"
    assert resolve_ratification_root(tmp_path / "explicit") == tmp_path / "explicit"
    assert grants_dir(tmp_path) == tmp_path / "grants"
