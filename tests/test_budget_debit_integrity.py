"""Skeptic fixes: receipt digest matches durable file; multi-call debit holds."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from builder_ii.config import Settings
from builder_ii.model_budget import (
    BudgetExceededError,
    create_model_budget,
    validate_model_budget,
)
from builder_ii.model_client_registry import create_model_client_registry
from builder_ii.model_execution_gateway import (
    ModelExecutionGateway,
    _digest,
    validate_model_call_receipt,
)
from builder_ii.model_routing_policy import create_model_execution_policy
from builder_ii.price_book import create_default_price_book


def _settings() -> Settings:
    return Settings(
        target_repo=Path("/tmp/core"),
        backend="mlx-lm",
        model_tier="primary",
        model_alias="qwen-coder",
        model_primary="g",
        model_fast="g",
        mlx_model_primary="m",
        mlx_model_fast="m",
        mlx_model_phi="m",
        mlx_model_qwen="m",
        mlx_model_deepseek="m",
        mlx_model_llama="m",
        mlx_model_codegeex="m",
        mlx_model_qwen14="m",
        mlx_model_qwen3_coder="m",
        base_url="http://127.0.0.1:8080/v1",
        host="127.0.0.1",
        port=8080,
        temperature=0.0,
        project_root=Path.cwd(),
        allow_cloud_models=True,
    )


def _gateway() -> ModelExecutionGateway:
    registry = create_model_client_registry()
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    policy = create_model_execution_policy(
        {
            "kind": "builder_ii.model_routing_recommendation",
            "recommended_candidates": [{"model_id": "gpt-4o-stub"}],
        }
    )
    return ModelExecutionGateway(
        _settings(), registry, policy, price_book=create_default_price_book()
    )


def test_receipt_digest_matches_on_disk_after_budget_debit(tmp_path: Path) -> None:
    gw = _gateway()
    budget = create_model_budget(session_id="debit-1", max_usd=10.0, max_total_tokens=50_000)
    budget_path = tmp_path / "budget.json"
    env, rec, debited = gw.run_model_call(
        model_id="gpt-4o-stub",
        prompt="one two three",
        envelope_path=tmp_path / "env.json",
        receipt_path=tmp_path / "rec.json",
        budget=budget,
        budget_path=budget_path,
        ledger_bound=True,
        events_dir=tmp_path / "events",
        session_id="debit-1",
    )
    assert debited is not None
    assert validate_model_call_receipt(rec) == []
    on_disk = json.loads((tmp_path / "rec.json").read_text(encoding="utf-8"))
    # Digest must match durable content (no post-write mutation)
    without = {k: v for k, v in on_disk.items() if k != "digest"}
    assert on_disk["digest"] == _digest(without)
    assert on_disk["digest"] == rec["digest"]
    # Post-debit fields present on disk receipt
    assert on_disk["budget_ref"]["post_debit_sha256"] == debited["digest"]
    assert on_disk["budget_ref"]["budget_version"] == debited["budget_version"]
    # Durable budget artifact written and valid
    assert budget_path.is_file()
    written_budget = json.loads(budget_path.read_text(encoding="utf-8"))
    assert validate_model_budget(written_budget) == []
    assert written_budget["digest"] == debited["digest"]
    assert written_budget["spent_total_tokens"] > 0
    # Ledger subject_ref must match durable receipt content (canonical_digest of file)
    from builder_ii.workflow_records import canonical_digest

    event_files = sorted((tmp_path / "events").glob("*.json"))
    assert event_files
    event = json.loads(event_files[-1].read_text(encoding="utf-8"))
    receipt_refs = [r for r in event["subject_refs"] if r.get("role") == "model_call_receipt"]
    assert receipt_refs
    assert receipt_refs[0]["sha256"] == canonical_digest(on_disk)
    # And durable file equals in-memory receipt (no post-write mutation drift)
    assert on_disk == rec


def test_multi_call_requires_debited_budget_not_original(tmp_path: Path) -> None:
    gw = _gateway()
    # Budget sized so first small call succeeds (max_tokens=32) but leaves little headroom
    budget = create_model_budget(
        session_id="multi",
        max_input_tokens=40,
        max_output_tokens=40,
        max_total_tokens=40,
        max_usd=10.0,
    )
    _env, _rec, debited = gw.run_model_call(
        model_id="gpt-4o-stub",
        prompt="alpha beta gamma",
        max_tokens=32,
        envelope_path=tmp_path / "e1.json",
        receipt_path=tmp_path / "r1.json",
        budget=budget,
        budget_path=tmp_path / "b1.json",
    )
    assert debited is not None
    assert debited["spent_total_tokens"] > 0
    # Second call with DEBITED budget and large prompt must fail closed
    with pytest.raises((BudgetExceededError, ValueError, RuntimeError)):
        gw.run_model_call(
            model_id="gpt-4o-stub",
            prompt="word " * 40,
            max_tokens=32,
            envelope_path=tmp_path / "e2.json",
            receipt_path=tmp_path / "r2.json",
            budget=debited,
            budget_path=tmp_path / "b2.json",
        )
    # Reusing ORIGINAL unspent budget still "works" only as a caller bug; public API
    # returns debited — prove original spent counters stayed 0 (immutable debit).
    assert budget["spent_total_tokens"] == 0
    assert debited["spent_total_tokens"] > budget["spent_total_tokens"]


def test_seam_trajectory_surfaces_debited_budget_for_next_node(tmp_path: Path) -> None:
    from builder_ii.wrp.gateway_nodes import run_gateway_node

    registry = create_model_client_registry()
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    budget = create_model_budget(
        session_id="seam-chain",
        max_input_tokens=5000,
        max_output_tokens=256,
        max_total_tokens=5000,
        max_usd=5.0,
    )
    _ev, state, traj, err = run_gateway_node(
        node_id="m1",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "payload": {
                "model_id": "gpt-4o-stub",
                "prompt": "step one",
                "budget": budget,
                "registry": registry,
                "artifact_dir": str(tmp_path / "s1"),
                "enable_stub_if_disabled": True,
                "session_id": "seam-chain",
                "max_tokens": 64,
            },
        },
        handoff_state={},
        plan_digest="1" * 64,
        approved_by="op",
        gateway_mode="invoke_local",
    )
    assert err is None, err
    assert isinstance(state.get("last_debited_budget"), dict)
    assert traj["m1"]["debited_budget"]["digest"] == state["last_debited_budget"]["digest"]
    # Second step chains budget from handoff without payload.budget
    _ev2, state2, traj2, err2 = run_gateway_node(
        node_id="m2",
        node_type="model_gateway",
        spec={
            "node_type": "model_gateway",
            "payload": {
                "model_id": "gpt-4o-stub",
                "prompt": "step two",
                "registry": registry,
                "artifact_dir": str(tmp_path / "s2"),
                "enable_stub_if_disabled": True,
                "session_id": "seam-chain",
                "max_tokens": 64,
            },
        },
        handoff_state=state,
        plan_digest="1" * 64,
        approved_by="op",
        gateway_mode="invoke_local",
    )
    assert err2 is None, err2
    assert state2["last_debited_budget"]["spent_total_tokens"] > state["last_debited_budget"]["spent_total_tokens"]
    assert traj2["m2"]["debited_budget"]["budget_version"] == state["last_debited_budget"]["budget_version"] + 1


def test_chaining_debited_budget_allows_second_small_call(tmp_path: Path) -> None:
    gw = _gateway()
    budget = create_model_budget(
        session_id="chain",
        max_input_tokens=5000,
        max_output_tokens=256,
        max_total_tokens=5000,
        max_usd=10.0,
    )
    _e1, _r1, b1 = gw.run_model_call(
        model_id="gpt-4o-stub",
        prompt="hi",
        max_tokens=64,
        envelope_path=tmp_path / "e1.json",
        receipt_path=tmp_path / "r1.json",
        budget=budget,
        budget_path=tmp_path / "b1.json",
    )
    assert b1 is not None
    spent_after_first = b1["spent_total_tokens"]
    _e2, _r2, b2 = gw.run_model_call(
        model_id="gpt-4o-stub",
        prompt="yo",
        max_tokens=64,
        envelope_path=tmp_path / "e2.json",
        receipt_path=tmp_path / "r2.json",
        budget=b1,
        budget_path=tmp_path / "b2.json",
    )
    assert b2 is not None
    assert b2["spent_total_tokens"] > spent_after_first
    assert b2["budget_version"] == b1["budget_version"] + 1
