from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from builder_ii.config_schema import attach_digest
from builder_ii.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_plan import (
    TARGET_CODE_EXECUTING_PROFILES,
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    validate_verification_execution_receipt_artifact,
)
from builder_ii.verification_execution_runner import (
    BUILDER_II_IMPORT_ROOT,
    SUPPORTED_COMMAND_PROFILES,
    _minimal_env,
    run_approved_verification,
)


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
        approval_actor="Jane Operator",
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


_FAKE_HEAD_SHA = "a" * 40
_FAKE_BRANCH = "main"


def _rev_parse_reply(
    args: list[str], head_sha: str = _FAKE_HEAD_SHA, branch: str = _FAKE_BRANCH
) -> subprocess.CompletedProcess[str] | None:
    """Canned reply for the runner's `git rev-parse HEAD --abbrev-ref HEAD` commit-identity call."""
    if args[:2] == ["git", "rev-parse"]:
        return _completed(args, stdout=f"{head_sha}\n{branch}\n")
    return None


def test_run_approved_executes_only_fixed_platform_status_profile(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    calls: list[dict[str, Any]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append({"args": list(args), "kwargs": kwargs})
        assert kwargs.get("shell") is False
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
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
    # commit identity is captured into the receipt (schema v2)
    assert receipt["target_commit"] == _FAKE_HEAD_SHA
    assert receipt["target_branch"] == _FAKE_BRANCH
    assert receipt["preflight_git_state"]["head_sha"] == _FAKE_HEAD_SHA
    assert receipt["observed_byproducts"] == []
    assert validate_verification_execution_receipt_artifact(receipt) == []
    # preflight (status + rev-parse) + profile exec + postflight (status + rev-parse)
    assert len(calls) == 5


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
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
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
    # the effective timeout comes from the plan (platform_status: 120s), not the old hardcoded 30s
    assert receipt["process_results"][0]["timeout_seconds"] == 120


def test_workspace_mutation_marks_receipt_invalid(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    git_calls = 0

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal git_calls
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            git_calls += 1
            return _completed(args, stdout="" if git_calls == 1 else " M changed.py\n")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
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
    # platform_status pins no ignore-globs, so a changed source file is a real mutation
    assert any("workspace mutation" in error and "changed.py" in error for error in receipt["errors"])


def test_cli_run_approved_writes_receipt(monkeypatch: Any, tmp_path: Path) -> None:
    from builder_ii.verification_execution_plan_cli import verify_app
    from typer.testing import CliRunner

    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
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

    env = _minimal_env(tmp_path, allow_target_repo_imports=False)

    assert env["PATH"] == "/usr/bin:/bin"
    assert env["TERM"] == "xterm-256color"
    assert env["SYSTEMDRIVE"] == "C:"
    assert env["CORE_REPO_PATH"] == "."
    # This used to read `== str(tmp_path)`: the safe profiles put the *target repo* on the child's
    # import path, which is what let a target shadow `builder_ii` and `sitecustomize`. A profile
    # that may not execute target code resolves imports against builder-II alone.
    assert env["PYTHONPATH"] == str(BUILDER_II_IMPORT_ROOT)
    assert env["PYTHONSAFEPATH"] == "1"
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
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
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


def _write_target_code_chain(
    tmp_path: Path,
    *,
    profile: str = "pytest_full",
    acknowledged: bool = True,
    target_profile: str = "builder",
    verification_profile: str = "builder_full",
) -> tuple[Path, Path, Path]:
    """Build a chain that approves a single target-code-executing profile, with/without the D7 ack."""
    root = _artifact_root(tmp_path)
    from builder_ii.verification_execution_plan import (
        finalize_verification_execution_plan,
        write_verification_execution_plan,
    )

    plan = finalize_verification_execution_plan(
        target_profile=target_profile,
        verification_profile=verification_profile,
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = root / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Jane Operator",
        approval_reason=f"Approve bounded {profile} runner proof.",
        approved_command_profiles=[profile],
        approved_step_ids=[profile],
        execution_risk_acknowledged=acknowledged,
        acknowledged_risk=(
            "Operator acknowledges this profile runs the target repository's own test and imported "
            "configuration code on this host with operator privileges."
            if acknowledged
            else None
        ),
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = root / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)
    receipt_path = root / "verification-execution-receipt.json"
    return plan_path, approval_path, receipt_path


def _profile_stdout_run(profile_marker: str) -> Any:
    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
        assert profile_marker in args
        return _completed(args, stdout=f"{profile_marker} ok\n")

    return fake_run


def test_pytest_full_runs_with_acknowledged_risk(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_target_code_chain(tmp_path, profile="pytest_full")
    monkeypatch.setattr(
        "builder_ii.verification_execution_runner.subprocess.run", _profile_stdout_run("pytest-full")
    )

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="pytest_full"
    )

    assert receipt["valid"] is True
    assert receipt["receipt_status"] == "EXECUTED"
    assert receipt["process_results"][0]["profile"] == "pytest_full"
    # plan declares 1800s for pytest_full; ceiling is 1800s -> effective 1800s (not the old 30s)
    assert receipt["process_results"][0]["timeout_seconds"] == 1800
    assert receipt["execution_risk_acknowledged"] is True
    assert receipt["acknowledged_risk"]
    assert receipt["target_commit"] == _FAKE_HEAD_SHA
    assert validate_verification_execution_receipt_artifact(receipt) == []


def test_builder_full_runs_with_acknowledged_risk(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_target_code_chain(tmp_path, profile="builder_full")
    monkeypatch.setattr(
        "builder_ii.verification_execution_runner.subprocess.run", _profile_stdout_run("builder-full")
    )

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="builder_full"
    )

    assert receipt["valid"] is True
    assert receipt["receipt_status"] == "EXECUTED"
    assert receipt["process_results"][0]["profile"] == "builder_full"
    assert receipt["execution_risk_acknowledged"] is True


def test_pytest_full_without_ack_is_blocked_before_execution(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    # An approval that approves pytest_full without the ack is itself invalid; the runner blocks it.
    plan_path, approval_path, receipt_path = _write_target_code_chain(
        tmp_path, profile="pytest_full", acknowledged=False
    )
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        rev_parse = _rev_parse_reply(args)
        return rev_parse if rev_parse is not None else _completed(args)

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="pytest_full"
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert not any("pytest-full" in call for call in calls), "no subprocess may run without the ack"


def test_runner_refuses_target_code_when_ack_stripped(monkeypatch: Any, tmp_path: Path) -> None:
    # Belt-and-suspenders (D7): even if an approval is forced valid-looking without the ack,
    # the runner independently refuses to spawn the target-code profile.
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_target_code_chain(tmp_path, profile="pytest_full")
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["execution_risk_acknowledged"] = False
    approval["acknowledged_risk"] = None
    approval["valid"] = True
    approval["errors"] = []
    approval = attach_digest(approval, digest_key="verification_execution_approval_digest")
    approval_path.write_text(json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        rev_parse = _rev_parse_reply(args)
        return rev_parse if rev_parse is not None else _completed(args)

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="pytest_full"
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("acknowledg" in error for error in receipt["errors"])
    assert not any("pytest-full" in call for call in calls)


def test_pytest_cache_byproduct_is_recorded_not_a_mutation(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_target_code_chain(tmp_path, profile="pytest_full")
    git_calls = 0

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal git_calls
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            git_calls += 1
            # postflight shows only a pinned-ignore byproduct path
            return _completed(args, stdout="" if git_calls == 1 else "?? .pytest_cache/v/cache/lastfailed\n")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
        return _completed(args, stdout="pytest-full ok\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="pytest_full"
    )

    assert receipt["workspace_mutation_detected"] is False
    assert receipt["observed_byproducts"] == [".pytest_cache/v/cache/lastfailed"]
    assert receipt["valid"] is True
    assert receipt["receipt_status"] == "EXECUTED"


def test_postflight_capture_failure_is_treated_as_mutation(monkeypatch: Any, tmp_path: Path) -> None:
    # Target code can corrupt/delete .git mid-run; a postflight git state that cannot be captured
    # must never be read as "clean" (fail-closed, not fail-open).
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_target_code_chain(tmp_path, profile="pytest_full")
    status_calls = 0

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal status_calls
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            status_calls += 1
            # preflight captures cleanly; postflight fails (non-zero return -> captured=False)
            return _completed(args, returncode=0 if status_calls == 1 else 1, stdout="")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
        return _completed(args, stdout="pytest-full ok\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="pytest_full"
    )

    assert receipt["workspace_mutation_detected"] is True
    assert receipt["valid"] is False
    assert any("postflight git state could not be captured" in error for error in receipt["errors"])


def test_nested_pytest_cache_path_is_a_mutation_not_a_byproduct(monkeypatch: Any, tmp_path: Path) -> None:
    # A file laundered under a same-named directory buried at depth must NOT be excused.
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_target_code_chain(tmp_path, profile="pytest_full")
    git_calls = 0

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal git_calls
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            git_calls += 1
            return _completed(args, stdout="" if git_calls == 1 else "?? notes/.pytest_cache/backdoor.py\n")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
        return _completed(args, stdout="pytest-full ok\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="pytest_full"
    )

    assert receipt["observed_byproducts"] == []
    assert receipt["workspace_mutation_detected"] is True
    assert receipt["valid"] is False
    assert any("notes/.pytest_cache/backdoor.py" in error for error in receipt["errors"])


def test_head_change_during_run_is_a_mutation(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_target_code_chain(tmp_path, profile="pytest_full")
    rev_parse_calls = 0

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal rev_parse_calls
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        if args[:2] == ["git", "rev-parse"]:
            rev_parse_calls += 1
            sha = ("a" * 40) if rev_parse_calls == 1 else ("b" * 40)  # HEAD moved between pre and post
            return _completed(args, stdout=f"{sha}\nmain\n")
        return _completed(args, stdout="pytest-full ok\n")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="pytest_full"
    )

    assert receipt["workspace_mutation_detected"] is True
    assert any("HEAD changed" in error for error in receipt["errors"])
    assert receipt["valid"] is False


def test_postflight_marks_mutation_mismatch_invalid(monkeypatch: Any, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_bound_artifacts(tmp_path)
    git_calls = 0

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal git_calls
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            git_calls += 1
            return _completed(args, stdout="" if git_calls == 1 else "?? new-file\n")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
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


def test_pytest_full_runs_for_generic_target(monkeypatch: Any, tmp_path: Path) -> None:
    # B4.2 (plan 1.3): the bounded runner verifies an arbitrary target repo, not just builder-II.
    (tmp_path / ".git").mkdir()
    plan_path, approval_path, receipt_path = _write_target_code_chain(
        tmp_path, profile="pytest_full", target_profile="generic", verification_profile="generic_basic"
    )
    monkeypatch.setattr(
        "builder_ii.verification_execution_runner.subprocess.run", _profile_stdout_run("pytest-full")
    )

    receipt = run_approved_verification(
        plan_path=plan_path, approval_path=approval_path, output=receipt_path, requested_profile="pytest_full"
    )

    assert receipt["valid"] is True
    assert receipt["receipt_status"] == "EXECUTED"
    assert receipt["target_profile"] == "generic"
    assert receipt["verification_profile"] == "generic_basic"
    # the recorded command_profile_ref tracks the generic namespace, not builder_full
    assert receipt["process_results"][0]["command_profile_ref"] == "verification_profiles.generic_basic.pytest_full"
    assert validate_verification_execution_receipt_artifact(receipt) == []


def test_builder_self_profile_refused_for_non_builder_verification_profile() -> None:
    # A builder-II self profile (runs builder-II's own matrix/docs checks) must be refused under a
    # non-builder verification profile; a target-code profile (pytest_full) is allowed anywhere.
    from builder_ii.verification_execution_runner import SUPPORTED_COMMAND_PROFILES, _validate_fixed_profile

    errors = _validate_fixed_profile(SUPPORTED_COMMAND_PROFILES["platform_status"], "generic_basic")
    assert any("requires verification_profile=builder_full" in error for error in errors)

    assert _validate_fixed_profile(SUPPORTED_COMMAND_PROFILES["platform_status"], "builder_full") == []
    assert _validate_fixed_profile(SUPPORTED_COMMAND_PROFILES["pytest_full"], "generic_basic") == []


def test_generic_plan_injecting_builder_self_profile_blocks_end_to_end(monkeypatch: Any, tmp_path: Path) -> None:
    # Defense-in-depth (review LOW): even a hand-built generic plan that declares a builder-II-self
    # profile under a generic namespace (which the plan validator accepts structurally) is blocked
    # by the runner before any subprocess -- so builder-II's own checks can never run against a
    # foreign target repo.
    from builder_ii.verification_execution_plan import (
        finalize_verification_execution_plan,
        write_verification_execution_plan,
    )

    (tmp_path / ".git").mkdir()
    root = _artifact_root(tmp_path)
    injected = {
        "profile": "platform_status",
        "command_profile_ref": "verification_profiles.generic_basic.platform_status",
        "description": "Injected builder-self profile under a generic namespace.",
        "requires_approval": True,
        "execution_enabled": False,
        "timeout_seconds": 120,
    }
    plan = finalize_verification_execution_plan(
        target_profile="generic",
        verification_profile="generic_basic",
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        allowed_command_profiles=[dict(injected)],
        planned_steps=[{**injected, "step_id": "platform_status"}],
        generated_at="2026-06-30T00:00:00+00:00",
    )
    assert plan["valid"] is True, plan["errors"]  # structurally valid; the runner is the semantic gate
    plan_path = root / "plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Jane Operator",
        approval_reason="Approve injected profile proof.",
        approved_command_profiles=["platform_status"],
        approved_step_ids=["platform_status"],
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = root / "approval.json"
    write_verification_execution_approval(approval, approval_path)

    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(list(args))
        return _completed(args)

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=root / "receipt.json",
        requested_profile="platform_status",
    )

    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert receipt["valid"] is False
    assert any("runs builder-II's own checks" in error for error in receipt["errors"])
    assert calls == [], "no subprocess may run for a refused builder-self profile"


# ---------------------------------------------------------------------------
# The subject must not supply the auditor that clears it.
#
# `run_approved_verification` spawns children with `cwd=target_repo`. Python puts the cwd at
# `sys.path[0]`, and `_minimal_env` used to add `PYTHONPATH=target_repo` on top. So a target
# repository could ship its own `builder_ii/` package and its own `sitecustomize.py`, and the two
# profiles documented as running builder-II's own checks -- `platform_status` and `docs_audit` --
# would execute the target's code instead. `sitecustomize` runs at interpreter startup, before
# `main()` is ever reached.
#
# These pins spawn the real child, both ways. The negative control reproduces the old behavior
# exactly, so the fix cannot decay into a comment.
# ---------------------------------------------------------------------------

_RUNNER_MODULE = "builder_ii.verification_runner_entrypoints"
# The real module, invoked with no subcommand, prints this and exits 2. A stand-in that lacks a
# `__main__` block exits 0 in silence. That difference identifies whose code ran, and needs no
# side effect to observe.
_REAL_MODULE_DIAGNOSTIC = "unsupported verification runner entrypoint"


def _target_repo_that_shadows_builder_ii(tmp_path: Path) -> Path:
    """A target repo carrying its own `builder_ii` package and a `sitecustomize.py`."""
    target = tmp_path / "target-repo"
    (target / "builder_ii").mkdir(parents=True)
    (target / "builder_ii" / "__init__.py").write_text("", encoding="utf-8")
    # No `__main__` block: if this module is the one `-m` runs, the child exits 0 silently.
    (target / "builder_ii" / "verification_runner_entrypoints.py").write_text(
        "MARKER = 'this module belongs to the target repository'\n", encoding="utf-8"
    )
    (target / "sitecustomize.py").write_text(
        "print('target-sitecustomize-executed')\n", encoding="utf-8"
    )
    return target


def _spawn_runner_module(target: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", _RUNNER_MODULE],
        cwd=target,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        shell=False,
    )


def test_a_target_repo_cannot_supply_the_module_that_audits_it(tmp_path: Path) -> None:
    target = _target_repo_that_shadows_builder_ii(tmp_path)

    completed = _spawn_runner_module(target, _minimal_env(target, allow_target_repo_imports=False))

    assert completed.returncode == 2, (
        "the child did not run builder-II's own entrypoint module; a target repo shadowing "
        f"`builder_ii` was able to answer for it. stdout={completed.stdout!r}"
    )
    assert _REAL_MODULE_DIAGNOSTIC in completed.stderr
    assert "target-sitecustomize-executed" not in completed.stdout, (
        "the target repo's sitecustomize.py executed at interpreter startup"
    )


def test_the_shadowing_the_pin_forbids_is_real_and_not_hypothetical(tmp_path: Path) -> None:
    """Negative control: reproduce the pre-fix environment and watch the target's code win.

    Without this, the pin above could pass for the wrong reason -- e.g. if `-m` never resolved
    against the cwd on some platform -- and would silently stop protecting anything.
    """
    target = _target_repo_that_shadows_builder_ii(tmp_path)
    unsafe = _minimal_env(target, allow_target_repo_imports=False)
    unsafe.pop("PYTHONSAFEPATH")  # restore `sys.path[0]` == cwd == the target repo
    unsafe["PYTHONPATH"] = str(target)  # and the old unconditional target-first import root

    completed = _spawn_runner_module(target, unsafe)

    assert completed.returncode == 0
    assert _REAL_MODULE_DIAGNOSTIC not in completed.stderr
    assert "target-sitecustomize-executed" in completed.stdout


def test_only_the_profiles_that_may_execute_target_code_get_it_on_the_import_path() -> None:
    """One list decides two things, so neither can drift from the other.

    `TARGET_CODE_EXECUTING_PROFILES` is what makes the approval demand an execution-risk
    acknowledgement (D7). It is now also what puts the target repository on the child's import
    path. A profile the operator must knowingly accept target-code risk for is exactly a profile
    permitted to import target code -- and no other.
    """
    target = Path("/tmp/target-repo")
    builder_root = str(BUILDER_II_IMPORT_ROOT)

    for name in SUPPORTED_COMMAND_PROFILES:
        may_import = name in TARGET_CODE_EXECUTING_PROFILES
        env = _minimal_env(target, allow_target_repo_imports=may_import)
        roots = env["PYTHONPATH"].split(os.pathsep)

        assert env["PYTHONSAFEPATH"] == "1", f"{name}: cwd must never reach sys.path"
        assert roots[0] == builder_root, f"{name}: builder-II must resolve `builder_ii` first"
        assert (str(target) in roots) is may_import, (
            f"{name}: target on import path={str(target) in roots}, may execute target code={may_import}"
        )

    assert {"platform_status", "docs_audit"}.isdisjoint(TARGET_CODE_EXECUTING_PROFILES), (
        "the two profiles this lane is promoted for must never be allowed to import target code"
    )


def test_a_target_code_profile_still_cannot_replace_the_runners_dispatch_module(tmp_path: Path) -> None:
    """pytest_full runs the target's suite by design -- but not the module that decides to run it."""
    target = _target_repo_that_shadows_builder_ii(tmp_path)

    completed = _spawn_runner_module(target, _minimal_env(target, allow_target_repo_imports=True))

    assert completed.returncode == 2
    assert _REAL_MODULE_DIAGNOSTIC in completed.stderr
