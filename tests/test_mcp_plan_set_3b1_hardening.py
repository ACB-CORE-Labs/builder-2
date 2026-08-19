"""Adversarial qualification for open-source-v1 Plan Set 3B1.

These tests pin the generic-first MCP service seam itself: transport parity, target/config
identity, bounded reads/preparation, evidence tamper resistance, and fail-closed ledger
continuation. They deliberately do not exercise or widen mutation/HITL authority.
"""

from __future__ import annotations

import copy
import json
import os
import socket
import subprocess
from pathlib import Path

import pytest

from builder_ii.adapters.mcp.governed_services import run_service, validate_mcp_service_receipt
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.governance.ledger.event_ledger import (
    EVENT_RECORD_KIND,
    create_event_record,
    validate_event_chain_integrity,
    write_event_record,
)
from builder_ii.governance.ledger.workflow_records import canonical_digest

SESSION = "plan3b1"


def _layout(tmp_path: Path) -> tuple[Path, Path]:
    target = tmp_path / "target"
    target.mkdir(exist_ok=True)
    builder_root = tmp_path / "builder-artifacts"
    return target, builder_root


def _server(
    tmp_path: Path,
    *,
    target_name: str = "generic",
    config_root: Path | None = None,
) -> tuple[GovernedMcpServer, Path, Path]:
    target, builder_root = _layout(tmp_path)
    return (
        GovernedMcpServer(
            session_id=SESSION,
            builder_root=builder_root,
            target_root=target,
            target_name=target_name,
            config_root=config_root,
        ),
        target,
        builder_root,
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


def _session_dir(builder_root: Path) -> Path:
    return builder_root / "sessions" / SESSION


def _events_dir(builder_root: Path) -> Path:
    return _session_dir(builder_root) / "events"


def _mcp_dir(builder_root: Path) -> Path:
    return _session_dir(builder_root) / "mcp"


def _receipts(builder_root: Path) -> list[Path]:
    return sorted(_mcp_dir(builder_root).glob("*_receipt.json"))


def _events(builder_root: Path) -> list[Path]:
    return sorted(_events_dir(builder_root).glob("*.json"))


def _last_receipt(builder_root: Path) -> dict:
    paths = _receipts(builder_root)
    assert paths
    return json.loads(paths[-1].read_text(encoding="utf-8"))


def _last_event(builder_root: Path) -> dict:
    paths = _events(builder_root)
    assert paths
    return json.loads(paths[-1].read_text(encoding="utf-8"))


def _domain(result: dict) -> dict:
    return json.loads(result["content"][0]["text"])


@pytest.mark.parametrize("target_name", ["generic", "builder", "core"])
def test_transport_preserves_generic_first_target_identity(tmp_path: Path, target_name: str) -> None:
    server, target, builder_root = _server(tmp_path, target_name=target_name)
    (target / "alpha.py").write_text("print('alpha')\n", encoding="utf-8")

    result = _call(server, "repo_map")

    assert result["isError"] is False
    domain = _domain(result)
    assert domain["target_name"] == target_name
    assert domain["repo_path"] == str(target.resolve())
    receipt = _last_receipt(builder_root)
    assert receipt["target_profile"] == target_name
    assert validate_mcp_service_receipt(receipt) == []


def test_builder_artifact_root_is_independent_from_target_root(tmp_path: Path) -> None:
    server, target, builder_root = _server(tmp_path)
    (target / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
    builder_root.mkdir()
    (builder_root / "must-not-be-mapped.txt").write_text("artifact", encoding="utf-8")

    result = _call(server, "repo_map")
    domain = _domain(result)

    assert domain["repo_path"] == str(target.resolve())
    paths = {item["path"] for item in domain["files"]}
    assert "source.py" in paths
    assert "must-not-be-mapped.txt" not in paths


def test_repo_search_transport_matches_direct_governed_service(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / "alpha.py").write_text("alpha = 1\n", encoding="utf-8")
    (target / "beta.py").write_text("beta = 2\n", encoding="utf-8")

    direct_root = tmp_path / "direct-artifacts"
    direct_receipt, _, _ = run_service(
        tool_name="repo_search",
        arguments={"query": "alpha"},
        session_id="direct",
        builder_root=direct_root,
        target_root=target,
        target_name="generic",
    )

    transport_root = tmp_path / "transport-artifacts"
    server = GovernedMcpServer(
        session_id="transport",
        builder_root=transport_root,
        target_root=target,
        target_name="generic",
    )
    transport = _call(server, "repo_search", {"query": "alpha"})

    assert transport["isError"] is False
    assert _domain(transport) == direct_receipt["result"]
    assert len(direct_receipt["result"]["repo_map_digest"]) == 64


@pytest.mark.parametrize("bad", [0, -1, 501])
def test_invalid_repo_map_bounds_are_denied_and_evidenced(tmp_path: Path, bad: int) -> None:
    server, _, builder_root = _server(tmp_path)

    result = _call(server, "repo_map", {"max_files": bad})

    assert result["isError"] is True
    assert result["_meta"]["status"] == "denied"
    assert _last_receipt(builder_root)["status"] == "denied"
    assert _last_event(builder_root)["event_type"] == "mcp_call_denied"


def test_empty_repo_search_is_denied_and_evidenced(tmp_path: Path) -> None:
    server, _, builder_root = _server(tmp_path)

    result = _call(server, "repo_search", {"query": "   "})

    assert result["isError"] is True
    assert result["_meta"]["status"] == "denied"
    assert _last_event(builder_root)["event_type"] == "mcp_call_denied"


def test_content_read_success_traversal_symlink_size_and_secret_bounds(tmp_path: Path) -> None:
    server, target, builder_root = _server(tmp_path)
    clean = target / "notes.txt"
    clean.write_text("ordinary governed notes", encoding="utf-8")

    success = _call(server, "content_read", {"path": "notes.txt"}, req_id=1)
    assert success["isError"] is False
    assert _domain(success)["kind"] == "builder_ii.content_read_receipt"

    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")
    traversal = _call(server, "content_read", {"path": "../outside.txt"}, req_id=2)
    assert traversal["isError"] is True
    assert traversal["_meta"]["status"] == "denied"

    link = target / "escape.txt"
    link.symlink_to(outside)
    symlink = _call(server, "content_read", {"path": "escape.txt"}, req_id=3)
    assert symlink["isError"] is True
    assert symlink["_meta"]["status"] == "denied"

    huge = target / "huge.txt"
    huge.write_bytes(b"x" * (256 * 1024 + 1))
    oversized = _call(server, "content_read", {"path": "huge.txt"}, req_id=4)
    assert oversized["isError"] is True
    assert oversized["_meta"]["status"] == "denied"

    secret = "ghp_0123456789abcdefghijABCDEFGHIJ0123"
    secret_file = target / "secret.txt"
    secret_file.write_text(f"token={secret}\n", encoding="utf-8")
    refused = _call(server, "content_read", {"path": "secret.txt"}, req_id=5)
    assert refused["isError"] is True
    assert refused["_meta"]["status"] == "denied"
    assert secret not in json.dumps(refused)
    assert secret not in json.dumps(_last_receipt(builder_root))

    assert validate_event_chain_integrity(_events_dir(builder_root))["valid"]


def test_prepare_package_uses_trusted_builder_config_not_target_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_root = Path.cwd().resolve()
    server, target, builder_root = _server(tmp_path, config_root=config_root)
    sentinel_name = "BUILDER_3B1_TARGET_ENV_SENTINEL"
    sentinel_value = "must-not-load-target-dotenv"
    (target / ".env").write_text(f"{sentinel_name}={sentinel_value}\n", encoding="utf-8")
    monkeypatch.delenv(sentinel_name, raising=False)

    result = _call(server, "prepare_package", {"task": "map this generic repository"})

    assert result["isError"] is False, result
    assert os.environ.get(sentinel_name) is None
    domain = _domain(result)
    output_dir = Path(domain["output_dir"]).resolve()
    package_root = (_mcp_dir(builder_root) / "prepare-package").resolve()
    output_dir.relative_to(package_root)
    assert output_dir.is_dir()
    assert domain["repo_path"] == str(target.resolve())

    validation = _call(server, "validate_prepare_package", {"path": str(output_dir)}, req_id=2)
    assert validation["isError"] is False, validation
    assert _domain(validation) == {"errors": [], "valid": True}


def test_prepare_package_without_trusted_config_root_fails_closed_with_denial_evidence(tmp_path: Path) -> None:
    server, _, builder_root = _server(tmp_path, config_root=None)

    result = _call(server, "prepare_package", {"task": "prepare"})

    assert result["isError"] is True
    assert result["_meta"]["status"] == "denied"
    assert _last_event(builder_root)["event_type"] == "mcp_call_denied"


def test_validate_package_refuses_escape_from_server_controlled_root(tmp_path: Path) -> None:
    server, _, builder_root = _server(tmp_path)
    outside = tmp_path / "outside-package"
    outside.mkdir()

    result = _call(server, "validate_prepare_package", {"path": str(outside)})

    assert result["isError"] is True
    assert result["_meta"]["status"] == "denied"
    assert _domain(result)["valid"] is False
    assert _last_event(builder_root)["event_type"] == "mcp_call_denied"


@pytest.mark.parametrize("hidden", ["echo", "utc_static"])
def test_unadvertised_legacy_tools_are_not_callable(tmp_path: Path, hidden: str) -> None:
    server, _, builder_root = _server(tmp_path)

    result = _call(server, hidden, {"text": "should not run"})

    assert result["isError"] is True
    assert result["_meta"]["inventory_admitted"] is False
    assert _receipts(builder_root) == []
    assert _events(builder_root) == []


def test_service_failure_is_failed_not_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server, _, builder_root = _server(tmp_path)

    def explode(**_kwargs):
        raise RuntimeError("simulated service failure")

    monkeypatch.setattr("builder_ii.adapters.mcp.server.run_service", explode)
    result = _call(server, "repo_map")

    assert result["isError"] is True
    assert result["_meta"]["status"] == "failed"
    assert _last_receipt(builder_root)["status"] == "failed"
    assert _last_event(builder_root)["event_type"] == "mcp_call_failed"


def test_corrupt_existing_ledger_refuses_continuation_without_new_evidence(tmp_path: Path) -> None:
    server, _, builder_root = _server(tmp_path)
    first = _call(server, "repo_map")
    assert first["isError"] is False

    wal = _events_dir(builder_root) / "events.wal"
    if wal.exists():
        wal.unlink()
    event_path = _events(builder_root)[0]
    event = json.loads(event_path.read_text(encoding="utf-8"))
    event["sequence"] = 9
    event_path.write_text(json.dumps(event, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt_count = len(_receipts(builder_root))
    event_count = len(_events(builder_root))

    second = _call(server, "repo_search", {"query": "anything"}, req_id=2)

    assert second["isError"] is True
    assert second["_meta"]["status"] == "failed"
    assert second["_meta"]["evidence_appended"] is False
    assert second["_meta"]["typed_error"] == "CorruptLedgerError"
    assert len(_receipts(builder_root)) == receipt_count
    assert len(_events(builder_root)) == event_count


def test_service_event_uses_current_non_initial_workflow_stage(tmp_path: Path) -> None:
    server, _, builder_root = _server(tmp_path)
    first = _call(server, "repo_map")
    assert first["isError"] is False
    events_dir = _events_dir(builder_root)
    first_path = _events(builder_root)[0]
    first_event = json.loads(first_path.read_text(encoding="utf-8"))

    planned = create_event_record(
        event_id="evt_plan3b1_planned",
        session_id=SESSION,
        sequence=2,
        event_type="workflow_planned",
        stage="planned",
        subject_refs=list(first_event["subject_refs"]),
        command_surface="test fixture",
        policy_snapshot_ref=dict(first_event["policy_snapshot_ref"]),
        previous_event_ref={
            "role": "event",
            "kind": EVENT_RECORD_KIND,
            "path": str(first_path),
            "sha256": canonical_digest(first_event),
            "name": str(first_event["event_type"]),
            "required": True,
        },
        message="advance fixture to planned",
    )
    write_event_record(planned, events_dir / "002_workflow_planned.json")

    third = _call(server, "repo_search", {"query": "anything"}, req_id=3)
    assert third["isError"] is False
    service_event = _last_event(builder_root)
    assert service_event["sequence"] == 3
    assert service_event["stage"] == "planned"
    assert validate_event_chain_integrity(events_dir)["valid"]


def test_receipt_validator_rejects_semantic_and_digest_tampering(tmp_path: Path) -> None:
    server, _, builder_root = _server(tmp_path)
    assert _call(server, "repo_map")["isError"] is False
    original = _last_receipt(builder_root)
    assert validate_mcp_service_receipt(original) == []

    mutations = [
        ("result", lambda receipt: receipt["result"].update({"file_count": 999})),
        ("arguments", lambda receipt: receipt["arguments"].update({"max_files": 1})),
        ("policy_ref", lambda receipt: receipt["policy_ref"].update({"sha256": "0" * 64})),
        ("target_profile", lambda receipt: receipt.update({"target_profile": "core"})),
        ("session_id", lambda receipt: receipt.update({"session_id": "other-session"})),
        ("service", lambda receipt: receipt.update({"service": "repo_search"})),
        ("digest", lambda receipt: receipt.update({"digest": "f" * 64})),
    ]
    for label, mutate in mutations:
        candidate = copy.deepcopy(original)
        mutate(candidate)
        assert validate_mcp_service_receipt(candidate), f"tampered {label} unexpectedly validated"


def test_receipt_validator_binds_persisted_policy_bytes(tmp_path: Path) -> None:
    server, _, builder_root = _server(tmp_path)
    assert _call(server, "repo_map")["isError"] is False
    receipt = _last_receipt(builder_root)
    policy_path = Path(receipt["policy_ref"]["path"])
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    policy["network_allowed"] = True
    policy_path.write_text(json.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    errors = validate_mcp_service_receipt(receipt)
    assert errors
    assert any("persisted policy" in error or "policy invalid" in error for error in errors)


def test_session_identity_is_validated_before_artifact_writes(tmp_path: Path) -> None:
    target, builder_root = _layout(tmp_path)

    with pytest.raises(ValueError, match="path-safe"):
        GovernedMcpServer(
            session_id="../escape",
            builder_root=builder_root,
            target_root=target,
            target_name="generic",
        )

    assert not builder_root.exists()


def test_read_prepare_services_never_invoke_subprocess_network_or_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    server, target, builder_root = _server(tmp_path, config_root=Path.cwd())
    (target / "alpha.py").write_text("alpha = 1\n", encoding="utf-8")
    (target / "notes.txt").write_text("ordinary notes", encoding="utf-8")

    def forbidden(*_args, **_kwargs):
        raise AssertionError("3B1 read/prepare service crossed a forbidden external-effect boundary")

    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    calls = [
        ("repo_map", {}),
        ("repo_search", {"query": "alpha"}),
        ("content_read", {"path": "notes.txt"}),
        ("prepare_package", {"task": "prepare without execution"}),
    ]
    package_output: str | None = None
    for index, (name, arguments) in enumerate(calls, start=1):
        result = _call(server, name, arguments, req_id=index)
        assert result["isError"] is False, result
        if name == "prepare_package":
            package_output = _domain(result)["output_dir"]

    assert package_output is not None
    validated = _call(server, "validate_prepare_package", {"path": package_output}, req_id=10)
    assert validated["isError"] is False

    for path in _receipts(builder_root):
        receipt = json.loads(path.read_text(encoding="utf-8"))
        governance = receipt["governance"]
        assert governance["shell_execution"] == "DISABLED"
        assert governance["network_access"] == "DISABLED"
        assert governance["model_execution"] == "DISABLED"
        assert governance["target_repo_writes"] == "DISABLED"
