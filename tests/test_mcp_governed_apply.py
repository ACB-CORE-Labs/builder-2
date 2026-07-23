"""G4 — in-loop governed patch apply (deny-by-default, delegated, fail-closed).

Tests the gate's routing/refusal logic. The gate delegates the actual mutation to
``apply_hitl_patch`` (which has its own suite); here it is mocked so we prove the gate is
deny-by-default at two levels and fails closed on every error path -- without any real git
apply.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from builder_ii.adapters.mcp.governed_apply import governed_apply_enabled, run_gated_patch_apply
from builder_ii.adapters.mcp.server import GovernedMcpServer


def _events(tmp_path: Path, session: str = "s") -> list[Path]:
    return sorted((tmp_path / ".builder" / "sessions" / session / "events").glob("*.json"))


def _last_event_type(tmp_path: Path, session: str = "s") -> str:
    events = _events(tmp_path, session)
    return json.loads(events[-1].read_text(encoding="utf-8"))["event_type"] if events else ""


def _inputs(tmp_path: Path) -> dict[str, str]:
    files = {}
    for name in ("proposal", "approval", "verification_receipt"):
        p = tmp_path / f"{name}.json"
        p.write_text("{}", encoding="utf-8")
        files[f"{name}_path"] = str(p)
    return files


def test_enablement_flag_is_deny_by_default(monkeypatch) -> None:
    monkeypatch.delenv("BUILDER_MCP_GOVERNED_APPLY", raising=False)
    assert governed_apply_enabled() is False
    monkeypatch.setenv("BUILDER_MCP_GOVERNED_APPLY", "1")
    assert governed_apply_enabled() is True
    monkeypatch.setenv("BUILDER_MCP_GOVERNED_APPLY", "0")
    assert governed_apply_enabled() is False


def test_refuses_when_not_enabled_and_never_calls_apply(tmp_path: Path) -> None:
    with patch("builder_ii.adapters.mcp.governed_apply.governed_apply_enabled", return_value=False), patch(
        "builder_ii.adapters.mcp.governed_apply.apply_hitl_patch"
    ) as mock_apply:
        outcome = run_gated_patch_apply(
            arguments=_inputs(tmp_path), session_id="s", builder_root=tmp_path / ".builder"
        )
    assert outcome.status == "refused"
    mock_apply.assert_not_called()
    assert _last_event_type(tmp_path) == "mcp_call_denied"


def test_refuses_missing_inputs_even_when_enabled(tmp_path: Path) -> None:
    with patch("builder_ii.adapters.mcp.governed_apply.governed_apply_enabled", return_value=True), patch(
        "builder_ii.adapters.mcp.governed_apply.apply_hitl_patch"
    ) as mock_apply:
        outcome = run_gated_patch_apply(arguments={}, session_id="s", builder_root=tmp_path / ".builder")
    assert outcome.status == "refused"
    mock_apply.assert_not_called()


def test_refuses_when_approval_is_not_schema_valid(tmp_path: Path) -> None:
    # validate_hitl_patch_approval_file runs for real on the dummy "{}" approval -> errors -> refuse.
    with patch("builder_ii.adapters.mcp.governed_apply.governed_apply_enabled", return_value=True), patch(
        "builder_ii.adapters.mcp.governed_apply.apply_hitl_patch"
    ) as mock_apply:
        outcome = run_gated_patch_apply(
            arguments=_inputs(tmp_path), session_id="s", builder_root=tmp_path / ".builder"
        )
    assert outcome.status == "refused"
    assert "schema-valid" in outcome.reason
    mock_apply.assert_not_called()


def test_applies_via_governed_lane_when_enabled_and_valid(tmp_path: Path) -> None:
    with patch("builder_ii.adapters.mcp.governed_apply.governed_apply_enabled", return_value=True), patch(
        "builder_ii.adapters.mcp.governed_apply.validate_hitl_patch_approval_file", return_value=[]
    ), patch("builder_ii.adapters.mcp.governed_apply.apply_hitl_patch") as mock_apply:
        outcome = run_gated_patch_apply(
            arguments=_inputs(tmp_path), session_id="s", builder_root=tmp_path / ".builder"
        )
    assert outcome.status == "applied"
    mock_apply.assert_called_once()
    assert _last_event_type(tmp_path) == "mcp_call_executed"


def test_fails_closed_when_governed_lane_raises(tmp_path: Path) -> None:
    with patch("builder_ii.adapters.mcp.governed_apply.governed_apply_enabled", return_value=True), patch(
        "builder_ii.adapters.mcp.governed_apply.validate_hitl_patch_approval_file", return_value=[]
    ), patch(
        "builder_ii.adapters.mcp.governed_apply.apply_hitl_patch",
        side_effect=ValueError("Target repository working tree is not clean"),
    ):
        outcome = run_gated_patch_apply(
            arguments=_inputs(tmp_path), session_id="s", builder_root=tmp_path / ".builder"
        )
    assert outcome.status == "refused"
    assert "not clean" in outcome.reason
    assert _last_event_type(tmp_path) == "mcp_call_denied"


def test_server_propose_patch_refuses_by_default(tmp_path: Path) -> None:
    server = GovernedMcpServer(session_id="s", builder_root=tmp_path / ".builder")
    resp = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "propose_patch", "arguments": {"path": "x", "content": "y"}},
        }
    )
    assert resp is not None
    assert resp["result"]["isError"] is True
    assert resp["result"]["_meta"]["applied"] is False
    assert _last_event_type(tmp_path) == "mcp_call_denied"
