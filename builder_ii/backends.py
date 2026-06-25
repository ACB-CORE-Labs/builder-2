from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Sequence

import httpx

from builder_ii.backend_state import check_backend_marker, read_backend_marker, write_backend_marker
from builder_ii.config import Settings


@dataclass(frozen=True)
class BackendSpec:
    name: str
    start_argv: tuple[str, ...]
    health_path: str = "/models"


@dataclass(frozen=True)
class ServedModelStatus:
    ok: bool
    message: str
    model_ids: tuple[str, ...]


def _bin(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"Required binary not on PATH: {name}")
    return found


def health_path_for_backend(settings: Settings) -> str:
    if settings.backend == "mlx-lm":
        # mlx_lm.server exposes OpenAI-compatible endpoints under /v1.
        # Polling /models returns 404 even when the server is healthy.
        return "/v1/models"
    if settings.backend == "ollama":
        return "/api/tags"
    return "/models"


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
            health_path=health_path_for_backend(settings),
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
            health_path=health_path_for_backend(settings),
        )

    # Ollama MLX engine — OpenAI-compatible via /v1 when OLLAMA_HOST points here.
    return BackendSpec(
        name="ollama",
        start_argv=(
            _bin("ollama"),
            "serve",
        ),
        health_path=health_path_for_backend(settings),
    )


def _without_v1_suffix(base_url: str) -> str:
    base = base_url.rstrip("/")
    if base.endswith("/v1"):
        return base[: -len("/v1")]
    return base


def health_url(settings: Settings, path: str) -> str:
    if settings.backend == "ollama":
        return f"http://{settings.host}:{11434}{path}"

    root = _without_v1_suffix(settings.base_url)
    return f"{root}{path}"


def check_health(settings: Settings, timeout: float = 3.0) -> tuple[bool, str]:
    url = health_url(settings, health_path_for_backend(settings))
    try:
        response = httpx.get(url, timeout=timeout)
        if response.status_code == 200:
            return True, f"OK {url}"
        return False, f"HTTP {response.status_code} from {url}"
    except httpx.HTTPError as exc:
        return False, f"{url} unreachable: {exc}"


def _extract_model_ids(payload: Any) -> tuple[str, ...]:
    if not isinstance(payload, dict):
        return ()

    found: list[str] = []

    # OpenAI-compatible /v1/models shape: {"data": [{"id": "..."}]}
    data = payload.get("data")
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                found.append(item["id"])
            elif isinstance(item, str):
                found.append(item)

    # Ollama /api/tags shape: {"models": [{"name": "..."}]}
    models = payload.get("models")
    if isinstance(models, list):
        for item in models:
            if isinstance(item, dict):
                value = item.get("name") or item.get("model") or item.get("id")
                if isinstance(value, str):
                    found.append(value)
            elif isinstance(item, str):
                found.append(item)

    # Legacy/simple shapes sometimes expose a single model directly.
    for key in ("id", "model", "name"):
        value = payload.get(key)
        if isinstance(value, str):
            found.append(value)

    return tuple(dict.fromkeys(found))


def _model_id_matches(expected: str, served: str) -> bool:
    return served == expected or served == expected.split("/")[-1]


def served_models(settings: Settings, timeout: float = 3.0) -> ServedModelStatus:
    url = health_url(settings, health_path_for_backend(settings))
    try:
        response = httpx.get(url, timeout=timeout)
    except httpx.HTTPError as exc:
        return ServedModelStatus(False, f"{url} unreachable: {exc}", ())

    if response.status_code != 200:
        return ServedModelStatus(False, f"HTTP {response.status_code} from {url}", ())

    try:
        payload = response.json()
    except ValueError:
        return ServedModelStatus(False, f"{url} did not return JSON model metadata", ())

    ids = _extract_model_ids(payload)
    if not ids:
        return ServedModelStatus(False, f"{url} returned no model ids", ())

    return ServedModelStatus(True, f"served models: {', '.join(ids)}", ids)


def check_serves_active_model(settings: Settings, timeout: float = 3.0) -> tuple[bool, str]:
    if settings.backend != "mlx-lm":
        return True, f"served-model identity check skipped for backend={settings.backend}"

    marker_check = check_backend_marker(settings)
    if not marker_check.ok:
        return False, marker_check.message

    status = served_models(settings, timeout=timeout)
    if not status.ok:
        return False, status.message

    expected = settings.active_model_id
    if any(_model_id_matches(expected, served) for served in status.model_ids):
        if read_backend_marker(settings) is None:
            write_backend_marker(settings)
        return True, f"serving selected model {expected}"

    served = ", ".join(status.model_ids)
    return (
        False,
        f"backend model list shows {served}, but selected model is {expected}; "
        "reset the local backend before switching models",
    )


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
