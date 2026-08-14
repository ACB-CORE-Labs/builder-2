import json
import subprocess
from pathlib import Path

from builder_ii.platform_status_cli import platform_app
from typer.testing import CliRunner

from builder_ii.core.demo_loop import (
    DEMO_REPORT_KIND,
    run_demo_loop,
    validate_demo_report,
)
from builder_ii.governance.hitl.hitl_patch_apply import _verification_receipt_errors


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _init_repo(repo: Path) -> None:
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.name", "Demo Test")
    _git(repo, "config", "user.email", "demo@example.com")


def _generic_repo(tmp_path: Path, name: str = "acme-lib") -> Path:
    # A plain generic target: no AssetOverflow/core remote, dirname != "core", and no docs/
    # directory (so the default marker lands in a brand-new directory).
    repo = tmp_path / name
    _init_repo(repo)
    (repo / "src").mkdir()
    (repo / "README.md").write_text("# acme-lib\n", encoding="utf-8")
    (repo / "src" / "lib.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def _target_repo(tmp_path: Path) -> Path:
    # Passes the CORE identity check via the "core" dirname fallback.
    repo = tmp_path / "core"
    _init_repo(repo)
    (repo / "docs").mkdir()
    (repo / "demos").mkdir()
    (repo / "README.md").write_text("# CORE\n", encoding="utf-8")
    (repo / "AGENTS.md").write_text("# CORE agents\n", encoding="utf-8")
    (repo / "docs" / "runtime_contracts.md").write_text("runtime contracts\n", encoding="utf-8")
    (repo / "demos" / "existing-core-data.json").write_text('{"kind":"core_fixture"}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return repo


def test_generic_demo_prepare_is_interactive_checkpoint(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"

    report = run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="prepare")

    assert report["kind"] == DEMO_REPORT_KIND
    assert report["phase"] == "prepare"
    assert report["target"]["name"] == "acme-lib"
    assert report["target"]["profile"] == "generic"
    assert "demo-loop --phase approve" in report["next_command"]
    assert "--target-name acme-lib" in report["next_command"]
    assert (output_dir / "demo-worktree").is_dir()
    assert (output_dir / "hitl-patch-proposal.json").is_file()
    assert (output_dir / "DEMO_EVIDENCE.md").is_file()
    assert _git(repo, "status", "--porcelain=v1") == ""
    assert validate_demo_report(report) == []
    planner = json.loads((output_dir / "deterministic-planner.json").read_text(encoding="utf-8"))
    assert planner["target"]["profile"] == "generic"
    assert planner["target_invariant_policy"]["sensitive_path_prefixes"] == []


def test_generic_demo_all_applies_verifies_rolls_back_and_indexes_evidence(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"

    run_demo_loop(
        target_repo=repo,
        output_dir=output_dir,
        target_name="acme-lib",
        phase="all",
        approve=True,
    )
    report = run_demo_loop(
        target_repo=repo,
        output_dir=output_dir,
        target_name="acme-lib",
        phase="all",
        approve=True,
        force=True,
    )

    assert report["kind"] == DEMO_REPORT_KIND
    assert report["phase"] == "all"
    assert report["final_state"]["source_repo_untouched_by_demo"] is True
    assert report["final_state"]["demo_worktree_clean_after_rollback"] is True
    assert report["chain_verification"]["valid"] is True
    assert (output_dir / "hitl-patch-approval.json").is_file()
    assert (output_dir / "hitl-rollback-approval.json").is_file()
    assert (output_dir / "patch-apply" / "patch_apply_receipt.json").is_file()
    assert (output_dir / "rollback" / "rollback_receipt.json").is_file()
    assert (output_dir / "artifact-index.json").is_file()
    assert (output_dir / "DEMO_EVIDENCE.md").is_file()
    assert not (output_dir / "demo-worktree" / "docs" / "builder_ii_demo_marker.md").exists()
    assert _git(output_dir / "demo-worktree", "status", "--porcelain=v1") == ""
    assert _git(repo, "status", "--porcelain=v1") == ""
    assert validate_demo_report(report) == []

    evidence = (output_dir / "DEMO_EVIDENCE.md").read_text(encoding="utf-8")
    assert all("demo-worktree/" not in ref["path"] for ref in report["artifact_refs"])
    assert all(not ref["path"].endswith("demo-loop-report.json") for ref in report["artifact_refs"])
    # The governing approvals are part of the demo evidence set.
    ref_kinds = {ref["kind"] for ref in report["artifact_refs"]}
    assert "builder_ii.hitl_patch_approval" in ref_kinds
    assert "builder_ii.hitl_rollback_approval" in ref_kinds
    for ref in report["artifact_refs"]:
        assert ref["sha256"] in evidence

    artifact_index = json.loads((output_dir / "artifact-index.json").read_text(encoding="utf-8"))
    assert artifact_index["status"] == "complete"
    assert artifact_index["counts"]["invalid"] == 0
    assert artifact_index["recursive"] is True
    assert str(output_dir / "demo-worktree") in artifact_index["excluded_paths"]
    assert all("demo-worktree/" not in artifact["path"] for artifact in artifact_index["artifacts"])
    assert all(artifact["path"] != "demo-loop-report.json" for artifact in artifact_index["artifacts"])


def test_core_profile_demo_all_keeps_identity_and_sensitive_checks(tmp_path: Path) -> None:
    repo = _target_repo(tmp_path)
    output_dir = tmp_path / "demo"

    report = run_demo_loop(
        target_repo=repo,
        output_dir=output_dir,
        target_name="core",
        phase="all",
        approve=True,
    )

    assert report["target"]["name"] == "core"
    assert report["target"]["profile"] == "core"
    assert report["final_state"]["demo_worktree_clean_after_rollback"] is True
    assert report["chain_verification"]["valid"] is True
    assert _git(repo, "status", "--porcelain=v1") == ""
    receipt = json.loads((output_dir / "post-apply-verification-receipt.json").read_text(encoding="utf-8"))
    check_names = {check["name"] for check in receipt["checks"]}
    assert "sensitive_target_modules_untouched" in check_names
    assert "only_demo_marker_mutated" in check_names
    planner = json.loads((output_dir / "deterministic-planner.json").read_text(encoding="utf-8"))
    assert "algebra/" in planner["target_invariant_policy"]["sensitive_path_prefixes"]


def test_core_profile_refuses_repo_without_core_identity(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"

    try:
        run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="core", phase="prepare")
    except ValueError as exc:
        assert "does not look like the core target" in str(exc)
    else:
        raise AssertionError("core profile accepted a repo without CORE identity")


def test_approve_checkpoint_mints_no_approval_without_flag(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="prepare")

    report = run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="approve")

    assert "no approval artifact was minted" in report["next_command"]
    assert not (output_dir / "hitl-patch-approval.json").exists()

    try:
        run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="apply")
    except ValueError as exc:
        assert "approval phase must run before apply" in str(exc)
    else:
        raise AssertionError("apply ran without an approval artifact")
    assert not (output_dir / "demo-worktree" / "docs" / "builder_ii_demo_marker.md").exists()


def test_marker_path_shape_is_fail_closed(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    for bad_marker, expected in (
        ("../escape.md", "traversal"),
        ("/tmp/abs.md", "relative"),
        (".git/hooks/pwn", ".git"),
        ("docs/", "file, not a directory"),
    ):
        try:
            run_demo_loop(
                target_repo=repo,
                output_dir=tmp_path / "demo-bad",
                target_name="acme-lib",
                marker_path=bad_marker,
                phase="prepare",
            )
        except ValueError as exc:
            assert "invalid demo target spec" in str(exc)
            assert expected in str(exc)
        else:
            raise AssertionError(f"marker path accepted: {bad_marker}")


def test_core_profile_refuses_marker_under_sensitive_prefix(tmp_path: Path) -> None:
    repo = _target_repo(tmp_path)
    try:
        run_demo_loop(
            target_repo=repo,
            output_dir=tmp_path / "demo",
            target_name="core",
            marker_path="algebra/marker.md",
            phase="prepare",
        )
    except ValueError as exc:
        assert "sensitive path prefix" in str(exc)
    else:
        raise AssertionError("core profile accepted a marker under a sensitive prefix")


def test_custom_marker_path_in_new_directory_round_trips(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"

    report = run_demo_loop(
        target_repo=repo,
        output_dir=output_dir,
        target_name="acme-lib",
        marker_path="notes/demo/marker.md",
        phase="all",
        approve=True,
    )

    assert report["final_state"]["demo_worktree_clean_after_rollback"] is True
    assert not (output_dir / "demo-worktree" / "notes").exists()
    assert _git(output_dir / "demo-worktree", "status", "--porcelain=v1") == ""
    receipt = json.loads((output_dir / "post-apply-verification-receipt.json").read_text(encoding="utf-8"))
    assert receipt["receipt_status"] == "EXECUTED"
    only_marker = next(check for check in receipt["checks"] if check["name"] == "only_demo_marker_mutated")
    assert only_marker["status"] == "PASS"
    assert only_marker["status_lines"] == ["?? notes/demo/marker.md"]


def test_verify_fails_closed_when_extra_file_mutated(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="prepare")
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="approve", approve=True)
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="apply")

    stray = output_dir / "demo-worktree" / "src" / "stray.txt"
    stray.write_text("unexpected\n", encoding="utf-8")

    try:
        run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="verify")
    except ValueError as exc:
        assert "only_demo_marker_mutated" in str(exc)
    else:
        raise AssertionError("verify passed despite an extra mutated file")
    receipt = json.loads((output_dir / "post-apply-verification-receipt.json").read_text(encoding="utf-8"))
    assert receipt["receipt_status"] == "FAILED"


def test_demo_apply_gate_rejects_malformed_demo_receipt(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="prepare")

    receipt_path = output_dir / "forged-demo-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.demo_verification_receipt",
                "schema_version": 1,
                "label": "after_apply",
                "target": {"name": "acme-lib", "repo": str(output_dir / "demo-worktree")},
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

    errors = _verification_receipt_errors(receipt_path, target_repo=output_dir / "demo-worktree")

    assert "label must be before_apply for HITL patch application" in errors
    assert "all checks must be PASS" in errors


def test_demo_receipt_fallback_is_bound_to_the_target_repo(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="prepare")

    receipt_path = output_dir / "forged-rebound-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.demo_verification_receipt",
                "schema_version": 1,
                "label": "before_apply",
                "target": {"name": "acme-lib", "repo": str(tmp_path / "some-other-repo")},
                "receipt_status": "EXECUTED",
                "checks": [{"name": "demo_marker_state", "status": "PASS"}],
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

    errors = _verification_receipt_errors(receipt_path, target_repo=output_dir / "demo-worktree")
    assert "target.repo must match proposal target repo" in errors


def test_demo_cli_runs_prepare_checkpoint(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"

    result = CliRunner().invoke(
        platform_app,
        [
            "demo-loop",
            "--target-repo",
            str(repo),
            "--target-name",
            "acme-lib",
            "--output-dir",
            str(output_dir),
            "--phase",
            "prepare",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["kind"] == DEMO_REPORT_KIND
    assert data["phase"] == "prepare"
    assert data["target"]["name"] == "acme-lib"


def test_demo_cli_accepts_deprecated_target_repo_alias(tmp_path: Path) -> None:
    repo = _target_repo(tmp_path)
    output_dir = tmp_path / "demo"

    result = CliRunner().invoke(
        platform_app,
        [
            "demo-loop",
            "--core-repo",
            str(repo),
            "--target-name",
            "core",
            "--output-dir",
            str(output_dir),
            "--phase",
            "prepare",
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["target"]["name"] == "core"
    assert data["target"]["profile"] == "core"


def test_demo_validate_cli_accepts_report(tmp_path: Path) -> None:
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="prepare")

    result = CliRunner().invoke(
        platform_app,
        ["validate-demo-loop", str(output_dir / "demo-loop-report.json")],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["valid"] is True


def test_demo_validate_cli_catches_tampered_receipt(tmp_path: Path) -> None:
    # The flagship tamper-detection beat (plan item 3.11): edit a receipt after the run and
    # validate-demo-loop must fail, naming the tampered file — the report alone proves nothing
    # about files it no longer matches.
    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="all", approve=True)
    report_path = output_dir / "demo-loop-report.json"

    untampered = CliRunner().invoke(platform_app, ["validate-demo-loop", str(report_path)])
    assert untampered.exit_code == 0, untampered.output

    receipt_path = output_dir / "post-apply-verification-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["workspace_mutation_detected"] = False
    receipt["status_lines"] = []
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tampered = CliRunner().invoke(platform_app, ["validate-demo-loop", str(report_path)])
    assert tampered.exit_code == 1
    flat = tampered.output.replace("\n", "")
    assert "does not match its recorded sha256" in flat
    assert "post-apply-verification-receipt.json" in flat


def test_demo_validate_cli_catches_retargeted_approval(tmp_path: Path) -> None:
    # Second tamper variant: re-pointing the governing approval at a different patch digest is
    # caught twice — the refs re-check names the edited file, and native approval validation
    # (via builder-chain verify-artifacts) rejects the broken digest-prefix confirmation binding.
    from builder_ii.core.artifact_chain_verification import verify_artifact_chain

    repo = _generic_repo(tmp_path)
    output_dir = tmp_path / "demo"
    run_demo_loop(target_repo=repo, output_dir=output_dir, target_name="acme-lib", phase="all", approve=True)

    approval_path = output_dir / "hitl-patch-approval.json"
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    digest = approval["patch_digest"]
    approval["patch_digest"] = ("0" if digest[0] != "0" else "1") + digest[1:]
    approval_path.write_text(json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tampered = CliRunner().invoke(platform_app, ["validate-demo-loop", str(output_dir / "demo-loop-report.json")])
    assert tampered.exit_code == 1
    assert "does not match its recorded sha256" in tampered.output.replace("\n", "")

    chain_report = verify_artifact_chain([output_dir / "hitl-patch-proposal.json", approval_path])
    assert chain_report["valid"] is False
    assert any("digest_prefix" in error for error in chain_report["errors"])
