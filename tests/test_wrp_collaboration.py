from __future__ import annotations

import time

from builder_ii.wrp.collaboration_planner import (
    REQUIRED_HANDOFF_KEYS,
    plan_collaboration,
    validate_collaboration_topology,
    validate_handoff_state,
)


def test_topology_valid_and_unbound() -> None:
    art = plan_collaboration(task="ship WRP W1 topology", priority=1, mode="standard")
    assert validate_collaboration_topology(art) == []
    assert art["runtime_binding"] == "UNBOUND"
    assert art["grants_authority"] is False
    assert {n["platform"] for n in art["nodes"]} <= {"maker", "governor"}


def test_security_mode_forces_high_security() -> None:
    art = plan_collaboration(task="sensitive audit", security_sensitive=True)
    assert art["mode"] == "high_security"


def test_handoff_zero_loss() -> None:
    state = {k: f"value-{k}" for k in REQUIRED_HANDOFF_KEYS}
    assert validate_handoff_state(state) == []
    assert validate_handoff_state({"task": "x"}) != []


def test_validation_latency_under_50ms_for_pure_topology() -> None:
    art = plan_collaboration(task="latency check")
    start = time.perf_counter()
    for _ in range(20):
        errs = validate_collaboration_topology(art)
        assert errs == []
    elapsed_ms = (time.perf_counter() - start) * 1000.0 / 20.0
    assert elapsed_ms < 50.0, f"avg validation {elapsed_ms:.2f}ms"
