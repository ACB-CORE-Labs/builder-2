from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

import builder_ii.cli.mcp_cli as mcp_cli
from builder_ii.adapters.mcp.governed_call import TOOL_SPECS
from builder_ii.adapters.mcp.governed_services import (
    MAX_MCP_UNIFIED_DIFF_BYTES,
    ServiceDenied,
    run_service,
    validate_mcp_service_receipt,
)
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.cli.mcp_cli import mcp_app
from builder_ii.governance.hitl.hitl_patch_proposal import (
    create_bound_hitl_patch_proposal,
    validate_hitl_patch_proposal,
)

DIFF = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n"


def _valid_diff_with_size(size: int) -> str:
    prefix = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+"
    suffix = "\n"
    filler_bytes = size - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
    assert filler_bytes >= 1
    diff = prefix + ("n" * filler_bytes) + suffix
    assert len(diff.encode("utf-8")) == size
    return diff


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


def test_patch_proposal_inventory_preserves_64_kib_mcp_boundary() -> None:
    schema = TOOL_SPECS["patch_proposal"]["inputSchema"]
    assert schema["properties"]["unified_diff"]["maxLength"] == MAX_MCP_UNIFIED_DIFF_BYTES


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


def _git(target: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=target,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _strong_target_snapshot(target: Path, artifact_root: Path) -> dict[str, object]:
    head = _git(target, "rev-parse", "HEAD").strip()
    head_tree = _git(target, "rev-parse", "HEAD^{tree}").strip()
    index = _git(target, "ls-files", "--stage", "-z")
    status = _git(target, "status", "--porcelain=v2", "--untracked-files=all", "-z")
    paths: list[tuple[str, str, int, str]] = []
    git_state: list[tuple[str, str, int, str]] = []
    for path in sorted(target.rglob("*")):
        if path == artifact_root or artifact_root in path.parents:
            continue
        relative = str(path.relative_to(target))
        mode = path.lstat().st_mode
        if path.is_symlink():
            entry = (relative, "symlink", stat.S_IMODE(mode), os.readlink(path))
        elif path.is_file():
            entry = (relative, "file", stat.S_IMODE(mode), hashlib.sha256(path.read_bytes()).hexdigest())
        elif path.is_dir():
            entry = (relative, "dir", stat.S_IMODE(mode), "")
        else:
            entry = (relative, "other", stat.S_IMODE(mode), "")
        paths.append(entry)
        if relative == ".git" or relative.startswith(".git/"):
            git_state.append(entry)
    return {
        "head": head,
        "head_tree": head_tree,
        "index": index,
        "status": status,
        "paths": tuple(paths),
        "git_state": tuple(git_state),
    }


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


def test_canonical_inside_target_artifact_namespace_preserves_full_git_state(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    artifact_root = target / ".builder" / "artifacts"
    artifact_root.mkdir(parents=True)
    receipt_path = artifact_root / "verification.json"
    receipt_path.write_text(json.dumps(_receipt(), sort_keys=True) + "\n", encoding="utf-8")
    (target / ".gitignore").write_text(".builder/artifacts/\n", encoding="utf-8")
    (target / "file.txt").write_text("old\n", encoding="utf-8")
    executable = target / "tool.sh"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    (target / "link.txt").symlink_to("file.txt")
    _git(target, "init", "-q")
    _git(target, "config", "user.email", "builder-ii@example.invalid")
    _git(target, "config", "user.name", "Builder II Qualification")
    _git(target, "add", ".gitignore", "file.txt", "tool.sh", "link.txt")
    _git(target, "commit", "-qm", "fixture")
    (target / "file.txt").write_text("old\nunstaged\n", encoding="utf-8")
    (target / "staged.txt").write_text("staged\n", encoding="utf-8")
    _git(target, "add", "staged.txt")
    (target / "untracked.txt").write_text("untracked\n", encoding="utf-8")
    before = _strong_target_snapshot(target, artifact_root)

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
            arguments=_arguments(receipt_path, target_head_sha=str(before["head"])),
            session_id="canonical-product-path",
            builder_root=artifact_root,
            target_root=target,
            target_name="generic",
        )

    assert approve.call_count == apply.call_count == rollback.call_count == 0
    assert run.call_count == popen.call_count == system.call_count == 0
    assert receipt["status"] == "succeeded"
    assert receipt["result"]["decision"] == "HUMAN_APPROVAL_REQUIRED"
    assert receipt_artifact.is_relative_to(artifact_root)
    assert event.is_relative_to(artifact_root)
    assert _strong_target_snapshot(target, artifact_root) == before
    artifact_paths = {str(path.relative_to(artifact_root)) for path in artifact_root.rglob("*") if path.is_file()}
    assert "verification.json" in artifact_paths
    assert any(path.endswith("hitl-patch-proposal.json") for path in artifact_paths)
    assert any(path.endswith("patch_proposal_receipt.json") for path in artifact_paths)
    assert any(path.endswith("mcp_service.json") for path in artifact_paths)


def test_builder_mcp_serve_default_product_path_creates_passive_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "target"
    artifact_root = target / ".builder" / "artifacts"
    artifact_root.mkdir(parents=True)
    receipt_path = artifact_root / "verification.json"
    receipt_path.write_text(json.dumps(_receipt(), sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.chdir(target)
    monkeypatch.delenv("BUILDER_ARTIFACT_ROOT", raising=False)
    monkeypatch.delenv("CORE_ARTIFACT_ROOT", raising=False)
    monkeypatch.setenv("BUILDER_MCP_SESSION_ID", "cli-product-path")
    monkeypatch.setenv("BUILDER_MCP_TARGET_PROFILE", "generic")
    monkeypatch.setattr(mcp_cli, "enforce_command_authority", lambda *_args, **_kwargs: None)
    request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": "patch_proposal", "arguments": _arguments(receipt_path)},
    }

    result = CliRunner().invoke(mcp_app, ["serve"], input=json.dumps(request) + "\n")

    assert result.exit_code == 0, result.output
    response = json.loads(result.output.strip())
    assert response["result"]["isError"] is False
    domain = json.loads(response["result"]["content"][0]["text"])
    assert domain["decision"] == "HUMAN_APPROVAL_REQUIRED"
    proposal_path = Path(domain["proposal_ref"]["path"])
    assert proposal_path.is_relative_to(artifact_root.resolve())
    assert proposal_path.is_file()


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
    oversized_diff = _valid_diff_with_size(MAX_MCP_UNIFIED_DIFF_BYTES + 1)
    with pytest.raises(
        ServiceDenied,
        match=f"unified_diff exceeds the {MAX_MCP_UNIFIED_DIFF_BYTES}-byte limit",
    ):
        run_service(
            tool_name="patch_proposal",
            arguments=_arguments(receipt_path, unified_diff=oversized_diff),
            session_id="oversize",
            builder_root=builder_root,
            target_root=target,
            target_name="generic",
        )
    assert not list(builder_root.rglob("hitl-patch-proposal.json"))
    with pytest.raises(ServiceDenied):
        run_service(
            tool_name="patch_proposal",
            arguments=_arguments(receipt_path, unified_diff="\ud800"),
            session_id="invalidunicode",
            builder_root=builder_root,
            target_root=target,
            target_name="generic",
        )


def test_patch_proposal_refuses_noncanonical_artifact_root_beneath_target(tmp_path: Path) -> None:
    target = tmp_path / "target"
    builder_root = target / "src" / "artifacts"
    builder_root.mkdir(parents=True)
    receipt_path = builder_root / "verification.json"
    receipt_path.write_text(json.dumps(_receipt()), encoding="utf-8")
    before = _target_fingerprint(target)
    with pytest.raises(ServiceDenied, match="must remain under .builder/artifacts"):
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


@pytest.mark.parametrize("failure_boundary", ["service_receipt", "event"])
def test_post_proposal_evidence_failure_removes_approval_ready_artifacts(
    tmp_path: Path, failure_boundary: str
) -> None:
    import builder_ii.adapters.mcp.governed_services as services

    target, builder_root, receipt_path = _setup(tmp_path)
    server = GovernedMcpServer(
        session_id=f"post-persist-{failure_boundary}",
        builder_root=builder_root,
        target_root=target,
        target_name="generic",
    )
    if failure_boundary == "service_receipt":
        original_json = services._json

        def fail_receipt(path: Path, value: dict[str, object]) -> None:
            if path.name.endswith("patch_proposal_receipt.json"):
                raise OSError("receipt storage unavailable")
            original_json(path, value)

        context = patch.object(services, "_json", side_effect=fail_receipt)
    else:
        context = patch.object(services, "write_event_record", side_effect=OSError("event storage unavailable"))

    with context:
        response = server.handle_request(
            {
                "jsonrpc": "2.0",
                "id": failure_boundary,
                "method": "tools/call",
                "params": {"name": "patch_proposal", "arguments": _arguments(receipt_path)},
            }
        )

    assert response is not None and response["result"]["isError"] is True
    assert "HUMAN_APPROVAL_REQUIRED" not in json.dumps(response)
    assert not list(builder_root.rglob("hitl-patch-proposal.json"))
    assert not list(builder_root.rglob("*patch_proposal_receipt.json"))
    assert not list(builder_root.rglob("*_mcp_service.json"))


def test_overlap_and_symlinked_artifact_namespaces_fail_before_write(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    with pytest.raises(ServiceDenied, match="must not equal"):
        GovernedMcpServer(session_id="equal", builder_root=target, target_root=target)

    outer_artifact = tmp_path / "outer-artifacts"
    nested_target = outer_artifact / "target"
    nested_target.mkdir(parents=True)
    with pytest.raises(ServiceDenied, match="must not be inside"):
        GovernedMcpServer(session_id="reverse", builder_root=outer_artifact, target_root=nested_target)

    outside = tmp_path / "outside"
    outside.mkdir()
    symlinked_root = target / ".builder" / "artifacts"
    symlinked_root.parent.mkdir()
    symlinked_root.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ServiceDenied, match="symlinked path component"):
        GovernedMcpServer(session_id="symlink-root", builder_root=symlinked_root, target_root=target)
    assert not list(outside.iterdir())


@pytest.mark.parametrize("symlink_component", ["sessions", "mcp", "events"])
def test_symlinked_session_output_components_cannot_redirect_evidence(
    tmp_path: Path, symlink_component: str
) -> None:
    target = tmp_path / "target"
    artifact_root = target / ".builder" / "artifacts"
    artifact_root.mkdir(parents=True)
    receipt_path = artifact_root / "verification.json"
    receipt_path.write_text(json.dumps(_receipt()) + "\n", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    session_id = f"symlink-{symlink_component}"
    if symlink_component == "sessions":
        link = artifact_root / "sessions"
    else:
        session_root = artifact_root / "sessions" / session_id
        session_root.mkdir(parents=True)
        link = session_root / symlink_component
    link.symlink_to(outside, target_is_directory=True)

    server = GovernedMcpServer(
        session_id=session_id,
        builder_root=artifact_root,
        target_root=target,
        target_name="generic",
    )
    response = server.handle_request(
        {
            "jsonrpc": "2.0",
            "id": symlink_component,
            "method": "tools/call",
            "params": {"name": "patch_proposal", "arguments": _arguments(receipt_path)},
        }
    )

    assert response is not None and response["result"]["isError"] is True
    assert "HUMAN_APPROVAL_REQUIRED" not in json.dumps(response)
    assert not list(outside.iterdir())


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
    assert "rollback" in names
    assert not ({"propose_patch", "run_shell", "approve_patch", "apply_patch"} & names)
    for retired in ("propose_patch", "run_shell", "approve_patch", "apply_patch"):
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
