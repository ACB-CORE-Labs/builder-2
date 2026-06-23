from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Sequence

import httpx

from builder_ii.config import Settings


@dataclass(frozen=True)
class BackendSpec:
    name: str
    start_argv: tuple[str, ...]
    health_path: str = "/models"


def _bin(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"Required binary not on PATH: {name}")
    return found


def build_backend_spec(settings: Settings) -> BackendSpec:
    host_flag = ("--host", settings.host)
    port_flag = ("--port", str(settings.port))

    if settings.backend == "rapid-mlx":
        return BackendSpec(
            name="rapid-mlx",
            start_argv=(
                _bin("rapid-mlx"),
                "serve",
                settings.active_model,
                *host_flag,
                *port_flag,
            ),
        )

    if settings.backend == "mlx-lm":
        return BackendSpec(
            name="mlx-lm",
            start_argv=(
                _bin("mlx_lm.server"),
                "--model",
                settings.active_mlx_model,
                *host_flag,
                *port_flag,
                "--temp",
                str(settings.temperature),
            ),
        )

    # Ollama MLX engine — OpenAI-compatible via /v1 when OLLAMA_HOST points here.
    return BackendSpec(
        name="ollama",
        start_argv=(
            _bin("ollama"),
            "serve",
        ),
        health_path="/api/tags",
    )


def health_url(settings: Settings, path: str) -> str:
    base = settings.base_url.rstrip("/v1").rstrip("/")
    if settings.backend == "ollama":
        return f"http://{settings.host}:{11434}{path}"
    return f"{base}{path}"


def check_health(settings: Settings, timeout: float = 3.0) -> tuple[bool, str]:
    spec = build_backend_spec(settings)
    url = health_url(settings, spec.health_path)
    try:
        response = httpx.get(url, timeout=timeout)
        if response.status_code == 200:
            return True, f"OK {url}"
        return False, f"HTTP {response.status_code} from {url}"
    except httpx.HTTPError as exc:
        return False, f"{url} unreachable: {exc}"


def start_backend_process(settings: Settings) -> subprocess.Popen[str]:
    spec = build_backend_spec(settings)
    env = None
    if settings.backend == "ollama":
        import os

        env = os.environ.copy()
        env["OLLAMA_HOST"] = f"http://{settings.host}:{settings.port}"
    return subprocess.Popen(
        list(spec.start_argv),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )


def backend_switch_hint(settings: Settings) -> str:
    return (
        f"Set CORE_AGENT_BACKEND={settings.backend!r} and "
        f"CORE_AGENT_MODEL_TIER={settings.model_tier!r} in .env"
    )


def list_start_command(settings: Settings) -> Sequence[str]:
    return list(build_backend_spec(settings).start_argv)