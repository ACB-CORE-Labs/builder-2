from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from typer.testing import CliRunner

from builder_ii.chain_summary_cli import chain_app
from builder_ii.artifact_chain_verification import verify_artifact_chain
from orchestration_assignment_fixtures import build_goal2_assignment_fixture

from builder_ii.approval_records import create_approval_record
from builder_ii.artifact_index_records import create_artifact_index_record
from builder_ii.chain_summary_records import create_chain_summary_record
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.handoff_bundle_records import create_handoff_bundle_record
from builder_ii.preflight_records import create_preflight_record
from builder_ii.promotion_decision_records import create_promotion_decision_record
from builder_ii.promotion_readiness_records import create_promotion_readiness_record
from builder_ii.receipt_records import create_receipt_record
from builder_ii.receive_records import create_receive_record
from builder_ii.snapshot_records import create_snapshot_record
from builder_ii.state_ledger_records import create_state_ledger_record
from builder_ii.config_schema import attach_digest
from builder_ii.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_ledger import (
    index_verification_execution_receipt,
    validate_verification_execution_ledger_integrity,
    write_verification_execution_ledger_record,
)
from builder_ii.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    finalize_verification_execution_receipt,
    write_verification_execution_receipt,
)

# ---------------------------------------------------------------------------
# Test Fixture Factories
# ---------------------------------------------------------------------------

_MANIFEST: dict[str, Any] = {
    "kind": "builder_ii.goose_session_manifest",
    "schema_version": 1,
    "target": {"name": "test-target", "repo": "/tmp/repo", "description": "test"},
    "agent_profile": {"name": "test-agent", "description": "test", "authority": "user"},
    "task": "governance invariant check",
    "requested_runtime_mode": "disabled",
}


def _proposal() -> dict[str, Any]:
    return create_goose_command_proposal(
        _MANIFEST,
        manifest_path="manifest.json",
        command="echo test",
        risk_level="low",
    )


def _approval(proposal: dict[str, Any], proposal_path: str) -> dict[str, Any]:
    return create_approval_record(
        proposal,
        proposal_path=proposal_path,
        decision="approved",
        decided_by="operator",
    )


def _preflight(
    proposal: dict[str, Any],
    approval: dict[str, Any],
    proposal_path: str,
    approval_path: str,
) -> dict[str, Any]:
    return create_preflight_record(
        proposal,
        approval,
        proposal_path=proposal_path,
        approval_path=approval_path,
        verification_refs=["ref"],
    )


def _receipt(preflight: dict[str, Any], preflight_path: str) -> dict[str, Any]:
    return create_receipt_record(
        preflight,
        preflight_path=preflight_path,
        status="passed",
        recorded_by="operator",
        evidence_refs=["evidence"],
    )


def _chain_summary(
    proposal: dict[str, Any],
    approval: dict[str, Any],
    preflight: dict[str, Any],
    receipt: dict[str, Any],
    proposal_path: str,
    approval_path: str,
    preflight_path: str,
    receipt_path: str,
) -> dict[str, Any]:
    return create_chain_summary_record(
        proposal,
        approval,
        preflight,
        receipt,
        proposal_path=proposal_path,
        approval_path=approval_path,
        preflight_path=preflight_path,
        receipt_path=receipt_path,
    )


def _handoff_bundle(summary: dict[str, Any], summary_path: str) -> dict[str, Any]:
    return create_handoff_bundle_record(
        summary,
        summary_path=summary_path,
        bundle_name="test-bundle",
    )


def _receive(bundle: dict[str, Any], bundle_path: str) -> dict[str, Any]:
    return create_receive_record(
        bundle,
        bundle_path=bundle_path,
        decision="accepted",
        received_by="downstream",
    )


def _readiness() -> dict[str, Any]:
    return create_promotion_readiness_record(
        capability_name="test_capability",
        docs_refs=["docs/README.md"],
        tests_refs=["tests/test.py"],
        cli_refs=["builder-test"],
        failure_mode_refs=["reports error"],
        approval_boundary_refs=["no-authority"],
        output_artifact_refs=["output.json"],
        rollback_refs=["delete output"],
        verification_refs=["uv run pytest -q"],
    )


def _promotion_decision(
    readiness: dict[str, Any], readiness_path: str
) -> dict[str, Any]:
    return create_promotion_decision_record(
        readiness,
        readiness_path=readiness_path,
        decision="approved",
        decided_by="operator",
    )


def _state_ledger(decision: dict[str, Any], decision_path: str) -> dict[str, Any]:
    return create_state_ledger_record(
        [(decision, decision_path)],
        ledger_name="test-ledger",
    )


def _artifact_index(tmp_path: Path) -> dict[str, Any]:
    return create_artifact_index_record(tmp_path)


def _snapshot(
    artifact_index: dict[str, Any],
    state_ledger: dict[str, Any],
    artifact_index_path: str,
    state_ledger_path: str,
) -> dict[str, Any]:
    return create_snapshot_record(
        artifact_index,
        state_ledger,
        artifact_index_path=artifact_index_path,
        state_ledger_path=state_ledger_path,
        snapshot_name="test-snapshot",
    )


# ---------------------------------------------------------------------------
# Unit Tests
# ---------------------------------------------------------------------------


def test_valid_partial_chain(tmp_path: Path) -> None:
    # 1. Generate records
    p = _proposal()
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    a = _approval(p, "proposal.json")
    a_path = tmp_path / "approval.json"
    a_path.write_text(json_lib.dumps(a))

    pf = _preflight(p, a, "proposal.json", "approval.json")
    pf_path = tmp_path / "preflight.json"
    pf_path.write_text(json_lib.dumps(pf))

    # 2. Run verification
    report = verify_artifact_chain([p_path, a_path, pf_path])

    assert report["valid"] is True
    assert report["status"] == "valid"
    assert report["counts"]["files"] == 3
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 0
    assert len(report["errors"]) == 0


def test_valid_full_chain(tmp_path: Path) -> None:
    # Build complete universe of records
    p = _proposal()
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    a = _approval(p, "proposal.json")
    a_path = tmp_path / "approval.json"
    a_path.write_text(json_lib.dumps(a))

    pf = _preflight(p, a, "proposal.json", "approval.json")
    pf_path = tmp_path / "preflight.json"
    pf_path.write_text(json_lib.dumps(pf))

    r = _receipt(pf, "preflight.json")
    r_path = tmp_path / "receipt.json"
    r_path.write_text(json_lib.dumps(r))

    s = _chain_summary(
        p, a, pf, r, "proposal.json", "approval.json", "preflight.json", "receipt.json"
    )
    s_path = tmp_path / "summary.json"
    s_path.write_text(json_lib.dumps(s))

    h = _handoff_bundle(s, "summary.json")
    h_path = tmp_path / "bundle.json"
    h_path.write_text(json_lib.dumps(h))

    rc = _receive(h, "bundle.json")
    rc_path = tmp_path / "receive.json"
    rc_path.write_text(json_lib.dumps(rc))

    readiness = _readiness()
    readiness_path = tmp_path / "readiness.json"
    readiness_path.write_text(json_lib.dumps(readiness))

    decision = _promotion_decision(readiness, "readiness.json")
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(json_lib.dumps(decision))

    ledger = _state_ledger(decision, "decision.json")
    ledger_path = tmp_path / "ledger.json"
    ledger_path.write_text(json_lib.dumps(ledger))

    idx = _artifact_index(tmp_path)
    idx_path = tmp_path / "index.json"
    idx_path.write_text(json_lib.dumps(idx))

    snap = _snapshot(idx, ledger, "index.json", "ledger.json")
    snap_path = tmp_path / "snapshot.json"
    snap_path.write_text(json_lib.dumps(snap))

    all_paths = [
        p_path,
        a_path,
        pf_path,
        r_path,
        s_path,
        h_path,
        rc_path,
        readiness_path,
        decision_path,
        ledger_path,
        idx_path,
        snap_path,
    ]
    report = verify_artifact_chain(all_paths)

    assert report["valid"] is True
    assert report["counts"]["files"] == 12
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 0


def test_broken_digest(tmp_path: Path) -> None:
    p = _proposal()
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    a = _approval(p, "proposal.json")
    # Mutate proposal sha256 to a wrong value
    a["proposal"]["sha256"] = "a" * 64
    a_path = tmp_path / "approval.json"
    a_path.write_text(json_lib.dumps(a))

    report = verify_artifact_chain([p_path, a_path])

    assert report["valid"] is False
    assert report["status"] == "invalid"
    assert report["counts"]["broken_links"] == 1
    assert any("Digest mismatch" in err for err in report["errors"])


def test_wrong_referenced_kind(tmp_path: Path) -> None:
    p = _proposal()
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    a = _approval(p, "proposal.json")
    # Mutate expected kind
    a["proposal"]["expected_kind"] = "builder_ii.wrong_kind"
    # Actually, approval_records does not have expected_kind in schema, but let's test a record type that does,
    # or just mutate proposal's kind to another valid kind and see kind mismatch.
    # Let's mutate proposal kind inside proposal.json to builder_ii.approval_record!
    p["kind"] = "builder_ii.approval_record"
    p_path.write_text(json_lib.dumps(p))

    a_path = tmp_path / "approval.json"
    a_path.write_text(json_lib.dumps(a))
    report = verify_artifact_chain([p_path, a_path])

    assert report["valid"] is False
    assert report["counts"]["broken_links"] >= 1
    assert any("Kind mismatch" in err for err in report["errors"])


def test_missing_referenced_file(tmp_path: Path) -> None:
    p = _proposal()
    a = _approval(p, "nonexistent_proposal.json")
    a_path = tmp_path / "approval.json"
    a_path.write_text(json_lib.dumps(a))

    # Verify only approval without proposal (nor does proposal exist on disk at that relative path)
    report = verify_artifact_chain([a_path])

    assert report["valid"] is False
    assert report["counts"]["broken_links"] == 1
    assert any("could not be resolved" in err for err in report["errors"])


def test_ambiguous_digest_match(tmp_path: Path) -> None:
    p = _proposal()
    p_path1 = tmp_path / "proposal1.json"
    p_path2 = tmp_path / "proposal2.json"
    p_content = json_lib.dumps(p)
    p_path1.write_text(p_content)
    p_path2.write_text(p_content)

    # approval refers to a nonexistent relative path, causing digest fallback
    a = _approval(p, "nonexistent.json")
    a_path = tmp_path / "approval.json"
    a_path.write_text(json_lib.dumps(a))

    # Run verification with both duplicate proposals loaded
    report = verify_artifact_chain([p_path1, p_path2, a_path])

    assert report["valid"] is False
    assert report["counts"]["broken_links"] == 1
    assert any("Ambiguous digest fallback match" in err for err in report["errors"])


def test_invalid_native_record(tmp_path: Path) -> None:
    p = _proposal()
    # Mutate governance to invalid ENABLED state
    p["governance"]["model_execution"] = "ENABLED"
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    report = verify_artifact_chain([p_path])

    assert report["valid"] is False
    assert report["counts"]["native_invalid"] == 1
    assert any("Native validation error" in err for err in report["errors"])


def test_goal2_assignment_chain_resolves_source_refs(tmp_path: Path) -> None:
    fixture = build_goal2_assignment_fixture(tmp_path)
    paths = list(fixture["paths"].values())

    report = verify_artifact_chain(paths)

    assert report["valid"] is True, report["errors"]
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 0
    assert report["counts"]["links"] >= 20
    assert any(
        link["source_kind"] == "builder_ii.agent_assignment_plan"
        for link in report["links"]
    )
    assert any(
        link["source_kind"] == "builder_ii.orchestration_assignment_plan"
        for link in report["links"]
    )
    assert any(
        link["source_kind"] == "builder_ii.orchestration_assignment_dry_run"
        for link in report["links"]
    )


def test_goal2_assignment_chain_detects_source_ref_digest_mismatch(
    tmp_path: Path,
) -> None:
    fixture = build_goal2_assignment_fixture(tmp_path)
    target_path = fixture["paths"]["target_profile"]
    target = json_lib.loads(target_path.read_text(encoding="utf-8"))
    target["description"] = "changed after assignment binding"
    target_path.write_text(
        json_lib.dumps(target, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    report = verify_artifact_chain([fixture["paths"]["assignment"], target_path])

    assert report["valid"] is False
    assert report["counts"]["broken_links"] == 1
    assert any("Digest mismatch" in err for err in report["errors"])


def test_chain_accepts_verification_execution_plan_artifact(tmp_path: Path) -> None:
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = tmp_path / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    report = verify_artifact_chain([plan_path])

    assert report["valid"] is True
    assert report["counts"]["files"] == 1
    assert report["counts"]["native_invalid"] == 0


def test_chain_rejects_malformed_verification_execution_plan_artifact(tmp_path: Path) -> None:
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan["execution_enabled"] = True
    plan = attach_digest(plan, digest_key="verification_execution_plan_digest")
    plan_path = tmp_path / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    report = verify_artifact_chain([plan_path])

    assert report["valid"] is False
    assert report["counts"]["native_invalid"] == 1
    assert any("execution_enabled must be false" in error for error in report["errors"])


def test_chain_accepts_verification_execution_approval_artifact(tmp_path: Path) -> None:
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path="verification-execution-plan.json",
        approval_actor="Joshua Shay",
        approval_reason="Approve passive B1.1 verification plan for future B1.3 runner testing.",
        generated_at="2026-06-30T00:00:01+00:00",
    )
    approval_path = tmp_path / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)

    report = verify_artifact_chain([approval_path])

    assert report["valid"] is True
    assert report["counts"]["files"] == 1
    assert report["counts"]["native_invalid"] == 0


def test_chain_rejects_malformed_verification_execution_approval_artifact(tmp_path: Path) -> None:
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path="verification-execution-plan.json",
        approval_actor="Joshua Shay",
        approval_reason="Approve passive B1.1 verification plan for future B1.3 runner testing.",
        generated_at="2026-06-30T00:00:01+00:00",
    )
    approval["approval_enables_execution"] = True
    approval = attach_digest(approval, digest_key="verification_execution_approval_digest")
    approval_path = tmp_path / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)

    report = verify_artifact_chain([approval_path])

    assert report["valid"] is False
    assert report["counts"]["native_invalid"] == 1
    assert any("approval_enables_execution must be false" in error for error in report["errors"])


def test_chain_accepts_verification_execution_ledger_record(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".builder" / "verification"
    artifact_root.mkdir(parents=True, exist_ok=True)
    ledger_root = tmp_path / ".builder" / "ledger"

    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = artifact_root / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Joshua Shay",
        approval_reason="Approve bounded platform_status verification runner proof.",
        approved_command_profiles=["platform_status"],
        approved_step_ids=["platform_status"],
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = artifact_root / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)

    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        generated_at="2026-06-30T00:02:00+00:00",
        receipt_status="EXECUTED",
        executed_steps=[{"step_id": "platform_status", "status": "success", "profile": "platform_status"}],
        skipped_steps=[],
        process_results=[
            {
                "step_id": "platform_status",
                "profile": "platform_status",
                "command_profile_ref": "verification_profiles.builder_full.platform_status",
                "status": "success",
                "returncode": 0,
                "timeout_seconds": 30,
                "shell": False,
                "argv_digest": "0" * 64,
                "stdout_sha256": "1" * 64,
                "stderr_sha256": "2" * 64,
                "stdout_excerpt": "builder-II platform status\n",
                "stderr_excerpt": "",
                "stdout_truncated": False,
                "stderr_truncated": False,
            }
        ],
        preflight_git_state={"state_label": "preflight", "captured": True, "returncode": 0, "porcelain_sha256": "3" * 64, "porcelain_lines": [], "stderr_sha256": "4" * 64},
        postflight_git_state={"state_label": "postflight", "captured": True, "returncode": 0, "porcelain_sha256": "3" * 64, "porcelain_lines": [], "stderr_sha256": "4" * 64},
        workspace_mutation_detected=False,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    )
    receipt_path = artifact_root / "verification-execution-receipt.json"
    write_verification_execution_receipt(receipt, receipt_path)

    record = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
    )
    record_path = ledger_root / "verification-execution-ledger.json"
    write_verification_execution_ledger_record(record, record_path)

    report = verify_artifact_chain([record_path])

    assert report["valid"] is True
    assert report["counts"]["files"] == 1
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 0


def test_chain_accepts_verification_execution_ledger_integrity_report(tmp_path: Path) -> None:
    artifact_root = tmp_path / ".builder" / "verification"
    artifact_root.mkdir(parents=True, exist_ok=True)
    ledger_root = tmp_path / ".builder" / "ledger"

    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = artifact_root / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Joshua Shay",
        approval_reason="Approve bounded platform_status verification runner proof.",
        approved_command_profiles=["platform_status"],
        approved_step_ids=["platform_status"],
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = artifact_root / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)

    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        generated_at="2026-06-30T00:02:00+00:00",
        receipt_status="EXECUTED",
        executed_steps=[{"step_id": "platform_status", "status": "success", "profile": "platform_status"}],
        skipped_steps=[],
        process_results=[
            {
                "step_id": "platform_status",
                "profile": "platform_status",
                "command_profile_ref": "verification_profiles.builder_full.platform_status",
                "status": "success",
                "returncode": 0,
                "timeout_seconds": 30,
                "shell": False,
                "argv_digest": "0" * 64,
                "stdout_sha256": "1" * 64,
                "stderr_sha256": "2" * 64,
                "stdout_excerpt": "builder-II platform status\n",
                "stderr_excerpt": "",
                "stdout_truncated": False,
                "stderr_truncated": False,
            }
        ],
        preflight_git_state={"state_label": "preflight", "captured": True, "returncode": 0, "porcelain_sha256": "3" * 64, "porcelain_lines": [], "stderr_sha256": "4" * 64},
        postflight_git_state={"state_label": "postflight", "captured": True, "returncode": 0, "porcelain_sha256": "3" * 64, "porcelain_lines": [], "stderr_sha256": "4" * 64},
        workspace_mutation_detected=False,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    )
    receipt_path = artifact_root / "verification-execution-receipt.json"
    write_verification_execution_receipt(receipt, receipt_path)

    record = index_verification_execution_receipt(
        receipt_path=receipt_path,
        plan_path=plan_path,
        approval_path=approval_path,
    )
    record_path = ledger_root / "verification-execution-ledger.json"
    write_verification_execution_ledger_record(record, record_path)
    integrity_report = validate_verification_execution_ledger_integrity(ledger_root=ledger_root)
    report_path = tmp_path / "verification-execution-ledger-integrity-report.json"
    report_path.write_text(json_lib.dumps(integrity_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = verify_artifact_chain([record_path, report_path])

    assert report["valid"] is True
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["broken_links"] == 0


# ---------------------------------------------------------------------------
# CLI Command Tests
# ---------------------------------------------------------------------------


def test_cli_verify_artifacts_stdout(tmp_path: Path) -> None:
    p = _proposal()
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    runner = CliRunner()
    result = runner.invoke(chain_app, ["verify-artifacts", str(p_path)])

    assert result.exit_code == 0
    data = json_lib.loads(result.output)
    assert data["kind"] == "builder_ii.artifact_chain_verification_report"
    assert data["valid"] is True


def test_cli_verify_artifacts_output_file(tmp_path: Path) -> None:
    p = _proposal()
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    out_file = tmp_path / "report.json"
    runner = CliRunner()
    result = runner.invoke(
        chain_app, ["verify-artifacts", str(p_path), "--output", str(out_file)]
    )

    assert result.exit_code == 0
    assert "Verification report written to" in result.output

    assert out_file.exists()
    data = json_lib.loads(out_file.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.artifact_chain_verification_report"
    assert data["valid"] is True


def test_cli_verify_artifacts_failure_exit_code(tmp_path: Path) -> None:
    p = _proposal()
    p["governance"]["model_execution"] = "ENABLED"
    p_path = tmp_path / "proposal.json"
    p_path.write_text(json_lib.dumps(p))

    runner = CliRunner()
    result = runner.invoke(chain_app, ["verify-artifacts", str(p_path)])

    assert result.exit_code == 1
    data = json_lib.loads(result.output)
    assert data["valid"] is False
