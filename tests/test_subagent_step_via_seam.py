"""W3.1 partial — subagent step uses invoke_local seam; spawn_executed stays false."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from builder_ii.routing.gateway_invocation import GatewayInvocationEngine, StreamChunk
from builder_ii.wrp.subagent_executor import run_governed_subagent_step


class _Transport:
    def stream(self, _request, _cancel):
        yield StreamChunk("ok")


def test_subagent_step_invoke_local(tmp_path: Path, route_sources_factory) -> None:
    route_sources = route_sources_factory("sub-1")
    engine = GatewayInvocationEngine(lambda _candidate: _Transport())
    with patch("builder_ii.routing.gateway_invocation.governed_invocation_engine", return_value=engine):
        out = run_governed_subagent_step(
        role="code_reviewer",
        task="review seam step",
        prompt="Review this honesty pin",
        plan_digest="e" * 64,
        approved_by="operator",
        route_sources=route_sources,
        artifact_dir=tmp_path / "sub",
        session_id="sub-1",
        )
    assert out["spawn_executed"] is False
    assert out["uses_seam"] is True
    assert out["gateway_result"]["executes_model_provider"] is True
    assert out["gateway_result"]["receipt_digest"]
