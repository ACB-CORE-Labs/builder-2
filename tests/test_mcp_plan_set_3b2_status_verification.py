"""Adversarial qualification for open-source-v1 Plan Set 3B2.

3B2 exposes only deterministic delegation/run status and passive verification planning through
MCP. It does not admit verification approval/execution, mutation, shell, network, delivery, or
new Deep Agents authority.
"""

from __future__ import annotations

import json
import socket
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.adapters.deepagents.deepagents_execution import (
    PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
    run_deepagents_approved_candidate,
)
from builder_ii.adapters.mcp.governed_services import run_service, validate_mcp_service_receipt
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.governance.ledger.event_ledger import validate_event_chain_integrity
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    validate_verification_execution_plan_artifact,
)
from test_orchestration_delegation_run import SMALL, _ladder4_candidate, _obligation, _seal

SESSION = "plan3b2"


def _server(
    tmp_path: Path,
    *,
    target_name: str = "generic",
    session_id: str = SESSION,
    builder_root: Path | None = None,
) -> tuple[GovernedMcpServer, Path, Path]:
    target = tmp_path / "target"
    target.mkdir(exist_ok=True)
    root = builder_root or (tmp_path / ".builder")
    return (
        GovernedMcpServer(
            session_id=session_id,
            builder_root=root,
            target_root=target,
            target_name=target_name,
        ),
        target,
        root,
    )


def _call(server: GovernedMcpServer, name: str, arguments: dict | None = None, *, req_id: int = 1) -> dict:
    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
    )
    assert response is not None
    return response["result"]


def _domain(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


def _mcp_dir(builder_root: Path, session_id: str = SESSION) -> Path:
    return builder_root / "sessions" / session_id / "mcp"


def _events_dir(builder_root: Path, session_id: str = SESSION) -> Path:
    return builder_root / "sessions" / session_id / "events"


def _last_receipt(builder_root: Path, session_id: str = SESSION) -> dict:
    paths = sorted(_mcp_dir(builder_root, session_id).glob("*_receipt.json"))
    assert paths
    return json.loads(paths[-1].read_text(encoding="utf-8"))


def _last_event(builder_root: Path, session_id: str = SESSION) -> dict:
    paths = sorted(_events_dir(builder_root, session_id).glob("*.json"))
    assert paths
    return json.loads(paths[-1].read_text(encoding="utf-8"))


def _normalized_plan(plan: dict) -> dict:
    normalized = dict(plan)
    normalized.pop("generated_at", None)
    normalized.pop("artifact_root", None)
    normalized.pop("verification_execution_plan_digest", None)
    return normalized


def _completed_delegation_run(tmp_path: Path) -> tuple[Path, Path]:
    candidate, policy, _policy_path, _work_plan, _work_plan_path = _ladder4_candidate(tmp_path)
    approval, candidate_path, approval_path = _seal(tmp_path, candidate)
    obligation_path, _ = _obligation(
        tmp_path,
        0,
        seal_digest=approval["approval_digest"],
        lpd=policy["lane_policy_digest"],
        expected_kind=PROPOSAL_ONLY_RESULT_CONTRACT_KIND,
        evidence=[],
        subagent="repo_mapper",
        budget=SMALL,
    )
    builder_root = tmp_path / "runs"
    output_dir = builder_root / "status-run"
    summary = run_deepagents_approved_candidate(
        candidate_path=candidate_path,
        approval_path=approval_path,
        output_dir=output_dir,
        obligation_paths=[obligation_path],
    )
    assert summary["status"] == "COMPLETED"
    return builder_root, output_dir


def test_tools_list_adds_only_status_and_passive_planning_surfaces(tmp_path: Path) -> None:
    server, _, _ = _server(tmp_path)
    response = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert response is not None
    names = {item["name"] for item in response["result"]["tools"]}
    assert {"delegation_status", "verification_plan"} <= names
    assert not {
        "verification_approve",
        "approve_verification",
        "verification_execute",
        "run_verification",
        "verification_run",
    } & names


@pytest.mark.parametrize(
    ("target_name", "verification_profile"),
    [("generic", "generic_basic"), ("builder", "builder_full"), ("core", "core_smoke")],
)
def test_verification_plan_is_target_bound_passive_and_persisted(
    tmp_path: Path, target_name: str, verification_profile: str
) -> None:
    server, target, builder_root = _server(tmp_path, target_name=target_name)
    args = {"verification_profile": verification_profile, "target_head_sha": "a" * 40, "tree_clean": True}

    result = _call(server, "verification_plan", args)

    assert result["isError"] is False, result
    plan = _domain(result)
    assert validate_verification_execution_plan_artifact(plan) == []
    assert plan["target_profile"] == target_name
    assert plan["verification_profile"] == verification_profile
    assert plan["target_repo"] == str(target.resolve())
    assert plan["target_head_sha"] == "a" * 40
    assert plan["tree_clean"] is True
    assert plan["plan_mode"] == "planned_only"
    assert plan["approval_required"] is True
    assert plan["execution_enabled"] is False
    assert plan["artifact_is_authority"] is False
    assert plan["disabled_authority"]["subprocess_execution"] == "disabled"
    assert plan["disabled_authority"]["mcp_tool_invocation"] == "disabled"
    assert plan["plan_scope"]["scope_id"] == "plan_set_3b2_mcp_passive_verification_plan"
    assert "caller-supplied target_head_sha and tree_clean metadata" in plan["plan_scope"]["includes"]
    assert "independent Git-state observation" in plan["plan_scope"]["excludes"]
    assert "verification approval minting" in plan["plan_scope"]["excludes"]
    assert "verification execution" in plan["plan_scope"]["excludes"]

    plan_path = Path(plan["artifact_root"]) / "verification-execution-plan.json"
    assert plan_path.is_file()
    plan_path.relative_to(builder_root.resolve())
    persisted = json.loads(plan_path.read_text(encoding="utf-8"))
    assert persisted == plan

    receipt = _last_receipt(builder_root)
    assert receipt["service"] == "verification_plan"
    assert receipt["status"] == "succeeded"
    assert receipt["arguments"] == args
    assert validate_mcp_service_receipt(receipt) == []
    assert validate_event_chain_integrity(_events_dir(builder_root))["valid"]


def test_verification_plan_transport_matches_direct_service_semantics(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    args = {"verification_profile": "generic_basic", "target_head_sha": "b" * 40, "tree_clean": False}

    direct_root = tmp_path / "direct-artifacts"
    direct_receipt, _, _ = run_service(
        tool_name="verification_plan",
        arguments=args,
        session_id="direct-plan",
        builder_root=direct_root,
        target_root=target,
        target_name="generic",
    )

    transport_root = tmp_path / "transport-artifacts"
    server = GovernedMcpServer(
        session_id="transport-plan",
        builder_root=transport_root,
        target_root=target,
        target_name="generic",
    )
    transport = _call(server, "verification_plan", args)

    assert transport["isError"] is False
    assert _normalized_plan(_domain(transport)) == _normalized_plan(direct_receipt["result"])


@pytest.mark.parametrize(
    "arguments",
    [
        {"verification_profile": "generic_basic", "target_head_sha": "bad", "tree_clean": True},
        {"verification_profile": "generic_basic", "target_head_sha": "a" * 40, "tree_clean": "yes"},
        {"verification_profile": "core_smoke", "target_head_sha": "a" * 40, "tree_clean": True},
    ],
)
def test_invalid_verification_plan_requests_are_denied_and_never_mint_approval(
    tmp_path: Path, arguments: dict
) -> None:
    server, _, builder_root = _server(tmp_path, target_name="generic")

    result = _call(server, "verification_plan", arguments)

    assert result["isError"] is True
    assert result["_meta"]["status"] == "denied"
    assert _last_receipt(builder_root)["status"] == "denied"
    assert _last_event(builder_root)["event_type"] == "mcp_call_denied"
    names = [path.name for path in builder_root.rglob("*.json")]
    assert not any("approval" in name or "execution-receipt" in name for name in names)


def test_verification_plan_service_does_not_invoke_subprocess_or_network(tmp_path: Path) -> None:
    server, _, _ = _server(tmp_path)
    args = {"verification_profile": "generic_basic", "target_head_sha": "c" * 40, "tree_clean": True}

    with (
        patch.object(subprocess, "run", side_effect=AssertionError("subprocess.run must not be called")),
        patch.object(subprocess, "Popen", side_effect=AssertionError("subprocess.Popen must not be called")),
        patch.object(socket, "create_connection", side_effect=AssertionError("network must not be called")),
    ):
        result = _call(server, "verification_plan", args)

    assert result["isError"] is False, result


def test_corrupt_mcp_ledger_refuses_plan_before_plan_artifact_write(tmp_path: Path) -> None:
    server, _, builder_root = _server(tmp_path)
    assert _call(server, "repo_map")["isError"] is False
    events_dir = _events_dir(builder_root)
    wal = events_dir / "events.wal"
    if wal.exists():
        wal.unlink()
    event_path = sorted(events_dir.glob("*.json"))[0]
    event = json.loads(event_path.read_text(encoding="utf-8"))
    event["sequence"] = 9
    event_path.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = _call(
        server,
        "verification_plan",
        {"verification_profile": "generic_basic", "target_head_sha": "e" * 40, "tree_clean": True},
        req_id=2,
    )

    assert result["isError"] is True
    assert result["_meta"]["status"] == "failed"
    assert result["_meta"]["typed_error"] == "CorruptLedgerError"
    assert result["_meta"]["evidence_appended"] is False
    assert not list(_mcp_dir(builder_root).glob("verification-plan/*/verification-execution-plan.json"))


def test_delegation_status_reads_exact_governed_run_and_matches_direct_service(tmp_path: Path) -> None:
    builder_root, output_dir = _completed_delegation_run(tmp_path)
    server, _, _ = _server(tmp_path, builder_root=builder_root, session_id="transport-status")
    args = {"run_output_dir": output_dir.name}

    transport = _call(server, "delegation_status", args)

    assert transport["isError"] is False, transport
    board = _domain(transport)
    assert board["run_status"] == "COMPLETED"
    assert board["chain_valid"] is True
    assert len(board["rows"]) == 1
    assert board["rows"][0]["board_state"] == "SATISFIED"

    direct_receipt, _, _ = run_service(
        tool_name="delegation_status",
        arguments=args,
        session_id="direct-status",
        builder_root=builder_root,
        target_root=tmp_path / "target",
        target_name="generic",
    )
    assert direct_receipt["result"] == board
    assert validate_mcp_service_receipt(direct_receipt) == []


def test_delegation_status_refuses_path_escape(tmp_path: Path) -> None:
    builder_root = tmp_path / ".builder"
    builder_root.mkdir()
    outside = tmp_path / "outside-run"
    outside.mkdir()
    server, _, _ = _server(tmp_path, builder_root=builder_root)

    result = _call(server, "delegation_status", {"run_output_dir": str(outside)})

    assert result["isError"] is True
    assert result["_meta"]["status"] == "denied"
    assert _last_event(builder_root)["event_type"] == "mcp_call_denied"


def test_delegation_status_reports_tampered_chain_as_failed_evidence(tmp_path: Path) -> None:
    builder_root, output_dir = _completed_delegation_run(tmp_path)
    event_path = sorted((output_dir / "events").glob("event-*.json"))[0]
    event = json.loads(event_path.read_text(encoding="utf-8"))
    event["event_digest"] = "0" * 64
    event_path.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    server, _, _ = _server(tmp_path, builder_root=builder_root)

    result = _call(server, "delegation_status", {"run_output_dir": output_dir.name})

    assert result["isError"] is True
    assert result["_meta"]["status"] == "failed"
    board = _domain(result)
    assert board["chain_valid"] is False
    assert board["chain_errors"]
    assert _last_receipt(builder_root)["status"] == "failed"
    assert _last_event(builder_root)["event_type"] == "mcp_call_failed"


def test_3b2_calls_do_not_change_existing_gated_mutation_behavior(tmp_path: Path) -> None:
    server, target, _ = _server(tmp_path)
    original = target / "original.txt"
    original.write_text("unchanged", encoding="utf-8")

    verification = _call(
        server,
        "verification_plan",
        {"verification_profile": "generic_basic", "target_head_sha": "d" * 40, "tree_clean": True},
    )
    shell = _call(server, "run_shell", {"cmd": "echo should-not-run"}, req_id=2)

    assert verification["isError"] is False
    assert shell["isError"] is True
    assert shell["_meta"]["gated"] is True
    assert shell["_meta"]["refused"] is True
    assert original.read_text(encoding="utf-8") == "unchanged"
