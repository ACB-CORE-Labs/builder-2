from __future__ import annotations

from builder_ii.wrp.adjoint_operator import adjoint_correct, simulate_epochs, validate_adjoint_correction
from builder_ii.wrp.experience_store import create_experience_store, validate_experience_store


def test_experience_store_immutable_append_and_no_live_routing() -> None:
    store = create_experience_store()
    assert validate_experience_store(store) == []
    updated, corr = adjoint_correct(
        store=store,
        trajectory_id="t1",
        success=False,
        error_signal=1.0,
        feature_deltas={"difficulty": 0.4},
    )
    assert validate_experience_store(updated) == []
    assert validate_adjoint_correction(corr) == []
    assert corr["updates_live_routing"] is False
    assert corr["requires_hitl_promotion_to_apply"] is True
    assert len(store["exemplars"]) == 0  # immutability of original
    assert len(updated["exemplars"]) == 1


def test_w4_epoch_error_reduction_at_least_30_percent() -> None:
    report = simulate_epochs(epochs=5, initial_error_rate=0.55, improvement_per_epoch=0.09)
    assert report["meets_w4_threshold"], f"reduction={report['relative_reduction']} rates={report['epoch_error_rates']}"
