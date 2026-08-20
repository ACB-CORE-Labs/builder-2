from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.adapters.mcp.governed_services import ServiceDenied, run_service, validate_mcp_service_receipt
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.governance.hitl.hitl_patch_proposal import (
    MAX_UNIFIED_DIFF_BYTES,
    create_bound_hitl_patch_proposal,
    validate_hitl_patch_proposal,
)

DIFF = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n"


def _receipt() -> dict[str, object]:
    return {
        "kind": "builder_ii.demo_verification_receipt",
        "schema_version": 1,
        "label": "before_apply",
        "receipt_status": "EXECUTED",
        "checks": [{"name": "passive", "status": "PASS"}],
        "governance": {
            "model_execution": "DISABLED",
            "source_writes": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def _setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    target = tmp_path / "target"
    builder_root = tmp_path / "builder-artifacts"
    target.mkdir()
    builder_root.mkdir()
    receipt_path = builder_root / "verification.json"
    receipt_path.write_text(json.dumps(_receipt(), sort_keys=True) + "\n", encoding="utf-8")
    return target, builder_root, receipt_path


def _arguments(receipt_path: Path, **updates: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "unified_diff": DIFF,
        "description": "Change one line",
        "reason": "qualification",
        "target_head_sha": "a" * 40,
        "verification_receipt_path": str(receipt_path),
    }
    arguments.update(updates)
    return arguments


def _target_fingerprint(target: Path) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (str(path.relative_to(target)), hashlib.sha256(path.read_bytes()).hexdigest())
            for path in target.rglob("*")
            if path.is_file()
        )
    )


def test_canonical_binding_derives_exact_digests_and_scope(tmp_path: Path) -> None:
    receipt_bytes = b"exact receipt bytes\r\n"
    proposal = create_bound_hitl_patch_proposal(
        target_name="generic",
        generic_repo=tmp_path,
        patch_description="description",
        reason="reason",
        unified_diff=DIFF,
        target_head_sha="A" * 40,
        verification_receipt_bytes=receipt_bytes,
    )
    assert validate_hitl_patch_proposal(proposal) == []
    assert proposal["patch_digest"] == hashlib.sha256(DIFF.encode("utf-8")).hexdigest()
    assert proposal["verification_receipt_file_sha256"] == hashlib.sha256(receipt_bytes).hexdigest()
    assert proposal["target_head_sha"] == "a" * 40
    assert proposal["exact_scope"]["files"] == [{"old_path": "file.txt", "new_path": "file.txt"}]

    changed = create_bound_hitl_patch_proposal(
        target_name="generic",
        generic_repo=tmp_path,
        patch_description="description",
        reason="reason",
        unified_diff=DIFF.replace("new", "New", 1),
        target_head_sha="a" * 40,
        verification_receipt_bytes=receipt_bytes + b"!",
    )
    assert changed["patch_digest"] != proposal["patch_digest"]
    assert changed["verification_receipt_file_sha256"] != proposal["verification_receipt_file_sha256"]


@pytest.mark.parametrize(
    "bad_diff",
    [
        "",
        "not a diff\n",
        "--- /absolute\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
        "--- a/../x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
        "diff --cc x\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-a\n+b\n",
        "GIT binary patch\n",
    ],
)
def test_canonical_binding_rejects_ambiguous_diff_forms(tmp_path: Path, bad_diff: str) -> None:
    with pytest.raises(ValueError):
        create_bound_hitl_patch_proposal(
            target_name="generic",
            generic_repo=tmp_path,
            patch_description="description",
            reason="reason",
            unified_diff=bad_diff,
            target_head_sha="a" * 40,
            verification_receipt_bytes=b"receipt",
        )


def test_mcp_success_is_passive_bound_and_evidence_complete(tmp_path: Path) -> None:
    target, builder_root, receipt_path = _setup(tmp_path)
    (target / "file.txt").write_text("old\n", encoding="utf-8")
    before = _target_fingerprint(target)
    with (
        patch("builder_ii.governance.hitl.hitl_patch_approval.create_hitl_patch_approval") as approve,
        patch("builder_ii.governance.hitl.hitl_patch_apply.apply_hitl_patch") as apply,
        patch("builder_ii.governance.hitl.hitl_patch_apply.rollback_hitl_patch") as rollback,
        patch.object(subprocess, "run") as run,
        patch.object(subprocess, "Popen") as popen,
        patch.object(os, "system") as system,
    ):
        receipt, receipt_artifact, event = run_service(
            tool_name="patch_proposal",
            arguments=_arguments(receipt_path),
            session_id="success",
            builder_root=builder_root,
            target_root=target,
            target_name="generic",
        )
    assert approve.call_count == apply.call_count == rollback.call_count == 0
    assert run.call_count == popen.call_count == system.call_count == 0
    assert _target_fingerprint(target) == before
    assert receipt["status"] == "succeeded"
    assert validate_mcp_service_receipt(receipt) == []
    assert receipt["result"]["decision"] == "HUMAN_APPROVAL_REQUIRED"
    assert receipt["result"]["target"]["repo"] == str(target.resolve())
    assert receipt["result"]["patch_digest"] == hashlib.sha256(DIFF.encode()).hexdigest()
    proposal_path = Path(receipt["result"]["proposal_ref"]["path"])
    assert proposal_path.is_relative_to(builder_root.resolve())
    assert receipt_artifact.is_file() and event.is_file()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("patch_digest", "0" * 64),
        ("target_repo", "/tmp/elsewhere"),
        ("output_path", "proposal.json"),
        ("approval", {"approved": True}),
        ("command", "git apply patch"),
        ("environment", {"BUILDER_MCP_GOVERNED_APPLY": "1"}),
        ("apply", True),
    ],
)
def test_authority_shaped_extra_arguments_fail_before_proposal_write(
    tmp_path: Path, field: str, value: object
) -> None:
    target, builder_root, receipt_path = _setup(tmp_path)
    before = _target_fingerprint(target)
    with pytest.raises(ServiceDenied):
        run_service(
            tool_name="patch_proposal",
            arguments=_arguments(receipt_path, **{field: value}),
            session_id="denied",
            builder_root=builder_root,
            target_root=target,
            target_name="generic",
        )
    assert _target_fingerprint(target) == before
    assert not list(builder_root.rglob("hitl-patch-proposal.json"))


def test_receipt_path_and_size_fail_closed(tmp_path: Path) -> None:
    target, builder_root, receipt_path = _setup(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    symlink = builder_root / "receipt-link.json"
    symlink.symlink_to(receipt_path)
    for invalid in (outside, symlink, "../outside.json"):
        with pytest.raises(ServiceDenied):
            run_service(
                tool_name="patch_proposal",
                arguments=_arguments(Path(invalid)),
                session_id="badpath",
                builder_root=builder_root,
                target_root=target,
                target_name="generic",
            )
    with pytest.raises(ServiceDenied):
        run_service(
            tool_name="patch_proposal",
            arguments=_arguments(receipt_path, unified_diff="x" * (MAX_UNIFIED_DIFF_BYTES + 1)),
            session_id="oversize",
            builder_root=builder_root,
            target_root=target,
            target_name="generic",
        )
    with pytest.raises(ServiceDenied):
        run_service(
            tool_name="patch_proposal",
            arguments=_arguments(receipt_path, unified_diff="\ud800"),
            session_id="invalidunicode",
            builder_root=builder_root,
            target_root=target,
            target_name="generic",
        )


def test_patch_proposal_refuses_artifact_root_beneath_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    builder_root = target / ".builder"
    builder_root.mkdir(parents=True)
    receipt_path = builder_root / "verification.json"
    receipt_path.write_text(json.dumps(_receipt()), encoding="utf-8")
    before = _target_fingerprint(target)
    with pytest.raises(ServiceDenied, match="outside the target repository"):
        run_service(
            tool_name="patch_proposal",
            arguments=_arguments(receipt_path),
            session_id="nested",
            builder_root=builder_root,
            target_root=target,
            target_name="generic",
        )
    assert _target_fingerprint(target) == before


def test_corrupt_ledger_and_proposal_write_failure_never_advertise_ready(tmp_path: Path) -> None:
    target, builder_root, receipt_path = _setup(tmp_path)
    server = GovernedMcpServer(
        session_id="corrupt", builder_root=builder_root, target_root=target, target_name="generic"
    )
    event_path = builder_root / "sessions" / "corrupt" / "events" / "001_bad.json"
    event_path.parent.mkdir(parents=True)
    event_path.write_text(json.dumps({"kind": "builder_ii.event_record"}) + "\n", encoding="utf-8")
    response = server.handle_request(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": {"name": "patch_proposal", "arguments": _arguments(receipt_path)}}
    )
    assert response is not None and response["result"]["isError"] is True
    assert "HUMAN_APPROVAL_REQUIRED" not in json.dumps(response)

    clean = GovernedMcpServer(
        session_id="writefail", builder_root=builder_root, target_root=target, target_name="generic"
    )
    with patch("builder_ii.adapters.mcp.governed_services.write_hitl_patch_proposal", side_effect=OSError("disk full")):
        response = clean.handle_request(
            {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "patch_proposal", "arguments": _arguments(receipt_path)}}
        )
    assert response is not None and response["result"]["isError"] is True
    assert "HUMAN_APPROVAL_REQUIRED" not in json.dumps(response)


def test_inventory_has_only_passive_patch_surface_and_env_cannot_reactivate_legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target, builder_root, _ = _setup(tmp_path)
    monkeypatch.setenv("BUILDER_MCP_GOVERNED_APPLY", "1")
    server = GovernedMcpServer(
        session_id="inventory", builder_root=builder_root, target_root=target, target_name="generic"
    )
    listed = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}})
    assert listed is not None
    names = {tool["name"] for tool in listed["result"]["tools"]}
    assert "patch_proposal" in names
    assert not ({"propose_patch", "run_shell", "approve_patch", "apply_patch", "rollback"} & names)
    for retired in ("propose_patch", "run_shell", "approve_patch", "apply_patch", "rollback"):
        response = server.handle_request(
            {"jsonrpc": "2.0", "id": retired, "method": "tools/call", "params": {"name": retired, "arguments": {}}}
        )
        assert response is not None
        assert response["result"]["_meta"]["inventory_admitted"] is False


def test_transport_has_no_legacy_apply_import_or_dispatch() -> None:
    import inspect

    import builder_ii.adapters.mcp.server as server_module

    source = inspect.getsource(server_module)
    assert "governed_apply" not in source
    assert "run_gated_patch_apply" not in source
    assert "apply_hitl_patch" not in source
    assert not (Path(server_module.__file__).parent / "governed_apply.py").exists()
