from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from builder_ii.config import Settings

# Expected complete sizes (GB) for cache heuristics.
_EXPECTED_GB: dict[str, float] = {
    "gemma-4-e4b": 4.8,
    "gemma-4-12b": 6.5,
    "qwen3.5-4b": 2.9,
}


@dataclass(frozen=True)
class ModelCacheStatus:
    alias: str
    hf_repo: str
    cache_dir: Path | None
    size_gb: float
    has_incomplete: bool
    weights_on_disk: bool
    likely_complete: bool
    resume_hint: str


def _hf_cache_dir(hf_repo: str) -> Path:
    slug = f"models--{hf_repo.replace('/', '--')}"
    return Path.home() / ".cache" / "huggingface" / "hub" / slug


def _expected_gb(hf_repo: str) -> float:
    lower = hf_repo.lower()
    for key, gb in _EXPECTED_GB.items():
        if key.replace("-", "") in lower.replace("-", "").replace("_", ""):
            return gb
        if key in lower:
            return gb
    return 2.0 if "e4b" in lower or "4b" in lower else 6.0


def inspect_model_cache(hf_repo: str, alias: str) -> ModelCacheStatus:
    cache = _hf_cache_dir(hf_repo)
    incomplete = list(cache.rglob("*.incomplete")) if cache.exists() else []
    weights_files = list(cache.rglob("*.safetensors")) if cache.exists() else []
    complete_weights = [
        f
        for f in weights_files
        if f.is_file()
        and ".incomplete" not in str(f)
        and f.stat().st_size > 500_000_000
    ]
    # E4B: single file. 12B: two shards both required.
    if "12b" in hf_repo.lower():
        names = {f.name for f in complete_weights}
        weights_complete = {"model-00001-of-00002.safetensors", "model-00002-of-00002.safetensors"} <= names
    else:
        weights_complete = any(f.name == "model.safetensors" for f in complete_weights)
    size = 0
    if cache.exists():
        proc = subprocess.run(["du", "-sk", str(cache)], capture_output=True, text=True)
        if proc.returncode == 0:
            size = int(proc.stdout.split()[0]) * 1024
    size_gb = round(size / (1024**3), 2)
    expected = _expected_gb(hf_repo)

    if weights_complete and not incomplete:
        likely = True
        hint = "ready — run: builder start --mode quick"
    elif incomplete:
        likely = False
        hint = f"resume — run: builder pull --tier fast  (or: ./scripts/pull-phased.sh weights)"
    elif cache.exists() and not weights_complete:
        has_meta = any(cache.rglob("config.json"))
        likely = False
        hint = (
            "metadata done — run: ./scripts/pull-phased.sh weights"
            if has_meta
            else "start — run: ./scripts/pull-phased.sh small"
        )
    else:
        likely = False
        hint = "start — run: ./scripts/pull-phased.sh small"

    return ModelCacheStatus(
        alias=alias,
        hf_repo=hf_repo,
        cache_dir=cache if cache.exists() else None,
        size_gb=size_gb,
        has_incomplete=bool(incomplete),
        weights_on_disk=weights_complete,
        likely_complete=likely,
        resume_hint=hint,
    )


def model_status_report(settings: Settings) -> list[ModelCacheStatus]:
    return [
        inspect_model_cache(settings.mlx_model_fast, settings.model_fast),
        inspect_model_cache(settings.mlx_model_primary, settings.model_primary),
    ]