from __future__ import annotations

from dataclasses import dataclass

from builder_ii.config import Settings
from builder_ii.models import ModelDefinition, model_definitions


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
