from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from builder_ii.config import Settings


@dataclass(frozen=True)
class BackendMarker:
    backend: str
    model_alias: str
    model_id: str
    host: str
    port: int
    base_url: str


@dataclass(frozen=True)
class BackendMarkerCheck:
    ok: bool
    message: str
    marker: BackendMarker | None = None


def backend_marker_path(settings: Settings) -> Path:
    return settings.project_root / ".builder" / "backend_marker.json"


def write_backend_marker(settings: Settings) -> BackendMarker:
    marker = BackendMarker(
        backend=settings.backend,
        model_alias=settings.model_alias,
        model_id=settings.active_model_id,
        host=settings.host,
        port=settings.port,
        base_url=settings.base_url,
    )
    path = backend_marker_path(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(marker), indent=2, sort_keys=True) + "\n")
    return marker


def clear_backend_marker(settings: Settings) -> None:
    try:
        backend_marker_path(settings).unlink()
    except FileNotFoundError:
        return


def read_backend_marker(settings: Settings) -> BackendMarker | None:
    try:
        payload: Any = json.loads(backend_marker_path(settings).read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return BackendMarker(
            backend=str(payload["backend"]),
            model_alias=str(payload["model_alias"]),
            model_id=str(payload["model_id"]),
            host=str(payload["host"]),
            port=int(payload["port"]),
            base_url=str(payload["base_url"]),
        )
    except (KeyError, TypeError, ValueError):
        return None


def marker_matches_settings(marker: BackendMarker, settings: Settings) -> bool:
    return (
        marker.backend == settings.backend
        and marker.model_id == settings.active_model_id
        and marker.host == settings.host
        and marker.port == settings.port
        and marker.base_url.rstrip("/") == settings.base_url.rstrip("/")
    )


def check_backend_marker(settings: Settings) -> BackendMarkerCheck:
    marker = read_backend_marker(settings)
    if marker is None:
        return BackendMarkerCheck(True, "no recorded builder backend marker")
    if marker_matches_settings(marker, settings):
        return BackendMarkerCheck(True, f"recorded backend marker matches selected model {marker.model_id}", marker)
    return BackendMarkerCheck(
        False,
        (
            f"recorded backend marker uses {marker.model_id} ({marker.model_alias}), "
            f"but selected model is {settings.active_model_id} ({settings.model_alias}); "
            "clear or restart the local backend before switching models"
        ),
        marker,
    )
