import json as json_lib
from pathlib import Path

from orchestration_assignment_fixtures import build_goal2_assignment_fixture

from builder_ii.adapters.goose.goose_command_proposal import (
    create_goose_command_proposal,
    write_goose_command_proposal,
)
from builder_ii.adapters.goose.goose_session import create_goose_session_manifest
from builder_ii.core.config import load_settings
from builder_ii.core.config_schema import attach_digest
from builder_ii.governance.ledger.artifact_index_records import (
    create_artifact_index_record,
    dumps_artifact_index_record,
    validate_artifact_index_record,
    validate_artifact_index_record_file,
)
from builder_ii.governance.ledger.snapshot_records import create_snapshot_record, write_snapshot_record
from builder_ii.governance.ledger.state_ledger_records import (
    create_state_ledger_record,
    write_state_ledger_record,
)
from builder_ii.lifecycle.candidate.approval_records import create_approval_record, write_approval_record
from builder_ii.lifecycle.candidate.promotion_decision_records import (
    create_promotion_decision_record,
    write_promotion_decision_record,
)
from builder_ii.lifecycle.candidate.promotion_readiness_records import (
    create_promotion_readiness_record,
    write_promotion_readiness_record,
)
from builder_ii.lifecycle.candidate.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)


def _write_known_artifacts(tmp_path: Path) -> None:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="artifact index check",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    proposal = create_goose_command_proposal(
        manifest,
        manifest_path=tmp_path / "goose-session.json",
        command="verify",
        risk_level="low",
    )
    approval = create_approval_record(
        proposal,
        proposal_path=tmp_path / "proposal.json",
        decision="approved",
        decided_by="operator",
    )
    write_goose_command_proposal(proposal, tmp_path / "proposal.json")
    write_approval_record(approval, tmp_path / "approval.json")


def _write_newer_artifacts(tmp_path: Path) -> None:
    readiness_path = tmp_path / "readiness.json"
    decision_path = tmp_path / "decision.json"
    ledger_path = tmp_path / "ledger.json"
    snapshot_path = tmp_path / "snapshot.json"

    readiness = create_promotion_readiness_record(
        capability_name="artifact-index-backfill",
        docs_refs=("docs/ARTIFACT_INDEX.md",),
        tests_refs=("tests/test_artifact_index_records.py",),
        cli_refs=("builder-index",),
        failure_mode_refs=("unknown artifacts remain incomplete",),
        approval_boundary_refs=("metadata only",),
        output_artifact_refs=("artifact-index.json",),
        rollback_refs=("revert validator entry",),
        verification_refs=("uv run pytest tests/test_artifact_index_records.py tests/test_artifact_index_cli.py -q",),
    )
    write_promotion_readiness_record(readiness, readiness_path)

    decision = create_promotion_decision_record(
        readiness,
        readiness_path=readiness_path,
        decision="approved",
        decided_by="operator",
        reason="test fixture",
    )
    write_promotion_decision_record(decision, decision_path)

    ledger = create_state_ledger_record([(decision, decision_path)], ledger_name="artifact-index-test")
    write_state_ledger_record(ledger, ledger_path)

    artifact_index = create_artifact_index_record(tmp_path)
    snapshot = create_snapshot_record(
        artifact_index,
        ledger,
        artifact_index_path="artifact-index.json",
        state_ledger_path=ledger_path,
        snapshot_name="artifact-index-test",
    )
    write_snapshot_record(snapshot, snapshot_path)


def test_create_complete_artifact_index_shape(tmp_path: Path) -> None:
    _write_known_artifacts(tmp_path)
    record = create_artifact_index_record(tmp_path)

    assert record["kind"] == "builder_ii.artifact_index_record"
    assert record["schema_version"] == 1
    assert record["record_state"] == "RECORDED_ONLY"
    assert record["current_state"] == "DISABLED"
    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["counts"]["total"] == 2
    assert record["counts"]["known"] == 2
    assert record["counts"]["invalid"] == 0
    assert {entry["kind"] for entry in record["artifacts"]} == {
        "builder_ii.goose_command_proposal",
        "builder_ii.approval_record",
    }
    assert record["grants_runtime_authority"] is False
    assert record["grants_action_authority"] is False
    assert record["performed_actions"] == []
    assert record["governance"]["artifact_is_authority"] is False
    assert record["governance"]["core_workbench_coupling"] == "NONE"
    assert validate_artifact_index_record(record) == []


def test_index_recognizes_newer_artifact_records(tmp_path: Path) -> None:
    _write_newer_artifacts(tmp_path)
    record = create_artifact_index_record(tmp_path)

    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["counts"] == {
        "total": 4,
        "known": 4,
        "unknown": 0,
        "valid": 4,
        "invalid": 0,
    }
    assert {entry["kind"] for entry in record["artifacts"]} == {
        "builder_ii.promotion_readiness_record",
        "builder_ii.promotion_decision_record",
        "builder_ii.state_ledger_record",
        "builder_ii.snapshot_record",
    }
    assert all(entry["known"] is True for entry in record["artifacts"])
    assert all(entry["valid"] is True for entry in record["artifacts"])
    assert all(entry["errors"] == [] for entry in record["artifacts"])
    assert validate_artifact_index_record(record) == []


def test_index_recognizes_goal2_assignment_artifacts(tmp_path: Path) -> None:
    fixture = build_goal2_assignment_fixture(tmp_path)
    record = create_artifact_index_record(fixture["artifact_dir"])

    indexed_kinds = {entry["kind"] for entry in record["artifacts"]}

    assert record["status"] == "complete"
    assert record["complete"] is True
    assert record["counts"]["unknown"] == 0
    assert record["counts"]["invalid"] == 0
    assert {
        "builder_ii.agent_assignment_plan",
        "builder_ii.orchestration_assignment_plan",
        "builder_ii.orchestration_assignment_dry_run",
        "builder_ii.orchestration_assignment_validation_report",
    }.issubset(indexed_kinds)
    assert validate_artifact_index_record(record) == []


def test_index_recognizes_verification_execution_plan_artifact(tmp_path: Path) -> None:
    plan = finalize_verification_execution_plan(
        target_head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        tree_clean=True,
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    write_verification_execution_plan(plan, tmp_path / "verification-execution-plan.json")

    record = create_artifact_index_record(tmp_path)

    assert record["status"] == "complete"
    assert record["counts"]["known"] == 1
    assert record["counts"]["invalid"] == 0
    assert record["artifacts"][0]["kind"] == "builder_ii.verification_execution_plan"
    assert record["artifacts"][0]["valid"] is True


def test_index_rejects_malformed_verification_execution_plan_artifact(tmp_path: Path) -> None:
    plan = finalize_verification_execution_plan(
        target_head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        tree_clean=True,
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan["execution_enabled"] = True
    plan = attach_digest(plan, digest_key="verification_execution_plan_digest")
    write_verification_execution_plan(plan, tmp_path / "verification-execution-plan.json")

    record = create_artifact_index_record(tmp_path)

    assert record["status"] == "incomplete"
    assert record["counts"]["known"] == 1
    assert record["counts"]["invalid"] == 1
    assert record["artifacts"][0]["kind"] == "builder_ii.verification_execution_plan"
    assert any(
        "execution_enabled must be false or NOT_AUTHORIZED" in error for error in record["artifacts"][0]["errors"]
    )


def test_index_recognizes_verification_execution_approval_artifact(tmp_path: Path) -> None:
    plan = finalize_verification_execution_plan(
        target_head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        tree_clean=True,
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    approval = finalize_verification_execution_approval(expires_at="2030-01-01T00:00:00Z",
        plan=plan,
        plan_path="verification-execution-plan.json",
        approval_actor="Jane Operator",
        approval_reason="Approve passive B1.1 verification plan for future B1.3 runner testing.",
        generated_at="2026-06-30T00:00:01+00:00",
    )
    write_verification_execution_approval(approval, tmp_path / "verification-execution-approval.json")

    record = create_artifact_index_record(tmp_path)

    assert record["status"] == "complete"
    assert record["counts"]["known"] == 1
    assert record["counts"]["invalid"] == 0
    assert record["artifacts"][0]["kind"] == "builder_ii.verification_execution_approval"
    assert record["artifacts"][0]["valid"] is True


def test_index_rejects_malformed_verification_execution_approval_artifact(tmp_path: Path) -> None:
    plan = finalize_verification_execution_plan(
        target_head_sha="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        tree_clean=True,
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=".",
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    approval = finalize_verification_execution_approval(expires_at="2030-01-01T00:00:00Z",
        plan=plan,
        plan_path="verification-execution-plan.json",
        approval_actor="Jane Operator",
        approval_reason="Approve passive B1.1 verification plan for future B1.3 runner testing.",
        generated_at="2026-06-30T00:00:01+00:00",
    )
    approval["execution_enabled"] = True
    approval = attach_digest(approval, digest_key="verification_execution_approval_digest")
    write_verification_execution_approval(approval, tmp_path / "verification-execution-approval.json")

    record = create_artifact_index_record(tmp_path)

    assert record["status"] == "incomplete"
    assert record["counts"]["known"] == 1
    assert record["counts"]["invalid"] == 1
    assert record["artifacts"][0]["kind"] == "builder_ii.verification_execution_approval"
    assert any(
        "execution_enabled must be false or NOT_AUTHORIZED" in error for error in record["artifacts"][0]["errors"]
    )


def test_index_marks_unknown_artifact_incomplete(tmp_path: Path) -> None:
    (tmp_path / "unknown.json").write_text(json_lib.dumps({"kind": "unknown", "schema_version": 1}), encoding="utf-8")
    record = create_artifact_index_record(tmp_path)

    assert record["status"] == "incomplete"
    assert record["complete"] is False
    assert record["counts"]["unknown"] == 1
    assert record["counts"]["invalid"] == 1
    assert record["artifacts"][0]["errors"] == ["unknown artifact kind"]
    assert validate_artifact_index_record(record) == []


def test_index_recursive_option(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    _write_known_artifacts(nested)

    shallow = create_artifact_index_record(tmp_path)
    recursive = create_artifact_index_record(tmp_path, recursive=True)

    assert shallow["counts"]["total"] == 0
    assert recursive["counts"]["total"] == 2


def test_artifact_index_json_round_trip(tmp_path: Path) -> None:
    _write_known_artifacts(tmp_path)
    record = create_artifact_index_record(tmp_path)
    data = json_lib.loads(dumps_artifact_index_record(record))

    assert data["complete"] is True
    assert validate_artifact_index_record(data) == []


def test_validate_rejects_authority_changes(tmp_path: Path) -> None:
    _write_known_artifacts(tmp_path)
    record = create_artifact_index_record(tmp_path)
    record["record_state"] = "ACTIVE"
    record["grants_runtime_authority"] = True
    record["grants_action_authority"] = True
    record["performed_actions"] = ["verify"]
    record["governance"]["artifact_is_authority"] = True

    errors = validate_artifact_index_record(record)

    assert "record_state must be RECORDED_ONLY" in errors
    assert "grants_runtime_authority must be false or NOT_AUTHORIZED" in errors
    assert "grants_action_authority must be false or NOT_AUTHORIZED" in errors
    assert "performed_actions must be empty" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_artifact_index_record_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_artifact_index_record_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "artifact index record must be a JSON object" in validate_artifact_index_record_file(not_object)
