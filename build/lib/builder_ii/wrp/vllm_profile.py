"""vLLM WRP research profile — interface/stub only; never a default runtime path.

Design (P6 / gap matrix / mechanical sympathy):
- Documents a research-oriented vLLM target profile for dual-platform review.
- Provides a Protocol + stub client that **always** fail-closes on invoke unless
  an explicit research client is injected **and** env opt-in is set.
- No torch/vLLM import at module load. CI and M1 defaults never require vLLM.
- ``is_default_runtime`` is always False on shipped profiles.

Promotion honesty: S4 backend promotion is separate; this module is interface +
docs substrate only. Cloud/provider invoke remains OPEN (H6).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from typing import Any, Protocol, runtime_checkable

VLLM_ENV: str = "BUILDER_II_WRP_VLLM"
VLLM_ENV_VALUE: str = "research"

# Research-only footprint guidance (M1 16GB: heavy GPU servers only — not local default).
RESEARCH_PROFILE_NAME: str = "wrp_vllm_research"
RESEARCH_MODEL_ID: str = "research/wrp-router-not-shipped"
RESEARCH_MAX_MODEL_LEN: int = 4096
RESEARCH_GPU_MEMORY_UTILIZATION: float = 0.45


class BackendUnavailableError(RuntimeError):
    """Raised when opt-in vLLM research path cannot be used (fail closed)."""


@dataclass(frozen=True)
class VllmResearchProfile:
    """Immutable research profile metadata (not a live engine config authority)."""

    name: str
    model_id: str
    max_model_len: int
    gpu_memory_utilization: float
    is_default_runtime: bool = False
    grants_authority: bool = False
    requires_opt_in_env: str = VLLM_ENV
    notes: str = (
        "Research / non-default target profile. Not installed by default. "
        "Never used by classify/route/gate/live-lane unless a future S4 decision "
        "and explicit env opt-in are both present."
    )

    def to_jsonable(self) -> dict[str, Any]:
        return dict(asdict(self))


DEFAULT_RESEARCH_PROFILE = VllmResearchProfile(
    name=RESEARCH_PROFILE_NAME,
    model_id=RESEARCH_MODEL_ID,
    max_model_len=RESEARCH_MAX_MODEL_LEN,
    gpu_memory_utilization=RESEARCH_GPU_MEMORY_UTILIZATION,
    is_default_runtime=False,
    grants_authority=False,
)


@runtime_checkable
class VllmWrPClient(Protocol):
    """Minimal client contract for a future vLLM research path."""

    name: str

    def complete(self, prompt: str, *, max_tokens: int = 64) -> dict[str, Any]:
        """Return a completion receipt. Must not mutate caller state."""
        ...


class StubVllmClient:
    """Fail-closed stub — present for interface tests and Governor review."""

    name: str = "vllm_stub"

    def complete(self, prompt: str, *, max_tokens: int = 64) -> dict[str, Any]:
        if not isinstance(prompt, str):
            raise TypeError("prompt must be a str")
        if max_tokens < 1:
            raise ValueError("max_tokens must be >= 1")
        if os.environ.get(VLLM_ENV) != VLLM_ENV_VALUE:
            raise BackendUnavailableError(
                "StubVllmClient is research opt-in only; set "
                f"{VLLM_ENV}={VLLM_ENV_VALUE}. Default WRP path never uses vLLM."
            )
        raise BackendUnavailableError(
            "vLLM research client not injected: pass a real VllmWrPClient via "
            "resolve_vllm_client(client=...) after S4 promotion. Weights are not "
            "shipped; this stub never becomes a default runtime path."
        )


def research_profile(*, overrides: Mapping[str, Any] | None = None) -> VllmResearchProfile:
    """Return the immutable research profile (optionally field-overridden for review)."""
    base = DEFAULT_RESEARCH_PROFILE
    if not overrides:
        return base
    data = base.to_jsonable()
    for key, value in overrides.items():
        if key not in data:
            raise ValueError(f"unknown VllmResearchProfile field: {key!r}")
        data[key] = value
    # Force honesty flags even if overrides try to inflate.
    data["is_default_runtime"] = False
    data["grants_authority"] = False
    return VllmResearchProfile(**data)  # type: ignore[arg-type]


def vllm_opt_in_enabled() -> bool:
    return os.environ.get(VLLM_ENV) == VLLM_ENV_VALUE


def resolve_vllm_client(client: VllmWrPClient | None = None) -> VllmWrPClient:
    """Resolve research client: injected client if opt-in, else fail-closed stub.

    Never imports vLLM. Never returns a live engine by default.
    """
    if client is not None:
        if not vllm_opt_in_enabled():
            raise BackendUnavailableError(
                "Injected vLLM client refused without "
                f"{VLLM_ENV}={VLLM_ENV_VALUE} (fail closed; not default runtime)."
            )
        return client
    return StubVllmClient()


def profile_status() -> dict[str, Any]:
    """CLI/review surface: profile metadata + opt-in state (no engine start)."""
    profile = research_profile()
    return {
        "kind": "builder_ii.wrp.vllm_research_profile_status",
        "profile": profile.to_jsonable(),
        "opt_in_env": VLLM_ENV,
        "opt_in_value": VLLM_ENV_VALUE,
        "opt_in_enabled": vllm_opt_in_enabled(),
        "default_runtime": False,
        "grants_authority": False,
        "engine_started": False,
        "backend": "stub" if not vllm_opt_in_enabled() else "research_opt_in_pending_client",
    }


__all__ = [
    "DEFAULT_RESEARCH_PROFILE",
    "RESEARCH_PROFILE_NAME",
    "VLLM_ENV",
    "VLLM_ENV_VALUE",
    "BackendUnavailableError",
    "StubVllmClient",
    "VllmResearchProfile",
    "VllmWrPClient",
    "profile_status",
    "research_profile",
    "resolve_vllm_client",
    "vllm_opt_in_enabled",
]
