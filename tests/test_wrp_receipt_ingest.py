"""P2.4 — receipt_ingest → ExperienceStore (immutable, no live-policy apply)."""

from __future__ import annotations

import copy

import pytest

from builder_ii.wrp.experience_store import create_experience_store, validate_experience_store
from builder_ii.wrp.receipt_ingest import (
    ACCEPTED_RECEIPT_KINDS,
    from_ledger_events,
    ingest_receipts,
    receipt_to_exemplar_fields,
)


def _base_receipt(**overrides: object) -> dict:
    receipt: dict = {
        "kind": "model_call",
        "success": True,
        "trajectory_id": "traj-1",
        "cost_tokens": 42,
        "workload_features": {"difficulty": 0.4, "safety": 0.2},
        "digest": "abc123def456",
    }
    receipt.update(overrides)
    return receipt


def test_accepted_kinds_cover_required_set() -> None:
    assert ACCEPTED_RECEIPT_KINDS == frozenset({"model_call", "tool_call", "verification", "wrp_live_step"})


def test_ingest_receipts_appends_exemplars_and_validates() -> None:
    store = create_experience_store(store_id="ingest-test")
    assert validate_experience_store(store) == []
    assert store["exemplars"] == []

    receipts = [
        _base_receipt(kind="model_call", success=True, trajectory_id="m1"),
        _base_receipt(
            kind="tool_call",
            success=False,
            trajectory_id="t1",
            cost_tokens=10,
            workload_features={"difficulty": 0.9},
        ),
        _base_receipt(kind="verification", success=True, trajectory_id="v1", cost_tokens=None),
        _base_receipt(kind="wrp_live_step", success=False, trajectory_id="s1"),
    ]

    updated = ingest_receipts(store, receipts)
    assert validate_experience_store(updated) == []
    assert len(updated["exemplars"]) == 4
    assert updated["updates_live_routing"] is False
    assert updated["grants_authority"] is False

    by_id = {e["trajectory_id"]: e for e in updated["exemplars"]}
    assert by_id["m1"]["success"] is True
    assert by_id["m1"]["error_signal"] == 0.0
    assert by_id["m1"]["features"]["difficulty"] == 0.4
    assert by_id["m1"]["features"]["cost_tokens"] == 42.0
    assert by_id["t1"]["success"] is False
    assert by_id["t1"]["error_signal"] == 1.0
    assert by_id["t1"]["features"]["difficulty"] == 0.9
    assert "kind=tool_call" in by_id["t1"]["notes"]


def test_ingest_receipts_immutability_does_not_mutate_input_store() -> None:
    store = create_experience_store(store_id="immutable")
    original = copy.deepcopy(store)
    original_exemplars = store["exemplars"]
    original_digest = store.get("digest")

    receipts = [
        _base_receipt(trajectory_id="keep-store-pure"),
        _base_receipt(kind="verification", trajectory_id="second", success=False),
    ]
    updated = ingest_receipts(store, receipts)

    assert store == original
    assert store["exemplars"] is original_exemplars
    assert len(store["exemplars"]) == 0
    assert store.get("digest") == original_digest
    assert len(updated["exemplars"]) == 2
    assert updated is not store
    assert updated["digest"] != original_digest


def test_ingest_receipts_rejects_unknown_kind() -> None:
    store = create_experience_store()
    with pytest.raises(ValueError, match=r"kind must be one of"):
        ingest_receipts(store, [{"kind": "shell_exec", "success": True}])
    assert store["exemplars"] == []


def test_ingest_receipts_rejects_missing_success() -> None:
    store = create_experience_store()
    with pytest.raises(ValueError, match=r"success is required"):
        ingest_receipts(store, [{"kind": "model_call"}])
    assert store["exemplars"] == []


def test_ingest_receipts_rejects_non_bool_success() -> None:
    store = create_experience_store()
    with pytest.raises(ValueError, match=r"success must be a bool"):
        ingest_receipts(store, [{"kind": "model_call", "success": "yes"}])


def test_ingest_receipts_rejects_bad_cost_tokens() -> None:
    store = create_experience_store()
    with pytest.raises(ValueError, match=r"cost_tokens"):
        ingest_receipts(store, [_base_receipt(cost_tokens=-1)])
    with pytest.raises(ValueError, match=r"cost_tokens"):
        ingest_receipts(store, [_base_receipt(cost_tokens="many")])


def test_ingest_receipts_rejects_bad_workload_features() -> None:
    store = create_experience_store()
    with pytest.raises(ValueError, match=r"workload_features"):
        ingest_receipts(store, [_base_receipt(workload_features="not-a-dict")])
    with pytest.raises(ValueError, match=r"workload_features"):
        ingest_receipts(store, [_base_receipt(workload_features={"x": "nope"})])


def test_ingest_receipts_fails_closed_on_mid_batch_malformed() -> None:
    store = create_experience_store()
    receipts = [
        _base_receipt(trajectory_id="ok-first"),
        {"kind": "model_call"},  # missing success
        _base_receipt(trajectory_id="would-be-third"),
    ]
    with pytest.raises(ValueError, match=r"success is required"):
        ingest_receipts(store, receipts)
    assert store["exemplars"] == []


def test_ingest_receipts_rejects_non_list_receipts() -> None:
    store = create_experience_store()
    with pytest.raises(ValueError, match=r"receipts must be a list"):
        ingest_receipts(store, {"kind": "model_call", "success": True})  # type: ignore[arg-type]


def test_receipt_to_exemplar_fields_default_trajectory_id() -> None:
    fields = receipt_to_exemplar_fields(
        {"kind": "tool_call", "success": True, "digest": "deadbeefcafebabe"},
        index=3,
    )
    assert fields["trajectory_id"].startswith("tool_call:deadbeefcafebabe"[: len("tool_call:") + 16])
    assert fields["success"] is True
    assert fields["error_signal"] == 0.0


def test_from_ledger_events_normalizes_model_and_tool() -> None:
    events = [
        {
            "event_type": "model_call_executed",
            "event_id": "e-m1",
            "cost_report": {"total_tokens": 100},
            "payload_sha256": "aa" * 32,
            "message": "ok model",
        },
        {
            "event_type": "model_call_failed",
            "event_id": "e-m2",
            "status": "failed",
        },
        {
            "event_type": "tool_call_denied",
            "event_id": "e-t1",
            "decision_result": "denied",
        },
        {
            "event_type": "workflow_planned",  # not a receipt-ish event
            "event_id": "skip-me",
        },
    ]
    receipts = from_ledger_events(events)
    assert len(receipts) == 3
    assert receipts[0]["kind"] == "model_call"
    assert receipts[0]["success"] is True
    assert receipts[0]["cost_tokens"] == 100
    assert receipts[0]["digest"] == "aa" * 32
    assert receipts[0]["event_id"] == "e-m1"
    assert receipts[1]["kind"] == "model_call"
    assert receipts[1]["success"] is False
    assert receipts[2]["kind"] == "tool_call"
    assert receipts[2]["success"] is False

    store = create_experience_store()
    updated = ingest_receipts(store, receipts)
    assert validate_experience_store(updated) == []
    assert len(updated["exemplars"]) == 3
    assert sum(1 for e in updated["exemplars"] if e["success"]) == 1


def test_from_ledger_events_rejects_non_list() -> None:
    with pytest.raises(ValueError, match=r"events must be a list"):
        from_ledger_events({"event_type": "model_call_executed"})  # type: ignore[arg-type]


def test_from_ledger_events_passes_through_already_normalized() -> None:
    events = [
        {
            "kind": "verification",
            "success": False,
            "trajectory_id": "v-ledger",
            "workload_features": {"safety": 0.8},
        }
    ]
    receipts = from_ledger_events(events)
    assert receipts == [
        {
            "kind": "verification",
            "success": False,
            "trajectory_id": "v-ledger",
            "workload_features": {"safety": 0.8},
        }
    ]
