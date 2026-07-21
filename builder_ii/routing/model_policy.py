from __future__ import annotations

from dataclasses import dataclass

from builder_ii.core.config import Settings
from builder_ii.core.models import ModelDefinition, model_definitions


@dataclass(frozen=True)
class ModelOperatingProfile:
    alias: str
    runtime: str
    role: str
    launch_policy: str
    recommended_for: str
    avoid_for: str


_RUNTIME_BY_ALIAS: dict[str, str] = {
    "phi-reasoning": "mlx-lm",
    "qwen-coder": "mlx-lm",
    "gemma-fast": "mlx-vlm-sidecar",
    "gemma-primary": "mlx-vlm-sidecar",
    "llama": "mlx-lm",
    "codegeex": "mlx-lm-candidate",
    "qwen-coder-14b": "mlx-lm-heavy",
    "qwen3-coder-heavy": "mlx-lm-heavy",
    "deepseek": "mlx-lm-heavy",
    "groq-llama": "groq",
    "groq-mixtral": "groq",
    "grok-reasoning": "xai",
    "grok-beta": "xai",
    "gemini-pro": "google",
    "gemini-flash": "google",
    "gemini-ultra": "google",
    "gemini-3.5-flash": "google",
    "gemini-3.1-pro": "google",
    "gemini-3.1-flash": "google",
    "gemini-3-flash": "google",
    "gemma4:e4b": "ollama",
    "gemma4:e2b": "ollama",
    "qwen3.5:2b": "ollama",
    "qwen3.5:0.8b": "ollama",
    "ibm/granite4.1:3b": "ollama",
    "groq-llama-instant": "groq",
    "groq-gpt-oss-20b": "groq",
    "groq-llama-scout": "groq",
    "groq-gpt-oss-120b": "groq",
    "groq-qwen3-32b": "groq",
    "groq-kimi-k2": "groq",
    "grok-4.3": "xai",
    "grok-build-0.1": "xai",
    "grok-4.1-fast": "xai",
    "gpt-5.5": "openai",
    "gpt-5.5-pro": "openai",
    "gpt-5.4": "openai",
    "gpt-5.4-mini": "openai",
    "gpt-5.4-nano": "openai",
    "gpt-5.3-codex": "openai",
    "gpt-4o": "openai",
    "o3": "openai",
    "claude-fable-5": "anthropic",
    "claude-opus-4.8": "anthropic",
    "claude-opus-4.7": "anthropic",
    "claude-opus-4.6": "anthropic",
    "claude-sonnet-5": "anthropic",
    "claude-sonnet-4.6": "anthropic",
    "claude-sonnet-4.5": "anthropic",
    "claude-haiku-4.5": "anthropic",
}

_PROFILE_BY_ALIAS: dict[str, tuple[str, str, str, str]] = {
    "phi-reasoning": (
        "probe/review",
        "default fast lane; review/planning only under Goose tools boundary",
        "audits, invariants, summaries, refusal/safety checks, cheap context compression",
        "heavy implementation, long Goose tool sessions, autonomous edits",
    ),
    "qwen-coder": (
        "primary code lane",
        "default implementation/planning lane after capability gates pass",
        "targeted Python/CLI/test patches, bounded refactors, code review with edits prepared for human verification",
        "whole-repo sweeps, giant-context refactors, unsupervised tool execution",
    ),
    "gemma-fast": (
        "multimodal sidecar",
        "not a normal mlx-lm Goose start target until a mlx-vlm adapter exists",
        "image/UI/screenshot interpretation and multimodal sidecar experiments",
        "plain Goose coding sessions through mlx_lm.server",
    ),
    "gemma-primary": (
        "heavy multimodal sidecar",
        "explicit opt-in only; not a normal mlx-lm Goose start target until a mlx-vlm adapter exists",
        "hard multimodal reasoning experiments when memory headroom is available",
        "default routing, long coding sessions, M1 16GB background use",
    ),
    "llama": (
        "constraint alternate",
        "manual alternate; validate latency before relying on it",
        "negative constraints, instruction-following comparison, prompt robustness checks",
        "default code implementation when qwen-coder is available",
    ),
    "codegeex": (
        "candidate code lane",
        "candidate-verify-first; do not route by default",
        "agentic coding experiments after local smoke tests",
        "trusted edits before dedicated validation",
    ),
    "qwen-coder-14b": (
        "heavy code lane",
        "heavy explicit opt-in only",
        "rare harder refactors when 7B fails and memory headroom is confirmed",
        "default or routine tasks on M1 16GB",
    ),
    "qwen3-coder-heavy": (
        "heavy agentic coder",
        "heavy explicit opt-in only; 30B-A3B cache footprint is above comfortable M1 default",
        "rare agentic-coding comparisons and hard coding benchmarks",
        "normal local Goose work on 16GB",
    ),
    "deepseek": (
        "heavy repo-sweep candidate",
        "heavy explicit opt-in only",
        "manual repo-sweep experiments after memory validation",
        "daily operation or default routing",
    ),
    "groq-llama": (
        "Groq cloud Llama 3.3",
        "cloud egress required; high-speed external inference",
        "extremely fast targeted implementation/coding tasks",
        "local-first or offline-only execution boundaries",
    ),
    "groq-mixtral": (
        "Groq cloud Mixtral",
        "cloud egress required; high-speed external inference",
        "extremely fast reasoning/coding alternate checks",
        "local-first or offline-only execution boundaries",
    ),
    "grok-reasoning": (
        "xAI cloud Grok 2",
        "cloud egress required; external reasoning engine",
        "deep architectural sweeps, negative constraints verification",
        "local-first or offline-only execution boundaries",
    ),
    "grok-beta": (
        "xAI cloud Grok Beta",
        "cloud egress required; external reasoning engine",
        "exploratory coding and alternate hypothesis testing",
        "local-first or offline-only execution boundaries",
    ),
    "gemini-pro": (
        "Google Cloud Gemini 1.5 Pro",
        "cloud egress required; high-fidelity Google reasoning model",
        "complex code edits, long multi-file refactoring plans",
        "local-first or offline-only execution boundaries",
    ),
    "gemini-flash": (
        "Google Cloud Gemini 1.5 Flash",
        "cloud egress required; fast external routing",
        "fast reviews, summaries, formatting, test iteration",
        "local-first or offline-only execution boundaries",
    ),
    "gemini-ultra": (
        "Google Cloud Gemini 1.0 Ultra",
        "cloud egress required; large capacity subscription model",
        "deep analysis, reasoning and complex instruction following",
        "local-first or offline-only execution boundaries",
    ),
    "gemini-3.5-flash": (
        "Google Cloud Gemini 3.5 Flash",
        "cloud egress required; stable Vertex UI flagship",
        "all fast tasks, code editing, reasoning",
        "local-first or offline-only execution boundaries",
    ),
    "gemini-3.1-pro": (
        "Google Cloud Gemini 3.1 Pro Preview",
        "cloud egress required; heavy reasoning preview model",
        "complex code refactors and reasoning tasks",
        "local-first or offline-only execution boundaries",
    ),
    "gemini-3.1-flash": (
        "Google Cloud Gemini 3.1 Flash",
        "cloud egress required; legacy flash model",
        "fast editing, summaries",
        "local-first or offline-only execution boundaries",
    ),
    "gemini-3-flash": (
        "Google Cloud Gemini 3 Flash Preview",
        "cloud egress required; global region exclusive preview model",
        "preview features and comparisons",
        "local-first or offline-only execution boundaries",
    ),
    "gemma4:e4b": (
        "Local Ollama Gemma 4 E4B",
        "candidate code lane; via Ollama",
        "local testing and coding",
        "production workflows",
    ),
    "gemma4:e2b": (
        "Local Ollama Gemma 4 E2B",
        "candidate code lane; via Ollama",
        "local testing and coding",
        "production workflows",
    ),
    "qwen3.5:2b": (
        "Local Ollama Qwen 3.5 2B",
        "candidate code lane; via Ollama",
        "local testing and coding",
        "production workflows",
    ),
    "qwen3.5:0.8b": (
        "Local Ollama Qwen 3.5 0.8B",
        "candidate code lane; via Ollama",
        "local testing and coding",
        "production workflows",
    ),
    "ibm/granite4.1:3b": (
        "Local Ollama Granite 4.1 3B",
        "candidate code lane; via Ollama",
        "local testing and coding",
        "production workflows",
    ),
    "groq-llama-instant": (
        "groq-llama-instant via groq",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "groq-gpt-oss-20b": (
        "groq-gpt-oss-20b via groq",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "groq-llama-scout": (
        "groq-llama-scout via groq",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "groq-gpt-oss-120b": (
        "groq-gpt-oss-120b via groq",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "groq-qwen3-32b": (
        "groq-qwen3-32b via groq",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "groq-kimi-k2": (
        "groq-kimi-k2 via groq",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "grok-4.3": (
        "grok-4.3 via xai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "grok-build-0.1": (
        "grok-build-0.1 via xai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "grok-4.1-fast": (
        "grok-4.1-fast via xai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "gpt-5.5": (
        "gpt-5.5 via openai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "gpt-5.5-pro": (
        "gpt-5.5-pro via openai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "gpt-5.4": (
        "gpt-5.4 via openai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "gpt-5.4-mini": (
        "gpt-5.4-mini via openai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "gpt-5.4-nano": (
        "gpt-5.4-nano via openai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "gpt-5.3-codex": (
        "gpt-5.3-codex via openai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "gpt-4o": (
        "gpt-4o via openai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "o3": (
        "o3 via openai",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "claude-fable-5": (
        "claude-fable-5 via anthropic",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "claude-opus-4.8": (
        "claude-opus-4.8 via anthropic",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "claude-opus-4.7": (
        "claude-opus-4.7 via anthropic",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "claude-opus-4.6": (
        "claude-opus-4.6 via anthropic",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "claude-sonnet-5": (
        "claude-sonnet-5 via anthropic",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "claude-sonnet-4.6": (
        "claude-sonnet-4.6 via anthropic",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "claude-sonnet-4.5": (
        "claude-sonnet-4.5 via anthropic",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
    "claude-haiku-4.5": (
        "claude-haiku-4.5 via anthropic",
        "cloud egress required",
        "general usage",
        "local-first or offline-only execution boundaries",
    ),
}


def runtime_for_alias(alias: str) -> str:
    return _RUNTIME_BY_ALIAS[alias]


def can_launch_with_backend(alias: str, backend: str) -> bool:
    runtime = runtime_for_alias(alias)
    if backend == "mlx-lm":
        return runtime.startswith("mlx-lm")
    return True


def launch_block_reason(alias: str, backend: str) -> str | None:
    if can_launch_with_backend(alias, backend):
        return None
    runtime = runtime_for_alias(alias)
    return (
        f"model alias {alias!r} is classified as {runtime!r}; "
        f"backend {backend!r} cannot launch it as a normal Goose chat model"
    )


def operating_profile(definition: ModelDefinition) -> ModelOperatingProfile:
    role, launch_policy, recommended_for, avoid_for = _PROFILE_BY_ALIAS[definition.alias]
    return ModelOperatingProfile(
        alias=definition.alias,
        runtime=runtime_for_alias(definition.alias),
        role=role,
        launch_policy=launch_policy,
        recommended_for=recommended_for,
        avoid_for=avoid_for,
    )


def operating_profiles(settings: Settings) -> tuple[ModelOperatingProfile, ...]:
    return tuple(operating_profile(definition) for definition in model_definitions(settings))
