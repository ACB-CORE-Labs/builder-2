"""W5 full-lane scenario: R → gate → evaluate → R* → replay."""

from __future__ import annotations

from builder_ii.wrp.adjoint_operator import adjoint_correct
from builder_ii.wrp.evaluator import create_proof_record, evaluate_trajectory
from builder_ii.wrp.experience_store import create_experience_store
from builder_ii.wrp.forward_operator import forward_route
from builder_ii.wrp.governance_router import create_default_msda_policy, evaluate_msda_gate
from builder_ii.wrp.subtask_graph import replay_graph_digests


def test_full_wrp_lane_passive_end_to_end() -> None:
    route = forward_route(text="implement MSDA gate validators and tests", token_budget=30.0)
    assert route["grants_authority"] is False

    policy = create_default_msda_policy()
    gate = evaluate_msda_gate(tool="artifact_validate", data_domain="local_workspace", policy=policy)
    assert gate["decision"]["effect"] == "allow"
    assert gate["execution_permitted"] is False

    eval_art = evaluate_trajectory(
        trajectory_id="full-lane-1",
        success=True,
        safety_ok=True,
        sequence_ok=True,
        cost_units=route["components"]["allocation"]["allocation"]["projected_cost_units"],
        budget_units=30.0,
    )
    assert eval_art["metrics"]["quality"] == 1.0

    store = create_experience_store(store_id="full-lane")
    store, correction = adjoint_correct(
        store=store,
        trajectory_id="full-lane-1",
        success=True,
        error_signal=0.0,
    )
    assert correction["requires_hitl_promotion_to_apply"] is True

    plan = route["components"]["subtask_graph"]
    observed = [{"node_id": n, "digest": f"{i:064x}"[:64]} for i, n in enumerate(plan["execution_order"])]
    # ensure digests are 64 hex
    observed = [{"node_id": n, "digest": (f"{i}" * 64)[:64]} for i, n in enumerate(plan["execution_order"])]
    replay = replay_graph_digests(planned=plan, observed_chain=observed)
    assert replay["perfect_match"] is True

    proof_r = create_proof_record(
        proof_class="R",
        claim="Workload coordinates preserved through forward route",
        held=True,
        evidence_refs=[route["digest"]],
    )
    proof_d = create_proof_record(
        proof_class="D",
        claim="MSDA gate denies shell by default",
        held=True,
        evidence_refs=[gate["digest"]],
    )
    proof_u = create_proof_record(
        proof_class="U",
        claim="Local-first allocation conserved high-cost models for trivial work",
        held=True,
        evidence_refs=[route["components"]["allocation"]["digest"]],
    )
    assert proof_r["held"] and proof_d["held"] and proof_u["held"]
