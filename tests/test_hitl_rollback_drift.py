"""Plan item 1.4 — rollback approval + drift-hardened preflight.

These exercise the *hardened* rollback lane against a real git working tree: the distinct
rollback approval gate, the pre-``git apply -R`` drift preflight, and the recovery-block-bearing
failure receipts. The happy path lives in ``test_hitl_patch_rollback.py``.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.hitl_patch_apply import (
    FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
    apply_hitl_patch,
    rollback_hitl_patch,
)
from builder_ii.hitl_patch_approval import create_hitl_patch_approval, write_hitl_patch_approval
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.hitl_rollback_approval import (
    canonical_json_digest,
    create_hitl_rollback_approval,
    write_hitl_rollback_approval,
)

_DIFF = (
    "diff --git a/file.txt b/file.txt\n"
    "index 273b063..843d1a8 100644\n"
    "--- a/file.txt\n"
    "+++ b/file.txt\n"
    "@@ -1,2 +1,2 @@\n"
    " Line 1\n"
    "-Line 2\n"
    "+Line 2 modified\n"
)


def _apply(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Run a full governed apply on a fresh repo; return (repo, out_dir, target_file)."""
    from builder_ii.artifact_chain_verification import VALIDATORS

    VALIDATORS["builder_ii.verification_execution_receipt"] = lambda data: []

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    target_file = repo / "file.txt"
    target_file.write_text("Line 1\nLine 2\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)

    patch_digest = hashlib.sha256(_DIFF.encode("utf-8")).hexdigest()
    prop = create_hitl_patch_proposal(generic_repo=repo, patch_digest=patch_digest, unified_diff=_DIFF)
    prop_path = tmp_path / "prop.json"
    write_hitl_patch_proposal(prop, prop_path)

    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(
        create_hitl_patch_approval(prop, confirmed_digest_prefix=patch_digest[:4]), approval_path
    )

    vr_path = tmp_path / "vr.json"
    vr_path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.verification_execution_receipt",
                "schema_version": "v1",
                "receipt_status": "EXECUTED",
                "valid": True,
            }
        )
    )

    out_dir = tmp_path / "out"
    with patch("builder_ii.hitl_patch_apply.validate_verification_execution_receipt_file", return_value=[]):
        apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)
    assert target_file.read_text() == "Line 1\nLine 2 modified\n"
    return repo, out_dir, target_file


def _mint_rollback_approval(out_dir: Path, tmp_path: Path, *, plan_override: dict | None = None) -> Path:
    plan = plan_override or json.loads((out_dir / "rollback_plan.json").read_text())
    approval_path = tmp_path / "rollback_approval.json"
    write_hitl_rollback_approval(
        create_hitl_rollback_approval(plan, confirmed_digest_prefix=canonical_json_digest(plan)[:4]),
        approval_path,
    )
    return approval_path


def test_rollback_refuses_on_worktree_drift_with_recovery_block(tmp_path: Path) -> None:
    _repo, out_dir, target_file = _apply(tmp_path)
    plan_path = out_dir / "rollback_plan.json"
    reverse_patch = out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME
    approval_path = _mint_rollback_approval(out_dir, tmp_path)

    # An IDE/agent/operator touches the tree between apply and rollback.
    target_file.write_text("Line 1\nLine 2 modified\nunexpected drift line\n")

    rollback_out = out_dir / "rollback_out"
    with pytest.raises(RuntimeError, match="Rollback refused"):
        rollback_hitl_patch(plan_path, reverse_patch, rollback_out, approval_path=approval_path)

    # No success receipt; a failure receipt with a recovery block was written instead.
    assert not (rollback_out / "rollback_receipt.json").exists()
    failure = json.loads((rollback_out / "rollback_failure_receipt.json").read_text())
    assert failure["rollback_outcome"] == "REFUSED_TREE_DRIFT"
    assert failure["rollback_state"] == "NOT_EXECUTED"
    recovery = failure["recovery"]
    plan = json.loads(plan_path.read_text())
    assert recovery["pre_apply_head"] == plan["pre_head"]
    assert recovery["recommended_command"] == f"git reset --hard {plan['pre_head']}"
    assert "discards ALL uncommitted changes" in recovery["data_loss_warning"]
    assert recovery["chain_invalidation"]["invalidated"] is True


def test_rollback_requires_approval_file(tmp_path: Path) -> None:
    _repo, out_dir, _target = _apply(tmp_path)
    with pytest.raises(ValueError, match="Rollback approval file does not exist"):
        rollback_hitl_patch(
            out_dir / "rollback_plan.json",
            out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
            out_dir / "rollback_out",
            approval_path=tmp_path / "missing.json",
        )


def test_rollback_rejects_unbound_approval(tmp_path: Path) -> None:
    _repo, out_dir, _target = _apply(tmp_path)
    plan = json.loads((out_dir / "rollback_plan.json").read_text())
    # Mint an approval bound to a DIFFERENT (tampered) plan.
    tampered = dict(plan)
    tampered["pre_head"] = "0" * 40
    approval_path = _mint_rollback_approval(out_dir, tmp_path, plan_override=tampered)

    with pytest.raises(ValueError, match="Rollback approval is not bound to this plan"):
        rollback_hitl_patch(
            out_dir / "rollback_plan.json",
            out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
            out_dir / "rollback_out",
            approval_path=approval_path,
        )


def test_rollback_rejects_expired_approval(tmp_path: Path) -> None:
    _repo, out_dir, _target = _apply(tmp_path)
    plan = json.loads((out_dir / "rollback_plan.json").read_text())
    approval_path = tmp_path / "rollback_approval.json"
    write_hitl_rollback_approval(
        create_hitl_rollback_approval(
            plan,
            confirmed_digest_prefix=canonical_json_digest(plan)[:4],
            approved_at=1000,
            ttl_seconds=1,  # long expired relative to now
        ),
        approval_path,
    )
    with pytest.raises(ValueError, match="Rollback approval has expired"):
        rollback_hitl_patch(
            out_dir / "rollback_plan.json",
            out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME,
            out_dir / "rollback_out",
            approval_path=approval_path,
        )


def test_rollback_refuses_plan_missing_drift_fingerprint(tmp_path: Path) -> None:
    """Fail closed: a plan without post_apply_worktree_digest cannot be drift-checked, so the
    execution boundary refuses it rather than silently skipping the check and running blind."""
    _repo, out_dir, target_file = _apply(tmp_path)
    plan_path = out_dir / "rollback_plan.json"
    plan = json.loads(plan_path.read_text())
    plan.pop("post_apply_worktree_digest", None)
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    approval_path = _mint_rollback_approval(out_dir, tmp_path)  # binds to the stripped plan

    rollback_out = out_dir / "rollback_out"
    with pytest.raises(ValueError, match="missing post_apply_worktree_digest"):
        rollback_hitl_patch(plan_path, out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME, rollback_out, approval_path=approval_path)
    # Refused before any mutation: the applied change is still present, no success receipt.
    assert target_file.read_text() == "Line 1\nLine 2 modified\n"
    assert not (rollback_out / "rollback_receipt.json").exists()


def test_rollback_refuses_plan_missing_pre_head(tmp_path: Path) -> None:
    _repo, out_dir, target_file = _apply(tmp_path)
    plan_path = out_dir / "rollback_plan.json"
    plan = json.loads(plan_path.read_text())
    plan.pop("pre_head", None)
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    approval_path = _mint_rollback_approval(out_dir, tmp_path)

    rollback_out = out_dir / "rollback_out"
    with pytest.raises(ValueError, match="missing pre_head"):
        rollback_hitl_patch(plan_path, out_dir / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME, rollback_out, approval_path=approval_path)
    assert target_file.read_text() == "Line 1\nLine 2 modified\n"


def test_reverse_apply_failure_emits_recovery_block(tmp_path: Path) -> None:
    """Backstop for a `git apply -R` that fails for any reason (e.g. an environmental git
    error) while the tree is un-drifted: the operator still gets a recovery-bearing receipt.
    Constructed by dropping the reverse-patch digest binding (so a non-appliable patch reaches
    git) while keeping the drift-protection fields present and matching (no drift)."""
    _repo, out_dir, _target = _apply(tmp_path)
    plan_path = out_dir / "rollback_plan.json"
    plan = json.loads(plan_path.read_text())
    plan.pop("rollback_patch_ref", None)  # skip the digest binding so a bad patch reaches git
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n")
    approval_path = _mint_rollback_approval(out_dir, tmp_path)

    garbage = out_dir / "garbage.patch"
    garbage.write_text("this is not a valid unified diff\n")

    rollback_out = out_dir / "rollback_out"
    with pytest.raises(RuntimeError, match="Rollback application failed"):
        rollback_hitl_patch(plan_path, garbage, rollback_out, approval_path=approval_path)

    failure = json.loads((rollback_out / "rollback_failure_receipt.json").read_text())
    assert failure["rollback_outcome"] == "REVERSE_PATCH_FAILED"
    assert failure["recovery"]["recommended_command"] == f"git reset --hard {plan['pre_head']}"
    assert failure["recovery"]["chain_invalidation"]["invalidated"] is True
