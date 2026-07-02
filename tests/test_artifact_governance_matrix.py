"""Cross-artifact governance invariant matrix for all governed record types.

Enumerates every record kind in the governed chain, creates a minimal valid
fixture for each, and asserts shared invariants that must hold across all
record types to prevent governance drift.
"""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.approval_records import create_approval_record, validate_approval_record
from builder_ii.artifact_index_records import create_artifact_index_record, validate_artifact_index_record
from builder_ii.chain_summary_records import create_chain_summary_record, validate_chain_summary_record
from builder_ii.goose_command_proposal import create_goose_command_proposal, validate_goose_command_proposal
from builder_ii.handoff_bundle_records import create_handoff_bundle_record, validate_handoff_bundle_record
from builder_ii.preflight_records import create_preflight_record, validate_preflight_record
from builder_ii.promotion_decision_records import create_promotion_decision_record, validate_promotion_decision_record
from builder_ii.promotion_readiness_records import (
    create_promotion_readiness_record,
    validate_promotion_readiness_record,
)
from builder_ii.receipt_records import create_receipt_record, validate_receipt_record
from builder_ii.receive_records import create_receive_record, validate_receive_record
from builder_ii.snapshot_records import create_snapshot_record, validate_snapshot_record
from builder_ii.state_ledger_records import create_state_ledger_record, validate_state_ledger_record

# ---------------------------------------------------------------------------
# Minimal fixture factories
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
        manifest_path="/tmp/manifest.json",
        command="echo test",
        risk_level="low",
    )


def _approval() -> dict[str, Any]:
    return create_approval_record(
        _proposal(),
        proposal_path="/tmp/proposal.json",
        decision="approved",
        decided_by="operator",
    )


def _preflight() -> dict[str, Any]:
    return create_preflight_record(
        _proposal(),
        _approval(),
        proposal_path="/tmp/proposal.json",
        approval_path="/tmp/approval.json",
        verification_refs=["ref"],
    )


def _receipt() -> dict[str, Any]:
    return create_receipt_record(
        _preflight(),
        preflight_path="/tmp/preflight.json",
        status="passed",
        recorded_by="operator",
        evidence_refs=["evidence"],
    )


def _chain_summary() -> dict[str, Any]:
    return create_chain_summary_record(
        _proposal(),
        _approval(),
        _preflight(),
        _receipt(),
        proposal_path="/tmp/proposal.json",
        approval_path="/tmp/approval.json",
        preflight_path="/tmp/preflight.json",
        receipt_path="/tmp/receipt.json",
    )


def _handoff_bundle() -> dict[str, Any]:
    return create_handoff_bundle_record(
        _chain_summary(),
        summary_path="/tmp/summary.json",
        bundle_name="test-bundle",
    )


def _receive() -> dict[str, Any]:
    return create_receive_record(
        _handoff_bundle(),
        bundle_path="/tmp/bundle.json",
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


def _promotion_decision() -> dict[str, Any]:
    return create_promotion_decision_record(
        _readiness(),
        readiness_path="/tmp/readiness.json",
        decision="approved",
        decided_by="operator",
    )


def _state_ledger() -> dict[str, Any]:
    return create_state_ledger_record(
        [(_promotion_decision(), "/tmp/decision.json")],
        ledger_name="test-ledger",
    )


def _artifact_index(tmp_path: Path) -> dict[str, Any]:
    return create_artifact_index_record(tmp_path)


def _snapshot(tmp_path: Path) -> dict[str, Any]:
    return create_snapshot_record(
        _artifact_index(tmp_path),
        _state_ledger(),
        artifact_index_path="/tmp/index.json",
        state_ledger_path="/tmp/ledger.json",
        snapshot_name="test-snapshot",
    )


# ---------------------------------------------------------------------------
# Record registry: (label, factory, validator)
# ---------------------------------------------------------------------------

_RECORD_KINDS_NO_TMP: list[tuple[str, Any, Any]] = [
    ("goose_command_proposal", _proposal, validate_goose_command_proposal),
    ("approval_record", _approval, validate_approval_record),
    ("preflight_record", _preflight, validate_preflight_record),
    ("receipt_record", _receipt, validate_receipt_record),
    ("chain_summary_record", _chain_summary, validate_chain_summary_record),
    ("handoff_bundle_record", _handoff_bundle, validate_handoff_bundle_record),
    ("receive_record", _receive, validate_receive_record),
    ("promotion_readiness_record", _readiness, validate_promotion_readiness_record),
    ("promotion_decision_record", _promotion_decision, validate_promotion_decision_record),
    ("state_ledger_record", _state_ledger, validate_state_ledger_record),
]

# Record types that use grants_runtime_authority / grants_action_authority
# (command proposal uses a different authority model: executed, runtime_started, etc.)
_GRANTS_AUTHORITY_RECORDS = {
    "approval_record",
    "preflight_record",
    "receipt_record",
    "chain_summary_record",
    "handoff_bundle_record",
    "receive_record",
    "promotion_readiness_record",
    "promotion_decision_record",
    "state_ledger_record",
    "artifact_index_record",
    "snapshot_record",
}


def _all_records(tmp_path: Path) -> list[tuple[str, dict[str, Any], Any]]:
    """Build all record fixtures and return (label, record, validator) triples."""
    result: list[tuple[str, dict[str, Any], Any]] = []
    for label, factory, validator in _RECORD_KINDS_NO_TMP:
        result.append((label, factory(), validator))
    result.append(("artifact_index_record", _artifact_index(tmp_path), validate_artifact_index_record))
    result.append(("snapshot_record", _snapshot(tmp_path), validate_snapshot_record))
    return result


# ---------------------------------------------------------------------------
# Shared invariant checks
# ---------------------------------------------------------------------------


def test_all_records_have_kind(tmp_path: Path) -> None:
    """Every record must have a non-empty 'kind' field."""
    for label, record, _validator in _all_records(tmp_path):
        assert "kind" in record, f"{label}: missing kind"
        assert isinstance(record["kind"], str), f"{label}: kind not string"
        assert record["kind"], f"{label}: kind is empty"


def test_all_records_have_schema_version(tmp_path: Path) -> None:
    """Every record must have an integer schema_version."""
    for label, record, _validator in _all_records(tmp_path):
        assert "schema_version" in record, f"{label}: missing schema_version"
        assert isinstance(record["schema_version"], int), f"{label}: schema_version not int"


def test_all_records_have_recorded_only_state(tmp_path: Path) -> None:
    """Every record must declare record_state=RECORDED_ONLY or execution_state=PROPOSED_ONLY."""
    for label, record, _validator in _all_records(tmp_path):
        if "record_state" in record:
            assert record["record_state"] == "RECORDED_ONLY", f"{label}: record_state drift"
        elif "execution_state" in record:
            assert record["execution_state"] == "PROPOSED_ONLY", f"{label}: execution_state drift"
        else:
            raise AssertionError(f"{label}: missing record_state or execution_state")


def test_all_records_have_disabled_current_state(tmp_path: Path) -> None:
    """Every record must declare its current state as DISABLED."""
    for label, record, _validator in _all_records(tmp_path):
        state_key = "current_state" if "current_state" in record else "current_runtime_state"
        assert state_key in record, f"{label}: missing current state key"
        assert record[state_key] == "DISABLED", f"{label}: {state_key} must be DISABLED"


def test_all_records_have_empty_performed_actions(tmp_path: Path) -> None:
    """Records with performed_actions must have it empty."""
    for label, record, _validator in _all_records(tmp_path):
        if "performed_actions" in record:
            assert record["performed_actions"] == [], f"{label}: performed_actions must be empty"


def test_grants_authority_records_deny_runtime_authority(tmp_path: Path) -> None:
    """Records that use grants_runtime_authority must set it false."""
    for label, record, _validator in _all_records(tmp_path):
        if label in _GRANTS_AUTHORITY_RECORDS:
            assert record.get("grants_runtime_authority") is False, f"{label}: grants_runtime_authority must be false"
            assert record.get("grants_action_authority") is False, f"{label}: grants_action_authority must be false"


def test_command_proposal_denies_execution(tmp_path: Path) -> None:
    """Command proposal uses executed=False and runtime_started=False for authority denial."""
    for label, record, _validator in _all_records(tmp_path):
        if label == "goose_command_proposal":
            assert record["executed"] is False
            assert record["runtime_started"] is False
            assert record["goose_process_started"] is False
            assert record["requires_human_approval"] is True
            assert record["commands_executed"] == []
            assert record["shell_commands_executed"] == []
            assert record["source_writes_applied"] == []
            assert record["patches_applied"] == []
            assert record["model_calls"] == []


def test_all_records_have_governance_object(tmp_path: Path) -> None:
    """Every record must have a governance dict."""
    for label, record, _validator in _all_records(tmp_path):
        assert "governance" in record, f"{label}: missing governance"
        assert isinstance(record["governance"], dict), f"{label}: governance not dict"


def test_all_records_governance_artifact_is_not_authority(tmp_path: Path) -> None:
    """No artifact is authority."""
    for label, record, _validator in _all_records(tmp_path):
        gov = record["governance"]
        assert gov.get("artifact_is_authority") is False, f"{label}: artifact_is_authority must be false"


def test_all_records_governance_no_core_workbench_coupling(tmp_path: Path) -> None:
    """No record may have core workbench coupling."""
    for label, record, _validator in _all_records(tmp_path):
        gov = record["governance"]
        assert gov.get("core_workbench_coupling") == "NONE", f"{label}: core_workbench_coupling must be NONE"


def test_all_records_governance_model_execution_disabled(tmp_path: Path) -> None:
    """model_execution must be DISABLED in all governance blocks."""
    for label, record, _validator in _all_records(tmp_path):
        gov = record["governance"]
        assert gov.get("model_execution") == "DISABLED", f"{label}: governance.model_execution must be DISABLED"


def test_all_records_governance_source_writes_disabled_where_present(tmp_path: Path) -> None:
    """source_writes must be DISABLED in all governance blocks that include it."""
    for label, record, _validator in _all_records(tmp_path):
        gov = record["governance"]
        if "source_writes" in gov:
            assert gov["source_writes"] == "DISABLED", f"{label}: governance.source_writes must be DISABLED"


def test_all_records_governance_memory_mutation_disabled_where_present(tmp_path: Path) -> None:
    """memory_mutation must be DISABLED in all governance blocks that include it."""
    for label, record, _validator in _all_records(tmp_path):
        gov = record["governance"]
        if "memory_mutation" in gov:
            assert gov["memory_mutation"] == "DISABLED", f"{label}: governance.memory_mutation must be DISABLED"


def test_all_records_governance_runtime_execution_disabled_where_present(tmp_path: Path) -> None:
    """runtime_execution must be DISABLED in all governance blocks that include it."""
    for label, record, _validator in _all_records(tmp_path):
        gov = record["governance"]
        if "runtime_execution" in gov:
            assert gov["runtime_execution"] == "DISABLED", f"{label}: governance.runtime_execution must be DISABLED"


def test_all_records_pass_their_own_validator(tmp_path: Path) -> None:
    """Every created record must pass its own validator with zero errors."""
    for label, record, validator in _all_records(tmp_path):
        errors = validator(record)
        assert errors == [], f"{label}: validation errors: {errors}"


def test_all_records_json_roundtrip_preserves_validity(tmp_path: Path) -> None:
    """JSON dump/load roundtrip must preserve validation."""
    for label, record, validator in _all_records(tmp_path):
        serialized = json_lib.dumps(record, indent=2, sort_keys=True)
        restored = json_lib.loads(serialized)
        errors = validator(restored)
        assert errors == [], f"{label}: post-roundtrip validation errors: {errors}"


def test_grants_authority_validators_reject_authority_drift(tmp_path: Path) -> None:
    """Mutating authority fields must produce validation errors for records that enforce them."""
    for label, record, validator in _all_records(tmp_path):
        if label not in _GRANTS_AUTHORITY_RECORDS:
            continue
        mutated = json_lib.loads(json_lib.dumps(record))
        mutated["grants_runtime_authority"] = True
        mutated["grants_action_authority"] = True
        mutated["governance"]["artifact_is_authority"] = True
        mutated["governance"]["core_workbench_coupling"] = "COUPLED"
        errors = validator(mutated)
        assert any("grants_runtime_authority" in e for e in errors), (
            f"{label}: must reject grants_runtime_authority=true"
        )
        assert any("grants_action_authority" in e for e in errors), f"{label}: must reject grants_action_authority=true"
        assert any("artifact_is_authority" in e for e in errors), f"{label}: must reject artifact_is_authority=true"
        assert any("core_workbench_coupling" in e for e in errors), (
            f"{label}: must reject core_workbench_coupling=COUPLED"
        )


def test_command_proposal_validator_rejects_execution_drift(tmp_path: Path) -> None:
    """Command proposal validator must reject if execution fields are enabled."""
    proposal = _proposal()
    mutated = json_lib.loads(json_lib.dumps(proposal))
    mutated["executed"] = True
    mutated["runtime_started"] = True
    mutated["goose_process_started"] = True
    mutated["governance"]["artifact_is_authority"] = True
    mutated["governance"]["core_workbench_coupling"] = "COUPLED"
    errors = validate_goose_command_proposal(mutated)
    assert any("executed" in e for e in errors)
    assert any("runtime_started" in e for e in errors)
    assert any("goose_process_started" in e for e in errors)
    assert any("artifact_is_authority" in e for e in errors)
    assert any("core_workbench_coupling" in e for e in errors)


def test_validators_reject_governance_execution_drift(tmp_path: Path) -> None:
    """Enabling execution governance keys must produce validation errors.

    Tests only governance keys that each validator actually enforces, based on
    the record's own governance block keys that are set to DISABLED.
    """
    _ENFORCED_GOV_KEYS: dict[str, set[str]] = {
        "goose_command_proposal": {"model_execution", "source_writes", "memory_mutation", "runtime_execution"},
        "approval_record": {"model_execution", "source_writes", "memory_mutation", "runtime_execution"},
        "preflight_record": {"model_execution", "source_writes", "memory_mutation", "runtime_execution"},
        "receipt_record": {"runtime_execution", "model_execution", "source_writes", "memory_mutation"},
        "chain_summary_record": {"runtime_execution", "model_execution", "source_writes", "memory_mutation"},
        "handoff_bundle_record": {"runtime_execution", "model_execution", "source_writes", "memory_mutation"},
        "receive_record": set(),  # validator only checks artifact_is_authority/core_workbench_coupling
        "promotion_readiness_record": {"runtime_execution", "model_execution", "source_writes", "memory_mutation"},
        "promotion_decision_record": {"runtime_execution", "model_execution", "source_writes", "memory_mutation"},
        "state_ledger_record": {"runtime_execution", "model_execution", "source_writes", "memory_mutation"},
        "artifact_index_record": set(),  # validator only checks artifact_is_authority/core_workbench_coupling
        "snapshot_record": {"runtime_execution", "model_execution", "source_writes", "memory_mutation"},
    }

    for label, record, validator in _all_records(tmp_path):
        enforced = _ENFORCED_GOV_KEYS.get(label, set())
        if not enforced:
            continue
        mutated = json_lib.loads(json_lib.dumps(record))
        gov = mutated["governance"]
        for key in enforced:
            if key in gov:
                gov[key] = "ENABLED"
        errors = validator(mutated)
        for key in enforced:
            if key in record["governance"]:
                assert any(key in e for e in errors), f"{label}: must reject {key}=ENABLED"


def test_record_count_covers_full_governed_chain(tmp_path: Path) -> None:
    """Verify we are testing all 12 record types in the governed chain."""
    records = _all_records(tmp_path)
    assert len(records) == 12, f"Expected 12 record types, got {len(records)}"
    kinds = {record["kind"] for _, record, _ in records}
    expected_kinds = {
        "builder_ii.goose_command_proposal",
        "builder_ii.approval_record",
        "builder_ii.preflight_record",
        "builder_ii.receipt_record",
        "builder_ii.chain_summary_record",
        "builder_ii.handoff_bundle_record",
        "builder_ii.receive_record",
        "builder_ii.promotion_readiness_record",
        "builder_ii.promotion_decision_record",
        "builder_ii.state_ledger_record",
        "builder_ii.artifact_index_record",
        "builder_ii.snapshot_record",
    }
    assert kinds == expected_kinds, f"Kind mismatch: missing={expected_kinds - kinds}, extra={kinds - expected_kinds}"
