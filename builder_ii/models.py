"""Phase 2 / Phase 4 – Local Model Cache Verification and Roster.

Before a cold start, interrogates the HuggingFace .cache directory to
verify that quantized .safetensors are fully seated on disk and not
flagged as .incomplete.

Expanded local roster for M1 16GB:
  Fast tier    (< 5 GB loaded):
    - gemma-4-e4b-it-4bit          4.8 GB
    - qwen2.5-coder-7b-instruct-4bit  4.5 GB  (superior Python formatting)

  Primary tier (5-8 GB loaded):
    - gemma-4-12b-it-4bit          6.5 GB
    - deepseek-coder-v2-lite (mlx) 6.0 GB  (repo-level context sweep)
    - llama-3.1-8b-instruct (mlx)  5.0 GB  (system-prompt adherence)
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from builder_ii.config import Settings

# ---------------------------------------------------------------------------
# Expected complete sizes (GB) — used as heuristic lower bound
# ---------------------------------------------------------------------------

_EXPECTED_GB: dict[str, float] = {
    # Gemma
    "gemma-4-e4b": 4.8,
    "gemma-4-12b": 6.5,
    # Qwen2.5-Coder (fast-alt: superior Python formatting)
    "qwen2.5-coder-7b": 4.5,
    "qwen25coder7b":    4.5,
    # DeepSeek-Coder-V2-Lite (primary-alt: repo-level context sweep)
    "deepseek-coder-v2-lite": 6.0,
    "deepseekcoder":          6.0,
    # Llama 3.1 8B (primary-alt: complex system-prompt adherence)
    "llama-3.1-8b": 5.0,
    "llama31":      5.0,
    # Legacy / smaller
    "qwen3.5-4b": 2.9,
}

# Human-readable notes for CLI display
ROSTER_NOTES: dict[str, str] = {
    "gemma-4-e4b":            "default fast tier",
    "gemma-4-12b":            "default primary tier",
    "qwen2.5-coder-7b":       "fast-alt: superior Python formatting & strict instruction adherence",
    "deepseek-coder-v2-lite": "primary-alt: repo-level sweep, versor_condition-aware refactor",
    "llama-3.1-8b":           "primary-alt: resilient to complex system prompts, respects negative constraints",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelCacheStatus:
    alias: str
    hf_repo: str
    cache_dir: Path | None
    size_gb: float
    expected_gb: float
    has_incomplete: bool
    weights_on_disk: bool
    likely_complete: bool
    resume_hint: str
    note: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    return 2.0 if ("e4b" in lower or "4b" in lower) else 6.0


def _alias_note(alias: str) -> str:
    lower = alias.lower()
    for key, note in ROSTER_NOTES.items():
        if key.replace("-", "") in lower.replace("-", "").replace("_", ""):
            return note
    return ""


def _detect_weights_complete(cache: Path, hf_repo: str) -> bool:
    """Generic N-shard detection: all model-NNNNN-of-NNNNN.safetensors present."""
    lower = hf_repo.lower()
    all_safetensors = [
        f for f in cache.rglob("*.safetensors")
        if f.is_file()
        and ".incomplete" not in str(f)
        and f.stat().st_size > 200_000_000  # ignore tiny metadata shards
    ]
    names = {f.name for f in all_safetensors}

    # Single-file model
    if "model.safetensors" in names:
        return True

    # N-shard: find max shard index
    import re
    shard_pattern = re.compile(r"model-(\d+)-of-(\d+)\.safetensors")
    shards: dict[int, int] = {}  # {index: total}
    for name in names:
        m = shard_pattern.match(name)
        if m:
            idx, total = int(m.group(1)), int(m.group(2))
            shards[idx] = total
    if not shards:
        return False
    total = max(shards.values())
    return all(i in shards for i in range(1, total + 1))


# ---------------------------------------------------------------------------
# Core inspection
# ---------------------------------------------------------------------------

def inspect_model_cache(hf_repo: str, alias: str) -> ModelCacheStatus:
    """Inspect the HuggingFace cache for a model and return full status."""
    cache = _hf_cache_dir(hf_repo)
    incomplete = list(cache.rglob("*.incomplete")) if cache.exists() else []
    weights_complete = _detect_weights_complete(cache, hf_repo) if cache.exists() else False

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
        hint = "resume — run: builder pull --tier fast  (or: ./scripts/pull-phased.sh weights)"
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
        hint = "not cached — run: ./scripts/pull-phased.sh small"

    return ModelCacheStatus(
        alias=alias,
        hf_repo=hf_repo,
        cache_dir=cache if cache.exists() else None,
        size_gb=size_gb,
        expected_gb=expected,
        has_incomplete=bool(incomplete),
        weights_on_disk=weights_complete,
        likely_complete=likely,
        resume_hint=hint,
        note=_alias_note(alias),
    )


def model_status_report(settings: Settings) -> list[ModelCacheStatus]:
    """Return cache status for all models in the full local roster."""
    roster = [
        (settings.mlx_model_fast,    settings.model_fast),
        (settings.mlx_model_primary, settings.model_primary),
    ]
    # Extended roster from Settings (if available)
    for attr, alias in [
        ("mlx_model_qwen",      "qwen2.5-coder-7b"),
        ("mlx_model_deepseek",  "deepseek-coder-v2-lite"),
        ("mlx_model_llama",     "llama-3.1-8b"),
    ]:
        hf = getattr(settings, attr, None)
        if hf:
            roster.append((hf, alias))
    return [inspect_model_cache(hf, alias) for hf, alias in roster]
