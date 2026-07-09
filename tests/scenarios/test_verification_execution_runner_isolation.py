import pytest
import subprocess
from pathlib import Path
from typing import Any

from builder_ii.verification_isolation_backend import DockerBackend, IsolationBackendError
from builder_ii.verification_execution_plan import finalize_verification_execution_plan

def test_isolation_backend_fail_closed_daemon_down(monkeypatch: pytest.MonkeyPatch) -> None:
    def _mock_run(*args: Any, **kwargs: Any) -> Any:
        raise FileNotFoundError("docker not found")
    monkeypatch.setattr(subprocess, "run", _mock_run)

    with pytest.raises(IsolationBackendError, match="docker daemon is unreachable or not installed"):
        DockerBackend(".", {"backend": "docker", "image_ref": "python:3.12-slim"})


def test_isolation_backend_fail_closed_image_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    def _mock_run(cmd: list[str], *args: Any, **kwargs: Any) -> Any:
        if "info" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="")
        if "inspect" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="sha256:wrong")
        raise AssertionError("unexpected call")
    monkeypatch.setattr(subprocess, "run", _mock_run)

    with pytest.raises(IsolationBackendError, match="image digest mismatch"):
        DockerBackend(".", {"backend": "docker", "image_ref": "python", "image_digest": "sha256:expected"})
