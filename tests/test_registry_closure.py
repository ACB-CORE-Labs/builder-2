import hashlib
import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
from builder_ii.artifact_chain_verification import extract_references, verify_artifact_chain
from builder_ii.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
from builder_ii.artifact_index_records import create_artifact_index_record, validate_artifact_index_record
from builder_ii.performance_measurements import PERFORMANCE_MEASUREMENT_KIND, create_performance_measurement_record
from builder_ii.readonly_inspection_promotion import READONLY_INSPECTION_PROMOTION_SPEC_KIND, create_readonly_inspection_promotion_spec
from builder_ii.research_adapters import RESEARCH_ADAPTER_KIND, create_research_adapter_artifact
from builder_ii.research_plans import RESEARCH_PLAN_KIND, create_research_plan_artifact
from builder_ii.readonly_inspection_reports import READONLY_INSPECTION_REPORT_KIND
from builder_ii.hitl_execution_records import (
    HITL_EXECUTION_REQUEST_KIND,
    HITL_EXECUTION_RECEIPT_KIND,
    create_hitl_execution_request,
    create_hitl_execution_receipt,
)
from builder_ii.hitl_patch_spec import (
    HITL_PATCH_APPLICATION_SPEC_KIND,
    create_hitl_patch_application_spec,
)
from builder_ii.rollback_artifacts import (
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
    create_rollback_plan,
    create_rollback_receipt,
)


CLOSURE_KINDS = {
    "builder_ii.target_profile",
    "builder_ii.verification_profile",
    "builder_ii.context_pack_record",
    "builder_ii.agent_profile_record",
    "builder_ii.git_state_record",
    RESEARCH_PLAN_KIND,
    RESEARCH_ADAPTER_KIND,
    PERFORMANCE_MEASUREMENT_KIND,
    READONLY_INSPECTION_PROMOTION_SPEC_KIND,
    READONLY_INSPECTION_REPORT_KIND,
    HITL_EXECUTION_REQUEST_KIND,
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_PATCH_APPLICATION_SPEC_KIND,
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
}

# ---------------------------------------------------------------------------
# Governance artifact kinds added in PR W / PR X / PR Y
# ---------------------------------------------------------------------------

GOVERNANCE_ARTIFACT_KINDS = {
    HITL_EXECUTION_REQUEST_KIND,
    HITL_EXECUTION_RECEIPT_KIND,
    HITL_PATCH_APPLICATION_SPEC_KIND,
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
}


def _digest(value: dict[str, Any]) -> str:
    raw = json_lib.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _plan() -> dict[str, Any]:
    return create_research_plan_artifact(
        target="builder",
        profile_name="research_planner",
        task="plan registry closure",
        topic="registry closure",
    )


def _adapter(plan: dict[str, Any]) -> dict[str, Any]:
    return create_research_adapter_artifact(
        target="builder",
        topic="registry closure",
        research_question="Which registries must stay aligned?",
        plan_path="research-plan.json",
        plan_sha256=_digest(plan),
    )


def _measurement() -> dict[str, Any]:
    return create_performance_measurement_record(
        target="builder",
        candidate_name="registry_closure",
        metric_name="closure_artifact_count",
        metric_value=4,
        unit="artifacts",
        method="operator supplied test fixture",
        source_ref="tests/test_registry_closure.py",
    )


# ---------------------------------------------------------------------------
# Governance artifact fixture factories
# ---------------------------------------------------------------------------

def _hitl_execution_request() -> dict[str, Any]:
    return create_hitl_execution_request(
        target_name="generic",
        command_proposal_ref="proposal.json",
        approval_record_ref="approval.json",
        preflight_record_ref="preflight.json",
        requested_by="operator",
        requested_at="2026-06-26T00:00:00Z",
        explicit_operator_intent="test fixture",
        command_preview="echo test",
    )


def _hitl_execution_receipt() -> dict[str, Any]:
    return create_hitl_execution_receipt(
        target_name="generic",
        request_ref="request.json",
    )


def _hitl_patch_application_spec() -> dict[str, Any]:
    return create_hitl_patch_application_spec(
        target_name="generic",
        patch_description="test patch",
        reason="test fixture",
    )


def _rollback_plan() -> dict[str, Any]:
    return create_rollback_plan(
        target_name="generic",
        related_artifact_refs=["receipt.json"],
        rollback_strategy="revert commit",
        operator_note="test fixture",
    )


def _rollback_receipt() -> dict[str, Any]:
    return create_rollback_receipt(
        target_name="generic",
        rollback_plan_ref="rollback-plan.json",
    )


# ---------------------------------------------------------------------------
# Original closure tests
# ---------------------------------------------------------------------------

def test_recent_artifact_kinds_are_registered_in_both_registries() -> None:
    for kind in CLOSURE_KINDS:
        assert kind in INDEX_VALIDATORS
        assert kind in CHAIN_VALIDATORS


def test_recent_artifact_fixtures_validate_through_both_registries() -> None:
    plan = _plan()
    records = [plan, _adapter(plan), _measurement(), create_readonly_inspection_promotion_spec(target="builder")]

    for record in records:
        kind = record["kind"]
        assert INDEX_VALIDATORS[kind](record) == []
        assert CHAIN_VALIDATORS[kind](record) == []


def test_artifact_index_recognizes_recent_artifacts(tmp_path: Path) -> None:
    plan = _plan()
    for filename, artifact in {
        "research-plan.json": plan,
        "research-adapter.json": _adapter(plan),
        "performance.json": _measurement(),
        "readonly-spec.json": create_readonly_inspection_promotion_spec(target="builder"),
    }.items():
        _write(tmp_path / filename, artifact)

    index = create_artifact_index_record(tmp_path)

    assert index["counts"] == {"total": 4, "known": 4, "unknown": 0, "valid": 4, "invalid": 0}
    assert validate_artifact_index_record(index) == []


def test_research_adapter_link_resolves_to_plan(tmp_path: Path) -> None:
    plan = _plan()
    adapter = _adapter(plan)
    plan_path = tmp_path / "research-plan.json"
    adapter_path = tmp_path / "research-adapter.json"
    _write(plan_path, plan)
    _write(adapter_path, adapter)

    report = verify_artifact_chain([adapter_path])

    assert report["valid"] is True
    assert report["counts"]["links"] == 1
    assert report["counts"]["resolved_links"] == 1
    assert report["links"][0]["field"] == "research_plan"
    assert report["links"][0]["target_kind_expected"] == RESEARCH_PLAN_KIND


# ---------------------------------------------------------------------------
# PR AA — Governance artifact registry closure tests
# ---------------------------------------------------------------------------


def test_governance_artifact_kinds_are_registered_in_both_registries() -> None:
    """Fails if any governance artifact kind from PR W/X/Y is missing from
    either the artifact index or chain verification registry."""
    for kind in GOVERNANCE_ARTIFACT_KINDS:
        assert kind in INDEX_VALIDATORS, f"{kind} missing from artifact index _VALIDATORS"
        assert kind in CHAIN_VALIDATORS, f"{kind} missing from chain verification VALIDATORS"


def test_governance_artifact_fixtures_validate_through_both_registries() -> None:
    """Creates valid fixtures for all five governance artifact kinds and
    validates them through both registries."""
    fixtures = [
        _hitl_execution_request(),
        _hitl_execution_receipt(),
        _hitl_patch_application_spec(),
        _rollback_plan(),
        _rollback_receipt(),
    ]

    for record in fixtures:
        kind = record["kind"]
        idx_errors = INDEX_VALIDATORS[kind](record)
        chain_errors = CHAIN_VALIDATORS[kind](record)
        assert idx_errors == [], f"{kind} index validation errors: {idx_errors}"
        assert chain_errors == [], f"{kind} chain validation errors: {chain_errors}"


def test_governance_artifacts_recognized_by_artifact_index(tmp_path: Path) -> None:
    """Writes all five governance artifact fixtures to disk and asserts the
    artifact index recognizes them all as known and valid."""
    fixtures = {
        "hitl-request.json": _hitl_execution_request(),
        "hitl-receipt.json": _hitl_execution_receipt(),
        "hitl-patch-spec.json": _hitl_patch_application_spec(),
        "rollback-plan.json": _rollback_plan(),
        "rollback-receipt.json": _rollback_receipt(),
    }
    for filename, artifact in fixtures.items():
        _write(tmp_path / filename, artifact)

    index = create_artifact_index_record(tmp_path)

    assert index["counts"] == {"total": 5, "known": 5, "unknown": 0, "valid": 5, "invalid": 0}
    assert validate_artifact_index_record(index) == []

    indexed_kinds = {entry["kind"] for entry in index["artifacts"]}
    for kind in GOVERNANCE_ARTIFACT_KINDS:
        assert kind in indexed_kinds, f"{kind} not found in artifact index entries"


def test_governance_artifacts_are_not_chain_evidence() -> None:
    """Explicitly verifies that governance artifact kinds do not produce
    outbound chain references.  They are standalone design records.

    If a future PR adds cross-reference fields to any of these kinds,
    extract_references() should be updated and this test should be revised."""
    fixtures = [
        _hitl_execution_request(),
        _hitl_execution_receipt(),
        _hitl_patch_application_spec(),
        _rollback_plan(),
        _rollback_receipt(),
    ]

    for record in fixtures:
        refs = extract_references(record)
        assert refs == [], (
            f"{record['kind']} unexpectedly produced chain references: {refs}"
        )


def test_governance_artifacts_chain_verify_natively(tmp_path: Path) -> None:
    """Writes all five governance artifacts and runs chain verification.
    All should be natively valid with zero links and zero errors."""
    fixtures = {
        "hitl-request.json": _hitl_execution_request(),
        "hitl-receipt.json": _hitl_execution_receipt(),
        "hitl-patch-spec.json": _hitl_patch_application_spec(),
        "rollback-plan.json": _rollback_plan(),
        "rollback-receipt.json": _rollback_receipt(),
    }
    paths = []
    for filename, artifact in fixtures.items():
        p = tmp_path / filename
        _write(p, artifact)
        paths.append(p)

    report = verify_artifact_chain(paths)

    assert report["valid"] is True
    assert report["counts"]["files"] == 5
    assert report["counts"]["native_valid"] == 5
    assert report["counts"]["native_invalid"] == 0
    assert report["counts"]["links"] == 0
    assert report["counts"]["broken_links"] == 0


def test_docs_list_governance_artifact_kinds() -> None:
    """Reads ARTIFACT_INDEX.md and asserts all five governance artifact
    kinds appear in the documentation.  Fails if docs are out of sync."""
    docs_path = Path(__file__).resolve().parent.parent / "docs" / "ARTIFACT_INDEX.md"
    content = docs_path.read_text(encoding="utf-8")

    for kind in GOVERNANCE_ARTIFACT_KINDS:
        assert kind in content, (
            f"{kind} not found in docs/ARTIFACT_INDEX.md — "
            f"registry closure requires docs coverage"
        )
