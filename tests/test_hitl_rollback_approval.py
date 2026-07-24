from __future__ import annotations

from pathlib import Path

from builder_ii.governance.hitl.hitl_rollback_approval import (
    HITL_ROLLBACK_APPROVAL_KIND,
    approval_is_expired,
    canonical_digest,
    create_hitl_rollback_approval,
    rollback_approval_binding_errors,
    validate_hitl_rollback_approval,
    validate_hitl_rollback_approval_file,
    write_hitl_rollback_approval,
)


def _plan() -> dict:
    return {
        "kind": "builder_ii.rollback_plan",
        "target": {"name": "generic", "repo": "/tmp/target", "description": "d"},
        "patch_digest": "a" * 64,
        "pre_head": "b" * 40,
        "post_apply_worktree_digest": "c" * 64,
    }


def test_valid_rollback_approval_validates() -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(plan, confirmed_digest_prefix=canonical_digest(plan)[:4])
    assert approval["kind"] == HITL_ROLLBACK_APPROVAL_KIND
    assert approval["schema_version"] == 1
    assert approval["artifact_is_authority"] is False
    assert approval["rollback_plan_digest"] == canonical_digest(plan)
    assert approval["patch_digest"] == "a" * 64
    assert validate_hitl_rollback_approval(approval) == []


def test_binding_holds_for_matching_plan() -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(plan, confirmed_digest_prefix=canonical_digest(plan)[:4])
    assert (
        rollback_approval_binding_errors(
            approval, rollback_plan_digest=canonical_digest(plan), patch_digest="a" * 64
        )
        == []
    )


def test_binding_fails_for_tampered_plan() -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(plan, confirmed_digest_prefix=canonical_digest(plan)[:4])
    tampered = dict(plan)
    tampered["pre_head"] = "0" * 40  # any change re-digests the plan
    errors = rollback_approval_binding_errors(
        approval, rollback_plan_digest=canonical_digest(tampered), patch_digest="a" * 64
    )
    assert any("rollback_plan_digest does not match" in e for e in errors)


def test_binding_fails_for_wrong_patch_digest() -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(plan, confirmed_digest_prefix=canonical_digest(plan)[:4])
    errors = rollback_approval_binding_errors(
        approval, rollback_plan_digest=canonical_digest(plan), patch_digest="f" * 64
    )
    assert any("patch_digest does not match" in e for e in errors)


def test_expiry_fails_closed() -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(
        plan, confirmed_digest_prefix=canonical_digest(plan)[:4], approved_at=1000, ttl_seconds=100
    )
    assert approval_is_expired(approval, now=1099) is False
    assert approval_is_expired(approval, now=1101) is True
    # A missing/invalid expiry is treated as expired (fail closed).
    assert approval_is_expired({"expires_at": None}, now=0) is True


def test_prefix_must_be_prefix_of_plan_digest() -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(plan, confirmed_digest_prefix="zzzz")
    errors = validate_hitl_rollback_approval(approval)
    assert any("digest_prefix must be a prefix of rollback_plan_digest" in e for e in errors)


def test_artifact_is_authority_true_fails() -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(plan, confirmed_digest_prefix=canonical_digest(plan)[:4])
    approval["artifact_is_authority"] = True
    errors = validate_hitl_rollback_approval(approval)
    assert any("artifact_is_authority must be false" in e for e in errors)


def test_wrong_kind_fails() -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(plan, confirmed_digest_prefix=canonical_digest(plan)[:4])
    approval["kind"] = "builder_ii.hitl_patch_approval"
    errors = validate_hitl_rollback_approval(approval)
    assert any(f"kind must be {HITL_ROLLBACK_APPROVAL_KIND}" in e for e in errors)


def test_file_round_trip(tmp_path: Path) -> None:
    plan = _plan()
    approval = create_hitl_rollback_approval(plan, confirmed_digest_prefix=canonical_digest(plan)[:4])
    out = tmp_path / "rollback_approval.json"
    write_hitl_rollback_approval(approval, out)
    assert validate_hitl_rollback_approval_file(out) == []


def test_missing_file_reports_clean_error(tmp_path: Path) -> None:
    errors = validate_hitl_rollback_approval_file(tmp_path / "nope.json")
    assert len(errors) == 1
    assert errors[0].startswith("file not found:")
