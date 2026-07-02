from __future__ import annotations

import json as json_lib
from pathlib import Path

import pytest

from builder_ii.approval_records import create_approval_record
from builder_ii.artifact_chain_verification import extract_references, verify_artifact_chain
from builder_ii.execution_postflight_records import (
    create_execution_postflight_record,
    create_execution_verification_record,
)
from builder_ii.goose_command_proposal import create_goose_command_proposal
from builder_ii.hitl_chain_binding import (
    HITL_CHAIN_BINDING_KIND,
    HITL_CHAIN_BINDING_SLOT_FIELDS,
    bind_hitl_chain_artifacts,
    create_artifact_ref,
    validate_hitl_chain_binding,
    validate_hitl_chain_binding_file,
    verify_hitl_chain_binding_files,
    write_hitl_chain_binding,
)
from builder_ii.hitl_evidence_bundle import create_hitl_evidence_bundle
from builder_ii.hitl_execution_records import create_hitl_execution_receipt, create_hitl_execution_request
from builder_ii.preflight_records import create_preflight_record

_DOC_PATH = Path(__file__).resolve().parent.parent / "docs" / "HITL_CHAIN_BINDING.md"


def _write_json(path: Path, value: dict[str, object]) -> None:
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _manifest() -> dict[str, object]:
    return {
        "kind": "builder_ii.goose_session_manifest",
        "schema_version": 1,
        "target": {"name": "generic", "repo": "/tmp/repo", "description": "test"},
        "agent_profile": {"name": "generic", "description": "test", "authority": "user"},
        "task": "chain binding test",
        "requested_runtime_mode": "disabled",
    }


def _artifact_fixtures(tmp_path: Path) -> dict[str, Path]:
    proposal = create_goose_command_proposal(
        _manifest(),
        manifest_path="proposal-manifest.json",
        command="echo test",
        risk_level="low",
    )
    approval = create_approval_record(
        proposal, proposal_path="proposal.json", decision="approved", decided_by="operator"
    )
    preflight = create_preflight_record(
        proposal,
        approval,
        proposal_path="proposal.json",
        approval_path="approval.json",
        verification_refs=["verification.json"],
    )
    request = create_hitl_execution_request(
        command_proposal_ref="proposal.json",
        approval_record_ref="approval.json",
        preflight_record_ref="preflight.json",
        requested_by="operator",
        requested_at="2026-06-27T00:00:00Z",
        explicit_operator_intent="chain binding test",
        command_preview="echo test",
    )
    receipt = create_hitl_execution_receipt(request_ref="request.json")
    postflight = create_execution_postflight_record(
        request_ref="request.json",
        receipt_ref="receipt.json",
        preflight_ref="preflight.json",
        approval_ref="approval.json",
        expected_outcome="echo test",
        observed_state_ref="state.json",
    )
    verification = create_execution_verification_record(
        request_ref="request.json",
        receipt_ref="receipt.json",
        postflight_ref="postflight.json",
    )
    evidence_bundle = create_hitl_evidence_bundle(
        bundle_id="bundle-001",
        created_at="2026-06-27T00:00:00Z",
        created_by="operator",
        proposal_ref="proposal.json",
        approval_ref="approval.json",
        preflight_ref="preflight.json",
        request_ref="request.json",
        postflight_ref="postflight.json",
        verification_ref="verification.json",
    )

    fixtures = {
        "proposal.json": proposal,
        "approval.json": approval,
        "preflight.json": preflight,
        "request.json": request,
        "receipt.json": receipt,
        "postflight.json": postflight,
        "verification.json": verification,
        "evidence-bundle.json": evidence_bundle,
    }
    for name, artifact in fixtures.items():
        _write_json(tmp_path / name, artifact)
    return {name: tmp_path / name for name in fixtures}


def test_happy_path_create_validate_and_verify(tmp_path: Path) -> None:
    paths = _artifact_fixtures(tmp_path)
    binding = bind_hitl_chain_artifacts(
        base_dir=tmp_path,
        proposal_path=paths["proposal.json"],
        approval_path=paths["approval.json"],
        preflight_path=paths["preflight.json"],
        request_path=paths["request.json"],
        receipt_path=paths["receipt.json"],
        postflight_path=paths["postflight.json"],
        verification_path=paths["verification.json"],
        evidence_bundle_path=paths["evidence-bundle.json"],
    )

    assert binding["kind"] == HITL_CHAIN_BINDING_KIND
    assert validate_hitl_chain_binding(binding) == []
    assert binding["proposal_ref"]["path"] == "proposal.json"
    assert binding["proposal_ref"]["path"].startswith("proposal")
    assert not Path(binding["proposal_ref"]["path"]).is_absolute()
    refs = extract_references(binding)
    refs_by_field = {ref["field"]: ref for ref in refs}
    assert set(HITL_CHAIN_BINDING_SLOT_FIELDS.values()).issubset(refs_by_field)
    assert verify_hitl_chain_binding_files(binding, base_dir=tmp_path) == []

    binding_file = tmp_path / "hitl-chain-binding.json"
    write_hitl_chain_binding(binding, binding_file)
    assert validate_hitl_chain_binding_file(binding_file) == []

    report = verify_artifact_chain([binding_file, *paths.values()])
    assert report["valid"] is True, report["errors"]
    assert report["counts"]["broken_links"] == 0


def test_bind_helper_stores_relative_paths(tmp_path: Path) -> None:
    paths = _artifact_fixtures(tmp_path)
    binding = bind_hitl_chain_artifacts(
        base_dir=tmp_path,
        proposal_path=paths["proposal.json"].resolve(),
        approval_path=paths["approval.json"].resolve(),
        preflight_path=paths["preflight.json"].resolve(),
        request_path=paths["request.json"].resolve(),
        receipt_path=paths["receipt.json"].resolve(),
        postflight_path=paths["postflight.json"].resolve(),
        verification_path=paths["verification.json"].resolve(),
    )

    for slot in (
        "proposal_ref",
        "approval_ref",
        "preflight_ref",
        "request_ref",
        "receipt_ref",
        "postflight_ref",
        "verification_ref",
    ):
        path = binding[slot]["path"]
        assert path == Path(path).as_posix()
        assert not Path(path).is_absolute()


def test_validation_failures_cover_slots_and_governance(tmp_path: Path) -> None:
    paths = _artifact_fixtures(tmp_path)
    binding = bind_hitl_chain_artifacts(
        base_dir=tmp_path,
        proposal_path=paths["proposal.json"],
        approval_path=paths["approval.json"],
        preflight_path=paths["preflight.json"],
        request_path=paths["request.json"],
        receipt_path=paths["receipt.json"],
        postflight_path=paths["postflight.json"],
        verification_path=paths["verification.json"],
    )

    missing = dict(binding)
    del missing["approval_ref"]
    assert any("approval_ref is required" in error for error in validate_hitl_chain_binding(missing))

    unknown = dict(binding)
    unknown["unexpected_ref"] = create_artifact_ref(kind="builder_ii.unknown", path="x.json", sha256="f" * 64)
    assert any("unknown slot or field" in error for error in validate_hitl_chain_binding(unknown))

    wrong_kind = json_lib.loads(json_lib.dumps(binding))
    wrong_kind["request_ref"]["kind"] = "builder_ii.goose_session_manifest"
    assert any(
        "request_ref.kind must be builder_ii.hitl_execution_request" in error
        for error in validate_hitl_chain_binding(wrong_kind)
    )

    bad_sha = json_lib.loads(json_lib.dumps(binding))
    bad_sha["receipt_ref"]["sha256"] = "abc"
    assert any(
        "receipt_ref.sha256 must be a 64-character hex digest" in error
        for error in validate_hitl_chain_binding(bad_sha)
    )

    unsafe_path = json_lib.loads(json_lib.dumps(binding))
    unsafe_path["verification_ref"]["path"] = "../escape.json"
    assert any("safe relative path" in error for error in validate_hitl_chain_binding(unsafe_path))

    runtime_enabled = json_lib.loads(json_lib.dumps(binding))
    runtime_enabled["governance"]["runtime_execution"] = "ENABLED"
    assert any(
        "governance.runtime_execution must be DISABLED" in error
        for error in validate_hitl_chain_binding(runtime_enabled)
    )

    absent_top_level = dict(binding)
    assert validate_hitl_chain_binding(absent_top_level) == []

    present_false = dict(binding)
    present_false["artifact_is_authority"] = False
    assert validate_hitl_chain_binding(present_false) == []

    present_top_level = dict(binding)
    present_top_level["artifact_is_authority"] = True
    assert any(
        "artifact_is_authority must be false when present" in error
        for error in validate_hitl_chain_binding(present_top_level)
    )


def test_binding_helper_rejects_absolute_and_traversal_paths(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_paths = _artifact_fixtures(outside)

    with pytest.raises(ValueError):
        bind_hitl_chain_artifacts(
            base_dir=base_dir,
            proposal_path=outside_paths["proposal.json"].resolve(),
            approval_path=outside_paths["approval.json"].resolve(),
            preflight_path=outside_paths["preflight.json"].resolve(),
            request_path=outside_paths["request.json"].resolve(),
            receipt_path=outside_paths["receipt.json"].resolve(),
            postflight_path=outside_paths["postflight.json"].resolve(),
            verification_path=outside_paths["verification.json"].resolve(),
        )

    with pytest.raises(ValueError):
        bind_hitl_chain_artifacts(
            base_dir=base_dir,
            proposal_path="../escape.json",
            approval_path="../escape.json",
            preflight_path="../escape.json",
            request_path="../escape.json",
            receipt_path="../escape.json",
            postflight_path="../escape.json",
            verification_path="../escape.json",
        )


def test_referenced_artifact_digest_and_kind_failures(tmp_path: Path) -> None:
    paths = _artifact_fixtures(tmp_path)
    binding = bind_hitl_chain_artifacts(
        base_dir=tmp_path,
        proposal_path=paths["proposal.json"],
        approval_path=paths["approval.json"],
        preflight_path=paths["preflight.json"],
        request_path=paths["request.json"],
        receipt_path=paths["receipt.json"],
        postflight_path=paths["postflight.json"],
        verification_path=paths["verification.json"],
        evidence_bundle_path=paths["evidence-bundle.json"],
    )
    binding_file = tmp_path / "hitl-chain-binding.json"
    write_hitl_chain_binding(binding, binding_file)

    tampered = json_lib.loads(json_lib.dumps(binding))
    tampered["approval_ref"]["sha256"] = "0" * 64
    assert any("digest mismatch" in error for error in verify_hitl_chain_binding_files(tampered, base_dir=tmp_path))

    unknown_kind = json_lib.loads(json_lib.dumps(binding))
    _write_json(paths["approval.json"], {"kind": "builder_ii.unknown_kind", "schema_version": 1})
    assert any("unknown kind" in error for error in verify_hitl_chain_binding_files(unknown_kind, base_dir=tmp_path))


def test_symlink_escape_fails(tmp_path: Path) -> None:
    base_dir = tmp_path / "base"
    base_dir.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    escape = base_dir / "escape.json"
    try:
        escape.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks are unavailable on this platform")

    binding = {
        "kind": HITL_CHAIN_BINDING_KIND,
        "schema_version": 1,
        "chain_state": "BOUND_ONLY",
        "proposal_ref": create_artifact_ref(
            kind="builder_ii.goose_command_proposal", path="escape.json", sha256="f" * 64
        ),
        "approval_ref": create_artifact_ref(kind="builder_ii.approval_record", path="escape.json", sha256="f" * 64),
        "preflight_ref": create_artifact_ref(kind="builder_ii.preflight_record", path="escape.json", sha256="f" * 64),
        "request_ref": create_artifact_ref(
            kind="builder_ii.hitl_execution_request", path="escape.json", sha256="f" * 64
        ),
        "receipt_ref": create_artifact_ref(
            kind="builder_ii.hitl_execution_receipt", path="escape.json", sha256="f" * 64
        ),
        "postflight_ref": create_artifact_ref(
            kind="builder_ii.execution_postflight_record", path="escape.json", sha256="f" * 64
        ),
        "verification_ref": create_artifact_ref(
            kind="builder_ii.execution_verification_record", path="escape.json", sha256="f" * 64
        ),
        "governance": {
            "capability_state": "hitl_chain_binding",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "goose_runtime_start": "DISABLED",
            "command_execution": "DISABLED",
            "git_mutation": "DISABLED",
            "commit_push": "DISABLED",
            "network_access": "DISABLED",
            "goose_runtime_activation": "DISABLED",
            "deepagents_runtime": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }

    errors = verify_hitl_chain_binding_files(binding, base_dir=base_dir)
    assert any("escapes base_dir" in error for error in errors)


def test_docs_exist_and_describe_passive_binding() -> None:
    assert _DOC_PATH.exists()
    content = _DOC_PATH.read_text(encoding="utf-8")
    assert "passive chain metadata" in content.lower()
    assert "no execution authority" in content.lower()
