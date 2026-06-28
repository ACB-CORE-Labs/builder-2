from __future__ import annotations

import inspect
import json as json_lib
from pathlib import Path

import builder_ii.hitl_verification_candidate as candidate_mod
from builder_ii.approval_records import create_approval_record
from builder_ii.artifact_chain_verification import VALIDATORS as CHAIN_VALIDATORS
from builder_ii.artifact_chain_verification import extract_references, verify_artifact_chain
from builder_ii.artifact_index_records import _VALIDATORS as INDEX_VALIDATORS
from builder_ii.artifact_index_records import create_artifact_index_record, validate_artifact_index_record
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.hitl_execution_records import create_hitl_execution_request
from builder_ii.hitl_verification_candidate import (
    HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND,
    create_hitl_verification_execution_candidate,
    dumps_hitl_verification_execution_candidate,
    validate_hitl_verification_execution_candidate,
    validate_hitl_verification_execution_candidate_file,
    write_hitl_verification_execution_candidate,
)
from builder_ii.preflight_records import create_preflight_record


def _manifest() -> dict[str, object]:
    return {
        "kind": "builder_ii.goose_session_manifest",
        "schema_version": 1,
        "target": {"name": "generic", "repo": "/tmp/repo", "description": "test"},
        "agent_profile": {"name": "generic", "description": "test", "authority": "user"},
        "task": "verification candidate test",
        "requested_runtime_mode": "disabled",
    }


def _candidate() -> dict[str, object]:
    return create_hitl_verification_execution_candidate(
        verification_command="uv run pytest tests/test_hitl_execution_records.py -q",
        allowed_command_kind="repo_native_pytest",
        proposal_ref="proposal.json",
        approval_ref="approval.json",
        preflight_ref="preflight.json",
        request_ref="request.json",
    )


def _write(path: Path, value: dict[str, object]) -> None:
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_happy_path_candidate_validates() -> None:
    candidate = _candidate()
    assert candidate["kind"] == HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND
    assert validate_hitl_verification_execution_candidate(candidate) == []


def test_candidate_executes_now_false() -> None:
    candidate = _candidate()
    assert candidate["candidate_state"] == "CANDIDATE_ONLY"
    assert candidate["operator_review_required"] is True
    assert candidate["executes_now"] is False
    assert candidate["runtime_execution"] == "DISABLED"
    assert candidate["command_execution"] == "DISABLED"


def test_governance_disables_runtime_boundaries() -> None:
    candidate = _candidate()
    gov = candidate["governance"]
    for key in (
        "runtime_execution",
        "model_execution",
        "shell_execution",
        "command_execution",
        "source_writes",
        "target_repo_writes",
        "memory_mutation",
        "git_mutation",
        "commit_push",
        "network_access",
        "goose_runtime_start",
        "deepagents_runtime",
    ):
        assert gov[key] == "DISABLED"
    assert gov["artifact_is_authority"] is False
    assert gov["core_workbench_coupling"] == "NONE"


def test_rejects_enabled_command_execution() -> None:
    candidate = _candidate()
    candidate["governance"]["command_execution"] = "ENABLED"
    errors = validate_hitl_verification_execution_candidate(candidate)
    assert "governance.command_execution must be DISABLED" in errors


def test_rejects_enabled_shell_execution() -> None:
    candidate = _candidate()
    candidate["governance"]["shell_execution"] = "ENABLED"
    errors = validate_hitl_verification_execution_candidate(candidate)
    assert "governance.shell_execution must be DISABLED" in errors


def test_rejects_source_and_target_repo_writes() -> None:
    candidate = _candidate()
    candidate["source_writes"] = "ENABLED"
    candidate["governance"]["target_repo_writes"] = "ENABLED"
    errors = validate_hitl_verification_execution_candidate(candidate)
    assert "source_writes must be DISABLED" in errors
    assert "governance.target_repo_writes must be DISABLED" in errors


def test_unknown_or_unsafe_command_fails_closed() -> None:
    unknown = _candidate()
    unknown["verification_command"] = "rm -rf ."
    errors = validate_hitl_verification_execution_candidate(unknown)
    assert "verification_command must be an allowlisted repo-native pytest command" in errors

    unsafe = _candidate()
    unsafe["verification_command"] = "uv run pytest -q && rm -rf ."
    errors = validate_hitl_verification_execution_candidate(unsafe)
    assert "verification_command must not contain shell control syntax" in errors


def test_missing_approval_preflight_request_requirements_fail() -> None:
    candidate = create_hitl_verification_execution_candidate(
        verification_command="uv run pytest -q",
        proposal_ref="proposal.json",
    )
    errors = validate_hitl_verification_execution_candidate(candidate)
    assert "approval_ref is required" in errors
    assert "preflight_ref is required" in errors
    assert "request_ref is required" in errors


def test_artifact_is_authority_true_fails_closed() -> None:
    candidate = _candidate()
    candidate["artifact_is_authority"] = True
    candidate["governance"]["artifact_is_authority"] = True
    errors = validate_hitl_verification_execution_candidate(candidate)
    assert "artifact_is_authority must be false" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_chain_and_index_validators_know_candidate_kind(tmp_path: Path) -> None:
    candidate = _candidate()
    assert HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND in INDEX_VALIDATORS
    assert HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND in CHAIN_VALIDATORS
    assert INDEX_VALIDATORS[HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND](candidate) == []
    assert CHAIN_VALIDATORS[HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND](candidate) == []

    _write(tmp_path / "candidate.json", candidate)
    index = create_artifact_index_record(tmp_path)
    assert index["counts"] == {"total": 1, "known": 1, "unknown": 0, "valid": 1, "invalid": 0}
    assert validate_artifact_index_record(index) == []


def test_chain_reference_extraction_and_resolution(tmp_path: Path) -> None:
    proposal = create_goose_command_proposal(
        _manifest(),
        manifest_path="manifest.json",
        command="uv run pytest tests/test_hitl_verification_candidate.py -q",
        risk_level="low",
    )
    approval = create_approval_record(proposal, proposal_path="proposal.json", decision="approved", decided_by="operator")
    preflight = create_preflight_record(
        proposal,
        approval,
        proposal_path="proposal.json",
        approval_path="approval.json",
        verification_refs=["tests/test_hitl_verification_candidate.py"],
    )
    request = create_hitl_execution_request(
        command_proposal_ref="proposal.json",
        approval_record_ref="approval.json",
        preflight_record_ref="preflight.json",
        requested_by="operator",
        requested_at="2026-06-27T00:00:00Z",
        explicit_operator_intent="verify candidate artifact",
        command_preview="uv run pytest tests/test_hitl_verification_candidate.py -q",
    )
    candidate = _candidate()

    paths = {
        "proposal.json": proposal,
        "approval.json": approval,
        "preflight.json": preflight,
        "request.json": request,
        "candidate.json": candidate,
    }
    written_paths: list[Path] = []
    for filename, artifact in paths.items():
        path = tmp_path / filename
        _write(path, artifact)
        written_paths.append(path)

    refs = extract_references(candidate)
    refs_by_field = {ref["field"]: ref for ref in refs}
    assert refs_by_field["proposal_ref"]["expected_kind"] == "builder_ii.goose_command_proposal"
    assert refs_by_field["approval_ref"]["expected_kind"] == "builder_ii.approval_record"
    assert refs_by_field["preflight_ref"]["expected_kind"] == "builder_ii.preflight_record"
    assert refs_by_field["request_ref"]["expected_kind"] == "builder_ii.hitl_execution_request"

    report = verify_artifact_chain(written_paths)
    assert report["valid"] is True, report["errors"]
    assert report["counts"]["broken_links"] == 0


def test_docs_state_no_execution_authority() -> None:
    doc_path = Path(__file__).resolve().parent.parent / "docs" / "HITL_VERIFICATION_CANDIDATE.md"
    assert doc_path.exists()
    text = doc_path.read_text(encoding="utf-8")
    lower = text.lower()
    assert "candidate only" in lower
    assert "no execution authority" in lower
    assert "does not execute commands" in lower
    assert "does not grant authority" in lower
    assert "builder_ii.hitl_verification_execution_candidate" in text


def test_module_does_not_import_or_call_subprocess() -> None:
    source = inspect.getsource(candidate_mod)
    assert "import subprocess" not in source
    assert "from subprocess" not in source
    assert "subprocess." not in source
    assert "os.system" not in source
    assert "exec(" not in source
    assert "eval(" not in source


def test_file_io_and_json_dump(tmp_path: Path) -> None:
    candidate = _candidate()
    output = tmp_path / "candidate.json"
    write_hitl_verification_execution_candidate(candidate, output)
    assert validate_hitl_verification_execution_candidate_file(output) == []
    assert json_lib.loads(dumps_hitl_verification_execution_candidate(candidate))["kind"] == HITL_VERIFICATION_EXECUTION_CANDIDATE_KIND
