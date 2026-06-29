"""Configuration — deterministic local-agent settings for builder-II.

The platform is optimized for an Apple Silicon MacBook Pro M1 with 16GB of
unified memory. The practical constraint is not merely model weight size:
macOS, Goose, Python, terminal buffers, and the agentic KV cache all compete
for the same RAM. For that reason builder-II treats model selection as an
explicit execution policy rather than a generic provider string.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKENDS = ("rapid-mlx", "mlx-lm", "ollama")
MODEL_TIERS = ("primary", "fast")

# Public aliases accepted by BUILDER_MODEL_ALIAS / CORE_AGENT_MODEL_ALIAS and
# `builder switch-model`.
# Keep these stable; docs/scripts depend on them.
MODEL_ALIASES = (
    "phi-reasoning",
    "qwen-coder",
    "gemma-fast",
    "gemma-primary",
    "llama",
    "codegeex",
    "qwen-coder-14b",
    "qwen3-coder-heavy",
    "deepseek",
)

_ALIAS_NORMALIZATION = {
    "fast": "phi-reasoning",
    "phi": "phi-reasoning",
    "phi4": "phi-reasoning",
    "phi-4": "phi-reasoning",
    "phi4-mini": "phi-reasoning",
    "phi-mini": "phi-reasoning",
    "primary": "qwen-coder",
    "qwen": "qwen-coder",
    "qwen7": "qwen-coder",
    "qwen-7b": "qwen-coder",
    "qwen2.5-coder": "qwen-coder",
    "gemma": "gemma-primary",
    "gemma-e4b": "gemma-fast",
    "gemma-4-e4b": "gemma-fast",
    "gemma-12b": "gemma-primary",
    "gemma-4-12b": "gemma-primary",
    "llama3": "llama",
    "llama31": "llama",
    "llama-3.1": "llama",
    "cgx": "codegeex",
    "codegeex4": "codegeex",
    "codegeex4-9b": "codegeex",
    "qwen14": "qwen-coder-14b",
    "qwen-14b": "qwen-coder-14b",
    "qwen2.5-coder-14b": "qwen-coder-14b",
    "qwen3": "qwen3-coder-heavy",
    "qwen3-coder": "qwen3-coder-heavy",
    "qwen3-heavy": "qwen3-coder-heavy",
    "deepseek-coder": "deepseek",
    "deepseek-lite": "deepseek",
}

# Human-readable roster for `builder models` and documentation. The HF repos are
# defaults only; every repo can be overridden by env var for rapid experimentation.
EXTENDED_ROSTER: tuple[tuple[str, str, str, str, str], ...] = (
    (
        "phi-reasoning",
        "CORE_AGENT_MLX_MODEL_PHI",
        "fast",
        "mlx-community/Phi-4-mini-reasoning-4bit",
        "Default fast/review lane — tiny math/reasoning model with large KV-cache headroom.",
    ),
    (
        "qwen-coder",
        "CORE_AGENT_MLX_MODEL_QWEN",
        "primary",
        "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        "Default implementation lane — code-specialized and still comfortable on M1 16GB.",
    ),
    (
        "gemma-fast",
        "CORE_AGENT_MLX_MODEL_FAST",
        "fast-alt",
        "mlx-community/gemma-4-e4b-it-4bit",
        "General fast alternate; useful when Phi is too math-biased.",
    ),
    (
        "gemma-primary",
        "CORE_AGENT_MLX_MODEL_PRIMARY",
        "primary-alt",
        "mlx-community/gemma-4-12B-it-4bit",
        "Heavier general reasoning alternate; watch swap under long Goose sessions.",
    ),
    (
        "llama",
        "CORE_AGENT_MLX_MODEL_LLAMA",
        "primary-alt",
        "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        "Instruction-following alternate for complex negative constraints.",
    ),
    (
        "codegeex",
        "CORE_AGENT_MLX_MODEL_CODEGEEX",
        "candidate",
        "mlx-community/codegeex4-all-9b-4bit",
        "Candidate implementation engine; verify repo availability/performance before relying on it.",
    ),
    (
        "qwen-coder-14b",
        "CORE_AGENT_MLX_MODEL_QWEN14",
        "heavy-candidate",
        "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        "Heavy refactor candidate; likely marginal on 16GB once KV cache grows.",
    ),
    (
        "qwen3-coder-heavy",
        "CORE_AGENT_MLX_MODEL_QWEN3_CODER",
        "heavy-candidate",
        "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        "Qwen3-Coder candidate lane; explicit opt-in only, not a 16GB default.",
    ),
    (
        "deepseek",
        "CORE_AGENT_MLX_MODEL_DEEPSEEK",
        "heavy-candidate",
        "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
        "Heavy repo-sweep candidate; use only after confirming memory headroom.",
    ),
)


def normalize_model_alias(raw: str | None, *, tier_fallback: str = "primary") -> str:
    """Normalize user/env model aliases to a stable MODEL_ALIASES value."""
    candidate = (raw or "").strip().lower().replace("_", "-")
    if not candidate:
        candidate = "phi-reasoning" if tier_fallback == "fast" else "qwen-coder"
    candidate = _ALIAS_NORMALIZATION.get(candidate, candidate)
    if candidate not in MODEL_ALIASES:
        raise ValueError(
            f"BUILDER_MODEL_ALIAS must be one of {MODEL_ALIASES}, got {raw!r}"
        )
    return candidate


@dataclass(frozen=True)
class Settings:
    core_repo: Path
    backend: str
    model_tier: str
    model_alias: str
    model_primary: str
    model_fast: str
    mlx_model_primary: str
    mlx_model_fast: str
    mlx_model_phi: str
    mlx_model_qwen: str
    mlx_model_deepseek: str
    mlx_model_llama: str
    mlx_model_codegeex: str
    mlx_model_qwen14: str
    mlx_model_qwen3_coder: str
    base_url: str
    host: str
    port: int
    temperature: float
    project_root: Path

    @property
    def active_model(self) -> str:
        """Rapid-MLX/Ollama model identifier for the selected alias."""
        if self.model_alias == "gemma-primary":
            return self.model_primary
        if self.model_alias == "gemma-fast":
            return self.model_fast
        # Rapid-MLX may not have every HF alias. Prefer mlx-lm for non-Gemma aliases.
        return self.model_alias

    @property
    def active_mlx_model(self) -> str:
        """MLX-LM Hugging Face repo for the selected alias."""
        return {
            "phi-reasoning": self.mlx_model_phi,
            "qwen-coder": self.mlx_model_qwen,
            "gemma-fast": self.mlx_model_fast,
            "gemma-primary": self.mlx_model_primary,
            "llama": self.mlx_model_llama,
            "codegeex": self.mlx_model_codegeex,
            "qwen-coder-14b": self.mlx_model_qwen14,
            "qwen3-coder-heavy": self.mlx_model_qwen3_coder,
            "deepseek": self.mlx_model_deepseek,
        }[self.model_alias]

    @property
    def active_model_id(self) -> str:
        """Provider-facing model id used by Goose's OpenAI-compatible client."""
        return self.active_mlx_model if self.backend == "mlx-lm" else self.active_model


def _resolve_core_repo(raw: str, project_root: Path) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (project_root / path).resolve()
    return path


def _env(primary: str, legacy: str | tuple[str, ...], default: str) -> str:
    value = os.getenv(primary)
    if value is not None and value.strip():
        return value
    aliases = (legacy,) if isinstance(legacy, str) else legacy
    for alias in aliases:
        value = os.getenv(alias)
        if value is not None and value.strip():
            return value
    return default


def load_settings(project_root: Path | None = None) -> Settings:
    root = (project_root or Path.cwd()).resolve()
    load_dotenv(root / ".env", override=False)

    backend = _env("BUILDER_MODEL_BACKEND", "CORE_AGENT_BACKEND", "mlx-lm").strip().lower()
    if backend not in BACKENDS:
        raise ValueError(f"BUILDER_MODEL_BACKEND must be one of {BACKENDS}, got {backend!r}")

    tier = _env("BUILDER_MODEL_TIER", "CORE_AGENT_MODEL_TIER", "primary").strip().lower()
    if tier not in MODEL_TIERS:
        raise ValueError(f"BUILDER_MODEL_TIER must be one of {MODEL_TIERS}, got {tier!r}")

    alias = normalize_model_alias(_env("BUILDER_MODEL_ALIAS", "CORE_AGENT_MODEL_ALIAS", ""), tier_fallback=tier)

    return Settings(
        core_repo=_resolve_core_repo(_env("BUILDER_TARGET_REPO", "CORE_REPO_PATH", "../core"), root),
        backend=backend,
        model_tier=tier,
        model_alias=alias,
        model_primary=_env("BUILDER_MODEL_PRIMARY", "CORE_AGENT_MODEL_PRIMARY", "gemma-4-12b-4bit"),
        model_fast=_env("BUILDER_MODEL_FAST", "CORE_AGENT_MODEL_FAST", "gemma-4-e4b-4bit"),
        mlx_model_primary=_env(
            "BUILDER_MLX_MODEL_PRIMARY",
            "CORE_AGENT_MLX_MODEL_PRIMARY",
            "mlx-community/gemma-4-12B-it-4bit",
        ),
        mlx_model_fast=_env(
            "BUILDER_MLX_MODEL_FAST",
            "CORE_AGENT_MLX_MODEL_FAST",
            "mlx-community/gemma-4-e4b-it-4bit",
        ),
        mlx_model_phi=_env(
            "BUILDER_MLX_MODEL_PHI",
            "CORE_AGENT_MLX_MODEL_PHI",
            "mlx-community/Phi-4-mini-reasoning-4bit",
        ),
        mlx_model_qwen=_env(
            "BUILDER_MLX_MODEL_QWEN",
            "CORE_AGENT_MLX_MODEL_QWEN",
            "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
        ),
        mlx_model_deepseek=_env(
            "BUILDER_MLX_MODEL_DEEPSEEK",
            "CORE_AGENT_MLX_MODEL_DEEPSEEK",
            "mlx-community/DeepSeek-Coder-V2-Lite-Instruct-4bit",
        ),
        mlx_model_llama=_env(
            "BUILDER_MLX_MODEL_LLAMA",
            "CORE_AGENT_MLX_MODEL_LLAMA",
            "mlx-community/Meta-Llama-3.1-8B-Instruct-4bit",
        ),
        mlx_model_codegeex=_env(
            "BUILDER_MLX_MODEL_CODEGEEX",
            "CORE_AGENT_MLX_MODEL_CODEGEEX",
            "mlx-community/codegeex4-all-9b-4bit",
        ),
        mlx_model_qwen14=_env(
            "BUILDER_MLX_MODEL_QWEN14",
            "CORE_AGENT_MLX_MODEL_QWEN14",
            "mlx-community/Qwen2.5-Coder-14B-Instruct-4bit",
        ),
        mlx_model_qwen3_coder=_env(
            "BUILDER_MLX_MODEL_QWEN3_CODER",
            "CORE_AGENT_MLX_MODEL_QWEN3_CODER",
            "mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit",
        ),
        base_url=_env("BUILDER_MODEL_BASE_URL", "CORE_AGENT_BASE_URL", "http://127.0.0.1:8080/v1"),
        host=_env("BUILDER_MODEL_HOST", "CORE_AGENT_HOST", "127.0.0.1"),
        port=int(_env("BUILDER_MODEL_PORT", "CORE_AGENT_PORT", "8080")),
        temperature=float(_env("BUILDER_MODEL_TEMPERATURE", "CORE_AGENT_TEMPERATURE", "0.0")),
        project_root=root,
    )
