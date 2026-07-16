import os
import subprocess
import sys
from pathlib import Path
from typing import Any

# Where the target repository is mounted inside the container, and where any other import root the
# caller chose (in practice builder-II's own package root) is mounted read-only beside it.
_CONTAINER_WORKSPACE = "/workspace"
_CONTAINER_BUILDER_II_ROOT = "/builder-ii"


def _import_roots(env: dict[str, str]) -> list[str]:
    return [root for root in env.get("PYTHONPATH", "").split(os.pathsep) if root]


def _same_path(left: str, right: str) -> bool:
    return Path(left).resolve() == Path(right).resolve()


class IsolationBackendError(Exception):
    """Raised when an isolation backend fails to initialize or validate constraints."""
    pass


class IsolationBackend:
    name: str = ""

    def __init__(self, target_repo: str, isolation_policy: dict[str, Any] | None):
        self.target_repo = target_repo
        self.isolation_policy = isolation_policy

    def wrap_command(self, argv: list[str], env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        raise NotImplementedError


class NoneBackend(IsolationBackend):
    name = "none"

    def wrap_command(self, argv: list[str], env: dict[str, str]) -> tuple[list[str], dict[str, str]]:
        return list(argv), dict(env)


class DockerBackend(IsolationBackend):
    name = "docker"

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
            result = subprocess.run(["docker", "inspect", "--format", "{{json .RepoDigests}}", image_ref],
                                    capture_output=True, text=True, check=True)
            if image_digest:
                import json
                try:
                    digests = json.loads(result.stdout)
                    if not any(d.endswith(f"@{image_digest}") or d == image_digest for d in (digests or [])):
                        raise IsolationBackendError(f"image digest mismatch: expected {image_digest}")
                except json.JSONDecodeError:
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

        docker_cmd.extend(["-v", f"{self.target_repo}:{_CONTAINER_WORKSPACE}"])

        container_env = dict(env)
        # This used to be `container_env["PYTHONPATH"] = "/workspace"`, unconditionally. The caller
        # had already decided which import roots this profile may use, and in which order, so that
        # the repository under verification could not supply the `builder_ii` package that audits
        # it. Overwriting the variable threw that decision away and put the target back first --
        # every isolated run of the two safe profiles imported the target's code. Containment of
        # the blast radius is not permission to relax what runs inside it.
        #
        # So translate the roots the caller chose into container paths instead of replacing them.
        # The target repo is already mounted at /workspace; every other root is mounted read-only,
        # in order, and none is silently dropped.
        container_roots: list[str] = []
        for index, host_root in enumerate(_import_roots(env)):
            if _same_path(host_root, self.target_repo):
                container_roots.append(_CONTAINER_WORKSPACE)
                continue
            mount_point = f"{_CONTAINER_BUILDER_II_ROOT}{'' if index == 0 else f'-{index}'}"
            docker_cmd.extend(["-v", f"{host_root}:{mount_point}:ro"])
            container_roots.append(mount_point)
        if not container_roots:
            # No PYTHONPATH at all: the workspace is the only thing that could be importable.
            container_roots.append(_CONTAINER_WORKSPACE)

        docker_cmd.extend(["-w", _CONTAINER_WORKSPACE])

        container_env["PYTHONPATH"] = os.pathsep.join(container_roots)
        container_env["HOME"] = "/tmp/home"  # nosec B108
        container_env["TMPDIR"] = "/tmp"  # nosec B108
        container_env["TEMP"] = "/tmp"  # nosec B108
        container_env["TMP"] = "/tmp"  # nosec B108

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
