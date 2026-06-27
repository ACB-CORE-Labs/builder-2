from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builder_ii.artifact_index_records import validate_artifact_index_record_file
from builder_ii.release_manifest import validate_v0_release_manifest_file
from scripts.verify_v0_release import run_proof_harness


def test_v0_release_proof_harness_e2e(tmp_path: Path) -> None:
    output_dir = tmp_path / "v0-proof-out"
    success = run_proof_harness(output_dir)
    assert success is True

    expected_files = [
        "prepare-package.json",
        "session-workflow.json",
        "goose-readonly-session.json",
        "verification-profile-report.json",
        "repo-map.json",
        "context-pack.json",
        "handoff-note.json",
        "deepagents-bridge-readiness.json",
        "platform-spine.json",
        "prepare-package-summary.json",
        "chain-verification-report.json",
        "release-manifest.json",
        "artifact-index.json",
    ]
    for filename in expected_files:
        assert (output_dir / filename).exists(), f"Expected artifact missing: {filename}"

    # Validate index record file
    index_errors = validate_artifact_index_record_file(output_dir / "artifact-index.json")
    assert index_errors == []

    index_data = json.loads((output_dir / "artifact-index.json").read_text(encoding="utf-8"))
    assert index_data["counts"]["invalid"] == 0
    assert index_data["counts"]["unknown"] == 0
    # The index records all emitted files prior to artifact-index.json itself (12 files)
    assert index_data["counts"]["known"] == len(expected_files) - 1

    # Validate release manifest file
    manifest_errors = validate_v0_release_manifest_file(output_dir / "release-manifest.json")
    assert manifest_errors == []

    manifest_data = json.loads((output_dir / "release-manifest.json").read_text(encoding="utf-8"))
    assert manifest_data["release_identity"]["repository"] == "AssetOverflow/builder-II"
    assert manifest_data["governance"]["runtime_execution"] == "DISABLED"
    assert manifest_data["proof_status"]["verified_chain_valid"] is True

    # Check chain report
    chain_data = json.loads((output_dir / "chain-verification-report.json").read_text(encoding="utf-8"))
    assert chain_data["valid"] is True
    assert chain_data["counts"]["broken_links"] == 0


def test_v0_release_proof_harness_rejects_nested_output_dir(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    output_dir = repo / "dist" / "proof"

    success = run_proof_harness(output_dir, repo_path=repo)
    assert success is False
