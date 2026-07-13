"""P4 end-to-end: real receipts → R* corrections → HITL apply → bound classify."""

from __future__ import annotations

from builder_ii.wrp.experience_store import create_experience_store, validate_experience_store
from builder_ii.wrp.rstar_apply import (
    apply_approved,
    build_rstar_apply_approval,
    build_rstar_apply_plan,
    corrections_from_receipts,
    create_phi_policy,
    phi_from_policy,
    validate_phi_policy,
    validate_rstar_apply_receipt,
)
from builder_ii.wrp.workload_classifier import classify_workload


def test_p4_full_lane_receipts_to_bound_classifier() -> None:
    store = create_experience_store(store_id="p4-e2e")
    receipts = [
        {
            "kind": "wrp_live_step",
            "success": False,
            "trajectory_id": "live-fail-1",
            "workload_features": {"difficulty": 0.8, "safety": 0.5, "domain": 0.6},
            "digest": "a" * 64,
            "notes": "graph step failed probe",
        },
        {
            "kind": "verification",
            "success": False,
            "trajectory_id": "verify-fail-1",
            "workload_features": {"difficulty": 0.9, "context": 0.4},
        },
        {
            "kind": "model_call",
            "success": True,
            "trajectory_id": "model-ok-1",
            "workload_features": {"difficulty": 0.2},
            "cost_tokens": 42,
        },
    ]
    store, corrections = corrections_from_receipts(store, receipts)
    assert validate_experience_store(store) == []
    assert store["version"] >= 1
    assert len(corrections) == 3

    base = create_phi_policy(policy_id="e2e")
    plan = build_rstar_apply_plan(
        base_policy=base,
        corrections=corrections,
        experience_store=store,
        notes="p4 e2e",
    )
    approval = build_rstar_apply_approval(plan=plan, approved_by="e2e-human")
    new_policy, receipt = apply_approved(plan=plan, approval=approval)

    assert validate_phi_policy(new_policy) == []
    assert validate_rstar_apply_receipt(receipt) == []
    assert new_policy["parent_policy_digest"] == base["digest"]
    assert receipt["plan_digest"] == plan["digest"]
    assert receipt["approval_digest"] == approval["digest"]

    # Explicit bind only — classifier uses applied φ without changing defaults.
    clf = classify_workload(
        text="implement multi-file refactor with tests",
        phi=phi_from_policy(new_policy),
        phi_policy_digest=new_policy["digest"],
    )
    assert clf["phi_bound"] is True
    assert clf["phi_policy_digest"] == new_policy["digest"]
    assert clf["grants_authority"] is False
    assert clf["executes_model"] is False
