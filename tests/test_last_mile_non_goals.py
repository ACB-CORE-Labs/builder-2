"""Permanent non-goals and honesty pins for the last-mile program."""

from __future__ import annotations

import pytest

from builder_ii.governance.hitl.hitl_command_runner import RunCommandDisabledError, execute_hitl_command
from builder_ii.wrp.agent_factory import spawn_agent, validate_agent_lifecycle_record
from builder_ii.wrp.gateway_nodes import GATEWAY_MODES


def test_hitl_run_command_remains_disabled(tmp_path) -> None:
    """REMOVED FROM DESIGN: MASTERPIECE_PLAN permanent non-goal (2026-07-11)."""
    with pytest.raises(RunCommandDisabledError):
        execute_hitl_command(
            request_path=tmp_path / "r.json",
            proposal_path=tmp_path / "p.json",
            approval_path=tmp_path / "a.json",
            output_dir=tmp_path / "out",
        )


def test_agent_factory_spawn_executed_false_by_default() -> None:
    """Default lifecycle record is unearned (false) — not a ban on earned paths."""
    rec = spawn_agent(role="code_reviewer", task="review last-mile honesty")
    assert rec["spawn_executed"] is False
    assert rec["spawn_permitted"] is False
    assert validate_agent_lifecycle_record(rec) == []


def test_gateway_modes_include_seam_modes() -> None:
    assert "invoke_local" in GATEWAY_MODES
    assert "invoke_cloud" in GATEWAY_MODES  # W2.2 implemented; hard-gated, not default
    assert "record" in GATEWAY_MODES
