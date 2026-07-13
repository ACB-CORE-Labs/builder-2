"""P4 — R* apply path: real receipts → HITL plan/approve/apply → versioned φ policy."""

from __future__ import annotations

import pytest

from builder_ii.wrp.experience_store import create_experience_store, validate_experience_store
from builder_ii.wrp.rstar_apply import (
    MAX_DELTA_PER_AXIS,
    RStarApplyError,
    apply_approved,
    build_rstar_apply_approval,
    build_rstar_apply_plan,
    corrections_from_receipts,
    create_phi_policy,
    phi_from_policy,
    simulate_receipt_epochs,
    validate_phi_policy,
    validate_rstar_apply_approval,
    validate_rstar_apply_plan,
    validate_rstar_apply_receipt,
)
from builder_ii.wrp.spaces import DEFAULT_PHI
from builder_ii.wrp.workload_classifier import classify_workload


def _failed_receipt(tid: str, *, difficulty: float = 0.7) -> dict:
    return {
        "kind": "verification",
        "success": False,
        "trajectory_id": tid,
        "workload_features": {"difficulty": difficulty, "safety": 0.4},
        "cost_tokens": 10,
    }


def _ok_receipt(tid: str) -> dict:
    return {
        "kind": "model_call",
        "success": True,
        "trajectory_id": tid,
        "workload_features": {"difficulty": 0.2},
    }


def test_phi_policy_default_and_versioning() -> None:
    p0 = create_phi_policy(policy_id="test")
    assert validate_phi_policy(p0) == []
    assert p0["version"] == 0
    assert p0["updates_live_routing_defaults"] is False
    assert p0["requires_explicit_bind"] is True
    assert phi_from_policy(p0)["difficulty"] == DEFAULT_PHI["difficulty"]


def test_corrections_from_real_receipts_immutable() -> None:
    store = create_experience_store(store_id="p4")
    original_digest = store["digest"]
    updated, corrections = corrections_from_receipts(
        store,
        [_failed_receipt("t-fail"), _ok_receipt("t-ok")],
    )
    assert store["digest"] == original_digest
    assert validate_experience_store(updated) == []
    assert updated["version"] == 1
    assert updated["parent_digest"] == store["digest"] or len(updated["exemplars"]) == 2
    assert len(corrections) == 2
    fail_corr = corrections[0]
    assert fail_corr["requires_hitl_promotion_to_apply"] is True
    assert fail_corr["updates_live_routing"] is False
    assert fail_corr["success"] is False


def test_apply_requires_hitl_approval() -> None:
    store = create_experience_store()
    store, corrections = corrections_from_receipts(store, [_failed_receipt("a")])
    base = create_phi_policy()
    plan = build_rstar_apply_plan(
        base_policy=base, corrections=corrections, experience_store=store
    )
    assert validate_rstar_apply_plan(plan) == []
    with pytest.raises(RStarApplyError, match="approval"):
        apply_approved(plan=plan, approval={"kind": "nope", "approved": True})


def test_apply_digest_bound_hitl_happy_path() -> None:
    store = create_experience_store()
    store, corrections = corrections_from_receipts(
        store,
        [_failed_receipt("f1"), _failed_receipt("f2", difficulty=0.9)],
    )
    base = create_phi_policy(policy_id="default")
    plan = build_rstar_apply_plan(
        base_policy=base, corrections=corrections, experience_store=store, notes="p4"
    )
    approval = build_rstar_apply_approval(plan=plan, approved_by="human-operator")
    assert validate_rstar_apply_approval(approval) == []
    new_policy, receipt = apply_approved(plan=plan, approval=approval)
    assert validate_phi_policy(new_policy) == []
    assert validate_rstar_apply_receipt(receipt) == []
    assert new_policy["version"] == 1
    assert new_policy["parent_policy_digest"] == base["digest"]
    assert new_policy["applied_by"] == "human-operator"
    assert receipt["new_policy_digest"] == new_policy["digest"]
    assert receipt["updates_live_routing_defaults"] is False
    # difficulty should have increased within cap
    delta = new_policy["phi"]["difficulty"] - base["phi"]["difficulty"]
    assert 0 < delta <= MAX_DELTA_PER_AXIS + 1e-9


def test_apply_rejects_plan_approval_digest_mismatch() -> None:
    store = create_experience_store()
    store, corrections = corrections_from_receipts(store, [_failed_receipt("x")])
    base = create_phi_policy()
    plan = build_rstar_apply_plan(base_policy=base, corrections=corrections)
    approval = build_rstar_apply_approval(plan=plan, approved_by="ops")
    # Tamper plan digest binding
    bad_approval = dict(approval)
    bad_approval["plan_digest"] = "0" * 64
    bad_approval.pop("digest", None)
    from builder_ii.wrp.artifacts import finalize_wrp_artifact

    bad_approval = finalize_wrp_artifact(bad_approval)
    with pytest.raises(RStarApplyError, match="plan_digest"):
        apply_approved(plan=plan, approval=bad_approval)


def test_success_only_receipts_cannot_plan_apply() -> None:
    store = create_experience_store()
    store, corrections = corrections_from_receipts(store, [_ok_receipt("s1"), _ok_receipt("s2")])
    base = create_phi_policy()
    with pytest.raises(RStarApplyError, match="no apply-worthy"):
        build_rstar_apply_plan(base_policy=base, corrections=corrections)


def test_classifier_explicit_phi_bind_does_not_mutate_defaults() -> None:
    default_clf = classify_workload(text="implement a validator")
    assert default_clf.get("phi_bound") is False
    policy = create_phi_policy(phi={**DEFAULT_PHI, "difficulty": 2.0, "safety": 2.0})
    bound = classify_workload(
        text="implement a validator",
        phi=phi_from_policy(policy),
        phi_policy_digest=policy["digest"],
    )
    assert bound["phi_bound"] is True
    assert bound["phi_policy_digest"] == policy["digest"]
    # DEFAULT_PHI unchanged
    assert DEFAULT_PHI["difficulty"] == 1.2


def test_simulate_receipt_epochs_tracks_error_reduction() -> None:
    # Epoch 0: mostly failures; later epochs mostly success → measurable reduction.
    epochs = [
        [_failed_receipt(f"e0-{i}") for i in range(8)] + [_ok_receipt("e0-ok")],
        [_failed_receipt(f"e1-{i}") for i in range(4)] + [_ok_receipt(f"e1-ok-{i}") for i in range(5)],
        [_ok_receipt(f"e2-ok-{i}") for i in range(9)],
    ]
    report = simulate_receipt_epochs(receipt_epochs=epochs)
    assert report["source"] == "real_receipts"
    assert report["correction_count"] == 9 + 9 + 9  # e0:8fail+1ok, e1:4fail+5ok, e2:9ok
    assert len(report["epoch_error_rates"]) == 3
    assert report["relative_reduction"] > 0.3
    assert report["meets_w4_threshold"] is True
    assert report["store"]["frozen"] is True


def test_unknown_phi_axis_rejected() -> None:
    with pytest.raises(RStarApplyError, match="unknown phi axis"):
        create_phi_policy(phi={**DEFAULT_PHI, "hacker_axis": 9.0})
