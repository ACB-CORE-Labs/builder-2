import json
import subprocess
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.core_demo_loop import (
    CORE_DEMO_REPORT_KIND,
    run_core_demo_loop,
    validate_core_demo_report,
)
from builder_ii.hitl_patch_apply import _verification_receipt_errors
from builder_ii.platform_status_cli import platform_app


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _core_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "core"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Demo Test")
    _git(repo, "config", "user.email", "demo@example.com")
    (repo / "docs").mkdir()
    (repo / "demos").mkdir()
    (repo / "README.md").write_text("# CORE\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("# CORE agents\n", encoding="utf-8")
    (repo / "docs" / "runtime_contracts.md").write_text("runtime contracts\n", encoding="utf-8")
    (repo / "demos" / "existing-core-data.json").write_text('{"kind":"core_fixture"}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def test_core_demo_prepare_is_interactive_checkpoint(tmp_path: Path) -> None:
    repo = _core_repo(tmp_path)
    output_dir = tmp_path / "demo"

    report = run_core_demo_loop(core_repo=repo, output_dir=output_dir, phase="prepare")

    assert report["kind"] == CORE_DEMO_REPORT_KIND
    assert report["phase"] == "prepare"
    assert "demo-loop --phase approve" in report["next_command"]
    assert (output_dir / "core-worktree").is_dir()
    assert (output_dir / "hitl-patch-proposal.json").is_file()
    assert (output_dir / "DEMO_EVIDENCE.md").is_file()
    assert _git(repo, "status", "--porcelain=v1") == ""
    assert validate_core_demo_report(report) == []


def test_core_demo_all_applies_verifies_rolls_back_and_indexes_evidence(tmp_path: Path) -> None:
    repo = _core_repo(tmp_path)
    output_dir = tmp_path / "demo"

    run_core_demo_loop(
        core_repo=repo,
        output_dir=output_dir,
        phase="all",
        approve=True,
    )
    report = run_core_demo_loop(
        core_repo=repo,
        output_dir=output_dir,
        phase="all",
        approve=True,
        force=True,
    )

    assert report["kind"] == CORE_DEMO_REPORT_KIND
    assert report["phase"] == "all"
    assert report["final_state"]["source_repo_untouched_by_demo"] is True
    assert report["final_state"]["demo_worktree_clean_after_rollback"] is True
    assert report["chain_verification"]["valid"] is True
    assert (output_dir / "patch-apply" / "patch_apply_receipt.json").is_file()
    assert (output_dir / "rollback" / "rollback_receipt.json").is_file()
    assert (output_dir / "artifact-index.json").is_file()
    assert (output_dir / "DEMO_EVIDENCE.md").is_file()
    assert not (output_dir / "core-worktree" / "docs" / "builder_ii_core_demo_marker.md").exists()
    assert _git(output_dir / "core-worktree", "status", "--porcelain=v1") == ""
    assert _git(repo, "status", "--porcelain=v1") == ""
    assert validate_core_demo_report(report) == []

    evidence = (output_dir / "DEMO_EVIDENCE.md").read_text(encoding="utf-8")
    assert "existing-core-data.json" not in evidence
    assert all("core-worktree/" not in ref["path"] for ref in report["artifact_refs"])
    assert all(not ref["path"].endswith("core-demo-loop-report.json") for ref in report["artifact_refs"])
    for ref in report["artifact_refs"]:
        assert ref["sha256"] in evidence

    artifact_index = json.loads((output_dir / "artifact-index.json").read_text(encoding="utf-8"))
    assert artifact_index["status"] == "complete"
    assert artifact_index["counts"]["invalid"] == 0
    assert artifact_index["recursive"] is True
    assert str(output_dir / "core-worktree") in artifact_index["excluded_paths"]
    assert all("core-worktree/" not in artifact["path"] for artifact in artifact_index["artifacts"])
    assert all(artifact["path"] != "core-demo-loop-report.json" for artifact in artifact_index["artifacts"])


def test_core_demo_apply_gate_rejects_malformed_demo_receipt(tmp_path: Path) -> None:
    repo = _core_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_core_demo_loop(core_repo=repo, output_dir=output_dir, phase="prepare")

    receipt_path = output_dir / "forged-core-demo-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.core_demo_verification_receipt",
                "schema_version": 1,
                "label": "after_apply",
                "target": {"name": "core", "repo": str(output_dir / "core-worktree")},
                "receipt_status": "EXECUTED",
                "checks": [{"name": "forged", "status": "FAIL"}],
                "governance": {
                    "model_execution": "DISABLED",
                    "source_writes": "DISABLED",
                    "artifact_is_authority": False,
                    "core_workbench_coupling": "NONE",
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    errors = _verification_receipt_errors(receipt_path, target_repo=output_dir / "core-worktree")

    assert "label must be before_apply for HITL patch application" in errors
    assert "all checks must be PASS" in errors


def test_core_demo_cli_runs_prepare_checkpoint(tmp_path: Path) -> None:
    repo = _core_repo(tmp_path)
    output_dir = tmp_path / "demo"

    result = CliRunner().invoke(
        platform_app,
        [
            "demo-loop",
            "--core-repo",
            str(repo),
            "--output-dir",
            str(output_dir),
            "--phase",
            "prepare",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kind"] == CORE_DEMO_REPORT_KIND
    assert data["phase"] == "prepare"


def test_core_demo_validate_cli_accepts_report(tmp_path: Path) -> None:
    repo = _core_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_core_demo_loop(core_repo=repo, output_dir=output_dir, phase="prepare")

    result = CliRunner().invoke(
        platform_app,
        ["validate-demo-loop", str(output_dir / "core-demo-loop-report.json")],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["valid"] is True
