"""Verification isolation tests (Ladder 9).

Covers:
- Receipt cross-field validation (isolation_backend / isolation_status / isolation_policy_digest).
- Digest-drift detection on receipt mutation.
- Backend parity: validator-accepted set == constructible set.
- none-path behavioral identity: same argv, same env.
- End-to-end runner: missing/invalid policy digest ⟹ BLOCKED, subprocess never called for profile.
- Explicit {"backend": "none"} policy ⟹ receipt valid, isolation_policy_digest null.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from builder_ii.lifecycle.candidate.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.lifecycle.candidate.verification_execution_receipt import (
    finalize_verification_execution_receipt,
    validate_verification_execution_receipt_artifact,
)
from builder_ii.lifecycle.candidate.verification_execution_runner import (
    SUPPORTED_COMMAND_PROFILES,
    _minimal_env,
    _process_result_from_completed,
    run_approved_verification,
)
from builder_ii.lifecycle.candidate.verification_isolation_backend import DockerBackend, NoneBackend, get_backend
from builder_ii.lifecycle.candidate.verification_isolation_policy import (
    finalize_verification_isolation_policy,
    validate_verification_isolation_policy_artifact,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _get_base_receipt_kwargs() -> dict[str, Any]:
    return {
        "process_results": [{"step_id": "test", "status": "pass", "profile": "p"}],
        "isolation_backend": "none",
        "isolation_status": "not_applied",
        "isolation_policy_digest": None,
        "plan": {
            "target_profile": "p",
            "verification_profile": "v",
            "target_repo": ".",
            "artifact_root": ".",
            "verification_execution_plan_digest": "a" * 64,
            "kind": "builder_ii.verification_execution_plan",
            "schema_version": 3,
        },
        "plan_path": "plan.json",
        "approval": {
            "approved_command_profiles": [],
            "verification_execution_approval_digest": "b" * 64,
            "kind": "builder_ii.verification_execution_approval",
            "schema_version": 3,
        },
        "approval_path": "approval.json",
    }


def _completed(
    args: list[str], returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=args, returncode=returncode, stdout=stdout, stderr=stderr)


_FAKE_HEAD_SHA = "a" * 40
_FAKE_BRANCH = "main"


def _rev_parse_reply(
    args: list[str], head_sha: str = _FAKE_HEAD_SHA, branch: str = _FAKE_BRANCH
) -> subprocess.CompletedProcess[str] | None:
    if args[:2] == ["git", "rev-parse"]:
        return _completed(args, stdout=f"{head_sha}\n{branch}\n")
    return None


def _artifact_root(tmp_path: Path) -> Path:
    root = tmp_path / ".builder" / "verification"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _write_bound_artifacts(
    tmp_path: Path,
    *,
    isolation_policy: dict[str, Any] | None = None,
) -> tuple[Path, Path, Path]:
    """Create a plan → approval → receipt path triple, optionally with an isolation policy."""
    root = _artifact_root(tmp_path)
    plan = finalize_verification_execution_plan(
        target_head_sha="0000000000000000000000000000000000000000",
        tree_clean=True,
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
        isolation_policy=isolation_policy,
    )
    plan_path = root / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Jane Operator",
        approval_reason="Approve bounded platform_status verification runner proof.",
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = root / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)
    receipt_path = root / "verification-execution-receipt.json"
    return plan_path, approval_path, receipt_path


# ── Receipt cross-field validation ───────────────────────────────────────────


def test_isolation_receipt_cross_field_validation() -> None:
    """All four invalid cross-field combinations are caught by the receipt validator."""
    kw = _get_base_receipt_kwargs()

    # Valid: none / not_applied / null
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert not any("isolation" in e for e in errors), errors

    # Valid: docker / applied / hex digest
    kw["isolation_backend"] = "docker"
    kw["isolation_status"] = "applied"
    kw["isolation_policy_digest"] = "c" * 64
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert not any("isolation" in e for e in errors), errors

    # Invalid: applied + none backend
    kw["isolation_backend"] = "none"
    kw["isolation_status"] = "applied"
    kw["isolation_policy_digest"] = "c" * 64
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any("isolation_backend cannot be 'none' when isolation_status is 'applied'" in e for e in errors)

    # Invalid: not_applied + docker backend
    kw["isolation_backend"] = "docker"
    kw["isolation_status"] = "not_applied"
    kw["isolation_policy_digest"] = None
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any("isolation_backend must be 'none' when isolation_status is 'not_applied'" in e for e in errors)

    # Invalid: applied + null digest
    kw["isolation_backend"] = "docker"
    kw["isolation_status"] = "applied"
    kw["isolation_policy_digest"] = None
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any(
        "isolation_policy_digest must be a SHA-256 hex string when isolation_status is 'applied'" in e for e in errors
    )


def test_receipt_digest_drift() -> None:
    """Mutating an isolation field after finalization is caught as digest drift."""
    kw = _get_base_receipt_kwargs()
    receipt = finalize_verification_execution_receipt(**kw)

    receipt["isolation_backend"] = "docker"
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any("drift detected" in e for e in errors)


# ── Backend parity ───────────────────────────────────────────────────────────


def test_isolation_backend_parity(monkeypatch: Any) -> None:
    """Validator-accepted backend names == constructible backend set."""

    def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='["sha256:test"]')

    monkeypatch.setattr(subprocess, "run", mock_run)

    valid_backends = {"none", "docker"}
    for backend in valid_backends:
        assert get_backend(".", {"backend": backend, "image_ref": "python:3.12-slim"}) is not None

    policy = {
        "kind": "builder_ii.verification_isolation_policy",
        "schema_version": 1,
        "backend": "podman",
    }
    errors = validate_verification_isolation_policy_artifact(policy)
    assert any("backend must be 'none' or 'docker'" in e for e in errors)


# ── none-path behavioral identity ────────────────────────────────────────────


def test_none_path_behavioral_identity() -> None:
    """NoneBackend.wrap_command returns identical argv and env — no transformation."""
    backend = NoneBackend(".", None)
    argv = ["pytest"]
    env = _minimal_env(".", allow_target_repo_imports=False)
    new_argv, new_env = backend.wrap_command(argv, env)
    assert new_argv == argv
    assert new_env == env


# ── End-to-end: missing policy digest blocks before subprocess ───────────────


class _FakeDockerBackend:
    """Stands in for DockerBackend without requiring docker daemon access."""

    name = "docker"

    def __init__(self, target_repo: str, isolation_policy: dict[str, Any] | None) -> None:
        self.target_repo = target_repo
        self.isolation_policy = isolation_policy

    def wrap_command(self, argv: list[str], env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        return ["docker", "run", "--rm"] + argv, {"PATH": ""}


def test_runner_fails_on_missing_policy_digest(monkeypatch: Any, tmp_path: Path) -> None:
    """A docker-isolated run whose policy digest is missing is BLOCKED; subprocess.run is never
    called for the profile argv.

    This is the end-to-end proof of must-fix #1: the runner's fail-closed guard at the
    isolation setup stage (before wrap_command) blocks execution when the plan carries a
    docker isolation policy without a valid SHA-256 hex digest.
    """
    (tmp_path / ".git").mkdir()

    # Build a docker policy with NO digest — strip it after finalize.
    policy = finalize_verification_isolation_policy(backend="docker", image_ref="python:3.12-slim")
    policy.pop("verification_isolation_policy_digest", None)

    plan_path, approval_path, receipt_path = _write_bound_artifacts(
        tmp_path,
        isolation_policy=policy,
    )

    profile_argv_called = False

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        nonlocal profile_argv_called
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
        # If we reach here, the profile argv was called — that must not happen.
        profile_argv_called = True
        return _completed(args, stdout="")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    # Replace get_backend so DockerBackend.__init__ doesn't need a real docker daemon.
    def fake_get_backend(target_repo: str, isolation_policy: dict[str, Any] | None) -> Any:
        if isolation_policy and isolation_policy.get("backend") == "docker":
            return _FakeDockerBackend(target_repo, isolation_policy)
        return NoneBackend(target_repo, isolation_policy)

    monkeypatch.setattr("builder_ii.verification_execution_runner.get_backend", fake_get_backend)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("isolation policy digest is missing or invalid" in e for e in receipt["errors"])
    assert not profile_argv_called, "subprocess.run was called for the profile — must be blocked before spawn"


def test_runner_fails_on_short_policy_digest(monkeypatch: Any, tmp_path: Path) -> None:
    """A docker-isolated run with a too-short digest is also BLOCKED before spawn."""
    (tmp_path / ".git").mkdir()

    policy = finalize_verification_isolation_policy(backend="docker", image_ref="python:3.12-slim")
    policy["verification_isolation_policy_digest"] = "abc123"  # too short

    plan_path, approval_path, receipt_path = _write_bound_artifacts(
        tmp_path,
        isolation_policy=policy,
    )

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
        raise AssertionError("profile subprocess.run must not be called")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    def fake_get_backend(target_repo: str, isolation_policy: dict[str, Any] | None) -> Any:
        if isolation_policy and isolation_policy.get("backend") == "docker":
            return _FakeDockerBackend(target_repo, isolation_policy)
        return NoneBackend(target_repo, isolation_policy)

    monkeypatch.setattr("builder_ii.verification_execution_runner.get_backend", fake_get_backend)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("isolation policy digest is missing or invalid" in e for e in receipt["errors"])


def test_runner_fails_on_non_hex_policy_digest(monkeypatch: Any, tmp_path: Path) -> None:
    """A docker-isolated run with a non-hex digest is BLOCKED before spawn."""
    (tmp_path / ".git").mkdir()

    policy = finalize_verification_isolation_policy(backend="docker", image_ref="python:3.12-slim")
    policy["verification_isolation_policy_digest"] = "g" * 64  # not hex

    plan_path, approval_path, receipt_path = _write_bound_artifacts(
        tmp_path,
        isolation_policy=policy,
    )

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
        rev_parse = _rev_parse_reply(args)
        if rev_parse is not None:
            return rev_parse
        raise AssertionError("profile subprocess.run must not be called")

    monkeypatch.setattr("builder_ii.verification_execution_runner.subprocess.run", fake_run)

    def fake_get_backend(target_repo: str, isolation_policy: dict[str, Any] | None) -> Any:
        if isolation_policy and isolation_policy.get("backend") == "docker":
            return _FakeDockerBackend(target_repo, isolation_policy)
        return NoneBackend(target_repo, isolation_policy)

    monkeypatch.setattr("builder_ii.verification_execution_runner.get_backend", fake_get_backend)

    receipt = run_approved_verification(
        plan_path=plan_path,
        approval_path=approval_path,
        output=receipt_path,
        requested_profile="platform_status",
    )

    assert receipt["valid"] is False
    assert receipt["receipt_status"] == "BLOCKED_BEFORE_EXECUTION"
    assert any("isolation policy digest is missing or invalid" in e for e in receipt["errors"])


# ── Explicit {"backend": "none"} policy ⟹ valid receipt, null digest ────────


def test_explicit_none_policy_produces_valid_receipt(monkeypatch: Any, tmp_path: Path) -> None:
    """A plan carrying an explicit {"backend": "none"} policy produces a receipt with
    isolation_status: "not_applied", isolation_policy_digest: null, and validate_*(receipt) == [].

    Pins must-fix #2: the runner gates isolation_policy_digest on the backend name, not on the
    policy's presence. An explicit {"backend": "none"} policy passes its own validator (which
    accepts "none") and carries a digest, but the receipt must record null.
    """
    (tmp_path / ".git").mkdir()

    # This is the exact scenario from the brief: a valid policy artifact with backend=none
    # that passes its own validator and carries a digest.
    policy = finalize_verification_isolation_policy(backend="none")
    policy_errors = validate_verification_isolation_policy_artifact(policy)
    assert policy_errors == [], f"policy itself must be valid: {policy_errors}"
    assert policy.get("verification_isolation_policy_digest") is not None, "policy carries a digest"

    plan_path, approval_path, receipt_path = _write_bound_artifacts(
        tmp_path,
        isolation_policy=policy,
    )

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if args[:3] == ["git", "status", "--porcelain=v1"]:
            return _completed(args, stdout="")
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

    assert receipt["valid"] is True, f"receipt must be valid: {receipt.get('errors')}"
    assert receipt["isolation_backend"] == "none"
    assert receipt["isolation_status"] == "not_applied"
    assert receipt["isolation_policy_digest"] is None, (
        "isolation_policy_digest must be null when backend is none, "
        "even when the policy artifact itself carries a digest"
    )
    receipt_errors = validate_verification_execution_receipt_artifact(receipt)
    assert receipt_errors == [], f"receipt validator must accept: {receipt_errors}"


# ---------------------------------------------------------------------------
# Containment is not permission to relax what runs inside it.
#
# `DockerBackend.wrap_command` used to end with `container_env["PYTHONPATH"] = "/workspace"`,
# unconditionally. The runner had already decided which import roots each profile may use and in
# what order, precisely so that the repository under verification cannot supply the `builder_ii`
# package that audits it. Overwriting the variable discarded that decision and put the target back
# in front: every *isolated* run of `platform_status` / `docs_audit` imported the target's code.
# ---------------------------------------------------------------------------


def _docker_backend(monkeypatch: Any, target_repo: str) -> Any:
    """A DockerBackend whose daemon/image preflight is satisfied. wrap_command is pure."""

    def ok(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="[]", stderr="")

    monkeypatch.setattr("builder_ii.verification_isolation_backend.subprocess.run", ok)
    policy = {"backend": "docker", "image_ref": "python:3.12-slim"}
    return DockerBackend(target_repo, policy)


def _wrap(backend: Any, *roots: str) -> tuple[list[str], str]:
    env = {"PYTHONSAFEPATH": "1", "PYTHONPATH": os.pathsep.join(roots)}
    argv, _ = backend.wrap_command(["/usr/bin/python3", "-m", "builder_ii.verification_runner_entrypoints"], env)
    container_pythonpath = ""
    for index, item in enumerate(argv):
        if item == "-e" and argv[index + 1].startswith("PYTHONPATH="):
            container_pythonpath = argv[index + 1].split("=", 1)[1]
    return argv, container_pythonpath


def test_docker_backend_preserves_the_callers_import_root_order(monkeypatch: Any, tmp_path: Path) -> None:
    target = tmp_path / "target-repo"
    builder = tmp_path / "builder-ii"
    target.mkdir()
    builder.mkdir()
    backend = _docker_backend(monkeypatch, str(target))

    argv, container_pythonpath = _wrap(backend, str(builder), str(target))

    assert container_pythonpath == "/builder-ii:/workspace", (
        "the target repo must not precede builder-II on the container's import path"
    )
    assert container_pythonpath != "/workspace", "this is the exact string the old code wrote"
    assert f"{builder}:/builder-ii:ro" in argv, "builder-II's import root is not mounted"
    assert f"{target}:/workspace" in argv
    assert "-e" in argv and "PYTHONSAFEPATH=1" in argv, "safe-path must survive containerisation"


def test_docker_backend_keeps_the_target_off_the_import_path_for_a_safe_profile(
    monkeypatch: Any, tmp_path: Path
) -> None:
    """platform_status / docs_audit get exactly one import root, and it is not the target."""
    target = tmp_path / "target-repo"
    builder = tmp_path / "builder-ii"
    target.mkdir()
    builder.mkdir()
    backend = _docker_backend(monkeypatch, str(target))

    _, container_pythonpath = _wrap(backend, str(builder))

    assert container_pythonpath == "/builder-ii"
    assert "/workspace" not in container_pythonpath.split(os.pathsep)


def test_docker_backend_mounts_nothing_extra_when_builder_ii_is_the_target(monkeypatch: Any, tmp_path: Path) -> None:
    """Self-verification: subject and verifier are one tree, so /workspace is the only root."""
    repo = tmp_path / "builder-ii"
    repo.mkdir()
    backend = _docker_backend(monkeypatch, str(repo))

    argv, container_pythonpath = _wrap(backend, str(repo))

    assert container_pythonpath == "/workspace"
    assert "/builder-ii:ro" not in " ".join(argv)


def test_docker_backend_drops_no_import_root_silently(monkeypatch: Any, tmp_path: Path) -> None:
    """Every root the caller passed reaches the container. Silent truncation is its own lie."""
    target = tmp_path / "target-repo"
    first = tmp_path / "root-a"
    second = tmp_path / "root-b"
    for path in (target, first, second):
        path.mkdir()
    backend = _docker_backend(monkeypatch, str(target))

    _, container_pythonpath = _wrap(backend, str(first), str(second), str(target))

    assert container_pythonpath.split(os.pathsep) == ["/builder-ii", "/builder-ii-1", "/workspace"]


def test_an_applied_isolation_receipt_records_the_approved_argv_not_the_executed_one() -> None:
    """A recorded limitation, pinned so nobody later reads `argv` as "what ran".

    `_process_result_from_completed` sets `argv = list(profile.argv)` on purpose: the receipt stays
    self-describing and bound to the approved fixed profile rather than to a host-specific
    `docker run …` line. The consequence is that under an applied isolation policy the receipt
    names a command that did not execute, and `isolation_status: "applied"` is the runner's own
    assertion about itself, corroborated by nothing else in the receipt.

    `docs/plan/VERIFICATION_ISOLATION_RFC.md` is why that is tolerable rather than alarming:
    "local isolation is containment, not attestation." A receipt was never going to attest it.
    `docs/audits/LADDER9_ASSURANCE_CLOSURE_AUDIT.md` records it; this pin makes sure the sentence
    stays true, or fails when someone changes the behaviour without changing the record.
    """
    profile = SUPPORTED_COMMAND_PROFILES["platform_status"]
    completed = subprocess.CompletedProcess(
        args=["docker", "run", "--rm", "python:3.12-slim", "python3", "-m", "x"], returncode=0, stdout="", stderr=""
    )

    result = _process_result_from_completed(
        profile=profile,
        completed=completed,
        effective_timeout=120,
        command_profile_ref="verification_profiles.builder_full.platform_status",
    )

    assert result["argv"] == list(profile.argv)
    assert "docker" not in result["argv"], "if this ever changes, the closure audit must change with it"
