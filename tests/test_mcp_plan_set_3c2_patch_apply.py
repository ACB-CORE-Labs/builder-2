from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from hitl_patch_lane_helpers import PATCH_DIFF, init_target_repo, real_verification_receipt

import builder_ii.adapters.mcp.governed_services as services
from builder_ii.governance.hitl.hitl_patch_approval import create_hitl_patch_approval, write_hitl_patch_approval
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal


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
    monkeypatch.setattr(services, "approval_is_expired", lambda value, *, now: False)
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


def _real_mcp_inputs(tmp_path: Path) -> tuple[Path, Path, dict[str, str], Path]:
    target = init_target_repo(tmp_path)
    builder_root = tmp_path / "builder"
    builder_root.mkdir()
    verification_source = real_verification_receipt(tmp_path, target)
    verification = builder_root / "verification.json"
    shutil.copyfile(verification_source, verification)
    patch_digest = hashlib.sha256(PATCH_DIFF.encode("utf-8")).hexdigest()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=target, check=True, capture_output=True, text=True
    ).stdout.strip()
    proposal = create_hitl_patch_proposal(
        generic_repo=target,
        patch_digest=patch_digest,
        unified_diff=PATCH_DIFF,
        target_head_sha=head,
        verification_receipt_file_sha256=hashlib.sha256(verification.read_bytes()).hexdigest(),
    )
    proposal_path = builder_root / "proposal.json"
    write_hitl_patch_proposal(proposal, proposal_path)
    approval_path = builder_root / "approval.json"
    write_hitl_patch_approval(
        create_hitl_patch_approval(proposal, confirmed_digest_prefix=patch_digest[:4]), approval_path
    )
    arguments = {
        "proposal_path": str(proposal_path),
        "approval_path": str(approval_path),
        "verification_receipt_path": str(verification),
    }
    return builder_root, target, arguments, proposal_path


def test_real_approval_and_verification_chain_reaches_canonical_executor_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder_root, target, arguments, _ = _real_mcp_inputs(tmp_path)
    real_apply = services.apply_hitl_patch
    calls = 0

    def counted_apply(*args: object, **kwargs: object) -> None:
        nonlocal calls
        calls += 1
        real_apply(*args, **kwargs)

    monkeypatch.setattr(services, "apply_hitl_patch", counted_apply)
    receipt, _, _ = services.run_service(
        tool_name="patch_apply",
        arguments=arguments,
        session_id="goose_real_session",
        builder_root=builder_root,
        target_root=target,
        target_name="generic",
    )
    assert calls == 1
    assert receipt["status"] == "succeeded"
    assert receipt["result"]["status"] == "succeeded"
    assert "patch_ledger_ref" in receipt["result"]
    assert (target / "file.txt").read_text(encoding="utf-8") == "Line 1\nLine 2 modified\n"


def test_outer_receipt_persistence_failure_preserves_mutation_uncertainty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder_root, target, arguments, _ = _real_mcp_inputs(tmp_path)
    monkeypatch.setattr(services, "_service_receipt", lambda **_: (_ for _ in ()).throw(OSError("receipt disk failure")))
    receipt, receipt_path, event_path = services.run_service(
        tool_name="patch_apply",
        arguments=arguments,
        session_id="goose_persist_failure",
        builder_root=builder_root,
        target_root=target,
        target_name="generic",
    )
    assert receipt["status"] == "failed"
    assert receipt["result"]["status"] == "mutation_uncertain"
    assert receipt["result"]["mutation_state"] == "APPLIED_OR_MAY_HAVE_BEEN_APPLIED"
    assert receipt["result"]["rollback_executed"] is False
    assert receipt_path == Path("")
    assert event_path == Path("")
    assert (target / "file.txt").read_text(encoding="utf-8") == "Line 1\nLine 2 modified\n"


def test_missing_canonical_evidence_after_apply_is_mutation_uncertain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder_root, target, arguments, _ = _real_mcp_inputs(tmp_path)
    real_apply = services.apply_hitl_patch

    def apply_then_remove_postflight(*args: object, **kwargs: object) -> None:
        real_apply(*args, **kwargs)
        output_dir = args[3] if len(args) > 3 else kwargs["output_dir"]
        (Path(output_dir) / "postflight_record.json").unlink()

    monkeypatch.setattr(services, "apply_hitl_patch", apply_then_remove_postflight)
    receipt, _, _ = services.run_service(
        tool_name="patch_apply",
        arguments=arguments,
        session_id="missing_postflight",
        builder_root=builder_root,
        target_root=target,
        target_name="generic",
    )
    assert receipt["status"] == "failed"
    assert receipt["result"]["status"] == "mutation_uncertain"
    assert receipt["result"]["mutation_state"] == "APPLIED_OR_MAY_HAVE_BEEN_APPLIED"
    assert receipt["result"]["rollback_executed"] is False
    assert (target / "file.txt").read_text(encoding="utf-8") == "Line 1\nLine 2 modified\n"
