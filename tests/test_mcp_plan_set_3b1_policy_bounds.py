from __future__ import annotations

import json
from pathlib import Path

from builder_ii.adapters.mcp.governed_services import (
    MAX_SERVICE_INPUT_BYTES,
    MAX_SERVICE_OUTPUT_BYTES,
)
from builder_ii.adapters.mcp.server import GovernedMcpServer


def test_persisted_policy_bounds_cover_the_exact_service_result(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "alpha.py").write_text("alpha = 1\n", encoding="utf-8")
    builder_root = tmp_path / "artifacts"
    server = GovernedMcpServer(
        session_id="policy-bounds",
        builder_root=builder_root,
        target_root=target,
        target_name="generic",
    )

    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "repo_map", "arguments": {}},
        }
    )
    assert response is not None
    assert response["result"]["isError"] is False

    receipt_path = Path(response["result"]["_meta"]["receipt_path"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    policy = json.loads(Path(receipt["policy_ref"]["path"]).read_text(encoding="utf-8"))
    result_size = len(
        json.dumps(receipt["result"], sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    )
    assert policy["max_input_bytes"] == MAX_SERVICE_INPUT_BYTES
    assert policy["max_output_bytes"] == MAX_SERVICE_OUTPUT_BYTES
    assert result_size <= policy["max_output_bytes"]


def test_oversized_service_arguments_are_denied_and_evidenced(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    builder_root = tmp_path / "artifacts"
    server = GovernedMcpServer(
        session_id="input-bounds",
        builder_root=builder_root,
        target_root=target,
        target_name="generic",
    )

    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "repo_search", "arguments": {"query": "x" * (MAX_SERVICE_INPUT_BYTES + 1)}},
        }
    )

    assert response is not None
    result = response["result"]
    assert result["isError"] is True
    assert result["_meta"]["status"] == "denied"
    receipt = json.loads(Path(result["_meta"]["receipt_path"]).read_text(encoding="utf-8"))
    assert receipt["status"] == "denied"
