"""W3.1 multi-step subagent loop."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from builder_ii.routing.gateway_invocation import GatewayInvocationEngine, StreamChunk
from builder_ii.wrp.subagent_executor import run_governed_subagent_loop


class _Transport:
    def stream(self, _request, _cancel):
        yield StreamChunk("ok")


def test_subagent_loop_spawn_executed_when_gated(tmp_path: Path, route_sources_factory) -> None:
    route_sources = route_sources_factory("loop-1")
    ks = tmp_path / "kill"
    # armed path (file absent = not tripped)
    engine = GatewayInvocationEngine(lambda _candidate: _Transport())
    with patch("builder_ii.routing.gateway_invocation.governed_invocation_engine", return_value=engine):
        out = run_governed_subagent_loop(
        role="code_reviewer",
        task="review honesty",
        steps=["step one prompt", "step two prompt"],
        plan_digest="e" * 64,
        approved_by="human",
        route_sources=route_sources,
        artifact_dir=tmp_path / "art",
        kill_switch_path=ks,
        )
    assert out["steps_executed"] == 2
    assert out["spawn_executed"] is True
    assert out["kill_switch_armed"] is True
    assert out["process_spawn"] is False
    assert out["evidence"]["step_count"] == 2


def test_kill_switch_stops_loop(tmp_path: Path, route_sources_factory) -> None:
    route_sources = route_sources_factory("loop-2")
    ks = tmp_path / "kill"
    ks.write_text("kill\n", encoding="utf-8")
    out = run_governed_subagent_loop(
        role="code_reviewer",
        task="review",
        steps=["a", "b"],
        plan_digest="f" * 64,
        approved_by="human",
        route_sources=route_sources,
        artifact_dir=tmp_path / "art2",
        kill_switch_path=ks,
    )
    assert out["steps_executed"] == 0
    assert out["stopped_reason"] == "kill_switch"
