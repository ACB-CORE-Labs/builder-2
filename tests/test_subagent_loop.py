"""W3.1 multi-step subagent loop."""

from __future__ import annotations

from pathlib import Path

from builder_ii.model_budget import create_model_budget
from builder_ii.model_client_registry import create_model_client_registry
from builder_ii.wrp.subagent_executor import run_governed_subagent_loop


def test_subagent_loop_spawn_executed_when_gated(tmp_path: Path) -> None:
    registry = create_model_client_registry()
    for c in registry["clients"]:
        if c["model_id"] == "gpt-4o-stub":
            c["enabled"] = True
    parent = create_model_budget(session_id="loop-1", max_usd=5.0, max_total_tokens=100_000)
    ks = tmp_path / "kill"
    # armed path (file absent = not tripped)
    out = run_governed_subagent_loop(
        role="code_reviewer",
        task="review honesty",
        model_id="gpt-4o-stub",
        steps=["step one prompt", "step two prompt"],
        plan_digest="e" * 64,
        approved_by="human",
        parent_budget=parent,
        registry=registry,
        artifact_dir=tmp_path / "art",
        kill_switch_path=ks,
        max_tokens=64,
    )
    assert out["steps_executed"] == 2
    assert out["spawn_executed"] is True
    assert out["kill_switch_armed"] is True
    assert out["process_spawn"] is False
    assert out["evidence"]["step_count"] == 2


def test_kill_switch_stops_loop(tmp_path: Path) -> None:
    registry = create_model_client_registry()
    for c in registry["clients"]:
        if c["model_id"] == "gpt-4o-stub":
            c["enabled"] = True
    parent = create_model_budget(session_id="loop-2", max_usd=5.0, max_total_tokens=100_000)
    ks = tmp_path / "kill"
    ks.write_text("kill\n", encoding="utf-8")
    out = run_governed_subagent_loop(
        role="code_reviewer",
        task="review",
        model_id="gpt-4o-stub",
        steps=["a", "b"],
        plan_digest="f" * 64,
        approved_by="human",
        parent_budget=parent,
        registry=registry,
        artifact_dir=tmp_path / "art2",
        kill_switch_path=ks,
    )
    assert out["steps_executed"] == 0
    assert out["stopped_reason"] == "kill_switch"
