"""Readiness rendering must fail closed on absence -- empty gates are not a pass.

`_render_readiness` (builder promote readiness/status) returned 0 (READY) for an artifact with no
gates and no explicit ready flag, because `all([])` is vacuously True: a promotion greenlit on zero
evaluated gates. That is the same absence-as-satisfaction fail-open the Third Door taxonomy closes.
This module was previously untested; these pins hold the fail-closed rule.
"""

from __future__ import annotations

from builder_ii.promote_tui import _render_readiness


def test_empty_gates_without_a_ready_flag_is_not_ready() -> None:
    """The defect: no gates + no flag must be NOT ready (exit 1), never a vacuous pass."""
    assert _render_readiness({"gates": {}}, verbose=False) == 1
    assert _render_readiness({}, verbose=False) == 1
    # An empty *list* of gates falls through to {} the same way -- still nothing evaluated.
    assert _render_readiness({"gates": []}, verbose=False) == 1


def test_an_explicit_ready_flag_is_still_honoured() -> None:
    """The renderer reflects the artifact's own stated claim; it does not overrule a real verdict."""
    assert _render_readiness({"gates": {}, "ready": True}, verbose=False) == 0
    assert _render_readiness({"promotion_ready": True}, verbose=False) == 0
    assert _render_readiness({"all_gates_passed": True}, verbose=False) == 0


def test_all_gates_passing_is_ready() -> None:
    assert _render_readiness({"gates": {"lint": True, "tests": True}}, verbose=False) == 0
    assert _render_readiness({"gates": [{"name": "lint", "passed": True}]}, verbose=False) == 0


def test_any_failing_gate_is_not_ready() -> None:
    assert _render_readiness({"gates": {"lint": True, "tests": False}}, verbose=False) == 1
    assert _render_readiness({"gates": [{"name": "lint", "passed": False}]}, verbose=False) == 1


def test_failures_only_still_counts_every_gate_for_the_verdict() -> None:
    """failures_only changes what prints, never the verdict: all-pass is still ready, and the
    empty-gates fail-closed rule still holds."""
    assert _render_readiness({"gates": {"a": True, "b": True}}, verbose=False, failures_only=True) == 0
    assert _render_readiness({"gates": {}}, verbose=False, failures_only=True) == 1
