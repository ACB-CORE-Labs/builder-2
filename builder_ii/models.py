from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from builder_ii.config import Settings


@dataclass(frozen=True)
class ModelCacheStatus:
    alias: str
    hf_repo: str
    cache_dir: Path | None
    size_gb: float
    has_incomplete: bool
    likely_complete: bool


def _hf_cache_dir(hf_repo: str) -> Path:
    slug = f"models--{hf_repo.replace('/', '--')}"
    return Path.home() / ".cache" / "huggingface" / "hub" / slug


def inspect_model_cache(hf_repo: str, alias: str) -> ModelCacheStatus:
    cache = _hf_cache_dir(hf_repo)
    incomplete = list(cache.rglob("*.incomplete")) if cache.exists() else []
    size = 0
    if cache.exists():
        proc = subprocess.run(
            ["du", "-sk", str(cache)],
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            size = int(proc.stdout.split()[0]) * 1024
    size_gb = round(size / (1024**3), 2)
    # Heuristic: 12B 4bit ~6-8GB, e4b ~2-3GB complete
    min_complete = 2.0 if "e4b" in hf_repo.lower() else 6.0
    likely = cache.exists() and not incomplete and size_gb >= min_complete
    return ModelCacheStatus(
        alias=alias,
        hf_repo=hf_repo,
        cache_dir=cache if cache.exists() else None,
        size_gb=size_gb,
        has_incomplete=bool(incomplete),
        likely_complete=likely,
    )


def model_status_report(settings: Settings) -> list[ModelCacheStatus]:
    return [
        inspect_model_cache(settings.mlx_model_fast, settings.model_fast),
        inspect_model_cache(settings.mlx_model_primary, settings.model_primary),
    ]