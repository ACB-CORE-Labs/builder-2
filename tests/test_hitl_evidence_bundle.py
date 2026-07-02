"""Tests for builder_ii.hitl_evidence_bundle — design-only evidence bundle validation."""
from __future__ import annotations

import ast
import inspect
import json as json_lib
from pathlib import Path
from typing import Any

import pytest

import builder_ii.hitl_evidence_bundle as bundle_mod
from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.hitl_evidence_bundle import (
    HITL_EVIDENCE_BUNDLE_KIND,
    create_hitl_evidence_bundle,
    dumps_hitl_evidence_bundle,
    validate_hitl_evidence_bundle,
    validate_hitl_evidence_bundle_file,
)

# ---------------------------------------------------------------------------
# Helpers & Fixtures
# ---------------------------------------------------------------------------
_DOC_PATH = Path(__file__).parent.parent / "docs" / "HITL_EVIDENCE_BUNDLE.md"
_MODULE_SRC = inspect.getsource(bundle_mod)


def _valid_bundle_args() -> dict[str, Any]:
    return {
        "bundle_id": "bundle-999",
        "created_at": "2026-06-26T12:00:00Z",
        "created_by": "operator",
        "proposal_ref": "proposal.json",
        "approval_ref": "approval.json",
        "preflight_ref": "preflight.json",
        "request_ref": "request.json",
        "postflight_ref": "postflight.json",
        "verification_ref": "verification.json",
        "rollback_plan_ref": None,
        "rollback_receipt_ref": None,
    }


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_valid_bundle_validates() -> None:
    """A standard complete bundle must pass validation."""
    bundle = create_hitl_evidence_bundle(**_valid_bundle_args())
    assert bundle["kind"] == HITL_EVIDENCE_BUNDLE_KIND
    errors = validate_hitl_evidence_bundle(bundle)
    assert errors == [], f"Unexpected validation errors: {errors}"


def test_required_refs_must_be_present_and_non_empty() -> None:
    """Each required reference field must be present and non-empty."""
    required_fields = [
        "proposal_ref",
        "approval_ref",
        "preflight_ref",
        "request_ref",
        "postflight_ref",
        "verification_ref",
    ]
    for field in required_fields:
        # Test empty string
        args = _valid_bundle_args()
        args[field] = ""
        bundle = create_hitl_evidence_bundle(**args)
        errors = validate_hitl_evidence_bundle(bundle)
        assert any(field in e for e in errors), f"Expected validation error for empty {field}"

        # Test missing field entirely
        bundle_no_field = create_hitl_evidence_bundle(**_valid_bundle_args())
        del bundle_no_field[field]
        errors = validate_hitl_evidence_bundle(bundle_no_field)
        assert any(field in e for e in errors), f"Expected validation error for missing {field}"


def test_target_name_must_be_valid() -> None:
    """target_name must be one of: generic, builder, core."""
    args = _valid_bundle_args()
    args["target_name"] = "invalid-profile"
    # Note: create_hitl_evidence_bundle calls target_profile which raises ValueError for unknown profiles.
    with pytest.raises(ValueError):
        create_hitl_evidence_bundle(**args)

    # Directly modify dictionary to test validation behavior
    bundle = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle["target_name"] = "invalid-profile"
    errors = validate_hitl_evidence_bundle(bundle)
    assert any("target_name must be one of" in e for e in errors)


def test_execution_authority_restrictions() -> None:
    """execution_authority, runtime_execution, and bundle_state must restrict execution capability."""
    # execution_authority check
    bundle = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle["execution_authority"] = "GRANTED"
    errors = validate_hitl_evidence_bundle(bundle)
    assert any("execution_authority must be NOT_GRANTED" in e for e in errors)

    # runtime_execution check
    bundle2 = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle2["runtime_execution"] = "RUN_BY_BUNDLE"
    errors2 = validate_hitl_evidence_bundle(bundle2)
    assert any("runtime_execution must be NOT_PERFORMED_BY_BUNDLE" in e for e in errors2)

    # bundle_state check
    bundle3 = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle3["bundle_state"] = "ACTIVE"
    errors3 = validate_hitl_evidence_bundle(bundle3)
    assert any("bundle_state must be INDEX_ONLY" in e for e in errors3)


def test_execution_state_cannot_imply_authority() -> None:
    """If execution_state is present, it must not imply authority."""
    bundle = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle["execution_state"] = "EXECUTED"
    errors = validate_hitl_evidence_bundle(bundle)
    assert any("execution_state cannot imply execution authority" in e for e in errors)

    # NOT_RUN or NOT_EXECUTED or INDEX_ONLY is allowed
    for allowed in ("NOT_RUN", "NOT_EXECUTED", "INDEX_ONLY"):
        bundle_allowed = create_hitl_evidence_bundle(**_valid_bundle_args())
        bundle_allowed["execution_state"] = allowed
        assert validate_hitl_evidence_bundle(bundle_allowed) == []


def test_verification_state_cannot_imply_approval() -> None:
    """If verification_state is present, it must not imply approval."""
    bundle = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle["verification_state"] = "APPROVED"
    errors = validate_hitl_evidence_bundle(bundle)
    assert any("verification_state cannot imply approval" in e for e in errors)

    # PASS / FAIL / NOT_RUN are allowed (as they reflect postflight verification result)
    for allowed in ("NOT_RUN", "PASS", "FAIL"):
        bundle_allowed = create_hitl_evidence_bundle(**_valid_bundle_args())
        bundle_allowed["verification_state"] = allowed
        assert validate_hitl_evidence_bundle(bundle_allowed) == []


def test_rollback_refs_are_optional_but_typed() -> None:
    """Rollback plan and receipt references can be omitted/None but must be strings if present."""
    # Omitted/None is valid
    args = _valid_bundle_args()
    args["rollback_plan_ref"] = None
    args["rollback_receipt_ref"] = None
    bundle = create_hitl_evidence_bundle(**args)
    assert validate_hitl_evidence_bundle(bundle) == []

    # Strings are valid
    args["rollback_plan_ref"] = "rollback-plan.json"
    args["rollback_receipt_ref"] = "rollback-receipt.json"
    bundle2 = create_hitl_evidence_bundle(**args)
    assert validate_hitl_evidence_bundle(bundle2) == []

    # Invalid type (e.g. integer) must fail
    bundle_bad_type = create_hitl_evidence_bundle(**args)
    bundle_bad_type["rollback_plan_ref"] = 12345
    errors = validate_hitl_evidence_bundle(bundle_bad_type)
    assert any("rollback_plan_ref must be a non-empty string or None" in e for e in errors)


def test_bundle_ref_paths_must_be_safe_relative_paths() -> None:
    """References must not contain absolute paths or directory traversal (..)."""
    unsafe_paths = (
        "/absolute/path/proposal.json",
        "\\absolute\\path\\proposal.json",
        "C:\\absolute\\path\\proposal.json",
        "../traversal/proposal.json",
        "dir/../../traversal/proposal.json",
    )
    for unsafe in unsafe_paths:
        # Test required ref
        args = _valid_bundle_args()
        args["proposal_ref"] = unsafe
        bundle = create_hitl_evidence_bundle(**args)
        errors = validate_hitl_evidence_bundle(bundle)
        assert any("safe relative path" in e for e in errors), f"Expected validation failure for path: {unsafe}"

        # Test optional ref
        args2 = _valid_bundle_args()
        args2["rollback_plan_ref"] = unsafe
        bundle2 = create_hitl_evidence_bundle(**args2)
        errors2 = validate_hitl_evidence_bundle(bundle2)
        assert any("safe relative path" in e for e in errors2), f"Expected validation failure for path: {unsafe}"


def test_governance_block_must_be_disabled() -> None:
    """Enabling any governance capability must fail validation."""
    bundle = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle["governance"]["shell_execution"] = "ENABLED"
    errors = validate_hitl_evidence_bundle(bundle)
    assert any("governance.shell_execution must be DISABLED" in e for e in errors)

    bundle2 = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle2["governance"]["artifact_is_authority"] = True
    errors2 = validate_hitl_evidence_bundle(bundle2)
    assert any("governance.artifact_is_authority must be false" in e for e in errors2)

    bundle3 = create_hitl_evidence_bundle(**_valid_bundle_args())
    bundle3["governance"]["core_workbench_coupling"] = "DIRECT"
    errors3 = validate_hitl_evidence_bundle(bundle3)
    assert any("governance.core_workbench_coupling must be NONE" in e for e in errors3)


def test_docs_exist_and_claim_generic_platform() -> None:
    """Documentation must exist and enforce design-only scope."""
    assert _DOC_PATH.exists()
    doc_text = _DOC_PATH.read_text(encoding="utf-8")
    assert "builder-II is generic-first" in doc_text
    assert "builder-II is not CORE Workbench/UI/UX" in doc_text
    assert "CORE is only a target profile" in doc_text
    assert "NOT_GRANTED" in doc_text
    assert "INDEX_ONLY" in doc_text


def test_no_forbidden_imports_or_execution() -> None:
    """Module must not import subprocess, execute shell commands or write source files."""
    assert "import subprocess" not in _MODULE_SRC
    assert "from subprocess" not in _MODULE_SRC
    assert "subprocess." not in _MODULE_SRC
    assert "os.system" not in _MODULE_SRC
    assert "os.popen" not in _MODULE_SRC
    assert "exec(" not in _MODULE_SRC
    assert "eval(" not in _MODULE_SRC

    tree = ast.parse(_MODULE_SRC)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            name = node.name
            assert "execute" not in name, f"Function {name!r} violates the no-execution policy."
            assert "apply_patch" not in name, f"Function {name!r} violates the no-execution policy."
            assert "write_source" not in name, f"Function {name!r} violates the no-execution policy."


# ---------------------------------------------------------------------------
# Chain Verification Integration Tests
# ---------------------------------------------------------------------------

def test_bundle_chain_verification_resolves_all_links(tmp_path: Path) -> None:
    """A bundle pointing to valid artifacts must resolve and pass chain verification."""
    from builder_ii.approval_records import create_approval_record
    from builder_ii.config import load_settings
    from builder_ii.execution_postflight_records import (
        create_execution_postflight_record,
        create_execution_verification_record,
    )
    from builder_ii.goose_command_proposal import create_goose_command_proposal
    from builder_ii.goose_session import create_goose_session_manifest
    from builder_ii.hitl_execution_records import create_hitl_execution_request
    from builder_ii.preflight_records import create_preflight_record

    # 1. Create references
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="patch_planner",
        task="evidence bundle test",
        runtime_mode="read_only",
        generic_repo=tmp_path,
    )
    proposal = create_goose_command_proposal(manifest, manifest_path="manifest.json", command="test", risk_level="low")
    approval = create_approval_record(proposal, proposal_path="proposal.json", decision="approved", decided_by="operator")
    preflight = create_preflight_record(proposal, approval, proposal_path="proposal.json", approval_path="approval.json")
    request = create_hitl_execution_request(
        target_name="generic",
        command_proposal_ref="proposal.json",
        approval_record_ref="approval.json",
        preflight_record_ref="preflight.json",
        requested_by="operator",
        requested_at="2026-06-26T00:00:00Z",
        explicit_operator_intent="test",
        command_preview="test",
        generic_repo=tmp_path,
    )
    postflight = create_execution_postflight_record(
        target_name="generic",
        request_ref="request.json",
        receipt_ref="receipt.json",
        preflight_ref="preflight.json",
        approval_ref="approval.json",
        expected_outcome="success",
        observed_state_ref="state",
        generic_repo=tmp_path,
    )
    verification = create_execution_verification_record(
        target_name="generic",
        request_ref="request.json",
        receipt_ref="receipt.json",
        postflight_ref="postflight.json",
        generic_repo=tmp_path,
    )

    # 2. Write them to disk
    _write_json(tmp_path / "proposal.json", proposal)
    _write_json(tmp_path / "approval.json", approval)
    _write_json(tmp_path / "preflight.json", preflight)
    _write_json(tmp_path / "request.json", request)
    _write_json(tmp_path / "postflight.json", postflight)
    _write_json(tmp_path / "verification.json", verification)

    # 3. Create and write the evidence bundle
    bundle_data = create_hitl_evidence_bundle(
        target_name="generic",
        bundle_id="bundle-777",
        created_at="2026-06-26T12:00:00Z",
        created_by="operator",
        proposal_ref="proposal.json",
        approval_ref="approval.json",
        preflight_ref="preflight.json",
        request_ref="request.json",
        postflight_ref="postflight.json",
        verification_ref="verification.json",
        generic_repo=tmp_path,
    )
    bundle_path = tmp_path / "bundle.json"
    _write_json(bundle_path, bundle_data)

    # 4. Verify the chain starting from the bundle
    report = verify_artifact_chain([bundle_path])
    assert report["valid"] is True, f"Chain verification failed: {report['errors']}"
    assert report["counts"]["broken_links"] == 0
    assert report["counts"]["resolved_links"] == 6


def test_bundle_chain_verification_fails_on_missing_referenced_file(tmp_path: Path) -> None:
    """If a referenced stage file is missing, chain verification must fail."""
    bundle_data = create_hitl_evidence_bundle(
        target_name="generic",
        bundle_id="bundle-777",
        created_at="2026-06-26T12:00:00Z",
        created_by="operator",
        proposal_ref="proposal-missing.json",
        approval_ref="approval-missing.json",
        preflight_ref="preflight-missing.json",
        request_ref="request-missing.json",
        postflight_ref="postflight-missing.json",
        verification_ref="verification-missing.json",
        generic_repo=tmp_path,
    )
    bundle_path = tmp_path / "bundle.json"
    _write_json(bundle_path, bundle_data)

    report = verify_artifact_chain([bundle_path])
    assert report["valid"] is False
    assert report["counts"]["broken_links"] > 0


def test_bundle_file_io_round_trip(tmp_path: Path) -> None:
    """Bundle file I/O round-trip must preserve fields and validate cleanly."""
    bundle = create_hitl_evidence_bundle(**_valid_bundle_args())
    out_file = tmp_path / "bundle.json"
    dumps_hitl_evidence_bundle(bundle)
    dumps_hitl_evidence_bundle(bundle)
    bundle_mod.write_hitl_evidence_bundle(bundle, out_file)
    assert out_file.exists()

    errors = validate_hitl_evidence_bundle_file(out_file)
    assert errors == [], f"Validation of written file failed: {errors}"

    missing = tmp_path / "missing.json"
    errors_missing = validate_hitl_evidence_bundle_file(missing)
    assert any("file not found" in e for e in errors_missing)
