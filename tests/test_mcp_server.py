"""G1 — governed stdio MCP server (read-only interposition seam).

The server introduces no new tool capability. It exposes only the executor's already
allowlisted read-only stub tools (``builtin.echo`` / ``builtin.utc_static``) and proves the
interposition seam: a JSON-RPC ``tools/call`` runs the existing governed ceremony
(policy + envelope -> execute_tool_envelope -> receipt -> chained event record), writes the
receipt and event under ``.builder``, and never mutates the target or enables shell.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import replace
from pathlib import Path

from builder_ii.adapters.mcp.governed_services import validate_mcp_service_receipt
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.core.config import load_settings
from builder_ii.governance.hitl.hitl_patch_apply import (
    FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
    apply_hitl_patch,
    rollback_hitl_patch,
)
from builder_ii.governance.hitl.hitl_patch_approval import create_hitl_patch_approval, write_hitl_patch_approval
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.governance.hitl.hitl_rollback_approval import (
    canonical_digest,
    create_hitl_rollback_approval,
    write_hitl_rollback_approval,
)
from builder_ii.governance.ledger.event_ledger import validate_event_chain_integrity
from tests.hitl_patch_test_helpers import write_executed_verification_receipt


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


def _git_server(tmp_path: Path) -> GovernedMcpServer:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    (tmp_path / "tracked.txt").write_text("tracked\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "initial"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "remote", "add", "origin", "https://github.com/ACB-CORE-Labs/builder-2"], check=True)
    return _server(tmp_path)


def _applied_delivery_server(tmp_path: Path, *, target_name: str = "builder") -> tuple[GovernedMcpServer, Path, Path, Path, str]:
    repo = tmp_path / "target"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    (repo / "tracked.txt").write_text("before\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "tracked.txt"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", "initial"], check=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/ACB-CORE-Labs/builder-2"],
        check=True,
    )
    head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
    builder_root = tmp_path / "artifacts"
    mcp_dir = builder_root / "sessions" / "delivery_session" / "mcp"
    mcp_dir.mkdir(parents=True)
    verification_path = mcp_dir / "verification_receipt.json"
    write_executed_verification_receipt(verification_path, repo, target_profile=target_name)
    diff = (
        "diff --git a/tracked.txt b/tracked.txt\n"
        "index 90be912..3bd1f0e 100644\n"
        "--- a/tracked.txt\n"
        "+++ b/tracked.txt\n"
        "@@ -1 +1 @@\n"
        "-before\n"
        "+after\n"
    )
    patch_digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    proposal_settings = replace(load_settings(), project_root=repo)
    proposal = create_hitl_patch_proposal(
        settings=proposal_settings,
        generic_repo=repo,
        patch_digest=patch_digest,
        unified_diff=diff,
        target_head_sha=head,
        verification_receipt_file_sha256=hashlib.sha256(verification_path.read_bytes()).hexdigest(),
        target_name=target_name,
    )
    proposal_path = mcp_dir / "proposal.json"
    write_hitl_patch_proposal(proposal, proposal_path)
    approval_path = mcp_dir / "approval.json"
    write_hitl_patch_approval(
        create_hitl_patch_approval(proposal, confirmed_digest_prefix=patch_digest[:4]),
        approval_path,
    )
    apply_hitl_patch(proposal_path, approval_path, verification_path, mcp_dir)
    plan_path = mcp_dir / "verification-plan.json"
    approval_receipt_path = mcp_dir / "verification-approval.json"
    plan_path.unlink()
    approval_receipt_path.unlink()
    server = GovernedMcpServer(
        session_id="delivery_session",
        builder_root=builder_root,
        target_root=repo,
        target_name=target_name,
    )
    return server, repo, verification_path, mcp_dir / "patch_apply_receipt.json", head


def _delivery_prepare_call(
    server: GovernedMcpServer,
    verification_path: Path,
    patch_path: Path,
    head: str,
    *,
    request_id: int,
) -> dict:
    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {
                "name": "delivery_prepare",
                "arguments": {
                    "target_head_sha": head,
                    "verification_evidence": {
                        "path": verification_path.name,
                        "sha256": hashlib.sha256(verification_path.read_bytes()).hexdigest(),
                    },
                    "patch_evidence": {
                        "path": patch_path.name,
                        "sha256": hashlib.sha256(patch_path.read_bytes()).hexdigest(),
                    },
                },
            },
        }
    )
    assert response is not None
    return response


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
    assert "rollback" in names
    assert {"git_status", "delivery_prepare", "delivery"} <= names
    assert not ({"propose_patch", "run_shell", "approve_patch", "apply_patch"} & names)
    for tool in resp["result"]["tools"]:
        assert tool["inputSchema"]["type"] == "object"


def test_git_status_and_delivery_boundary_are_read_only_and_receipted(tmp_path: Path) -> None:
    server = _git_server(tmp_path)
    status = server.handle_request({"jsonrpc": "2.0", "id": 50, "method": "tools/call", "params": {"name": "git_status", "arguments": {}}})
    assert status and status["result"]["isError"] is False
    payload = json.loads(status["result"]["content"][0]["text"])
    assert payload["git_state"]["state"] == "clean"
    assert payload["repository_identity"]["matches"] is False
    before = subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True).strip()
    prepared = server.handle_request({"jsonrpc": "2.0", "id": 51, "method": "tools/call", "params": {"name": "delivery_prepare", "arguments": {"target_head_sha": before}}})
    assert prepared and prepared["result"]["isError"] is True
    prepared_result = json.loads(prepared["result"]["content"][0]["text"])
    assert prepared_result["status"] == "BLOCKED"
    assert any("missing required verification_evidence" in error for error in prepared_result["errors"])
    assert any("missing required patch_evidence" in error for error in prepared_result["errors"])
    boundary = server.handle_request({"jsonrpc": "2.0", "id": 52, "method": "tools/call", "params": {"name": "delivery", "arguments": {}}})
    assert boundary and boundary["result"]["isError"] is True
    assert boundary["result"]["_meta"]["status"] == "denied"
    result = json.loads(boundary["result"]["content"][0]["text"])
    assert result["status"] == "HUMAN_APPROVAL_REQUIRED"
    assert result["performed_actions"] == []
    assert subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True).strip() == before
    assert validate_event_chain_integrity(_events_dir(tmp_path))["valid"]


def test_delivery_prepare_handoff_requires_canonical_patch_to_remain_applied(tmp_path: Path) -> None:
    server, repo, verification_path, patch_path, head = _applied_delivery_server(tmp_path)

    prepared = _delivery_prepare_call(server, verification_path, patch_path, head, request_id=54)
    assert prepared["result"]["isError"] is False
    result = json.loads(prepared["result"]["content"][0]["text"])
    assert result["status"] == "HANDOFF_PREPARED"
    assert result["delivery_execution"] == "NOT_ADMITTED"
    assert result["git_status"]["git_state"]["state"] == "dirty"
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "after\n"
    boundary = server.handle_request(
        {"jsonrpc": "2.0", "id": 56, "method": "tools/call", "params": {"name": "delivery", "arguments": {}}}
    )
    assert boundary and boundary["result"]["isError"] is True
    boundary_result = json.loads(boundary["result"]["content"][0]["text"])
    assert boundary_result["status"] == "HUMAN_APPROVAL_REQUIRED"
    assert boundary_result["performed_actions"] == []


def test_delivery_prepare_blocks_evidence_from_different_target_profile(tmp_path: Path) -> None:
    _, repo, verification_path, patch_path, head = _applied_delivery_server(tmp_path, target_name="generic")
    server = GovernedMcpServer(
        session_id="delivery_session",
        builder_root=tmp_path / "artifacts",
        target_root=repo,
        target_name="builder",
    )

    prepared = _delivery_prepare_call(server, verification_path, patch_path, head, request_id=57)
    assert prepared["result"]["isError"] is True
    result = json.loads(prepared["result"]["content"][0]["text"])
    assert result["status"] == "BLOCKED"
    assert any("target profile" in error for error in result["errors"])


def test_delivery_prepare_blocks_historical_apply_evidence_after_rollback(tmp_path: Path) -> None:
    server, repo, verification_path, patch_path, head = _applied_delivery_server(tmp_path)
    mcp_dir = patch_path.parent
    rollback_plan_path = mcp_dir / "rollback_plan.json"
    rollback_plan = json.loads(rollback_plan_path.read_text(encoding="utf-8"))
    rollback_approval_path = mcp_dir / "rollback_approval.json"
    write_hitl_rollback_approval(
        create_hitl_rollback_approval(
            rollback_plan,
            confirmed_digest_prefix=canonical_digest(rollback_plan)[:4],
        ),
        rollback_approval_path,
    )
    rollback_hitl_patch(
        rollback_plan_path,
        mcp_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
        mcp_dir / "rollback_out",
        approval_path=rollback_approval_path,
    )

    prepared = _delivery_prepare_call(server, verification_path, patch_path, head, request_id=55)
    assert prepared["result"]["isError"] is True
    result = json.loads(prepared["result"]["content"][0]["text"])
    assert result["status"] == "BLOCKED"
    assert any("drifted after apply" in error for error in result["errors"])
    assert (repo / "tracked.txt").read_text(encoding="utf-8") == "before\n"


def test_delivery_services_reject_extra_execution_arguments(tmp_path: Path) -> None:
    server = _git_server(tmp_path)
    response = server.handle_request({"jsonrpc": "2.0", "id": 53, "method": "tools/call", "params": {"name": "delivery", "arguments": {"command": "git push"}}})
    assert response and response["result"]["isError"] is True
    assert response["result"]["_meta"]["status"] == "denied"


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
