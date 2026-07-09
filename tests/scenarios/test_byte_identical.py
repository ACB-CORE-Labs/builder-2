import subprocess

from builder_ii.verification_execution_receipt import (
    finalize_verification_execution_receipt,
    validate_verification_execution_receipt_artifact,
)
from builder_ii.verification_execution_runner import _minimal_env
from builder_ii.verification_isolation_backend import NoneBackend, get_backend
from builder_ii.verification_isolation_policy import validate_verification_isolation_policy_artifact


def _get_base_receipt_kwargs():
    return {
        "process_results": [{"step_id": "test", "status": "pass", "profile": "p"}],
        "isolation_backend": "none",
        "isolation_status": "not_applied",
        "isolation_policy_digest": None,
        "plan": {"target_profile": "p", "verification_profile": "v", "target_repo": ".", "artifact_root": ".", "verification_execution_plan_digest": "a"*64, "kind": "builder_ii.verification_execution_plan", "schema_version": 3},
        "plan_path": "plan.json",
        "approval": {"approved_command_profiles": [], "verification_execution_approval_digest": "b"*64, "kind": "builder_ii.verification_execution_approval", "schema_version": 2},
        "approval_path": "approval.json",
    }

def test_isolation_receipt_validation():
    # Test valid combinations
    kw = _get_base_receipt_kwargs()
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert not any("isolation" in e for e in errors), errors

    kw["isolation_backend"] = "docker"
    kw["isolation_status"] = "applied"
    kw["isolation_policy_digest"] = "c"*64
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert not any("isolation" in e for e in errors), errors

    # Inconsistent: applied+none
    kw["isolation_backend"] = "none"
    kw["isolation_status"] = "applied"
    kw["isolation_policy_digest"] = "c"*64
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any("isolation_backend cannot be 'none' when isolation_status is 'applied'" in e for e in errors)

    # Inconsistent: not_applied+docker
    kw["isolation_backend"] = "docker"
    kw["isolation_status"] = "not_applied"
    kw["isolation_policy_digest"] = None
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any("isolation_backend must be 'none' when isolation_status is 'not_applied'" in e for e in errors)

    # Inconsistent: applied+null digest
    kw["isolation_backend"] = "docker"
    kw["isolation_status"] = "applied"
    kw["isolation_policy_digest"] = None
    receipt = finalize_verification_execution_receipt(**kw)
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any("isolation_policy_digest must be a SHA-256 hex string when isolation_status is 'applied'" in e for e in errors)

def test_receipt_digest_drift():
    kw = _get_base_receipt_kwargs()
    receipt = finalize_verification_execution_receipt(**kw)

    # Mutate a field
    receipt["isolation_backend"] = "docker"
    errors = validate_verification_execution_receipt_artifact(receipt)
    assert any("drift detected" in e for e in errors)

def test_isolation_backend_parity(monkeypatch):
    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(args=args, returncode=0, stdout='["sha256:test"]')
    monkeypatch.setattr(subprocess, "run", mock_run)
    # validator accepted set == constructible set
    valid_backends = {"none", "docker"}
    for backend in valid_backends:
        assert get_backend(".", {"backend": backend, "image_ref": "python:3.12-slim"}) is not None

    policy = {
        "kind": "builder_ii.verification_isolation_policy",
        "schema_version": 1,
        "backend": "podman"
    }
    errors = validate_verification_isolation_policy_artifact(policy)
    assert any("backend must be 'none' or 'docker'" in e for e in errors)

def test_none_path_behavioral_identity(monkeypatch):
    backend = NoneBackend(".", None)
    argv = ["pytest"]
    env = _minimal_env(".")
    new_argv, new_env = backend.wrap_command(argv, env)
    assert new_argv == argv
    assert new_env == env

