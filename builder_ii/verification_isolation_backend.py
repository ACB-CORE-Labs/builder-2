import os
import subprocess
import sys
from typing import Any


class IsolationBackendError(Exception):
    """Raised when an isolation backend fails to initialize or validate constraints."""
    pass


class IsolationBackend:
    def __init__(self, target_repo: str, isolation_policy: dict[str, Any] | None):
        self.target_repo = target_repo
        self.isolation_policy = isolation_policy

    def wrap_command(self, argv: list[str], env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError


class NoneBackend(IsolationBackend):
    def wrap_command(self, argv: list[str], env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        return list(argv), dict(env)


class DockerBackend(IsolationBackend):
    def __init__(self, target_repo: str, isolation_policy: dict[str, Any] | None):
        super().__init__(target_repo, isolation_policy)
        self._check_daemon()
        self._check_image()

    def _check_daemon(self) -> None:
        try:
            subprocess.run(["docker", "info"], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise IsolationBackendError("docker daemon is unreachable or not installed")

    def _check_image(self) -> None:
        if not self.isolation_policy:
            return
        image_ref = self.isolation_policy.get("image_ref")
        image_digest = self.isolation_policy.get("image_digest")
        
        if not image_ref:
            raise IsolationBackendError("image_ref is required for docker backend")

        try:
            result = subprocess.run(["docker", "inspect", "--format", "{{index .RepoDigests 0}}", image_ref], 
                                    capture_output=True, text=True, check=True)
            if image_digest and image_digest not in result.stdout:
                raise IsolationBackendError(f"image digest mismatch: expected {image_digest}")
        except subprocess.CalledProcessError:
            raise IsolationBackendError(f"image {image_ref} not found locally")
        except FileNotFoundError:
            raise IsolationBackendError("docker command not found")

    def wrap_command(self, argv: list[str], env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        image_ref = self.isolation_policy.get("image_ref") if self.isolation_policy else "python:3.12-slim"
        
        # Re-map sys.executable for container
        container_argv = list(argv)
        if container_argv and container_argv[0] == sys.executable:
            container_argv[0] = "python3"
        
        docker_cmd = ["docker", "run", "--rm"]
        
        docker_cmd.extend(["-v", f"{self.target_repo}:/workspace"])
        docker_cmd.extend(["-w", "/workspace"])
        
        container_env = dict(env)
        container_env["PYTHONPATH"] = "/workspace"
        container_env["HOME"] = "/tmp/home"
        container_env["TMPDIR"] = "/tmp"
        container_env["TEMP"] = "/tmp"
        container_env["TMP"] = "/tmp"
        
        for k, v in container_env.items():
            docker_cmd.extend(["-e", f"{k}={v}"])
            
        docker_cmd.append(image_ref)
        docker_cmd.extend(container_argv)
        
        safe_host_env = {"PATH": os.environ.get("PATH", "")}
        return docker_cmd, safe_host_env


def get_backend(target_repo: str, isolation_policy: dict[str, Any] | None) -> IsolationBackend:
    if not isolation_policy:
        return NoneBackend(target_repo, isolation_policy)
    
    backend_name = isolation_policy.get("backend", "none")
    if backend_name == "docker":
        return DockerBackend(target_repo, isolation_policy)
    
    # Fallback to none if explicitly set, or raise if unsupported
    if backend_name == "none":
        return NoneBackend(target_repo, isolation_policy)
        
    raise IsolationBackendError(f"unsupported isolation backend: {backend_name}")
