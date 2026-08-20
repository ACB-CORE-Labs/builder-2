from __future__ import annotations

import datetime
import json
import multiprocessing
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from builder_ii.adapters.mcp.governed_call import TOOL_SPECS
from builder_ii.adapters.mcp.governed_services import ServiceDenied, run_service, validate_mcp_service_receipt
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.core.config_schema import digest_jsonable
from builder_ii.governance.ledger.verification_approval_consumption import (
    ApprovalConsumptionError,
    consume_approval,
    load_consumption_chain,
)
from builder_ii.lifecycle.candidate.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)


def _artifacts(tmp_path: Path, *, expires_at: str = "2099-01-01T00:00:00Z") -> tuple[Path, Path, Path, Path]:
    target = tmp_path / "target"
    target.mkdir(parents=True)
    (target / ".git").mkdir()
    builder_root = target / ".builder"
    artifact_root = builder_root / "verification"
    artifact_root.mkdir(parents=True)
    plan = finalize_verification_execution_plan(
        target_head_sha="a" * 40,
        tree_clean=True,
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(target),
        artifact_root=str(artifact_root),
        generated_at="2026-08-20T00:00:00+00:00",
    )
    plan_path = artifact_root / "plan.json"
    write_verification_execution_plan(plan, plan_path)
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="human_operator",
        approval_reason="Approve one bounded platform status verification lane.",
        approved_command_profiles=["platform_status"],
        approved_step_ids=["platform_status"],
        generated_at="2026-08-20T00:01:00+00:00",
        expires_at=expires_at,
    )
    approval_path = artifact_root / "approval.json"
    write_verification_execution_approval(approval, approval_path)
    return target, builder_root, plan_path, approval_path


def _fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    if args[:3] == ["git", "status", "--porcelain=v1"]:
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")
    if args[:2] == ["git", "rev-parse"]:
        return subprocess.CompletedProcess(args, 0, stdout=f"{'a' * 40}\nmain\n", stderr="")
    assert kwargs["shell"] is False
    assert "builder_ii.verification_runner_entrypoints" in args
    return subprocess.CompletedProcess(args, 0, stdout="builder-II platform status\n", stderr="")


def _consume_claim_worker(root_value: str, digest_char: str, start: Any, results: Any) -> None:
    import builder_ii.governance.ledger.verification_approval_consumption as consumption

    original_load = consumption.load_consumption_chain

    def delayed_load(root: Path) -> list[dict[str, Any]]:
        records = original_load(root)
        time.sleep(0.1)
        return records

    consumption.load_consumption_chain = delayed_load
    start.wait()
    try:
        record = consumption.consume_approval(
            root=Path(root_value),
            approval={
                "approval_id": digest_char * 64,
                "verification_execution_approval_digest": digest_char * 64,
            },
            plan={"verification_execution_plan_digest": "f" * 64},
            now=datetime.datetime.now(datetime.timezone.utc),
        )
        results.put(("ok", record["ledger_index"]))
    except Exception as exc:  # pragma: no cover - surfaced by the parent assertion
        results.put(("error", repr(exc)))


def test_direct_service_executes_canonical_runner_once_and_consumes_approval(monkeypatch: Any, tmp_path: Path) -> None:
    target, root, plan_path, approval_path = _artifacts(tmp_path)
    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", _fake_run)
    arguments = {"plan_path": str(plan_path), "approval_path": str(approval_path)}
    receipt, _, _ = run_service(
        tool_name="verification_execute", arguments=arguments, session_id="direct",
        builder_root=root, target_root=target, target_name="builder",
    )
    assert receipt["status"] == "succeeded"
    assert receipt["result"]["receipt_status"] == "EXECUTED"
    assert receipt["governance"]["bounded_subprocess_execution"] == "HITL_APPROVAL_GATED"
    assert receipt["governance"]["shell_execution"] == "DISABLED"
    assert validate_mcp_service_receipt(receipt) == []

    second, _, _ = run_service(
        tool_name="verification_execute", arguments=arguments, session_id="direct",
        builder_root=root, target_root=target, target_name="builder",
    )
    assert second["status"] == "denied"
    assert "already been consumed" in " ".join(second["result"]["errors"])


def test_distinct_concurrent_approval_claims_are_serialized(tmp_path: Path) -> None:
    context = multiprocessing.get_context("fork")
    start = context.Event()
    results = context.Queue()
    root = tmp_path / "approval-consumption"
    processes = [
        context.Process(target=_consume_claim_worker, args=(str(root), char, start, results))
        for char in ("a", "b", "c", "d")
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(timeout=10)
        assert process.exitcode == 0

    outcomes = [results.get(timeout=2) for _ in processes]
    assert sorted(outcomes) == [("ok", 1), ("ok", 2), ("ok", 3), ("ok", 4)]
    assert [record["ledger_index"] for record in load_consumption_chain(root)] == [1, 2, 3, 4]


def test_duplicate_approval_claim_is_corrupt_even_with_valid_chain_digests(tmp_path: Path) -> None:
    root = tmp_path / "approval-consumption"
    now = datetime.datetime.now(datetime.timezone.utc)
    first = consume_approval(
        root=root,
        approval={"approval_id": "a" * 64, "verification_execution_approval_digest": "b" * 64},
        plan={"verification_execution_plan_digest": "f" * 64},
        now=now,
    )
    consume_approval(
        root=root,
        approval={"approval_id": "c" * 64, "verification_execution_approval_digest": "d" * 64},
        plan={"verification_execution_plan_digest": "f" * 64},
        now=now,
    )
    second_path = sorted(root.glob("*.json"))[1]
    second = json.loads(second_path.read_text(encoding="utf-8"))
    second["approval_id"] = first["approval_id"]
    second["approval_digest"] = first["approval_digest"]
    second["verification_approval_consumption_digest"] = digest_jsonable(
        second, digest_key="verification_approval_consumption_digest"
    )
    second_path.write_text(json.dumps(second, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises(ApprovalConsumptionError, match="duplicate approval claim"):
        load_consumption_chain(root)


def test_expired_approval_and_corrupt_consumption_fail_before_profile_execution(monkeypatch: Any, tmp_path: Path) -> None:
    target, root, plan_path, approval_path = _artifacts(tmp_path, expires_at="2026-08-20T00:02:00Z")
    calls: list[list[str]] = []
    monkeypatch.setattr(
        "builder_ii.verification_execution_runner.subprocess.run",
        lambda args, **kwargs: calls.append(list(args)) or _fake_run(args, **kwargs),
    )
    receipt, _, _ = run_service(
        tool_name="verification_execute",
        arguments={"plan_path": str(plan_path), "approval_path": str(approval_path)},
        session_id="expired", builder_root=root, target_root=target, target_name="builder",
    )
    assert receipt["status"] == "denied"
    assert "expired" in " ".join(receipt["result"]["errors"])
    assert calls == []

    target2, root2, plan2, approval2 = _artifacts(tmp_path / "corrupt")
    consumption = root2 / "verification" / "approval-consumption"
    consumption.mkdir()
    (consumption / "000001-bad.json").write_text("{}\n", encoding="utf-8")
    corrupt, _, _ = run_service(
        tool_name="verification_execute",
        arguments={"plan_path": str(plan2), "approval_path": str(approval2)},
        session_id="corrupt", builder_root=root2, target_root=target2, target_name="builder",
    )
    assert corrupt["status"] == "denied"
    assert "corrupt approval consumption" in " ".join(corrupt["result"]["errors"])


@pytest.mark.parametrize(
    "arguments",
    [
        {"plan_path": "../plan.json", "approval_path": "approval.json"},
        {"plan_path": "plan.json", "approval_path": "approval.json", "shell": "echo pwned"},
    ],
)
def test_path_escape_and_authority_smuggling_are_denied(tmp_path: Path, arguments: dict[str, Any]) -> None:
    target, root, _, _ = _artifacts(tmp_path)
    with pytest.raises(ServiceDenied):
        run_service(
            tool_name="verification_execute", arguments=arguments, session_id="denied",
            builder_root=root, target_root=target, target_name="builder",
        )


def test_absolute_and_symlink_path_escapes_are_denied(tmp_path: Path) -> None:
    target, root, _plan_path, approval_path = _artifacts(tmp_path)
    outside = tmp_path / "outside-plan.json"
    outside.write_text("{}\n", encoding="utf-8")
    escaping_link = root / "escaping-plan.json"
    escaping_link.symlink_to(outside)

    for plan_path in (outside, escaping_link):
        with pytest.raises(ServiceDenied, match="server-controlled Builder-II artifact root"):
            run_service(
                tool_name="verification_execute",
                arguments={"plan_path": str(plan_path), "approval_path": str(approval_path)},
                session_id="path-escape",
                builder_root=root,
                target_root=target,
                target_name="builder",
            )


def test_mcp_transport_matches_direct_result_shape_and_mints_no_approval(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", _fake_run)

    direct_target, direct_root, direct_plan, direct_approval = _artifacts(tmp_path / "direct")
    direct_receipt, _, _ = run_service(
        tool_name="verification_execute",
        arguments={"plan_path": str(direct_plan), "approval_path": str(direct_approval)},
        session_id="direct-equivalence", builder_root=direct_root,
        target_root=direct_target, target_name="builder",
    )

    target, root, plan_path, approval_path = _artifacts(tmp_path / "mcp")
    server = GovernedMcpServer(
        session_id="transport", builder_root=root, target_root=target, target_name="builder"
    )
    response = server.handle_request({
        "jsonrpc": "2.0", "id": 1, "method": "tools/call",
        "params": {"name": "verification_execute", "arguments": {
            "plan_path": str(plan_path), "approval_path": str(approval_path),
        }},
    })
    assert response is not None
    result = response["result"]
    assert result["isError"] is False
    domain = json.loads(result["content"][0]["text"])
    assert domain["receipt_status"] == "EXECUTED"
    assert domain["requested_profile"] == "platform_status"
    for field in (
        "valid", "receipt_status", "requested_profile", "executed_steps", "skipped_steps",
        "workspace_mutation_detected", "errors",
    ):
        assert domain[field] == direct_receipt["result"][field]
    assert "verification_approve" not in TOOL_SPECS
    assert "approve_and_run_verification" not in TOOL_SPECS


def test_artifact_swap_after_service_validation_is_denied_before_subprocess(monkeypatch: Any, tmp_path: Path) -> None:
    target, root, plan_path, approval_path = _artifacts(tmp_path)
    from builder_ii.adapters.mcp import governed_services

    original_runner = governed_services.run_approved_verification
    calls: list[list[str]] = []

    def swapping_runner(**kwargs: Any) -> dict[str, Any]:
        replacement_plan = finalize_verification_execution_plan(
            target_head_sha="a" * 40,
            tree_clean=True,
            target_profile="builder",
            verification_profile="builder_full",
            target_repo=str(target),
            artifact_root=str(root / "verification"),
            generated_at="2026-08-20T00:00:30+00:00",
        )
        write_verification_execution_plan(replacement_plan, plan_path)
        replacement_approval = finalize_verification_execution_approval(
            plan=replacement_plan,
            plan_path=str(plan_path),
            approval_actor="human_operator",
            approval_reason="Approve one bounded platform status verification lane.",
            approved_command_profiles=["platform_status"],
            approved_step_ids=["platform_status"],
            generated_at="2026-08-20T00:01:30+00:00",
            expires_at="2099-01-01T00:00:00Z",
        )
        write_verification_execution_approval(replacement_approval, approval_path)
        return original_runner(**kwargs)

    monkeypatch.setattr(governed_services, "run_approved_verification", swapping_runner)
    monkeypatch.setattr(
        "builder_ii.verification_execution_runner.subprocess.run",
        lambda args, **kwargs: calls.append(list(args)) or _fake_run(args, **kwargs),
    )
    with pytest.raises(RuntimeError, match="caller-validated artifacts"):
        run_service(
            tool_name="verification_execute",
            arguments={"plan_path": str(plan_path), "approval_path": str(approval_path)},
            session_id="artifact-swap",
            builder_root=root,
            target_root=target,
            target_name="builder",
        )
    assert calls == []


def test_runner_receipt_byte_corruption_is_not_advertised(monkeypatch: Any, tmp_path: Path) -> None:
    target, root, plan_path, approval_path = _artifacts(tmp_path)
    from builder_ii.adapters.mcp import governed_services

    original_runner = governed_services.run_approved_verification

    def corrupting_runner(**kwargs: Any) -> dict[str, Any]:
        receipt = original_runner(**kwargs)
        output = Path(kwargs["output"])
        stored = json.loads(output.read_text(encoding="utf-8"))
        stored["errors"] = ["tampered after runner return"]
        output.write_text(json.dumps(stored, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", _fake_run)
    monkeypatch.setattr(governed_services, "run_approved_verification", corrupting_runner)
    with pytest.raises(RuntimeError, match="receipt bytes do not match"):
        run_service(
            tool_name="verification_execute",
            arguments={"plan_path": str(plan_path), "approval_path": str(approval_path)},
            session_id="receipt-corruption",
            builder_root=root,
            target_root=target,
            target_name="builder",
        )


def test_runner_postflight_reference_corruption_is_not_advertised(monkeypatch: Any, tmp_path: Path) -> None:
    target, root, plan_path, approval_path = _artifacts(tmp_path)
    from builder_ii.adapters.mcp import governed_services

    original_runner = governed_services.run_approved_verification

    def corrupting_runner(**kwargs: Any) -> dict[str, Any]:
        receipt = original_runner(**kwargs)
        output = Path(kwargs["output"])
        postflight_path = output.with_name(output.stem + "-postflight.json")
        postflight = json.loads(postflight_path.read_text(encoding="utf-8"))
        postflight["receipt_ref"] = str(output.with_name("other-receipt.json"))
        postflight["postflight_digest"] = digest_jsonable(postflight, digest_key="postflight_digest")
        postflight_path.write_text(json.dumps(postflight, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return receipt

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", _fake_run)
    monkeypatch.setattr(governed_services, "run_approved_verification", corrupting_runner)
    with pytest.raises(RuntimeError, match="receipt_ref does not match"):
        run_service(
            tool_name="verification_execute",
            arguments={"plan_path": str(plan_path), "approval_path": str(approval_path)},
            session_id="postflight-corruption",
            builder_root=root,
            target_root=target,
            target_name="builder",
        )
