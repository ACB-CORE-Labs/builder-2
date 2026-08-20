"""G1 — governed stdio MCP server (read-only interposition seam).

The server introduces no new tool capability. It exposes only the executor's already
allowlisted read-only stub tools (``builtin.echo`` / ``builtin.utc_static``) and proves the
interposition seam: a JSON-RPC ``tools/call`` runs the existing governed ceremony
(policy + envelope -> execute_tool_envelope -> receipt -> chained event record), writes the
receipt and event under ``.builder``, and never mutates the target or enables shell.
"""

from __future__ import annotations

import json
from pathlib import Path

from builder_ii.adapters.mcp.governed_services import validate_mcp_service_receipt
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.governance.ledger.event_ledger import validate_event_chain_integrity


def _server(tmp_path: Path) -> GovernedMcpServer:
    return GovernedMcpServer(
        session_id="test_session",
        builder_root=tmp_path / ".builder" / "artifacts",
        target_root=tmp_path,
        target_name="generic",
    )


def _events_dir(tmp_path: Path) -> Path:
    return tmp_path / ".builder" / "artifacts" / "sessions" / "test_session" / "events"


def _mcp_dir(tmp_path: Path) -> Path:
    return tmp_path / ".builder" / "artifacts" / "sessions" / "test_session" / "mcp"


def test_initialize_advertises_tools_capability(tmp_path: Path) -> None:
    resp = _server(tmp_path).handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
    assert resp is not None
    assert resp["id"] == 1
    assert "tools" in resp["result"]["capabilities"]
    assert resp["result"]["serverInfo"]["name"]


def test_tools_list_advertises_services_without_legacy_mutation_tools(tmp_path: Path) -> None:
    resp = _server(tmp_path).handle_request({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert resp is not None
    names = {t["name"] for t in resp["result"]["tools"]}
    assert {"repo_map", "repo_search", "content_read", "prepare_package", "validate_prepare_package"} <= names
    assert not ({"echo", "utc_static"} & names)  # legacy stubs are compatibility-only, not admitted inventory
    assert "patch_proposal" in names
    assert not ({"propose_patch", "run_shell", "approve_patch", "apply_patch", "rollback"} & names)
    for tool in resp["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"


def test_unknown_method_is_method_not_found(tmp_path: Path) -> None:
    resp = _server(tmp_path).handle_request({"jsonrpc": "2.0", "id": 3, "method": "does/not/exist", "params": {}})
    assert resp is not None
    assert resp["error"]["code"] == -32601


def test_notification_without_id_returns_no_response(tmp_path: Path) -> None:
    resp = _server(tmp_path).handle_request({"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert resp is None


def test_tools_call_runs_governed_ceremony_and_ledgers(tmp_path: Path) -> None:
    resp = _server(tmp_path).handle_request(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "repo_map", "arguments": {}},
        }
    )
    assert resp is not None
    assert resp["result"]["isError"] is False
    assert '"kind": "builder_ii.repo_map"' in resp["result"]["content"][0]["text"]

    receipts = list(_mcp_dir(tmp_path).glob("*_receipt.json"))
    assert receipts, "no receipt written"
    receipt = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert validate_mcp_service_receipt(receipt) == []
    assert receipt["status"] == "succeeded"
    # Read-only invariants hold on the receipt governance block.
    assert receipt["governance"]["target_repo_writes"] == "DISABLED"
    assert receipt["governance"]["shell_execution"] == "DISABLED"

    integrity = validate_event_chain_integrity(_events_dir(tmp_path))
    assert integrity["valid"], integrity


def test_two_calls_produce_a_linked_event_chain(tmp_path: Path) -> None:
    server = _server(tmp_path)
    for i in range(2):
        server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": 10 + i,
                "method": "tools/call",
                "params": {"name": "repo_map", "arguments": {}},
            }
        )
    events = sorted(_events_dir(tmp_path).glob("*.json"))
    assert len(events) == 2
    integrity = validate_event_chain_integrity(_events_dir(tmp_path))
    assert integrity["valid"], integrity
    second = json.loads(events[1].read_text(encoding="utf-8"))
    assert second["previous_event_sha256"] is not None


def test_no_target_mutation_from_a_tool_call(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("original", encoding="utf-8")
    _server(tmp_path).handle_request(
        {
            "jsonrpc": "2.0",
            "id": 20,
            "method": "tools/call",
            "params": {"name": "repo_map", "arguments": {}},
        }
    )
    assert target.read_text(encoding="utf-8") == "original"


def test_retired_tool_call_is_inventory_denied_without_mutation(tmp_path: Path) -> None:
    target = tmp_path / "target.txt"
    target.write_text("original", encoding="utf-8")
    resp = _server(tmp_path).handle_request(
        {
            "jsonrpc": "2.0",
            "id": 30,
            "method": "tools/call",
            "params": {"name": "run_shell", "arguments": {"cmd": "echo hi"}},
        }
    )
    assert resp is not None
    assert resp["result"]["isError"] is True
    assert resp["result"]["_meta"]["inventory_admitted"] is False
    assert target.read_text(encoding="utf-8") == "original"
    assert not _events_dir(tmp_path).exists()


def test_retired_propose_patch_writes_no_receipt(tmp_path: Path) -> None:
    _server(tmp_path).handle_request(
        {
            "jsonrpc": "2.0",
            "id": 31,
            "method": "tools/call",
            "params": {"name": "propose_patch", "arguments": {"path": "x", "content": "y"}},
        }
    )
    # A refused call builds no envelope and writes no execution receipt.
    assert list(_mcp_dir(tmp_path).glob("*_receipt.json")) == []


def test_unknown_retired_tool_does_not_extend_valid_service_chain(tmp_path: Path) -> None:
    server = _server(tmp_path)
    server.handle_request(
        {"jsonrpc": "2.0", "id": 40, "method": "tools/call", "params": {"name": "repo_map", "arguments": {}}}
    )
    server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 41,
            "method": "tools/call",
            "params": {"name": "run_shell", "arguments": {"cmd": "rm -rf /"}},
        }
    )
    events = sorted(_events_dir(tmp_path).glob("*.json"))
    assert len(events) == 1
    assert validate_event_chain_integrity(_events_dir(tmp_path))["valid"]


def test_serve_command_is_registered_in_authority_registry() -> None:
    from builder_ii.governance.authority import COMMAND_AUTHORITY_REGISTRY

    names = {rec.name for rec in COMMAND_AUTHORITY_REGISTRY}
    assert "builder-mcp serve" in names


def test_serve_stdio_roundtrip_over_text_streams(tmp_path: Path) -> None:
    import io

    stdin = io.StringIO(
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"})
        + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        + "\n"
    )
    stdout = io.StringIO()
    _server(tmp_path).serve_stdio(stdin=stdin, stdout=stdout)
    lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
    # initialize + tools/list produce responses; the notification does not.
    assert [msg["id"] for msg in lines] == [1, 2]
