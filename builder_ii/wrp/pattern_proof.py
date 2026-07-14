"""W.4 — Pure graph_runtime mastery proof for the five official orchestration patterns.

Validation-only: noop graphs via patterns.py + execute_graph. No S2 live, no gateways,
no shell, no models, no S3 enablement.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

from builder_ii.config_schema import attach_digest
from builder_ii.wrp.graph_runtime import SUPPORTED_PATTERNS, execute_graph, normalize_pattern
from builder_ii.wrp.patterns import (
    cyclic_revisitation,
    handoff_route,
    hierarchical,
    parallel_fanout,
    sequential_chain,
)
from builder_ii.wrp.spaces import TrajectoryGraph

# Canonical pattern → (graph builder, execute_graph kwargs)
_ProofCase = tuple[str, Callable[[], TrajectoryGraph], dict[str, Any]]

_HANDOFF_STATE = {
    "task": "pattern-proof",
    "target": "builder-ii",
    "authority": "none",
    "risks": "low",
    "evidence_status": "pending",
}

PROOF_CASES: tuple[_ProofCase, ...] = (
    ("sequential", lambda: sequential_chain(["a", "b", "c"]), {}),
    ("fan_out_fan_in", lambda: parallel_fanout("root", ["w1", "w2"], "sink"), {}),
    ("hierarchical", lambda: hierarchical("mgr", ["u1", "u2"]), {}),
    (
        "handoff",
        lambda: handoff_route(["maker", "governor"]),
        {
            "handoff_state": dict(_HANDOFF_STATE),
            "required_keys": list(_HANDOFF_STATE.keys()),
        },
    ),
    (
        "cyclic",
        lambda: cyclic_revisitation(["eval", "agent"]),
        {"max_iterations": 2},
    ),
)


def prove_all_patterns() -> dict[str, Any]:
    """Run all five patterns through pure graph_runtime; return digest-bound report."""
    rows: list[dict[str, Any]] = []
    for expected, builder, kwargs in PROOF_CASES:
        graph = builder()
        norm = normalize_pattern(graph.pattern)
        t0 = perf_counter()
        result = execute_graph(graph, **kwargs)
        wall_ms = round((perf_counter() - t0) * 1000.0, 3)
        ok = (
            result.get("status") == "success"
            and result.get("pattern") == expected
            and norm == expected
            and result.get("grants_authority") is False
            and result.get("executes_model") is False
            and result.get("executes_tools") is False
            and isinstance(result.get("digest"), str)
            and len(str(result.get("digest"))) == 64
        )
        rows.append(
            {
                "pattern": expected,
                "source_pattern": graph.pattern,
                "ok": ok,
                "wall_ms": wall_ms,
                "status": result.get("status"),
                "execution_order": result.get("execution_order"),
                "run_digest": result.get("digest"),
                "error": result.get("error"),
            }
        )

    covered = {r["pattern"] for r in rows}
    all_ok = all(r["ok"] for r in rows) and covered == set(SUPPORTED_PATTERNS)
    return attach_digest(
        {
            "kind": "builder_ii.wrp.pattern_mastery_report",
            "schema_version": 1,
            "artifact_state": "VALIDATION_ONLY",
            "ok": all_ok,
            "patterns": rows,
            "pattern_count": len(rows),
            "runtime": "builder_ii.wrp.graph_runtime",
            "s2_live": False,
            "gateway_handler": False,
            "grants_authority": False,
            "executes_model": False,
            "executes_tools": False,
            "s3_enabled": False,
            "notes": (
                "Pure noop graph_runtime proof of five orchestration patterns. "
                "Not S2 live lane; not cloud invoke; not S3 enablement."
            ),
        }
    )


def prove_patterns_entrypoint() -> int:
    """CLI/runner entry: exit 0 iff all patterns prove ok."""
    report = prove_all_patterns()
    import json
    import sys

    sys.stdout.write(json.dumps(report, indent=2, sort_keys=True) + "\n")
    return 0 if report.get("ok") else 1


__all__ = ["PROOF_CASES", "prove_all_patterns", "prove_patterns_entrypoint"]
