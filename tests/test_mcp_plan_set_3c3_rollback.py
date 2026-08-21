from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import builder_ii.adapters.mcp.governed_services as services
from builder_ii.adapters.goose.goose_runtime_harness import GooseRuntimeHarness
from builder_ii.adapters.mcp.server import GovernedMcpServer
from builder_ii.governance.hitl.hitl_rollback_approval import (
    create_hitl_rollback_approval,
    write_hitl_rollback_approval,
)


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    return path


def _inputs(tmp_path: Path, *, target: Path | None = None) -> tuple[Path, dict[str, str]]:
    builder = tmp_path / "builder"
    builder.mkdir()
    target = target or (tmp_path / "target")
    target.mkdir(exist_ok=True)
    reverse = builder / "reverse.patch"
    reverse.write_text("diff --git a/a b/a\n", encoding="utf-8")
    plan = _write(builder / "plan.json", {"kind": "builder_ii.rollback_plan", "target": {"name": "generic", "repo": str(target)}, "patch_digest": "p", "pre_head": "h", "rollback_patch_ref": {"path": str(reverse), "sha256": hashlib.sha256(reverse.read_bytes()).hexdigest()}})
    approval = _write(builder / "approval.json", {"kind": "builder_ii.hitl_rollback_approval"})
    return builder, {"rollback_plan_path": str(plan), "rollback_reverse_patch_path": str(reverse), "rollback_approval_path": str(approval)}


def _validations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "validate_rollback_plan_file", lambda path: [])
    monkeypatch.setattr(services, "validate_rollback_receipt_file", lambda path: [])
    monkeypatch.setattr(services, "validate_hitl_patch_ledger_record_file", lambda path: [])


def test_rollback_denies_plan_target_mismatch_before_executor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    builder, args = _inputs(tmp_path)
    different = tmp_path / "different"
    different.mkdir()
    _validations(monkeypatch)
    calls = 0

    def executor(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1

    monkeypatch.setattr(services, "rollback_hitl_patch", executor)
    with pytest.raises(services.ServiceDenied, match="target repo"):
        services.run_service(tool_name="rollback", arguments=args, session_id="s", builder_root=builder, target_root=different, target_name="generic")
    assert calls == 0


def test_rollback_delegates_exactly_once_and_projects_canonical_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    builder, args = _inputs(tmp_path)
    _validations(monkeypatch)
    calls: list[tuple[object, ...]] = []

    def executor(*call_args: object, **kwargs: object) -> None:
        calls.append(call_args)
        output = Path(call_args[2])
        output.mkdir(parents=True)
        approval = json.loads(Path(args["rollback_approval_path"]).read_text())
        plan = json.loads(Path(args["rollback_plan_path"]).read_text())
        receipt = {"target": plan["target"], "rollback_approval_digest": services.canonical_digest(approval), "rollback_state": "EXECUTED", "current_state": "OPERATIONALLY_VERIFIED", "rollback_equivalence_verified": True, "rollback_plan_ref": args["rollback_plan_path"], "rollback_patch_ref": {"path": args["rollback_reverse_patch_path"], "sha256": plan["rollback_patch_ref"]["sha256"]}, "pre_apply_status_digest": "same", "post_rollback_status_digest": "same"}
        _write(output / "rollback_receipt.json", receipt)
        _write(output / "rollback_ledger_record.json", {"event_type": "patch_rolled_back", "target": plan["target"], "patch_digest": plan["patch_digest"], "pre_head": plan["pre_head"], "subject_refs": [{"role": role, "path": value, "sha256": services._file_digest(Path(value)), "required": True} for role, value in (("rollback_plan", args["rollback_plan_path"]), ("rollback_approval", args["rollback_approval_path"]), ("rollback_reverse_patch", args["rollback_reverse_patch_path"]), ("rollback_receipt", str(output / "rollback_receipt.json")))]})

    monkeypatch.setattr(services, "rollback_hitl_patch", executor)
    result = services.run_service(tool_name="rollback", arguments=args, session_id="s", builder_root=builder, target_root=tmp_path / "target", target_name="generic")[0]
    assert len(calls) == 1
    assert result["status"] == "succeeded"
    assert result["result"]["canonical_executor"].endswith("rollback_hitl_patch")
    assert result["result"]["rollback_equivalence_verified"] is True


def test_real_apply_then_rollback_and_rollback_only_goose_close(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The transport writes real evidence and a later Goose close consumes that evidence."""
    from test_mcp_plan_set_3c2_patch_apply import _real_mcp_inputs

    builder, target, apply_args, _ = _real_mcp_inputs(tmp_path)
    applied, _, _ = services.run_service(
        tool_name="patch_apply", arguments=apply_args, session_id="apply-session", builder_root=builder,
        target_root=target, target_name="generic",
    )
    assert applied["status"] == "succeeded"
    apply_result = applied["result"]
    from builder_ii.adapters.goose.goose_runtime_harness import _get_target_files
    applied_snapshot = _get_target_files(target)
    plan_path = Path(apply_result["rollback_plan_ref"]["path"])
    reverse_path = Path(apply_result["rollback_patch_ref"]["path"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    approval_path = builder / "rollback-approval.json"
    write_hitl_rollback_approval(
        create_hitl_rollback_approval(plan, confirmed_digest_prefix=services.canonical_digest(plan)[:4]), approval_path
    )
    rollback_args = {
        "rollback_plan_path": str(plan_path),
        "rollback_reverse_patch_path": str(reverse_path),
        "rollback_approval_path": str(approval_path),
    }
    rolled, _, _ = services.run_service(
        tool_name="rollback", arguments=rollback_args, session_id="rollback-session", builder_root=builder,
        target_root=target, target_name="generic",
    )
    assert rolled["status"] == "succeeded"
    assert (target / "file.txt").read_text(encoding="utf-8") == "Line 1\nLine 2\n"

    harness = GooseRuntimeHarness.__new__(GooseRuntimeHarness)
    harness.session_id = "rollback-session"
    harness.target_root = target
    harness.session_plan = SimpleNamespace(target_name="generic")
    harness._proc = None
    harness._preflight_snapshot = applied_snapshot
    harness._admitted_artifact_root = builder
    real_run = subprocess.run
    monkeypatch.setattr(
        "builder_ii.adapters.goose.goose_runtime_harness.subprocess.run",
        lambda *a, **k: None if a and a[0] and a[0][0] == "goose" else real_run(*a, **k),
    )
    _, postflight = harness.close("launch-digest")
    assert postflight["unexplained_mutations"] == []
    assert str(target / "file.txt") in postflight["approved_mutations"]
    assert postflight["mutation_mode"] == "approved_hitl_rollback"
    assert postflight["approved_patch_evidence"] is None
    assert postflight["approved_mutation_evidence"]["session_id"] == "rollback-session"


def _real_rollback_server_inputs(tmp_path: Path) -> tuple[Path, Path, dict[str, str]]:
    from test_mcp_plan_set_3c2_patch_apply import _real_mcp_inputs

    builder, target, apply_args, _ = _real_mcp_inputs(tmp_path)
    applied, _, _ = services.run_service(
        tool_name="patch_apply", arguments=apply_args, session_id="rollback-server", builder_root=builder,
        target_root=target, target_name="generic",
    )
    plan_path = Path(applied["result"]["rollback_plan_ref"]["path"])
    reverse_path = Path(applied["result"]["rollback_patch_ref"]["path"])
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    approval_path = builder / "rollback-approval.json"
    write_hitl_rollback_approval(
        create_hitl_rollback_approval(plan, confirmed_digest_prefix=services.canonical_digest(plan)[:4]), approval_path
    )
    return builder, target, {
        "rollback_plan_path": str(plan_path),
        "rollback_reverse_patch_path": str(reverse_path),
        "rollback_approval_path": str(approval_path),
    }


def test_server_reports_expired_rollback_approval_as_denied_and_preserves_target(
    tmp_path: Path,
) -> None:
    builder, target, args = _real_rollback_server_inputs(tmp_path)
    approval_path = Path(args["rollback_approval_path"])
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["expires_at"] = 0
    approval_path.write_text(json.dumps(approval) + "\n", encoding="utf-8")
    before = (target / "file.txt").read_text(encoding="utf-8")
    response = GovernedMcpServer(
        session_id="rollback-server", builder_root=builder, target_root=target, target_name="generic"
    ).handle_request({"id": 1, "method": "tools/call", "params": {"name": "rollback", "arguments": args}})
    assert response is not None
    result = json.loads(response["result"]["content"][0]["text"])
    assert response["result"]["_meta"]["status"] == "denied"
    assert result["status"] == "denied"
    assert result["mutation_state"] == "NO_MUTATION"
    assert (target / "file.txt").read_text(encoding="utf-8") == before


def test_server_reports_command_authority_refusal_as_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    builder, target, args = _real_rollback_server_inputs(tmp_path)
    monkeypatch.setattr(
        services,
        "rollback_hitl_patch",
        lambda *a, **k: (_ for _ in ()).throw(services.ServiceDenied("command authority denied")),
    )
    response = GovernedMcpServer(
        session_id="rollback-server", builder_root=builder, target_root=target, target_name="generic"
    ).handle_request({"id": 2, "method": "tools/call", "params": {"name": "rollback", "arguments": args}})
    assert response is not None
    result = json.loads(response["result"]["content"][0]["text"])
    assert response["result"]["_meta"]["status"] == "denied"
    assert result["mutation_state"] == "NO_MUTATION"


def test_malformed_rollback_target_is_invalid_close_not_attribute_error(tmp_path: Path) -> None:
    from builder_ii.adapters.goose.goose_runtime_harness import _validated_rollback_close_evidence

    result = {
        key: {"path": str(tmp_path / f"{key}.json"), "sha256": "0" * 64}
        for key in (
            "rollback_receipt_ref", "rollback_ledger_ref", "rollback_plan_ref",
            "rollback_approval_ref", "rollback_reverse_patch_ref",
        )
    }
    (tmp_path / "rollback_plan_ref.json").write_text(json.dumps({"target": None}) + "\n", encoding="utf-8")
    paths, summary, errors = _validated_rollback_close_evidence(
        result, artifact_root=tmp_path, session_id="s", target_root=tmp_path, target_name="generic"
    )
    assert paths == set()
    assert summary is None
    assert errors


def test_changed_bytes_on_an_already_dirty_path_are_uncertain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    builder, target, args = _real_rollback_server_inputs(tmp_path)
    path = target / "file.txt"
    path.write_text("already dirty\n", encoding="utf-8")
    monkeypatch.setattr(
        services,
        "rollback_hitl_patch",
        lambda *a, **k: (path.write_text("changed again\n", encoding="utf-8"), (_ for _ in ()).throw(RuntimeError("after mutation")))[1],
    )
    response = GovernedMcpServer(
        session_id="rollback-server", builder_root=builder, target_root=target, target_name="generic"
    ).handle_request({"id": 3, "method": "tools/call", "params": {"name": "rollback", "arguments": args}})
    assert response is not None
    result = json.loads(response["result"]["content"][0]["text"])
    assert result["status"] == "rollback_uncertain"
    assert result["mutation_state"] == "ROLLED_BACK_OR_MAY_HAVE_BEEN_ROLLED_BACK"


@pytest.mark.parametrize("malformed", [[], "event", 1])
def test_malformed_rollback_result_shapes_are_invalid_close(tmp_path: Path, malformed: object) -> None:
    from builder_ii.adapters.goose.goose_runtime_harness import _validated_rollback_close_evidence

    result = {
        key: {"path": str(tmp_path / f"{key}.json"), "sha256": "0" * 64}
        for key in (
            "rollback_receipt_ref", "rollback_ledger_ref", "rollback_plan_ref",
            "rollback_approval_ref", "rollback_reverse_patch_ref",
        )
    }
    result["rollback_reverse_patch_ref"] = malformed
    paths, summary, errors = _validated_rollback_close_evidence(
        result, artifact_root=tmp_path, session_id="s", target_root=tmp_path, target_name="generic"
    )
    assert paths == set()
    assert summary is None
    assert errors
