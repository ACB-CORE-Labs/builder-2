from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKENDS = ("rapid-mlx", "mlx-lm", "ollama")
MODEL_TIERS = ("primary", "fast")


@dataclass(frozen=True)
class Settings:
    core_repo: Path
    backend: str
    model_tier: str
    model_primary: str
    model_fast: str
    mlx_model_primary: str
    mlx_model_fast: str
    base_url: str
    host: str
    port: int
    temperature: float
    project_root: Path

    @property
    def active_model(self) -> str:
        return self.model_primary if self.model_tier == "primary" else self.model_fast

    @property
    def active_mlx_model(self) -> str:
        return (
            self.mlx_model_primary
            if self.model_tier == "primary"
            else self.mlx_model_fast
        )


def _resolve_core_repo(raw: str, project_root: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def load_settings(project_root: Path | None = None) -> Settings:
    root = (project_root or Path.cwd()).resolve()
    load_dotenv(root / ".env", override=False)

    backend = os.getenv("CORE_AGENT_BACKEND", "rapid-mlx").strip().lower()
    if backend not in BACKENDS:
        raise ValueError(f"CORE_AGENT_BACKEND must be one of {BACKENDS}, got {backend!r}")

    tier = os.getenv("CORE_AGENT_MODEL_TIER", "primary").strip().lower()
    if tier not in MODEL_TIERS:
        raise ValueError(f"CORE_AGENT_MODEL_TIER must be one of {MODEL_TIERS}, got {tier!r}")

    return Settings(
        core_repo=_resolve_core_repo(os.getenv("CORE_REPO_PATH", "../core"), root),
        backend=backend,
        model_tier=tier,
        model_primary=os.getenv("CORE_AGENT_MODEL_PRIMARY", "gemma-4-12b-4bit"),
        model_fast=os.getenv("CORE_AGENT_MODEL_FAST", "gemma-4-e4b-4bit"),
        mlx_model_primary=os.getenv(
            "CORE_AGENT_MLX_MODEL_PRIMARY", "mlx-community/gemma-4-12B-it-4bit"
        ),
        mlx_model_fast=os.getenv(
            "CORE_AGENT_MLX_MODEL_FAST", "mlx-community/gemma-4-e4b-it-4bit"
        ),
        base_url=os.getenv("CORE_AGENT_BASE_URL", "http://127.0.0.1:8080/v1"),
        host=os.getenv("CORE_AGENT_HOST", "127.0.0.1"),
        port=int(os.getenv("CORE_AGENT_PORT", "8080")),
        temperature=float(os.getenv("CORE_AGENT_TEMPERATURE", "0.0")),
        project_root=root,
    )