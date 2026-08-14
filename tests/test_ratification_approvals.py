"""Pins for ratification approvals: subject binding, expiry, and non-transferability.

An approval is the strictest satisfier in the lane, so the tests here are mostly about what it
must *refuse*: a different point, a different subject, a stale clock, and a missing file.
"""

from __future__ import annotations

import json
from pathlib import Path

from builder_ii.governance.ratification_approvals import (
    RATIFICATION_APPROVAL_KIND,
    build_ratification_approval,
    check_ratification_approval,
    validate_ratification_approval_artifact,
    validate_ratification_approval_file,
    write_ratification_approval,
)
from builder_ii.governance.ratification_points import get_ratification_point

POINT = "setup.apply.overlay_digest"
OTHER_POINT = "setup.rollback.receipt_digest"
SUBJECT = "a" * 64
OTHER_SUBJECT = "b" * 64


def _point(point_id: str = POINT):
    point = get_ratification_point(point_id)
    assert point is not None
    return point


def _write(tmp_path: Path, **kwargs) -> Path:
    defaults = {
        "subject_digest": SUBJECT,
        "approved_by": "op",
        "confirmed_digest_prefix": SUBJECT[:4],
        "approved_at": 1_000_000,
    }
    defaults.update(kwargs)
    point = defaults.pop("point", _point())
    artifact = build_ratification_approval(point, **defaults)
    return write_ratification_approval(artifact, tmp_path / "approval.json")


def test_a_well_formed_approval_validates_and_is_accepted(tmp_path: Path) -> None:
    path = _write(tmp_path)
    assert validate_ratification_approval_file(path) == []
    check = check_ratification_approval(path, point_id=POINT, subject_digest=SUBJECT, now=1_000_100)
    assert check.accepted
    assert check.approved_by == "op"


def test_a_missing_path_is_a_refusal_that_says_so() -> None:
    check = check_ratification_approval(None, point_id=POINT, subject_digest=SUBJECT)
    assert not check.accepted
    assert "none was supplied" in check.because


def test_an_approval_never_transfers_to_another_point(tmp_path: Path) -> None:
    path = _write(tmp_path)
    check = check_ratification_approval(path, point_id=OTHER_POINT, subject_digest=SUBJECT, now=1_000_100)
    assert not check.accepted
    assert "never transfers between points" in check.because


def test_an_approval_never_authorises_a_different_subject(tmp_path: Path) -> None:
    """The binding that matters: approving one overlay plan cannot approve a different one."""
    path = _write(tmp_path)
    check = check_ratification_approval(path, point_id=POINT, subject_digest=OTHER_SUBJECT, now=1_000_100)
    assert not check.accepted
    assert "binds subject digest" in check.because


def test_an_expired_approval_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path, ttl_seconds=60)
    assert check_ratification_approval(path, point_id=POINT, subject_digest=SUBJECT, now=1_000_030).accepted
    stale = check_ratification_approval(path, point_id=POINT, subject_digest=SUBJECT, now=1_000_061)
    assert not stale.accepted
    assert "expired" in stale.because


def test_expiry_is_a_property_of_the_use_not_of_the_artifact(tmp_path: Path) -> None:
    """A stale approval is still structurally valid; conflating the two would misreport it."""
    path = _write(tmp_path, ttl_seconds=60)
    assert validate_ratification_approval_file(path) == []
    assert not check_ratification_approval(path, point_id=POINT, subject_digest=SUBJECT, now=9_999_999).accepted


def test_a_tampered_approval_is_refused(tmp_path: Path) -> None:
    path = _write(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["approved_by"] = "someone-else"
    path.write_text(json.dumps(payload), encoding="utf-8")

    check = check_ratification_approval(path, point_id=POINT, subject_digest=SUBJECT, now=1_000_100)
    assert not check.accepted
    assert "invalid" in check.because


def test_approval_shape_and_governance() -> None:
    artifact = build_ratification_approval(
        _point(), subject_digest=SUBJECT, approved_by="op", confirmed_digest_prefix=SUBJECT[:4]
    )
    assert artifact["kind"] == RATIFICATION_APPROVAL_KIND
    assert artifact["governance"]["originates_approval"] is True
    assert artifact["confirmation"]["method"] == "digest_prefix"
    assert validate_ratification_approval_artifact(artifact) == []


def test_expiry_must_follow_approval_time() -> None:
    artifact = build_ratification_approval(
        _point(), subject_digest=SUBJECT, approved_by="op", confirmed_digest_prefix=SUBJECT[:4]
    )
    artifact["expires_at"] = artifact["approved_at"]
    assert any("expires_at must be after approved_at" in error for error in validate_ratification_approval_artifact(artifact))


def test_booleans_are_not_accepted_as_timestamps() -> None:
    artifact = build_ratification_approval(
        _point(), subject_digest=SUBJECT, approved_by="op", confirmed_digest_prefix=SUBJECT[:4]
    )
    artifact["approved_at"] = True
    assert any("approved_at must be an integer" in error for error in validate_ratification_approval_artifact(artifact))


def test_an_unreadable_file_reports_rather_than_raises(tmp_path: Path) -> None:
    errors = validate_ratification_approval_file(tmp_path / "absent.json")
    assert errors and "unreadable" in errors[0]
