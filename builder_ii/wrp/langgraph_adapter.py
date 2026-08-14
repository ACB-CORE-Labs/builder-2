"""Optional LangGraph adapter — pure projection always; real LangGraph opt-in only.

Design (P6 / gap matrix):
- Default path projects ``TrajectoryGraph`` / subtask-graph plans into a pure-Python
  state-machine dict. No ``langgraph`` import is required for CI or M1 defaults.
- Optional compile path activates only when **both** are true:
  1. Environment: ``BUILDER_II_WRP_LANGGRAPH=1``
  2. Importable ``langgraph`` package **or** an injected compiler callable
- Fail-closed: missing package + env requested → ``BackendUnavailableError``.
- Never grants execution authority; never replaces ``graph_runtime``.

Promotion honesty: this adapter is substrate only (S4-ready interface). Enabling
LangGraph as a promoted backend requires a separate HUMAN + G-LEAD decision.
"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

from builder_ii.wrp.spaces import TrajectoryGraph

LANGGRAPH_ENV: str = "BUILDER_II_WRP_LANGGRAPH"
LANGGRAPH_ENV_VALUE: str = "1"

# Injected compiler: (projection_dict) -> opaque compiled graph handle
LangGraphCompiler = Callable[[dict[str, Any]], Any]


class BackendUnavailableError(RuntimeError):
    """Raised when opt-in LangGraph backend cannot be used (fail closed)."""


@runtime_checkable
class GraphAdapter(Protocol):
    """Minimal adapter contract for WRP graph projection."""

    name: str

    def project(self, graph: TrajectoryGraph | Mapping[str, Any]) -> dict[str, Any]:
        """Return a pure, JSON-serializable graph projection (never executes)."""
        ...


def _as_graph(graph: TrajectoryGraph | Mapping[str, Any]) -> TrajectoryGraph:
    if isinstance(graph, TrajectoryGraph):
        return graph
    if isinstance(graph, Mapping):
        return TrajectoryGraph.from_mapping(graph)
    raise TypeError("graph must be a TrajectoryGraph or mapping")


def project_trajectory_graph(graph: TrajectoryGraph | Mapping[str, Any]) -> dict[str, Any]:
    """Pure projection of a TrajectoryGraph into a LangGraph-shaped plan dict.

    Always available (no optional deps). Output is review/plan only — not a live
    StateGraph and not an authority grant.
    """
    g = _as_graph(graph)
    try:
        order = g.topological_order()
    except ValueError:
        # Cyclic / non-DAG: use declaration order as revisitation skeleton.
        order = list(g.nodes)

    nodes: list[dict[str, Any]] = []
    for node_id in g.nodes:
        nodes.append(
            {
                "id": str(node_id),
                "kind": "node",
                # LangGraph-ish naming for Governor review only.
                "langgraph_node_name": str(node_id),
            }
        )

    edges: list[dict[str, Any]] = []
    for edge in g.edges:
        edges.append(
            {
                "source": str(edge.source),
                "target": str(edge.target),
                "expected_cost": float(edge.expected_cost),
                "expected_reward": float(getattr(edge, "expected_reward", 0.0) or 0.0),
            }
        )

    return {
        "adapter": "builder_ii.wrp.langgraph_adapter",
        "backend": "pure_projection",
        "pattern": str(g.pattern or "sequential"),
        "nodes": nodes,
        "edges": edges,
        "execution_order": list(order),
        "entry_point": order[0] if order else None,
        "finish_point": order[-1] if order else None,
        "langgraph_available": langgraph_importable(),
        "grants_authority": False,
        "executes_model": False,
        "executes_tools": False,
        "is_default_runtime": False,
        "notes": (
            "Pure WRP projection for Governor review. Optional LangGraph compile "
            f"requires {LANGGRAPH_ENV}={LANGGRAPH_ENV_VALUE} and importable langgraph."
        ),
    }


def langgraph_importable() -> bool:
    """True when the optional ``langgraph`` package can be imported."""
    try:
        importlib.import_module("langgraph")
        return True
    except ImportError:
        return False


def langgraph_opt_in_enabled() -> bool:
    """True when env requests LangGraph opt-in (does not imply package present)."""
    return os.environ.get(LANGGRAPH_ENV) == LANGGRAPH_ENV_VALUE


class PureGraphProjection:
    """Always-available pure-Python graph projection (M1-safe default)."""

    name: str = "pure_projection"

    def project(self, graph: TrajectoryGraph | Mapping[str, Any]) -> dict[str, Any]:
        return project_trajectory_graph(graph)


class OptionalLangGraphAdapter:
    """Fail-closed optional LangGraph compile surface.

    Construction never requires LangGraph. ``project`` always works.
    ``compile`` requires opt-in env + (importable package or injected compiler).
    """

    name: str = "langgraph"

    def __init__(self, compiler: LangGraphCompiler | None = None) -> None:
        self._compiler = compiler

    @property
    def available(self) -> bool:
        """True when a compile path exists (injected or importable), regardless of env."""
        if self._compiler is not None:
            return True
        return langgraph_importable()

    def project(self, graph: TrajectoryGraph | Mapping[str, Any]) -> dict[str, Any]:
        return project_trajectory_graph(graph)

    def compile(self, graph: TrajectoryGraph | Mapping[str, Any]) -> dict[str, Any]:
        """Attempt optional LangGraph compile; fail closed when unavailable.

        Returns a digest-friendly handle dict. Never executes tools/models.
        """
        if not langgraph_opt_in_enabled():
            raise BackendUnavailableError(
                "OptionalLangGraphAdapter.compile is opt-in only; set "
                f"{LANGGRAPH_ENV}={LANGGRAPH_ENV_VALUE}. Default WRP path uses "
                "builder_ii.wrp.graph_runtime (pure Python)."
            )
        projection = self.project(graph)
        compiler = self._compiler if self._compiler is not None else _try_load_langgraph_compiler()
        if compiler is None:
            raise BackendUnavailableError(
                "LangGraph compiler unavailable: install optional package 'langgraph' "
                "or inject compiler= callable. Not required for M1 defaults or CI."
            )
        handle = compiler(projection)
        return {
            "adapter": self.name,
            "backend": "langgraph",
            "status": "compiled_handle",
            "projection": projection,
            "handle_type": type(handle).__name__,
            # Do not embed opaque runtime objects in digests — type name only.
            "grants_authority": False,
            "executes_model": False,
            "executes_tools": False,
            "is_default_runtime": False,
        }


def _try_load_langgraph_compiler() -> LangGraphCompiler | None:
    """Best-effort optional import. Never raises — fail closed via None."""
    try:
        importlib.import_module("langgraph")
    except ImportError:
        return None

    def _compiler(projection: dict[str, Any]) -> dict[str, Any]:
        # Real StateGraph construction is environment-specific; research path
        # records a structured compile receipt without granting authority.
        return {
            "compiled": True,
            "entry_point": projection.get("entry_point"),
            "node_ids": [n.get("id") for n in projection.get("nodes") or []],
            "edge_count": len(projection.get("edges") or []),
            "note": "langgraph import present; handle is research stub (not default runtime)",
        }

    return _compiler


def compile_projection_to_wrp_seam_plan(
    projection: Mapping[str, Any],
    *,
    task: str,
    gateway_mode: str = "invoke_local",
) -> dict[str, Any]:
    """W3.3 — compile a LangGraph-shaped projection into WRP node_specs + seam mode.

    Never executes models. Output is a plan fragment for ``build_live_run_plan`` /
    graph_runtime. Authority remains with WRP + HITL + seam gates.
    """
    if gateway_mode not in {"record", "invoke_local", "invoke_cloud", "stub_tool"}:
        raise ValueError(f"unsupported gateway_mode for seam compile: {gateway_mode!r}")
    order = list(projection.get("execution_order") or [])
    if not order:
        nodes = projection.get("nodes") or []
        order = [str(n.get("id")) for n in nodes if isinstance(n, Mapping) and n.get("id")]
    node_specs: dict[str, dict[str, Any]] = {}
    for node_id in order:
        nid = str(node_id)
        # Heuristic: names containing model/llm map to model_gateway; tools to tool_gateway.
        lower = nid.lower()
        if "tool" in lower:
            ntype = "tool_gateway"
            payload: dict[str, Any] = {"tool_id": "builtin.echo", "tool": "builtin.echo", "text": nid}
        elif "model" in lower or "llm" in lower or "agent" in lower:
            ntype = "model_gateway"
            payload = {
                "tool": "model_call",
                "model_id": "record-only-local" if gateway_mode == "record" else "gpt-4o-stub",
                "prompt": f"{task} :: {nid}",
                "enable_stub_if_disabled": True,
            }
        else:
            ntype = "record"
            payload = {"note": nid}
        node_specs[nid] = {
            "node_type": ntype,
            "cost_estimate": 0.0,
            "payload": payload,
            "compiled_from": "langgraph_projection",
        }
    return {
        "kind": "builder_ii.wrp.langgraph_seam_compile",
        "adapter": "builder_ii.wrp.langgraph_adapter",
        "task": task,
        "gateway_mode": gateway_mode,
        "nodes": list(order),
        "node_specs": node_specs,
        "source_backend": projection.get("backend"),
        "grants_authority": False,
        "executes_model": False,
        "is_default_runtime": False,
        "notes": (
            "Inner planner projection compiled to WRP nodes + seam mode. "
            "Execution requires live_lane HITL + gateway_mode gates; never autonomous."
        ),
    }


__all__ = [
    "LANGGRAPH_ENV",
    "LANGGRAPH_ENV_VALUE",
    "BackendUnavailableError",
    "GraphAdapter",
    "OptionalLangGraphAdapter",
    "PureGraphProjection",
    "compile_projection_to_wrp_seam_plan",
    "langgraph_importable",
    "langgraph_opt_in_enabled",
    "project_trajectory_graph",
]
