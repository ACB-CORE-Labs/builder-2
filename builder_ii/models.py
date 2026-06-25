"""Local model cache verification and governed M1 roster.

The cache inspector is intentionally filesystem-only. It does not phone home or
assume a model exists remotely. Download scripts are allowed to fail loudly if a
candidate repo name changed; the runtime should remain deterministic and honest.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

from builder_ii.config import Settings


@dataclass(frozen=True)
class ModelDefinition:
    alias: str
    hf_repo: str
    tier: str
    expected_gb: float
    policy: str
    note: str


@dataclass(frozen=True)
class ModelCacheStatus:
    alias: str
    hf_repo: str
    tier: str
    policy: str
    cache_dir: Path | None
    size_gb: float
    expected_gb: float
    has_incomplete: bool
    weights_on_disk: bool
    likely_complete: bool
    resume_hint: str
    note: str


# Expected disk/cache footprints are heuristics used for status reporting, not a
# hard proof of correctness. Hugging Face file layouts vary across conversions.
_EXPECTED_GB_BY_ALIAS: dict[str, float] = {
    "phi-reasoning": 2.16,
    "qwen-coder": 4.3,
    "gemma-fast": 5.2,
    "gemma-primary": 6.8,
    "llama": 4.6,
    "codegeex": 8.7,
    "qwen-coder-14b": 8.5,
    "qwen3-coder-heavy": 12.0,
    "deepseek": 8.9,
}

_POLICIES: dict[str, str] = {
    "phi-reasoning": "default-fast",
    "qwen-coder": "default-primary",
    "gemma-fast": "alternate",
    "gemma-primary": "alternate-watch-swap",
    "llama": "alternate",
    "codegeex": "candidate-verify-first",
    "qwen-coder-14b": "heavy-explicit-opt-in",
    "qwen3-coder-heavy": "heavy-explicit-opt-in",
    "deepseek": "heavy-explicit-opt-in",
}

_NOTES: dict[str, str] = {
    "phi-reasoning": "logic/review/refusal; maximum KV-cache headroom",
    "qwen-coder": "safe implementation default for targeted patches",
    "gemma-fast": "general fast alternate",
    "gemma-primary": "general reasoning alternate; monitor swap",
    "llama": "negative-constraint/system-prompt alternate",
    "codegeex": "candidate agentic implementation model; validate repo + behavior",
    "qwen-coder-14b": "heavy code-refactor candidate; not a default on 16GB",
    "qwen3-coder-heavy": "Qwen3 coder candidate; public lineup is heavy/MoE, not default M1",
    "deepseek": "heavy repo-sweep candidate; use only with memory discipline",
}


def model_definitions(settings: Settings) -> tuple[ModelDefinition, ...]:
    """Return the full configured roster in the order docs/scripts present it."""
    values = (
        ("phi-reasoning", settings.mlx_model_phi, "fast"),
        ("qwen-coder", settings.mlx_model_qwen, "primary"),
        ("gemma-fast", settings.mlx_model_fast, "fast-alt"),
        ("gemma-primary", settings.mlx_model_primary, "primary-alt"),
        ("llama", settings.mlx_model_llama, "primary-alt"),
        ("codegeex", settings.mlx_model_codegeex, "candidate"),
        ("qwen-coder-14b", settings.mlx_model_qwen14, "heavy-candidate"),
        ("qwen3-coder-heavy", settings.mlx_model_qwen3_coder, "heavy-candidate"),
        ("deepseek", settings.mlx_model_deepseek, "heavy-candidate"),
    )
    return tuple(
        ModelDefinition(
            alias=alias,
            hf_repo=repo,
            tier=tier,
            expected_gb=_EXPECTED_GB_BY_ALIAS[alias],
            policy=_POLICIES[alias],
            note=_NOTES[alias],
        )
        for alias, repo, tier in values
    )


def _hf_cache_dir(hf_repo: str) -> Path:
    slug = f"models--{hf_repo.replace('/', '--')}"
    return Path.home() / ".cache" / "huggingface" / "hub" / slug


def _large_safetensors(cache: Path) -> list[Path]:
    return [
        f
        for f in cache.rglob("*.safetensors")
        if f.is_file()
        and ".incomplete" not in str(f)
        and f.stat().st_size > 50_000_000
    ]


def _detect_weights_complete(cache: Path) -> bool:
    """Detect single-file or complete N-shard safetensors weights.

    Requirements:
      - no reliance on a fixed shard count;
      - all shard names agree on the same total;
      - every index 1..N is present;
      - single large model.safetensors is accepted.
    """
    all_safetensors = _large_safetensors(cache)
    names = {f.name for f in all_safetensors}

    if "model.safetensors" in names:
        return True

    shard_pattern = re.compile(r"model-(\d+)-of-(\d+)\.safetensors")
    shards: dict[int, int] = {}
    totals: set[int] = set()
    for name in names:
        match = shard_pattern.fullmatch(name)
        if not match:
            continue
        index, total = int(match.group(1)), int(match.group(2))
        shards[index] = total
        totals.add(total)

    if not shards or len(totals) != 1:
        return False

    total = next(iter(totals))
    return set(shards) == set(range(1, total + 1))


def _disk_size_gb(path: Path) -> float:
    proc = subprocess.run(["du", "-sk", str(path)], capture_output=True, text=True)
    if proc.returncode != 0 or not proc.stdout.strip():
        return 0.0
    return round((int(proc.stdout.split()[0]) * 1024) / (1024**3), 2)


def inspect_model_cache(definition: ModelDefinition) -> ModelCacheStatus:
    """Inspect the Hugging Face cache for one configured model."""
    cache = _hf_cache_dir(definition.hf_repo)
    incomplete = list(cache.rglob("*.incomplete")) if cache.exists() else []
    weights_complete = _detect_weights_complete(cache) if cache.exists() else False
    size_gb = _disk_size_gb(cache) if cache.exists() else 0.0

    if weights_complete and not incomplete:
        likely = True
        hint = f"ready — run: CORE_AGENT_MODEL_ALIAS={definition.alias} builder start"
    elif incomplete:
        likely = False
        hint = f"resume — run: ./scripts/pull-roster.sh alias {definition.alias}"
    elif cache.exists() and not weights_complete:
        has_meta = any(cache.rglob("config.json"))
        likely = False
        hint = (
            f"metadata only — run: ./scripts/pull-roster.sh alias {definition.alias}"
            if has_meta
            else f"partial cache — run: ./scripts/pull-roster.sh alias {definition.alias}"
        )
    else:
        likely = False
        hint = f"not cached — run: ./scripts/pull-roster.sh alias {definition.alias}"

    return ModelCacheStatus(
        alias=definition.alias,
        hf_repo=definition.hf_repo,
        tier=definition.tier,
        policy=definition.policy,
        cache_dir=cache if cache.exists() else None,
        size_gb=size_gb,
        expected_gb=definition.expected_gb,
        has_incomplete=bool(incomplete),
        weights_on_disk=weights_complete,
        likely_complete=likely,
        resume_hint=hint,
        note=definition.note,
    )


def model_status_report(settings: Settings) -> list[ModelCacheStatus]:
    """Return cache status for all models in the configured local roster."""
    return [inspect_model_cache(definition) for definition in model_definitions(settings)]
