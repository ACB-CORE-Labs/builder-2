import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.governance.authority import CommandAuthorityError
from builder_ii.governance.hitl.hitl_patch_apply import (
    FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
    PATCH_APPLY_RECEIPT_KIND,
    apply_hitl_patch,
    create_patch_apply_receipt,
    rollback_hitl_patch,
    validate_patch_apply_receipt,
)
from builder_ii.governance.hitl.hitl_patch_approval import create_hitl_patch_approval, write_hitl_patch_approval
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from tests.hitl_patch_test_helpers import write_executed_verification_receipt


def _init_clean_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=path, check=True)
    (path / "file.txt").write_text("a\n")
    subprocess.run(["git", "add", "file.txt"], cwd=path, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True)
    return path


def _write_proposal(tmp_path: Path, repo: Path, *, unified_diff: str, patch_digest: str) -> Path:
    prop_path = tmp_path / "prop.json"
    proposal = create_hitl_patch_proposal(generic_repo=repo, patch_digest=patch_digest, unified_diff=unified_diff)
    write_hitl_patch_proposal(proposal, prop_path)
    return prop_path


def _write_passing_vr(tmp_path: Path) -> Path:
    vr_path = tmp_path / "vr.json"
    vr_path.write_text(json.dumps({"kind": "builder_ii.verification_execution_receipt", "receipt_status": "EXECUTED"}))
    return vr_path


def test_validate_patch_apply_receipt():
    receipt = create_patch_apply_receipt(
        proposal_ref="prop.json",
        rollback_plan_ref="roll.json",
        postflight_ref="post.json",
    )
    assert receipt["kind"] == PATCH_APPLY_RECEIPT_KIND
    errors = validate_patch_apply_receipt(receipt)
    assert not errors


def test_apply_hitl_patch_succeeds_unmocked_with_schema_valid_receipt(tmp_path: Path):
    """The whole apply boundary with nothing patched out: a real proposal, a real governed
    approval, and a finalized, digest-bound verification receipt. The mocked variants below
    each isolate one refusal; this one proves the lane works when everything is genuine."""
    repo = _init_clean_repo(tmp_path / "repo")
    (repo / "file.txt").write_text("b\n")
    unified_diff = subprocess.run(["git", "diff"], cwd=repo, check=True, capture_output=True, text=True).stdout
    subprocess.run(["git", "checkout", "--", "file.txt"], cwd=repo, check=True)

    patch_digest = hashlib.sha256(unified_diff.encode("utf-8")).hexdigest()
    prop_path = _write_proposal(tmp_path, repo, unified_diff=unified_diff, patch_digest=patch_digest)
    proposal_data = json.loads(prop_path.read_text())

    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(
        create_hitl_patch_approval(proposal_data, confirmed_digest_prefix=patch_digest[:4]),
        approval_path,
    )
    vr_path = tmp_path / "vr.json"
    write_executed_verification_receipt(vr_path, repo)

    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)

    assert (repo / "file.txt").read_text() == "b\n"
    assert (out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME).exists()
    receipt = json.loads((out_dir / "patch_apply_receipt.json").read_text())
    assert receipt["status"] == "succeeded"


@patch("builder_ii.hitl_patch_apply.validate_verification_execution_receipt_file", return_value=[])
def test_apply_hitl_patch_rejects_dirty_repo(mock_validate, tmp_path: Path):
    repo = _init_clean_repo(tmp_path / "repo")
    # Dirty the tree after the clean commit.
    (repo / "file.txt").write_text("content")

    prop_path = _write_proposal(tmp_path, repo, unified_diff="patch", patch_digest="abc")
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps({"patch_digest": "abc"}))
    vr_path = _write_passing_vr(tmp_path)

    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="Target repository working tree is not clean"):
        apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    failure = out_dir / "patch_apply_failure_receipt.json"
    assert failure.exists()
    assert json.loads(failure.read_text())["status"] == "failed"


@patch("builder_ii.hitl_patch_apply.validate_verification_execution_receipt_file", return_value=[])
def test_apply_rejects_forged_bare_digest_approval(mock_validate, tmp_path: Path):
    """The weak-approval gap: a bare JSON echoing the digest must NOT authorize a mutation."""
    repo = _init_clean_repo(tmp_path / "repo")
    prop_path = _write_proposal(tmp_path, repo, unified_diff="patch", patch_digest="abc")

    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps({"patch_digest": "abc"}))  # forged: not a governed approval
    vr_path = _write_passing_vr(tmp_path)

    with pytest.raises(ValueError, match="Invalid patch approval"):
        apply_hitl_patch(prop_path, approval_path, vr_path, tmp_path / "out")


@patch("builder_ii.hitl_patch_apply.validate_verification_execution_receipt_file", return_value=[])
def test_apply_rejects_approval_bound_to_other_proposal(mock_validate, tmp_path: Path):
    repo = _init_clean_repo(tmp_path / "repo")
    prop_path = _write_proposal(tmp_path, repo, unified_diff="patch", patch_digest="abc")
    proposal_data = json.loads(prop_path.read_text())

    approval = create_hitl_patch_approval(proposal_data, confirmed_digest_prefix="abc")
    approval["proposal_digest"] = "0" * 64  # simulate binding to a different proposal
    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(approval, approval_path)
    vr_path = _write_passing_vr(tmp_path)

    with pytest.raises(ValueError, match="not bound to this proposal"):
        apply_hitl_patch(prop_path, approval_path, vr_path, tmp_path / "out")


@patch("builder_ii.hitl_patch_apply.validate_verification_execution_receipt_file", return_value=[])
def test_apply_rejects_expired_approval(mock_validate, tmp_path: Path):
    repo = _init_clean_repo(tmp_path / "repo")
    prop_path = _write_proposal(tmp_path, repo, unified_diff="patch", patch_digest="abc")
    proposal_data = json.loads(prop_path.read_text())

    approval = create_hitl_patch_approval(
        proposal_data, confirmed_digest_prefix="abc", approved_at=1000, ttl_seconds=10
    )
    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(approval, approval_path)
    vr_path = _write_passing_vr(tmp_path)

    with pytest.raises(ValueError, match="expired"):
        apply_hitl_patch(prop_path, approval_path, vr_path, tmp_path / "out")


@patch("builder_ii.hitl_patch_apply.validate_verification_execution_receipt_file", return_value=[])
def test_apply_hitl_patch_happy_path_applies_diff(mock_validate, tmp_path: Path):
    """A schema-valid, bound, live approval authorizes a real apply."""
    repo = _init_clean_repo(tmp_path / "repo")

    # Produce a real unified diff, then restore the clean tree.
    (repo / "file.txt").write_text("b\n")
    unified_diff = subprocess.run(["git", "diff"], cwd=repo, check=True, capture_output=True, text=True).stdout
    subprocess.run(["git", "checkout", "--", "file.txt"], cwd=repo, check=True)
    assert (repo / "file.txt").read_text() == "a\n"

    patch_digest = hashlib.sha256(unified_diff.encode("utf-8")).hexdigest()
    prop_path = _write_proposal(tmp_path, repo, unified_diff=unified_diff, patch_digest=patch_digest)
    proposal_data = json.loads(prop_path.read_text())

    approval = create_hitl_patch_approval(proposal_data, confirmed_digest_prefix=patch_digest[:4])
    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(approval, approval_path)
    vr_path = _write_passing_vr(tmp_path)

    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)

    assert (repo / "file.txt").read_text() == "b\n"
    assert (out_dir / "patch_apply_receipt.json").exists()


@patch(
    "builder_ii.command_authority.enforce_command_authority",
    side_effect=CommandAuthorityError("denied"),
)
def test_apply_consults_command_authority_gate_before_io(mock_gate, tmp_path: Path):
    """The write lane fails closed at the gate — before reading or mutating anything —
    even for a direct (non-CLI) caller."""
    with pytest.raises(CommandAuthorityError):
        apply_hitl_patch(tmp_path / "p.json", tmp_path / "a.json", tmp_path / "vr.json", tmp_path / "out")
    mock_gate.assert_called_once()
    assert not (tmp_path / "out").exists()


@patch(
    "builder_ii.command_authority.enforce_command_authority",
    side_effect=CommandAuthorityError("denied"),
)
def test_rollback_consults_command_authority_gate_before_io(mock_gate, tmp_path: Path):
    with pytest.raises(CommandAuthorityError):
        rollback_hitl_patch(
            tmp_path / "plan.json",
            tmp_path / "rev.patch",
            tmp_path / "out",
            approval_path=tmp_path / "approval.json",
        )
    mock_gate.assert_called_once()
    assert not (tmp_path / "out").exists()


def test_apply_binding_failure_leaves_a_failure_receipt(tmp_path: Path):
    """The refusal is evidence, not only an exception: a mis-bound approval writes a
    patch_apply_failure_receipt before raising (hardening-line intent, applied at this
    lineage's stronger binding guard)."""
    repo = _init_clean_repo(tmp_path / "repo")
    prop_path = _write_proposal(tmp_path, repo, unified_diff="patch", patch_digest="abc")
    proposal_data = json.loads(prop_path.read_text())

    approval = create_hitl_patch_approval(proposal_data, confirmed_digest_prefix="abc")
    approval["proposal_digest"] = "0" * 64  # bound to a different proposal
    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(approval, approval_path)
    vr_path = tmp_path / "vr.json"
    write_executed_verification_receipt(vr_path, repo)

    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="not bound to this proposal"):
        apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    failure = json.loads((out_dir / "patch_apply_failure_receipt.json").read_text())
    assert failure["status"] == "failed"
    assert "not bound" in failure["error_summary"]


def test_apply_hitl_patch_rejects_invalid_verification_receipt(tmp_path: Path):
    repo = _init_clean_repo(tmp_path / "repo")
    prop_path = _write_proposal(tmp_path, repo, unified_diff="patch", patch_digest="abc")
    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps({"patch_digest": "abc"}))

    vr_path = tmp_path / "vr.json"
    vr_path.write_text(json.dumps({"kind": "wrong_kind", "receipt_status": "NOT_EXECUTED"}))

    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="Invalid verification receipt"):
        apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    failure = json.loads((out_dir / "patch_apply_failure_receipt.json").read_text())
    assert failure["status"] == "failed"
    assert "Invalid verification receipt" in failure["error_summary"]
