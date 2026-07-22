"""The governed rollback lane, end to end, unmocked.

Merged from two lineages that hardened this lane independently. The Forgejo line added the
authority gate, the distinct rollback approval, the drift-verifiability precondition, and the
drift preflight with a recovery block; the hardening line removed the verification-receipt mocks
(a schema-valid receipt is built by ``tests/hitl_patch_test_helpers``), renamed the stored patch
honestly (it is the FORWARD patch, kept for ``git apply -R``), emitted failure receipts on refused
rollbacks, and refused to mint a success receipt without post-rollback equivalence evidence.
These tests hold the union.
"""

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from builder_ii.core.artifact_chain_verification import verify_artifact_chain
from builder_ii.governance.hitl.hitl_patch_apply import (
    FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
    apply_hitl_patch,
    rollback_hitl_patch,
)
from builder_ii.governance.hitl.hitl_patch_approval import create_hitl_patch_approval, write_hitl_patch_approval
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.governance.hitl.hitl_rollback_approval import (
    canonical_json_digest,
    create_hitl_rollback_approval,
    write_hitl_rollback_approval,
)
from tests.hitl_patch_test_helpers import write_executed_verification_receipt


def _setup_repo_with_patch(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path, str]:
    """A real repo, a real proposal, a real approval, and a real verification receipt.

    No mocks: the receipt is a finalized, digest-bound ``verification_execution_receipt``, so the
    apply boundary is exercised exactly as an operator exercises it.
    """
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
    write_hitl_patch_approval(
        create_hitl_patch_approval(prop, confirmed_digest_prefix=patch_digest[:4]),
        approval_path,
    )

    vr_path = tmp_path / "vr.json"
    write_executed_verification_receipt(vr_path, repo)
    return repo, test_file, prop_path, approval_path, vr_path, patch_digest


def _mint_rollback_approval(tmp_path: Path, rollback_plan_path: Path) -> Path:
    """The distinct, plan-bound approval the hardened rollback lane requires."""
    plan_data = json.loads(rollback_plan_path.read_text())
    rollback_approval_path = tmp_path / "rollback_approval.json"
    write_hitl_rollback_approval(
        create_hitl_rollback_approval(
            plan_data, confirmed_digest_prefix=canonical_json_digest(plan_data)[:4]
        ),
        rollback_approval_path,
    )
    return rollback_approval_path


def test_successful_apply_and_rollback(tmp_path: Path):
    repo, test_file, prop_path, approval_path, vr_path, _patch_digest = _setup_repo_with_patch(tmp_path)

    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    assert test_file.read_text() == "Line 1\nLine 2 modified\n"

    rollback_plan_path = out_dir / "rollback_plan.json"
    assert rollback_plan_path.exists()
    plan_data = json.loads(rollback_plan_path.read_text())
    assert "rollback_patch_ref" in plan_data
    assert "reverse_patch_ref" not in plan_data
    assert plan_data["rollback_patch_apply_mode"] == "git_apply_reverse_flag"
    assert "reverse_patch_apply_mode" not in plan_data
    # apply records a post-apply working-tree fingerprint so rollback can detect drift
    assert isinstance(plan_data.get("post_apply_worktree_digest"), str)

    rollback_approval_path = _mint_rollback_approval(tmp_path, rollback_plan_path)

    bundle_path = out_dir / "rollback_bundle.json"
    assert bundle_path.exists()
    bundle_data = json.loads(bundle_path.read_text())
    assert "rollback_patch_ref" in bundle_data
    assert "reverse_patch_ref" not in bundle_data

    reverse_patch_file = out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME
    assert reverse_patch_file.exists()

    # Digest-mismatch rejection: a corrupted patch is refused AND the refusal leaves evidence.
    rollback_out = out_dir / "rollback_out"
    original_reverse_patch_content = reverse_patch_file.read_text()
    reverse_patch_file.write_text("corrupted content")
    with pytest.raises(ValueError, match="Reverse patch digest does not match rollback plan binding"):
        rollback_hitl_patch(
            rollback_plan_path,
            reverse_patch_file,
            rollback_out,
            approval_path=rollback_approval_path,
        )
    failure_receipt = json.loads((rollback_out / "rollback_failure_receipt.json").read_text())
    assert failure_receipt["rollback_outcome"] == "REVERSE_PATCH_DIGEST_MISMATCH"
    assert "recovery" in failure_receipt

    reverse_patch_file.write_text(original_reverse_patch_content)

    rollback_hitl_patch(
        rollback_plan_path,
        reverse_patch_file,
        rollback_out,
        approval_path=rollback_approval_path,
    )
    assert test_file.read_text() == "Line 1\nLine 2\n"

    rollback_receipt = json.loads((rollback_out / "rollback_receipt.json").read_text())
    # The success receipt binds the rollback approval that authorized it (evidence parity with
    # the apply receipt's approval_digest).
    assert rollback_receipt["rollback_approval_digest"] == canonical_json_digest(
        json.loads(rollback_approval_path.read_text())
    )
    # And it carries post-rollback equivalence evidence: the tree provably returned to the
    # pre-apply state, not merely "git apply -R exited 0".
    assert rollback_receipt["rollback_equivalence_verified"] is True
    assert rollback_receipt["pre_apply_status_digest"] == rollback_receipt["post_rollback_status_digest"]

    paths_to_verify = [
        prop_path,
        approval_path,
        vr_path,
        rollback_plan_path,
        reverse_patch_file,
        bundle_path,
        out_dir / "patch_apply_receipt.json",
        out_dir / "postflight_record.json",
        rollback_out / "rollback_receipt.json",
    ]
    report = verify_artifact_chain(paths_to_verify)
    assert report.get("valid") is True, f"Artifact chain verification failed: {report.get('errors')}"


def test_rollback_refuses_a_drifted_tree_and_instructs(tmp_path: Path):
    """Touch the tree after apply: rollback must refuse before `git apply -R`, with a recovery block."""
    repo, _test_file, prop_path, approval_path, vr_path, _ = _setup_repo_with_patch(tmp_path)
    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)

    rollback_plan_path = out_dir / "rollback_plan.json"
    rollback_approval_path = _mint_rollback_approval(tmp_path, rollback_plan_path)
    (repo / "extra.txt").write_text("drift after apply")

    rollback_out = out_dir / "rollback_out"
    with pytest.raises(RuntimeError, match="Rollback refused"):
        rollback_hitl_patch(
            rollback_plan_path,
            out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
            rollback_out,
            approval_path=rollback_approval_path,
        )
    failure_receipt = json.loads((rollback_out / "rollback_failure_receipt.json").read_text())
    assert failure_receipt["rollback_outcome"] == "REFUSED_TREE_DRIFT"
    assert "git reset --hard" in failure_receipt["recovery"]["recommended_command"]
    assert failure_receipt["recovery"]["chain_invalidation"]["invalidated"] is True


def test_a_second_rollback_of_the_same_plan_is_refused(tmp_path: Path):
    """After a clean rollback the tree is at pre-apply state, which no longer matches the plan's
    post-apply fingerprint — so a repeat rollback is refused by the drift preflight rather than
    mutating a tree the plan was never minted for."""
    repo, test_file, prop_path, approval_path, vr_path, _ = _setup_repo_with_patch(tmp_path)
    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)

    rollback_plan_path = out_dir / "rollback_plan.json"
    reverse_patch_file = out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME
    rollback_approval_path = _mint_rollback_approval(tmp_path, rollback_plan_path)

    rollback_hitl_patch(
        rollback_plan_path, reverse_patch_file, out_dir / "rollback_out", approval_path=rollback_approval_path
    )
    assert test_file.read_text() == "Line 1\nLine 2\n"

    repeat_out = out_dir / "rollback_repeat"
    with pytest.raises(RuntimeError, match="Rollback refused"):
        rollback_hitl_patch(
            rollback_plan_path, reverse_patch_file, repeat_out, approval_path=rollback_approval_path
        )
    failure_receipt = json.loads((repeat_out / "rollback_failure_receipt.json").read_text())
    assert failure_receipt["rollback_outcome"] == "REFUSED_TREE_DRIFT"
    assert failure_receipt["rollback_state"] == "NOT_EXECUTED"
