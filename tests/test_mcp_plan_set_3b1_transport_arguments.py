from __future__ import annotations

import json
from pathlib import Path

from builder_ii.adapters.mcp.server import GovernedMcpServer


def test_empty_list_arguments_are_denied_and_evidenced(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    builder_root = tmp_path / "builder-artifacts"
    server = GovernedMcpServer(
        session_id="malformed-arguments",
        builder_root=builder_root,
        target_root=target,
        target_name="generic",
    )

    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "repo_map", "arguments": []},
        }
    )

    assert response is not None
    result = response["result"]
    assert result["isError"] is True
    assert result["_meta"]["status"] == "denied"
    assert result["_meta"]["evidence_appended"] is True

    receipts = sorted((builder_root / "sessions" / "malformed-arguments" / "mcp").glob("*_receipt.json"))
    events = sorted((builder_root / "sessions" / "malformed-arguments" / "events").glob("*.json"))
    assert len(receipts) == 1
    assert len(events) == 1
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    event = json.loads(events[0].read_text(encoding="utf-8"))
    assert receipt["status"] == "denied"
    assert event["event_type"] == "mcp_call_denied"
