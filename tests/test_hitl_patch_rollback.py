import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from builder_ii.hitl_patch_apply import (
    FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
    apply_hitl_patch,
    rollback_hitl_patch,
)
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from tests.hitl_patch_test_helpers import write_executed_verification_receipt


def _setup_repo_with_patch(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, str]:
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
    return repo, test_file, prop_path, approval_path, vr_path, patch_digest


def test_successful_apply_and_rollback(tmp_path: Path):
    repo, test_file, prop_path, approval_path, vr_path, _patch_digest = _setup_repo_with_patch(tmp_path)
    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    assert test_file.read_text() == "Line 1\nLine 2 modified\n"

    rollback_plan_path = out_dir / "rollback_plan.json"
    plan_data = json.loads(rollback_plan_path.read_text())
    assert plan_data["rollback_patch_apply_mode"] == "git_apply_reverse_flag"

    reverse_patch_file = out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME
    original_reverse_patch_content = reverse_patch_file.read_text()
    reverse_patch_file.write_text("corrupted content")

    rollback_out = out_dir / "rollback_out"
    with pytest.raises(ValueError, match="Reverse patch digest does not match rollback plan binding"):
        rollback_hitl_patch(rollback_plan_path, reverse_patch_file, rollback_out)
    assert (rollback_out / "rollback_failure_receipt.json").exists()

    reverse_patch_file.write_text(original_reverse_patch_content)
    rollback_hitl_patch(rollback_plan_path, reverse_patch_file, rollback_out)
    assert test_file.read_text() == "Line 1\nLine 2\n"
    assert (rollback_out / "rollback_receipt.json").exists()
    rollback_receipt = json.loads((rollback_out / "rollback_receipt.json").read_text())
    assert rollback_receipt["rollback_equivalence_verified"] is True


def test_rollback_refuses_when_already_at_pre_apply_state(tmp_path: Path):
    repo, test_file, prop_path, approval_path, vr_path, _ = _setup_repo_with_patch(tmp_path)
    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    rollback_plan_path = out_dir / "rollback_plan.json"
    reverse_patch_file = out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME
    rollback_out = out_dir / "rollback_out"
    rollback_hitl_patch(rollback_plan_path, reverse_patch_file, rollback_out)
    assert test_file.read_text() == "Line 1\nLine 2\n"

    with pytest.raises(ValueError, match="already matches pre-apply state"):
        rollback_hitl_patch(rollback_plan_path, reverse_patch_file, rollback_out / "repeat")
    assert (rollback_out / "repeat" / "rollback_failure_receipt.json").exists()


def test_rollback_equivalence_failure_emits_failure_receipt(tmp_path: Path):
    repo, _test_file, prop_path, approval_path, vr_path, _ = _setup_repo_with_patch(tmp_path)
    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    (repo / "extra.txt").write_text("drift after apply")
    rollback_plan_path = out_dir / "rollback_plan.json"
    reverse_patch_file = out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME
    fail_out = out_dir / "rollback_fail"
    with pytest.raises(RuntimeError, match="did not restore pre-apply working tree state"):
        rollback_hitl_patch(rollback_plan_path, reverse_patch_file, fail_out)
    data = json.loads((fail_out / "rollback_failure_receipt.json").read_text())
    assert data["status"] == "failed"
    assert data["rollback_attempted"] is True
