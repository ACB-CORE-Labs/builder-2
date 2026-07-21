import json
from pathlib import Path

from builder_ii.governance.hitl.hitl_patch_approval import (
    APPROVAL_CONFIRMATION_PREFIX_LENGTH,
    HITL_PATCH_APPROVAL_KIND,
    HITL_PATCH_APPROVAL_SCHEMA_VERSION,
    approval_binding_errors,
    approval_is_expired,
    canonical_json_digest,
    create_hitl_patch_approval,
    validate_hitl_patch_approval,
    validate_hitl_patch_approval_file,
    write_hitl_patch_approval,
)
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal


def _proposal(tmp_path: Path, *, patch_digest: str = "a7f2deadbeef") -> dict:
    return create_hitl_patch_proposal(
        generic_repo=tmp_path, patch_digest=patch_digest, unified_diff="diff-body"
    )


def test_create_hitl_patch_approval_is_valid_and_non_authoritative(tmp_path: Path):
    proposal = _proposal(tmp_path)
    approval = create_hitl_patch_approval(
        proposal, confirmed_digest_prefix="a7f2", approved_at=1000, ttl_seconds=100
    )
    assert approval["kind"] == HITL_PATCH_APPROVAL_KIND
    assert approval["schema_version"] == HITL_PATCH_APPROVAL_SCHEMA_VERSION
    assert approval["artifact_is_authority"] is False
    assert approval["patch_digest"] == proposal["patch_digest"]
    assert approval["proposal_digest"] == canonical_json_digest(proposal)
    assert approval["expires_at"] == 1100
    assert approval["confirmation"]["prefix_length"] == APPROVAL_CONFIRMATION_PREFIX_LENGTH
    assert validate_hitl_patch_approval(approval) == []


def test_validate_rejects_bare_digest_echo():
    # The exact forged shape the weak-approval gap accepted.
    assert validate_hitl_patch_approval({"patch_digest": "abc"})


def test_validate_rejects_authoritative_flag(tmp_path: Path):
    approval = create_hitl_patch_approval(_proposal(tmp_path), confirmed_digest_prefix="a7f2")
    approval["artifact_is_authority"] = True
    errors = validate_hitl_patch_approval(approval)
    assert any("artifact_is_authority" in e for e in errors)


def test_validate_rejects_prefix_not_in_digest(tmp_path: Path):
    approval = create_hitl_patch_approval(_proposal(tmp_path), confirmed_digest_prefix="zzzz")
    errors = validate_hitl_patch_approval(approval)
    assert any("digest_prefix must be a prefix" in e for e in errors)


def test_validate_rejects_expiry_before_approval(tmp_path: Path):
    approval = create_hitl_patch_approval(
        _proposal(tmp_path), confirmed_digest_prefix="a7f2", approved_at=1000, ttl_seconds=-5
    )
    errors = validate_hitl_patch_approval(approval)
    assert any("expires_at must be after approved_at" in e for e in errors)


def test_validate_rejects_bool_timestamp(tmp_path: Path):
    approval = create_hitl_patch_approval(_proposal(tmp_path), confirmed_digest_prefix="a7f2")
    approval["approved_at"] = True  # bool must not pass as int
    errors = validate_hitl_patch_approval(approval)
    assert any("approved_at must be an integer" in e for e in errors)


def test_binding_errors_flags_mismatch(tmp_path: Path):
    proposal = _proposal(tmp_path)
    approval = create_hitl_patch_approval(proposal, confirmed_digest_prefix="a7f2")
    # Correct binding: no errors.
    assert (
        approval_binding_errors(
            approval, proposal_digest=canonical_json_digest(proposal), patch_digest=proposal["patch_digest"]
        )
        == []
    )
    # Wrong content digest.
    assert approval_binding_errors(
        approval, proposal_digest="0" * 64, patch_digest=proposal["patch_digest"]
    )
    # Wrong patch digest.
    assert approval_binding_errors(
        approval, proposal_digest=canonical_json_digest(proposal), patch_digest="different"
    )


def test_approval_is_expired():
    assert approval_is_expired({"expires_at": 1000}, now=2000) is True
    assert approval_is_expired({"expires_at": 3000}, now=2000) is False
    # Fail closed when expiry is missing or malformed.
    assert approval_is_expired({}, now=2000) is True
    assert approval_is_expired({"expires_at": "soon"}, now=2000) is True
    assert approval_is_expired({"expires_at": True}, now=2000) is True


def test_roundtrip_file(tmp_path: Path):
    approval = create_hitl_patch_approval(_proposal(tmp_path), confirmed_digest_prefix="a7f2")
    out = tmp_path / "approval.json"
    write_hitl_patch_approval(approval, out)
    assert validate_hitl_patch_approval_file(out) == []
    assert json.loads(out.read_text())["kind"] == HITL_PATCH_APPROVAL_KIND
    assert validate_hitl_patch_approval_file(tmp_path / "missing.json")
