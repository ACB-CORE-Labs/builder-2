from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest
from builder_ii.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    validate_verification_execution_receipt_artifact,
)
from builder_ii.verification_execution_runner import _minimal_env, run_approved_verification


def _artifact_root(tmp_path: Path) -> Path:
    root = tmp_path / ".builder" / "verification"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_bound_artifacts(
    tmp_path: Path,
    *,
    approved_profiles: list[str] | None = None,
    approved_steps: list[str] | None = None,
) -> tuple[Path, Path, Path]:
    root = _artifact_root(tmp_path)
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = root / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Joshua Shay",
        approval_reason="Approve bounded platform_status verification runner proof.",
        approved_command_profiles=approved_profiles,
        approved_step_ids=approved_steps,
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = root / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)
    receipt_path = root / "verification-execution-receipt.json"
    return plan_path, approval_path, receipt_path


def _completed(
    args: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


def test_run_approved_executes_only_fixed_platform_status_profile(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    calls: list[dict[str, Any]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": list(args), "kwargs": kwargs})
        assert kwargs.get("shell") is False
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        assert "builder_ii.verification_runner_entrypoints" in args
        assert "platform-status" in args
        return _completed(args, stdout="builder-II platform status\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt_path.exists()
    assert receipt["valid"] is True
    assert receipt["receipt_status"] == "EXECUTED"
    assert receipt["runner_mode"] == RUNNER_MODE_BOUNDED_APPROVED
    assert receipt["execution_enabled"] is True
    assert receipt["shell_enabled"] is False
    assert receipt["subprocess_mode"] == SUBPROCESS_MODE_SHELL_FALSE_BOUNDED
    assert receipt["workspace_mutation_detected"] is False
    assert receipt["process_results"][0]["status"] == "success"
    assert receipt["process_results"][0]["shell"] is False
    assert validate_verification_execution_receipt_artifact(receipt) == []
    assert len(calls) == 3


def test_unapproved_profile_blocks_before_execution(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(
        tmp_path,
        approved_profiles=["docs_audit"],
        approved_steps=["docs_audit"],
    )
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return _completed(args)

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert receipt["process_results"][0]["status"] == "blocked_before_execution"
    assert any("not approved" in error for error in receipt["errors"])
    assert calls == []


def test_timeout_emits_failed_bounded_receipt(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        raise subprocess.TimeoutExpired(cmd=args, timeout=kwargs["timeout"], stderr="timeout")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is True
    assert receipt["receipt_status"] == "FAILED"
    assert receipt["process_results"][0]["status"] == "timeout"


def test_workspace_mutation_marks_receipt_invalid(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    git_calls = 0

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal git_calls
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            git_calls += 1
            return _completed(args, stdout="" if git_calls == 1 else " M changed.py\n")
        return _completed(args, stdout="builder-II platform status\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["workspace_mutation_detected"] is True
    assert any("workspace mutation" in error for error in receipt["errors"])


def test_cli_run_approved_writes_receipt(monkeypatch: Any, tmp_path: Path) -> None:
    from builder_ii.verification_execution_plan_cli import verify_app
    from typer.testing import CliRunner

    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        return _completed(args, stdout="builder-II platform status\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    result = CliRunner().invoke(
        verify_app,
        [
            "run-approved",
            "--plan",
            str(plan_path),
            "--approval",
            str(approval_path),
            "--output",
            str(receipt_path),
        ],
    )

    assert result.exit_code == 0, result.output
    assert json.loads(receipt_path.read_text(encoding="utf-8"))["receipt_status"] == "EXECUTED"


def test_minimal_env_preserves_path_without_forwarding_secrets(monkeypatch: Any, tmp_path: Path) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    monkeypatch.setenv("TERM", "xterm-256color")
    monkeypatch.setenv("SYSTEMDRIVE", "C:")
    monkeypatch.setenv("OPENAI_API_KEY", "secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    monkeypatch.setenv("GITHUB_TOKEN", "secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")

    env = _minimal_env(tmp_path)

    assert env["PATH"] == "/usr/bin:/bin"
    assert env["TERM"] == "xterm-256color"
    assert env["SYSTEMDRIVE"] == "C:"
    assert env["CORE_REPO_PATH"] == "."
    assert env["PYTHONPATH"] == str(tmp_path)
    assert "OPENAI_API_KEY" not in env
    assert "ANTHROPIC_API_KEY" not in env
    assert "GITHUB_TOKEN" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env


def test_invalid_non_object_plan_blocks_without_crashing(tmp_path: Path) -> None:
    root = _artifact_root(tmp_path)
    plan_path = root / "invalid-plan.json"
    approval_path = root / "invalid-approval.json"
    receipt_path = root / "receipt.json"

    plan_path.write_text("[]", encoding="utf-8")
    approval_path.write_text("{}", encoding="utf-8")

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("plan" in error.lower() for error in receipt["errors"])


def test_invalid_false_plan_blocks_without_subprocess(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    plan["valid"] = False
    plan["errors"] = ["synthetic invalid plan"]
    plan = attach_digest(plan, digest_key="verification_execution_plan_digest")
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return _completed(args)

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("plan must be valid" in error for error in receipt["errors"])
    assert calls == []


def test_invalid_false_approval_blocks_without_subprocess(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["valid"] = False
    approval["errors"] = ["synthetic invalid approval"]
    approval = attach_digest(approval, digest_key="verification_execution_approval_digest")
    approval_path.write_text(json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return _completed(args)

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("approval must be valid" in error for error in receipt["errors"])
    assert calls == []


def test_output_outside_artifact_root_blocks_without_write_or_subprocess(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, _receipt_path = _write_bound_artifacts(tmp_path)
    unsafe_output = tmp_path / "receipt-outside-root.json"
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return _completed(args)

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=unsafe_output,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("artifact root" in error for error in receipt["errors"])
    assert not unsafe_output.exists()
    assert calls == []


def test_output_equal_to_artifact_root_blocks_without_write_or_subprocess(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, _receipt_path = _write_bound_artifacts(tmp_path)
    unsafe_output = tmp_path / ".builder" / "verification"
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return _completed(args)

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=unsafe_output,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("artifact root" in error for error in receipt["errors"])
    assert unsafe_output.is_dir()
    assert calls == []


def test_docs_audit_profile_runs_and_writes_postflight(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    receipt_path = receipt_path.with_name("docs-audit-receipt.json")

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        assert args[-1] == "docs-audit"
        assert kwargs.get("shell") is False
        return _completed(args, stdout="docs truth audit passed\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="docs_audit",
    )

    postflight_path = receipt_path.with_name(receipt_path.stem + "-postflight.json")
    postflight = json.loads(postflight_path.read_text(encoding="utf-8"))
    assert receipt["valid"] is True
    assert receipt["process_results"][0]["profile"] == "docs_audit"
    assert receipt["command_authority_decision"]["allowed"] is True
    assert receipt["postflight_ref"]["path"] == str(postflight_path)
    assert postflight["postflight_state"] == "RUN_COMPLETE"
    assert postflight["receipt_digest"]
    assert postflight["valid"] is True


def test_postflight_marks_mutation_mismatch_invalid(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    git_calls = 0

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal git_calls
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            git_calls += 1
            return _completed(args, stdout="" if git_calls == 1 else "?? new-file\n")
        return _completed(args, stdout="builder-II platform status\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    postflight_path = receipt_path.with_name(receipt_path.stem + "-postflight.json")
    postflight = json.loads(postflight_path.read_text(encoding="utf-8"))
    assert receipt["valid"] is False
    assert postflight["valid"] is False
    assert "postflight detected workspace mutation" in postflight["errors"]
