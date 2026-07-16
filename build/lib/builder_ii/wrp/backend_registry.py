"""WRP backend registry + doctor (P6.1 productization of existing opt-in adapters).

Inventory and health only — validation surface. Does **not**:
- promote S4 backends
- install heavy deps
- start vLLM/torch/LangGraph engines by default
- grant execution authority
- soft-enable multi-agent (S3)

Defaults remain M1-safe (hash embed + pure MSDA + pure graph projection).
"""

from __future__ import annotations

import importlib
import os
from typing import Any, Callable

from builder_ii.wrp.embedding_backend import (
    MODERNBERT_ENV,
    MODERNBERT_ENV_VALUE,
    modernbert_opt_in_enabled,
    resolve_embedder,
)
from builder_ii.wrp.langgraph_adapter import (
    LANGGRAPH_ENV,
    LANGGRAPH_ENV_VALUE,
    langgraph_importable,
    langgraph_opt_in_enabled,
)
from builder_ii.wrp.msda_preflight import ENV_MSDA_PREFLIGHT, msda_preflight_status
from builder_ii.wrp.opa_adapter import OpaEvalAdapter
from builder_ii.wrp.vllm_profile import (
    VLLM_ENV,
    VLLM_ENV_VALUE,
    vllm_opt_in_enabled,
)
from builder_ii.wrp.vllm_profile import (
    profile_status as vllm_profile_status,
)

# Optional classifier embed switch (hash kNN, not ModernBERT).
ENV_WRP_EMBED = "BUILDER_II_WRP_EMBED"


def _health(
    *,
    ready: bool,
    available: bool,
    detail: str,
    state: str,
) -> dict[str, Any]:
    return {
        "ready": ready,
        "available": available,
        "state": state,  # healthy | unavailable | opt_in_pending | research_stub
        "detail": detail,
    }


def _row(
    *,
    backend_id: str,
    family: str,
    module: str,
    tier: str,
    is_default_runtime: bool,
    opt_in_env: str | None,
    opt_in_value: str | None,
    opt_in_enabled: bool,
    cli_commands: list[str],
    health: dict[str, Any],
    notes: str,
) -> dict[str, Any]:
    return {
        "id": backend_id,
        "family": family,
        "module": module,
        "tier": tier,  # default | opt_in | research | policy
        "is_default_runtime": is_default_runtime,
        "grants_authority": False,
        "opt_in_env": opt_in_env,
        "opt_in_value": opt_in_value,
        "opt_in_enabled": opt_in_enabled,
        "cli_commands": list(cli_commands),
        "health": health,
        "notes": notes,
    }


def _modernbert_provider_importable() -> bool:
    try:
        mod = importlib.import_module("builder_ii.wrp._optional_modernbert")
    except ImportError:
        return False
    return callable(getattr(mod, "embed", None))


def _hash_embed_row() -> dict[str, Any]:
    backend = resolve_embedder()
    return _row(
        backend_id="hashing_embed",
        family="embedder",
        module="builder_ii.wrp.embedding_backend",
        tier="default",
        is_default_runtime=True,
        opt_in_env=None,
        opt_in_value=None,
        opt_in_enabled=False,
        cli_commands=["builder-wrp embed-status", "builder-wrp classify"],
        health=_health(
            ready=True,
            available=True,
            detail=f"active_resolver={backend.name}",
            state="healthy",
        ),
        notes="M1-safe deterministic HashingEmbedder; default for resolve_embedder().",
    )


def _modernbert_row() -> dict[str, Any]:
    opt_in = modernbert_opt_in_enabled()
    provider_ok = _modernbert_provider_importable()
    if not opt_in:
        health = _health(
            ready=False,
            available=False,
            detail=f"set {MODERNBERT_ENV}={MODERNBERT_ENV_VALUE} and inject/install provider",
            state="unavailable",
        )
    elif not provider_ok:
        health = _health(
            ready=False,
            available=False,
            detail="env set but provider module missing (fail-closed on embed)",
            state="opt_in_pending",
        )
    else:
        health = _health(
            ready=True,
            available=True,
            detail="env set and optional provider importable",
            state="healthy",
        )
    return _row(
        backend_id="modernbert_embed",
        family="embedder",
        module="builder_ii.wrp.embedding_backend",
        tier="opt_in",
        is_default_runtime=False,
        opt_in_env=MODERNBERT_ENV,
        opt_in_value=MODERNBERT_ENV_VALUE,
        opt_in_enabled=opt_in,
        cli_commands=["builder-wrp embed-status"],
        health=health,
        notes="OptionalModernBertBackend; never default. S4 promote separate.",
    )


def _msda_python_row() -> dict[str, Any]:
    return _row(
        backend_id="msda_python",
        family="msda_eval",
        module="builder_ii.wrp.opa_adapter",
        tier="default",
        is_default_runtime=True,
        opt_in_env=None,
        opt_in_value=None,
        opt_in_enabled=False,
        cli_commands=["builder-wrp opa-eval", "builder-wrp gate"],
        health=_health(
            ready=True,
            available=True,
            detail="pure-Python eval_msda_python / evaluate_msda_gate",
            state="healthy",
        ),
        notes="Reference MSDA backend; parity source for optional OPA.",
    )


def _opa_row() -> dict[str, Any]:
    adapter = OpaEvalAdapter()
    available = bool(adapter.available)
    health = (
        _health(
            ready=True,
            available=True,
            detail=f"opa binary at {adapter.opa_path}",
            state="healthy",
        )
        if available
        else _health(
            ready=False,
            available=False,
            detail="opa not on PATH; use --backend python",
            state="unavailable",
        )
    )
    return _row(
        backend_id="opa",
        family="msda_eval",
        module="builder_ii.wrp.opa_adapter",
        tier="opt_in",
        is_default_runtime=False,
        opt_in_env=None,
        opt_in_value=None,
        opt_in_enabled=available,
        cli_commands=["builder-wrp opa-eval --backend opa"],
        health=health,
        notes="Optional OpaEvalAdapter via shutil.which('opa'); CLI --backend opa.",
    )


def _pure_graph_row() -> dict[str, Any]:
    return _row(
        backend_id="pure_graph_projection",
        family="graph",
        module="builder_ii.wrp.langgraph_adapter",
        tier="default",
        is_default_runtime=False,  # graph_runtime is execute default; projection is always-on tool
        opt_in_env=None,
        opt_in_value=None,
        opt_in_enabled=False,
        cli_commands=["builder-wrp langgraph-project"],
        health=_health(
            ready=True,
            available=True,
            detail="project_trajectory_graph always available",
            state="healthy",
        ),
        notes="Pure projection for Governor review; not LangGraph execute. Runtime is graph_runtime.",
    )


def _langgraph_row() -> dict[str, Any]:
    opt_in = langgraph_opt_in_enabled()
    importable = langgraph_importable()
    if not opt_in:
        health = _health(
            ready=False,
            available=importable,
            detail=f"set {LANGGRAPH_ENV}={LANGGRAPH_ENV_VALUE} to compile (importable={importable})",
            state="unavailable",
        )
    elif not importable:
        health = _health(
            ready=False,
            available=False,
            detail="env set but langgraph package not importable",
            state="opt_in_pending",
        )
    else:
        health = _health(
            ready=True,
            available=True,
            detail="opt-in env set and langgraph importable",
            state="healthy",
        )
    return _row(
        backend_id="langgraph",
        family="graph",
        module="builder_ii.wrp.langgraph_adapter",
        tier="opt_in",
        is_default_runtime=False,
        opt_in_env=LANGGRAPH_ENV,
        opt_in_value=LANGGRAPH_ENV_VALUE,
        opt_in_enabled=opt_in,
        cli_commands=["builder-wrp langgraph-project --compile"],
        health=health,
        notes="OptionalLangGraphAdapter.compile only; never default runtime.",
    )


def _vllm_row() -> dict[str, Any]:
    opt_in = vllm_opt_in_enabled()
    status = vllm_profile_status()
    health = _health(
        ready=False,
        available=False,
        detail=(
            "research stub only; inject client after S4"
            if opt_in
            else f"set {VLLM_ENV}={VLLM_ENV_VALUE} (still stub without injected client)"
        ),
        state="research_stub",
    )
    return _row(
        backend_id="vllm_research",
        family="model_research",
        module="builder_ii.wrp.vllm_profile",
        tier="research",
        is_default_runtime=False,
        opt_in_env=VLLM_ENV,
        opt_in_value=VLLM_ENV_VALUE,
        opt_in_enabled=opt_in,
        cli_commands=["builder-wrp vllm-profile"],
        health=health,
        notes=f"profile={status.get('profile', {}).get('name')}; engine never started by doctor.",
    )


def _msda_preflight_row() -> dict[str, Any]:
    st = msda_preflight_status()
    enabled = bool(st.get("global_env_enabled"))
    health = _health(
        ready=True,
        available=True,
        detail=(
            f"global env ON ({ENV_MSDA_PREFLIGHT}); live lane / gateway nodes still force independently"
            if enabled
            else "global env OFF (default); live lane / gateway nodes force preflight"
        ),
        state="healthy",
    )
    return _row(
        backend_id="msda_preflight",
        family="policy",
        module="builder_ii.wrp.msda_preflight",
        tier="policy",
        is_default_runtime=False,
        opt_in_env=ENV_MSDA_PREFLIGHT,
        opt_in_value="1|true|yes|on",
        opt_in_enabled=enabled,
        cli_commands=["builder-wrp msda-status"],
        health=health,
        notes="Honesty/policy surface; not a model backend. product_default_on=false.",
    )


def _classifier_embed_row() -> dict[str, Any]:
    raw = os.getenv(ENV_WRP_EMBED, "").strip().lower()
    enabled = raw in {"1", "true", "yes", "on"}
    return _row(
        backend_id="classifier_hash_embed",
        family="embedder",
        module="builder_ii.wrp.workload_classifier",
        tier="opt_in",
        is_default_runtime=False,
        opt_in_env=ENV_WRP_EMBED,
        opt_in_value="1|true|yes|on",
        opt_in_enabled=enabled,
        cli_commands=["builder-wrp classify"],
        health=_health(
            ready=True,
            available=True,
            detail="HashingEmbedder+kNN when env on; default rule/metric path when off",
            state="healthy",
        ),
        notes="Does not enable ModernBERT; separate from BUILDER_II_WRP_EMBEDDER.",
    )


_BUILDERS: tuple[Callable[[], dict[str, Any]], ...] = (
    _hash_embed_row,
    _modernbert_row,
    _classifier_embed_row,
    _msda_python_row,
    _opa_row,
    _pure_graph_row,
    _langgraph_row,
    _vllm_row,
    _msda_preflight_row,
)


def list_backends() -> list[dict[str, Any]]:
    """Return immutable inventory of WRP backends (no side effects, no heavy imports beyond existing modules)."""
    return [builder() for builder in _BUILDERS]


def doctor_backends() -> dict[str, Any]:
    """Structured health report for all registered backends.

    ``ok`` is True when **default** paths are healthy (M1-safe). Opt-in unavailable
    backends do not fail the doctor — they report unavailable/pending honestly.
    """
    backends = list_backends()
    defaults = [b for b in backends if b.get("tier") == "default"]
    default_ok = all(b["health"]["ready"] for b in defaults)
    opt_in = [b for b in backends if b.get("tier") in {"opt_in", "research", "policy"}]
    unavailable = [b["id"] for b in backends if not b["health"]["available"] and b["tier"] != "default"]
    pending = [b["id"] for b in backends if b["health"]["state"] == "opt_in_pending"]
    research = [b["id"] for b in backends if b["health"]["state"] == "research_stub"]

    return {
        "kind": "builder_ii.wrp.backend_doctor_report",
        "schema_version": 1,
        "artifact_state": "VALIDATION_ONLY",
        "grants_authority": False,
        "s3_enabled": False,
        "s4_promoted": False,
        "default_runtime_ok": default_ok,
        "ok": default_ok,
        "backend_count": len(backends),
        "defaults": [b["id"] for b in defaults],
        "opt_in_or_research": [b["id"] for b in opt_in],
        "unavailable": unavailable,
        "opt_in_pending": pending,
        "research_stub": research,
        "backends": backends,
        "m1_safe_defaults": True,
        "notes": (
            "Doctor validates inventory/health only. Missing opa/langgraph/modernbert is expected "
            "on M1 defaults and does not fail ok. Never starts engines. S4 promotion is separate."
        ),
    }


def backend_ids() -> list[str]:
    return [b["id"] for b in list_backends()]


__all__ = [
    "backend_ids",
    "doctor_backends",
    "list_backends",
]
