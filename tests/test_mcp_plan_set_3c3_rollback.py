from __future__ import annotations

import json
from pathlib import Path

import pytest

import builder_ii.adapters.mcp.governed_services as services


def _write(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    return path


def _inputs(tmp_path: Path, *, target: Path | None = None) -> tuple[Path, dict[str, str]]:
    builder = tmp_path / "builder"
    builder.mkdir()
    target = target or (tmp_path / "target")
    target.mkdir(exist_ok=True)
    plan = _write(builder / "plan.json", {"kind": "builder_ii.rollback_plan", "target": {"name": "generic", "repo": str(target)}})
    reverse = builder / "reverse.patch"
    reverse.write_text("diff --git a/a b/a\n", encoding="utf-8")
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
        receipt = {"target": json.loads(Path(args["rollback_plan_path"]).read_text())["target"], "rollback_approval_digest": services.canonical_digest(approval), "rollback_state": "EXECUTED", "current_state": "OPERATIONALLY_VERIFIED", "rollback_equivalence_verified": True, "rollback_plan_ref": args["rollback_plan_path"], "rollback_patch_ref": {"path": args["rollback_reverse_patch_path"]}, "pre_apply_status_digest": "same", "post_rollback_status_digest": "same"}
        _write(output / "rollback_receipt.json", receipt)
        _write(output / "rollback_ledger_record.json", {"event_type": "patch_rolled_back", "subject_refs": [{"path": value} for value in (args["rollback_plan_path"], args["rollback_approval_path"], args["rollback_reverse_patch_path"], str(output / "rollback_receipt.json"))]})

    monkeypatch.setattr(services, "rollback_hitl_patch", executor)
    result = services.run_service(tool_name="rollback", arguments=args, session_id="s", builder_root=builder, target_root=tmp_path / "target", target_name="generic")[0]
    assert len(calls) == 1
    assert result["status"] == "succeeded"
    assert result["result"]["canonical_executor"].endswith("rollback_hitl_patch")
    assert result["result"]["rollback_equivalence_verified"] is True
