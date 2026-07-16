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
    "groq-llama": 0.0,
    "groq-mixtral": 0.0,
    "grok-reasoning": 0.0,
    "grok-beta": 0.0,
    "gemini-pro": 0.0,
    "gemini-flash": 0.0,
    "gemini-ultra": 0.0,
    "gemini-3.5-flash": 0.0,
    "gemini-3.1-pro": 0.0,
    "gemini-3.1-flash": 0.0,
    "gemini-3-flash": 0.0,
    "gemma4:e4b": 9.6,
    "gemma4:e2b": 7.2,
    "qwen3.5:2b": 1.8,
    "qwen3.5:0.8b": 0.9,
    "ibm/granite4.1:3b": 2.1,
    "groq-llama-instant": 0.0,
    "groq-gpt-oss-20b": 0.0,
    "groq-llama-scout": 0.0,
    "groq-gpt-oss-120b": 0.0,
    "groq-qwen3-32b": 0.0,
    "groq-kimi-k2": 0.0,
    "grok-4.3": 0.0,
    "grok-build-0.1": 0.0,
    "grok-4.1-fast": 0.0,
    "gpt-5.5": 0.0,
    "gpt-5.5-pro": 0.0,
    "gpt-5.4": 0.0,
    "gpt-5.4-mini": 0.0,
    "gpt-5.4-nano": 0.0,
    "gpt-5.3-codex": 0.0,
    "gpt-4o": 0.0,
    "o3": 0.0,
    "claude-fable-5": 0.0,
    "claude-opus-4.8": 0.0,
    "claude-opus-4.7": 0.0,
    "claude-opus-4.6": 0.0,
    "claude-sonnet-5": 0.0,
    "claude-sonnet-4.6": 0.0,
    "claude-sonnet-4.5": 0.0,
    "claude-haiku-4.5": 0.0,
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
    "groq-llama": "cloud-egress",
    "groq-mixtral": "cloud-egress",
    "grok-reasoning": "cloud-egress",
    "grok-beta": "cloud-egress",
    "gemini-pro": "cloud-egress",
    "gemini-flash": "cloud-egress",
    "gemini-ultra": "cloud-egress",
    "gemini-3.5-flash": "cloud-egress",
    "gemini-3.1-pro": "cloud-egress",
    "gemini-3.1-flash": "cloud-egress",
    "gemini-3-flash": "cloud-egress",
    "gemma4:e4b": "alternate",
    "gemma4:e2b": "alternate",
    "qwen3.5:2b": "candidate",
    "qwen3.5:0.8b": "candidate",
    "ibm/granite4.1:3b": "candidate",
    "groq-llama-instant": "cloud-egress",
    "groq-gpt-oss-20b": "cloud-egress",
    "groq-llama-scout": "cloud-egress",
    "groq-gpt-oss-120b": "cloud-egress",
    "groq-qwen3-32b": "cloud-egress",
    "groq-kimi-k2": "cloud-egress",
    "grok-4.3": "cloud-egress",
    "grok-build-0.1": "cloud-egress",
    "grok-4.1-fast": "cloud-egress",
    "gpt-5.5": "cloud-egress",
    "gpt-5.5-pro": "cloud-egress",
    "gpt-5.4": "cloud-egress",
    "gpt-5.4-mini": "cloud-egress",
    "gpt-5.4-nano": "cloud-egress",
    "gpt-5.3-codex": "cloud-egress",
    "gpt-4o": "cloud-egress",
    "o3": "cloud-egress",
    "claude-fable-5": "cloud-egress",
    "claude-opus-4.8": "cloud-egress",
    "claude-opus-4.7": "cloud-egress",
    "claude-opus-4.6": "cloud-egress",
    "claude-sonnet-5": "cloud-egress",
    "claude-sonnet-4.6": "cloud-egress",
    "claude-sonnet-4.5": "cloud-egress",
    "claude-haiku-4.5": "cloud-egress",
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
    "groq-llama": "Groq Llama 3.3 speculative decoding",
    "groq-mixtral": "Groq Mixtral 8x7B instruct",
    "grok-reasoning": "xAI Grok 2 reasoning",
    "grok-beta": "xAI Grok Beta",
    "gemini-pro": "Google Vertex AI Gemini 1.5 Pro",
    "gemini-flash": "Google Vertex AI Gemini 1.5 Flash",
    "gemini-ultra": "Google Vertex AI Gemini 1.0 Ultra",
    "gemini-3.5-flash": "Google Vertex AI Gemini 3.5 Flash",
    "gemini-3.1-pro": "Google Vertex AI Gemini 3.1 Pro Preview",
    "gemini-3.1-flash": "Google Vertex AI Gemini 3.1 Flash",
    "gemini-3-flash": "Google Vertex AI Gemini 3 Flash Preview",
    "gemma4:e4b": "Local Ollama Gemma 4 E4B",
    "gemma4:e2b": "Local Ollama Gemma 4 E2B",
    "qwen3.5:2b": "Local Ollama Qwen 3.5 2B",
    "qwen3.5:0.8b": "Local Ollama Qwen 3.5 0.8B",
    "ibm/granite4.1:3b": "Local Ollama IBM Granite 4.1 3B",
    "groq-llama-instant": "Cloud Egress Model: groq-llama-instant",
    "groq-gpt-oss-20b": "Cloud Egress Model: groq-gpt-oss-20b",
    "groq-llama-scout": "Cloud Egress Model: groq-llama-scout",
    "groq-gpt-oss-120b": "Cloud Egress Model: groq-gpt-oss-120b",
    "groq-qwen3-32b": "Cloud Egress Model: groq-qwen3-32b",
    "groq-kimi-k2": "Cloud Egress Model: groq-kimi-k2",
    "grok-4.3": "Cloud Egress Model: grok-4.3",
    "grok-build-0.1": "Cloud Egress Model: grok-build-0.1",
    "grok-4.1-fast": "Cloud Egress Model: grok-4.1-fast",
    "gpt-5.5": "Cloud Egress Model: gpt-5.5",
    "gpt-5.5-pro": "Cloud Egress Model: gpt-5.5-pro",
    "gpt-5.4": "Cloud Egress Model: gpt-5.4",
    "gpt-5.4-mini": "Cloud Egress Model: gpt-5.4-mini",
    "gpt-5.4-nano": "Cloud Egress Model: gpt-5.4-nano",
    "gpt-5.3-codex": "Cloud Egress Model: gpt-5.3-codex",
    "gpt-4o": "Cloud Egress Model: gpt-4o",
    "o3": "Cloud Egress Model: o3",
    "claude-fable-5": "Cloud Egress Model: claude-fable-5",
    "claude-opus-4.8": "Cloud Egress Model: claude-opus-4.8",
    "claude-opus-4.7": "Cloud Egress Model: claude-opus-4.7",
    "claude-opus-4.6": "Cloud Egress Model: claude-opus-4.6",
    "claude-sonnet-5": "Cloud Egress Model: claude-sonnet-5",
    "claude-sonnet-4.6": "Cloud Egress Model: claude-sonnet-4.6",
    "claude-sonnet-4.5": "Cloud Egress Model: claude-sonnet-4.5",
    "claude-haiku-4.5": "Cloud Egress Model: claude-haiku-4.5",
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
        ("groq-llama", "groq/Llama-3.3-70b-specdec", "cloud"),
        ("groq-mixtral", "groq/Mixtral-8x7b-32768", "cloud"),
        ("grok-reasoning", "xai/Grok-2-1212", "cloud"),
        ("grok-beta", "xai/Grok-Beta", "cloud"),
        ("gemini-pro", "google/Gemini-1.5-Pro", "cloud"),
        ("gemini-flash", "google/Gemini-1.5-Flash", "cloud"),
        ("gemini-ultra", "google/Gemini-1.0-Ultra", "cloud"),
        ("gemini-3.5-flash", "google/gemini-3.5-flash", "cloud"),
        ("gemini-3.1-pro", "google/gemini-3.1-pro-preview", "cloud"),
        ("gemini-3.1-flash", "google/gemini-3.1-flash-lite", "cloud"),
        ("gemini-3-flash", "google/gemini-3-flash-preview", "cloud"),
        ("gemma4:e4b", "ollama/gemma4:e4b", "candidate"),
        ("gemma4:e2b", "ollama/gemma4:e2b", "candidate"),
        ("qwen3.5:2b", "ollama/qwen3.5:2b", "candidate"),
        ("qwen3.5:0.8b", "ollama/qwen3.5:0.8b", "candidate"),
        ("ibm/granite4.1:3b", "ollama/ibm/granite4.1:3b", "candidate"),
        ("groq-llama-instant", "groq/groq-llama-instant", "cloud"),
        ("groq-gpt-oss-20b", "groq/groq-gpt-oss-20b", "cloud"),
        ("groq-llama-scout", "groq/groq-llama-scout", "cloud"),
        ("groq-gpt-oss-120b", "groq/groq-gpt-oss-120b", "cloud"),
        ("groq-qwen3-32b", "groq/groq-qwen3-32b", "cloud"),
        ("groq-kimi-k2", "groq/groq-kimi-k2", "cloud"),
        ("grok-4.3", "grok/grok-4.3", "cloud"),
        ("grok-build-0.1", "grok/grok-build-0.1", "cloud"),
        ("grok-4.1-fast", "grok/grok-4.1-fast", "cloud"),
        ("gpt-5.5", "gpt/gpt-5.5", "cloud"),
        ("gpt-5.5-pro", "gpt/gpt-5.5-pro", "cloud"),
        ("gpt-5.4", "gpt/gpt-5.4", "cloud"),
        ("gpt-5.4-mini", "gpt/gpt-5.4-mini", "cloud"),
        ("gpt-5.4-nano", "gpt/gpt-5.4-nano", "cloud"),
        ("gpt-5.3-codex", "gpt/gpt-5.3-codex", "cloud"),
        ("gpt-4o", "gpt/gpt-4o", "cloud"),
        ("o3", "o3/o3", "cloud"),
        ("claude-fable-5", "claude/claude-fable-5", "cloud"),
        ("claude-opus-4.8", "claude/claude-opus-4.8", "cloud"),
        ("claude-opus-4.7", "claude/claude-opus-4.7", "cloud"),
        ("claude-opus-4.6", "claude/claude-opus-4.6", "cloud"),
        ("claude-sonnet-5", "claude/claude-sonnet-5", "cloud"),
        ("claude-sonnet-4.6", "claude/claude-sonnet-4.6", "cloud"),
        ("claude-sonnet-4.5", "claude/claude-sonnet-4.5", "cloud"),
        ("claude-haiku-4.5", "claude/claude-haiku-4.5", "cloud"),
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
        if f.is_file() and ".incomplete" not in str(f) and f.stat().st_size > 50_000_000
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
    if definition.tier == "cloud":
        return ModelCacheStatus(
            alias=definition.alias,
            hf_repo=definition.hf_repo,
            tier=definition.tier,
            policy=definition.policy,
            cache_dir=None,
            size_gb=0.0,
            expected_gb=0.0,
            has_incomplete=False,
            weights_on_disk=True,
            likely_complete=True,
            resume_hint="ready (cloud egress enabled)",
            note=definition.note,
        )
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
