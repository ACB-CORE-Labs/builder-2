import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from builder_ii.hitl_patch_apply import (
    FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
    PATCH_APPLY_RECEIPT_KIND,
    apply_hitl_patch,
    create_patch_apply_receipt,
    validate_patch_apply_receipt,
)
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from tests.hitl_patch_test_helpers import write_core_demo_verification_receipt, write_executed_verification_receipt


def test_validate_patch_apply_receipt():
    receipt = create_patch_apply_receipt(
        proposal_ref="prop.json",
        rollback_plan_ref="roll.json",
        postflight_ref="post.json",
    )
    assert receipt["kind"] == PATCH_APPLY_RECEIPT_KIND
    errors = validate_patch_apply_receipt(receipt)
    assert not errors


def test_apply_hitl_patch_succeeds_with_valid_verification_receipt(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    test_file = repo / "file.txt"
    test_file.write_text("Line 1\nLine 2\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True)

    diff = (
        "diff --git a/file.txt b/file.txt\n"
        "index 273b063..843d1a8 100644\n"
        "--- a/file.txt\n"
        "+++ b/file.txt\n"
        "@@ -1,2 +1,2 @@\n"
        " Line 1\n"
        "-Line 2\n"
        "+Line 2 modified\n"
    )
    patch_digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    prop_path = tmp_path / "prop.json"
    prop = create_hitl_patch_proposal(generic_repo=repo, patch_digest=patch_digest, unified_diff=diff)
    write_hitl_patch_proposal(prop, prop_path)

    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps({"kind": "builder_ii.approval_record", "patch_digest": patch_digest}))
    vr_path = tmp_path / "vr.json"
    write_executed_verification_receipt(vr_path, repo)

    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)

    assert test_file.read_text() == "Line 1\nLine 2 modified\n"
    assert (out_dir / "patch_apply_receipt.json").exists()
    assert (out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME).exists()
    receipt = json.loads((out_dir / "patch_apply_receipt.json").read_text())
    assert receipt["status"] == "succeeded"


def test_apply_hitl_patch_rejects_dirty_repo(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)

    (repo / "file.txt").write_text("content")

    prop_path = tmp_path / "prop.json"
    prop = create_hitl_patch_proposal(generic_repo=repo, patch_digest="abc", unified_diff="patch")
    write_hitl_patch_proposal(prop, prop_path)

    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps({"patch_digest": "abc"}))

    vr_path = tmp_path / "vr.json"
    write_core_demo_verification_receipt(vr_path, repo)

    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="Target repository working tree is not clean"):
        apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    failure = out_dir / "patch_apply_failure_receipt.json"
    assert failure.exists()
    assert json.loads(failure.read_text())["status"] == "failed"


def test_apply_hitl_patch_rejects_digest_mismatch(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    (repo / "file.txt").write_text("a")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    prop_path = tmp_path / "prop.json"
    prop = create_hitl_patch_proposal(generic_repo=repo, patch_digest="abc", unified_diff="patch")
    write_hitl_patch_proposal(prop, prop_path)

    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps({"patch_digest": "def"}))

    vr_path = tmp_path / "vr.json"
    write_core_demo_verification_receipt(vr_path, repo)

    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="Approval digest does not match proposal digest"):
        apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    failure = out_dir / "patch_apply_failure_receipt.json"
    assert failure.exists()
    data = json.loads(failure.read_text())
    assert data["status"] == "failed"


def test_apply_hitl_patch_rejects_invalid_verification_receipt(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    (repo / "file.txt").write_text("a")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    prop_path = tmp_path / "prop.json"
    prop = create_hitl_patch_proposal(generic_repo=repo, patch_digest="abc", unified_diff="patch")
    write_hitl_patch_proposal(prop, prop_path)

    approval_path = tmp_path / "approval.json"
    approval_path.write_text(json.dumps({"patch_digest": "abc"}))

    vr_path = tmp_path / "vr.json"
    vr_path.write_text(json.dumps({"kind": "wrong_kind", "receipt_status": "NOT_EXECUTED"}))

    out_dir = tmp_path / "out"
    with pytest.raises(ValueError, match="Invalid verification receipt"):
        apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    failure = out_dir / "patch_apply_failure_receipt.json"
    assert failure.exists()
    data = json.loads(failure.read_text())
    assert data["status"] == "failed"
    assert "Invalid verification receipt" in data["error_summary"]