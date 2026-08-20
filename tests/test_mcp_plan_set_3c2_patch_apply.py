from __future__ import annotations

import json
from pathlib import Path

import pytest

import builder_ii.adapters.mcp.governed_services as services


def _artifact(path: Path, value: dict[str, object]) -> Path:
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")
    return path


def _inputs(tmp_path: Path, *, target: Path | None = None, receipt_kind: str = "builder_ii.verification_execution_receipt") -> tuple[Path, dict[str, object]]:
    builder_root = tmp_path / "builder"
    builder_root.mkdir()
    target = target or (tmp_path / "target")
    target.mkdir(exist_ok=True)
    proposal = _artifact(
        builder_root / "proposal.json",
        {"kind": "builder_ii.hitl_patch_proposal", "target": {"name": "generic", "repo": str(target)}},
    )
    approval = _artifact(builder_root / "approval.json", {"kind": "approval"})
    verification = _artifact(
        builder_root / "verification.json",
        {"kind": receipt_kind, "receipt_status": "EXECUTED", "valid": True, "target_repo": str(target)},
    )
    return builder_root, {
        "proposal_path": str(proposal),
        "approval_path": str(approval),
        "verification_receipt_path": str(verification),
    }


def _patch_validation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(services, "validate_hitl_patch_proposal", lambda value: [])
    monkeypatch.setattr(services, "validate_hitl_patch_approval_file", lambda path: [])
    monkeypatch.setattr(services, "approval_binding_errors", lambda *args, **kwargs: [])
    monkeypatch.setattr(services, "approval_is_expired", lambda value: False)
    monkeypatch.setattr(services, "validate_verification_execution_receipt_artifact", lambda value: [])


def test_target_mismatch_is_denied_before_canonical_executor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    builder_root, arguments = _inputs(tmp_path)
    different_target = tmp_path / "different-target"
    different_target.mkdir()
    _patch_validation(monkeypatch)
    executor = 0

    def apply(*args: object, **kwargs: object) -> None:
        nonlocal executor
        executor += 1

    monkeypatch.setattr(services, "apply_hitl_patch", apply)
    with pytest.raises(services.ServiceDenied, match="proposal target repo"):
        services.run_service(
            tool_name="patch_apply", arguments=arguments, session_id="s", builder_root=builder_root,
            target_root=different_target, target_name="generic",
        )
    assert executor == 0


def test_demo_receipt_is_denied_before_canonical_executor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    builder_root, arguments = _inputs(tmp_path, receipt_kind="builder_ii.demo_verification_receipt")
    _patch_validation(monkeypatch)
    executor = 0
    monkeypatch.setattr(services, "apply_hitl_patch", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()))
    with pytest.raises(services.ServiceDenied, match="demo receipts are not admitted"):
        services.run_service(
            tool_name="patch_apply", arguments=arguments, session_id="s", builder_root=builder_root,
            target_root=tmp_path / "target", target_name="generic",
        )
    assert executor == 0


def test_post_apply_projection_failure_returns_mutation_uncertain_evidence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    builder_root, arguments = _inputs(tmp_path)
    _patch_validation(monkeypatch)

    def apply(proposal: Path, approval: Path, verification: Path, output_dir: Path) -> None:
        output_dir.mkdir(parents=True)
        for name in ("patch_apply_receipt.json", "postflight_record.json", "rollback_plan.json", "rollback_bundle.json"):
            (output_dir / name).write_text("{}\n", encoding="utf-8")

    monkeypatch.setattr(services, "apply_hitl_patch", apply)
    monkeypatch.setattr(services, "validate_patch_apply_receipt_file", lambda path: ["forced projection failure"])
    receipt, _, _ = services.run_service(
        tool_name="patch_apply", arguments=arguments, session_id="s", builder_root=builder_root,
        target_root=tmp_path / "target", target_name="generic",
    )
    payload = receipt
    assert payload["status"] == "failed"
    assert payload["result"]["status"] == "mutation_uncertain"
    assert payload["result"]["mutation_state"] == "APPLIED_OR_MAY_HAVE_BEEN_APPLIED"
    assert payload["result"]["rollback_executed"] is False
    assert "patch_apply_receipt_ref" in payload["result"]
    assert "rollback_executor" not in payload["result"]
