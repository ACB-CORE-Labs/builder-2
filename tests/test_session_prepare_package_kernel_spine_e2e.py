from __future__ import annotations

import hashlib
import json
from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.governed_prepare_package import (
    create_governed_prepare_package,
    validate_governed_prepare_package_directory,
    summarize_governed_prepare_package_directory,
)
from builder_ii.convention_kernel import (
    ConventionKernel,
    ConventionKernelPlatformBundle,
    validate_convention_kernel_platform_bundle,
)
from builder_ii.artifact_index_records import create_artifact_index_record
from builder_ii.artifact_chain_verification import verify_artifact_chain


ROOT = Path(__file__).resolve().parents[1]


def _make_fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "target-repo"
    repo.mkdir()
    (repo / "README.md").write_text("# Target repo\n", encoding="utf-8")
    src_dir = repo / "src"
    src_dir.mkdir()
    (src_dir / "example.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_example.py").write_text("from src.example import add\ndef test_add(): assert add(1, 2) == 3\n", encoding="utf-8")
    return repo


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_session_prepare_package_kernel_spine_e2e(tmp_path):
    repo = _make_fixture_repo(tmp_path)
    output_dir = tmp_path / "package-out"
    settings = load_settings(project_root=ROOT)

    # Snapshot target repo contents before governed flow
    initial_files = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}

    # 1. Prepare package is created
    package = create_governed_prepare_package(
        settings,
        "generic",
        output_dir=output_dir,
        repo_path=str(repo),
        task="prove canonical governed session lane e2e",
        include_deepagents_readiness=True,
    )

    expected_files = [
        "prepare-package.json",
        "session-workflow.json",
        "goose-readonly-session.json",
        "verification-profile-report.json",
        "repo-map.json",
        "context-pack.json",
        "handoff-note.json",
        "deepagents-bridge-readiness.json",
    ]
    for filename in expected_files:
        assert (output_dir / filename).exists(), f"Missing expected artifact: {filename}"

    # 2. Prepare package manifest is honest
    assert package["package_state"] == "PREPARED_ONLY"
    assert package["runtime_execution_performed"] is False
    assert package["target_repo_writes_performed"] is False

    gov = package["governance"]
    assert gov["runtime_execution"] == "DISABLED"
    assert gov["model_execution"] == "DISABLED"
    assert gov["shell_execution"] == "DISABLED"
    assert gov["source_writes"] == "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT DIRECTORY"
    assert gov["target_repo_writes"] == "DISABLED"
    assert gov["artifact_is_authority"] is False

    refs = package["artifact_refs"]
    assert len(refs) == 7  # session, goose, verification, repo_map, context_pack, handoff, deepagents
    for ref in refs:
        rel_path = ref["path"]
        emitted_file = output_dir / rel_path
        assert emitted_file.exists(), f"Referenced artifact missing: {rel_path}"
        data = json.loads(emitted_file.read_text(encoding="utf-8"))
        canonical_raw = json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        assert hashlib.sha256(canonical_raw).hexdigest() == ref["sha256"]

    # 3. Prepare package validates and summarizes
    val_errors = validate_governed_prepare_package_directory(output_dir)
    assert val_errors == [], f"Package directory validation failed: {val_errors}"

    summary = summarize_governed_prepare_package_directory(output_dir)
    assert summary["validation_state"] == "VALIDATED"
    assert summary["runtime_execution_performed"] is False
    assert summary["target_repo_writes_performed"] is False
    assert "Planned verification has not been executed" in summary["operator_report"]["verification_status"]

    _write_json(output_dir / "prepare-package-summary.json", summary)

    # 4. ConventionKernel platform spine composes successfully
    kernel = ConventionKernel()
    bundle = kernel.prepare_platform_spine(
        settings,
        "generic",
        repo_path=str(repo),
        task="prove canonical governed session lane e2e",
        include_deepagents_readiness=True,
    )
    assert isinstance(bundle, ConventionKernelPlatformBundle)
    bundle_dict = bundle.to_dict()

    spine_errors = validate_convention_kernel_platform_bundle(bundle_dict)
    assert spine_errors == [], f"Platform spine validation failed: {spine_errors}"

    assert bundle_dict["executes_now"] is False
    assert bundle_dict["operator_review_required"] is True

    spine_gov = bundle_dict["governance"]
    assert spine_gov["runtime_execution"] == "DISABLED"
    assert spine_gov["model_execution"] == "DISABLED"
    assert spine_gov["shell_execution"] == "DISABLED"
    assert spine_gov["source_writes"] == "DISABLED"
    assert spine_gov["target_repo_writes"] == "DISABLED"

    cmd_check = bundle_dict["command_authority_check"]
    assert "referenced_commands" in cmd_check
    for cmd_record in cmd_check["referenced_commands"]:
        is_tier_0_1 = "Tier 0" in cmd_record["tier"] or "Tier 1" in cmd_record["tier"]
        if not is_tier_0_1:
            assert cmd_record["status"] == "not_invoked_requires_operator_invocation"

    _write_json(output_dir / "platform-spine.json", bundle_dict)

    # 5. Artifact index recognizes emitted artifacts
    index_record = create_artifact_index_record(output_dir)
    assert index_record["counts"]["invalid"] == 0, f"Invalid artifacts found in index: {index_record['issues']}"
    assert index_record["counts"]["unknown"] == 0, f"Unknown artifacts found: {[e['path'] for e in index_record['artifacts'] if not e['known']]}"
    assert index_record["counts"]["known"] == index_record["counts"]["total"]
    assert index_record["counts"]["total"] >= 10  # 8 prepare files + summary + platform spine

    # 6. Artifact chain verification validates passive artifacts
    paths_to_verify = sorted(list(output_dir.glob("*.json")))
    chain_report = verify_artifact_chain(paths_to_verify)
    assert chain_report["valid"] is True, f"Chain verification errors: {chain_report['errors']}"
    assert chain_report["status"] == "valid"
    assert chain_report["counts"]["native_invalid"] == 0
    assert chain_report["counts"]["broken_links"] == 0

    # 7. Target repo remains untouched
    final_files = {p.relative_to(repo): p.read_bytes() for p in repo.rglob("*") if p.is_file()}
    assert initial_files == final_files, "Target repository was unexpectedly modified during governed flow"
