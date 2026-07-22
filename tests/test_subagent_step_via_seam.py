"""W3.1 partial — subagent step uses invoke_local seam; spawn_executed stays false."""

from __future__ import annotations

from pathlib import Path

from builder_ii.routing.model_budget import create_model_budget
from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.wrp.subagent_executor import run_governed_subagent_step


def test_subagent_step_invoke_local(tmp_path: Path) -> None:
    registry = create_model_client_registry()
    for client in registry["clients"]:
        if client["model_id"] == "gpt-4o-stub":
            client["enabled"] = True
    budget = create_model_budget(session_id="sub-1", max_usd=2.0)
    out = run_governed_subagent_step(
        role="code_reviewer",
        task="review seam step",
        model_id="gpt-4o-stub",
        prompt="Review this honesty pin",
        plan_digest="e" * 64,
        approved_by="operator",
        budget=budget,
        registry=registry,
        artifact_dir=tmp_path / "sub",
        session_id="sub-1",
    )
    assert out["spawn_executed"] is False
    assert out["uses_seam"] is True
    assert out["gateway_result"]["executes_model_provider"] is True
    assert out["gateway_result"]["receipt_digest"]
