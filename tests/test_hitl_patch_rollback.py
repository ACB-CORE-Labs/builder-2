import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.artifact_chain_verification import verify_artifact_chain
from builder_ii.hitl_patch_apply import (
    apply_hitl_patch,
    rollback_hitl_patch,
)
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal


@patch("builder_ii.hitl_patch_apply.validate_verification_execution_receipt_file", return_value=[])
def test_successful_apply_and_rollback(mock_validate, tmp_path: Path):
    from builder_ii.artifact_chain_verification import VALIDATORS

    VALIDATORS["builder_ii.approval_record"] = lambda data: []
    VALIDATORS["builder_ii.verification_execution_receipt"] = lambda data: []

    # 1. Setup clean target git repository
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)

    test_file = repo / "file.txt"
    test_file.write_text("Line 1\nLine 2\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True)

    # 2. Create patch proposal
    # Diff to apply: change "Line 2" to "Line 2 modified"
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

    # 3. Create approval and verification receipt artifacts
    raw_prop = json.dumps(prop, sort_keys=True, separators=(",", ":")).encode("utf-8")
    prop_digest = hashlib.sha256(raw_prop).hexdigest()

    approval_path = tmp_path / "approval.json"
    approval_path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.approval_record",
                "schema_version": "v1",
                "patch_digest": patch_digest,
                "valid": True,
                "proposal": {
                    "path": str(prop_path),
                    "sha256": prop_digest,
                    "kind": "builder_ii.hitl_patch_proposal",
                },
            }
        )
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

    # 4. Apply the patch
    out_dir = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out_dir)

    # Verify the patch is applied to file.txt
    assert test_file.read_text() == "Line 1\nLine 2 modified\n"

    # Verify metadata contains renamed rollback keys
    rollback_plan_path = out_dir / "rollback_plan.json"
    assert rollback_plan_path.exists()
    plan_data = json.loads(rollback_plan_path.read_text())
    assert "rollback_patch_ref" in plan_data
    assert "reverse_patch_ref" not in plan_data
    assert plan_data["rollback_patch_apply_mode"] == "git_apply_reverse_flag"
    assert "reverse_patch_apply_mode" not in plan_data

    bundle_path = out_dir / "rollback_bundle.json"
    assert bundle_path.exists()
    bundle_data = json.loads(bundle_path.read_text())
    assert "rollback_patch_ref" in bundle_data
    assert "reverse_patch_ref" not in bundle_data

    # Verify the reverse patch file was written
    reverse_patch_file = out_dir / "rollback.patch"
    assert reverse_patch_file.exists()

    # 5. Rollback verification: test digest mismatch rejection
    # If we corrupt the rollback patch file, rollback should be rejected
    original_reverse_patch_content = reverse_patch_file.read_text()
    reverse_patch_file.write_text("corrupted content")

    with pytest.raises(ValueError, match="Reverse patch digest does not match rollback plan binding"):
        rollback_hitl_patch(rollback_plan_path, reverse_patch_file, out_dir / "rollback_out")

    # Restore the original rollback patch content
    reverse_patch_file.write_text(original_reverse_patch_content)

    # 6. Execute successful rollback
    rollback_hitl_patch(rollback_plan_path, reverse_patch_file, out_dir / "rollback_out")

    # Verify file is restored to the initial state
    assert test_file.read_text() == "Line 1\nLine 2\n"

    # 7. Validate artifact chain verification
    # Compile the list of paths to verify
    paths_to_verify = [
        prop_path,
        approval_path,
        vr_path,
        rollback_plan_path,
        reverse_patch_file,
        bundle_path,
        out_dir / "patch_apply_receipt.json",
        out_dir / "postflight_record.json",
        out_dir / "rollback_out" / "rollback_receipt.json",
    ]

    # Run chain verification
    report = verify_artifact_chain(paths_to_verify)
    print("CHAIN VERIFICATION ERRORS:", json.dumps(report.get("errors"), indent=2))
    assert report.get("valid") is True, f"Artifact chain verification failed: {report.get('errors')}"
