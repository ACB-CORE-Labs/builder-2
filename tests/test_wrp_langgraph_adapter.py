"""P6 optional LangGraph adapter — pure projection + fail-closed compile."""

from __future__ import annotations

import os
from typing import Any

import pytest

from builder_ii.wrp.langgraph_adapter import (
    LANGGRAPH_ENV,
    LANGGRAPH_ENV_VALUE,
    BackendUnavailableError,
    OptionalLangGraphAdapter,
    PureGraphProjection,
    langgraph_opt_in_enabled,
    project_trajectory_graph,
)
from builder_ii.wrp.patterns import sequential_chain


@pytest.fixture(autouse=True)
def _clear_langgraph_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(LANGGRAPH_ENV, raising=False)


def test_pure_projection_always_available() -> None:
    graph = sequential_chain(["a", "b", "c"])
    proj = project_trajectory_graph(graph)
    assert proj["backend"] == "pure_projection"
    assert proj["execution_order"] == ["a", "b", "c"]
    assert proj["entry_point"] == "a"
    assert proj["finish_point"] == "c"
    assert proj["grants_authority"] is False
    assert proj["is_default_runtime"] is False
    assert len(proj["nodes"]) == 3
    assert len(proj["edges"]) == 2


def test_pure_graph_projection_class() -> None:
    adapter = PureGraphProjection()
    assert adapter.name == "pure_projection"
    out = adapter.project(sequential_chain(["x", "y"]))
    assert out["execution_order"] == ["x", "y"]


def test_optional_adapter_project_without_env() -> None:
    adapter = OptionalLangGraphAdapter()
    out = adapter.project(sequential_chain(["m", "g"]))
    assert out["backend"] == "pure_projection"
    assert out["grants_authority"] is False


def test_compile_fail_closed_without_env() -> None:
    adapter = OptionalLangGraphAdapter(compiler=lambda p: {"ok": True})
    with pytest.raises(BackendUnavailableError, match="opt-in only"):
        adapter.compile(sequential_chain(["a", "b"]))


def test_compile_fail_closed_with_env_no_compiler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LANGGRAPH_ENV, LANGGRAPH_ENV_VALUE)
    assert langgraph_opt_in_enabled() is True
    adapter = OptionalLangGraphAdapter()
    # No langgraph package in CI typically; no injected compiler.
    if not adapter.available:
        with pytest.raises(BackendUnavailableError, match="compiler unavailable"):
            adapter.compile(sequential_chain(["a", "b"]))
    else:
        # If somehow langgraph is installed, compile should still not grant authority.
        result = adapter.compile(sequential_chain(["a", "b"]))
        assert result["grants_authority"] is False
        assert result["is_default_runtime"] is False


def test_compile_with_injected_compiler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(LANGGRAPH_ENV, LANGGRAPH_ENV_VALUE)

    def _compiler(projection: dict[str, Any]) -> dict[str, Any]:
        return {"nodes": [n["id"] for n in projection["nodes"]], "research": True}

    adapter = OptionalLangGraphAdapter(compiler=_compiler)
    assert adapter.available is True
    result = adapter.compile(sequential_chain(["a", "b", "c"]))
    assert result["status"] == "compiled_handle"
    assert result["backend"] == "langgraph"
    assert result["grants_authority"] is False
    assert result["projection"]["execution_order"] == ["a", "b", "c"]
    assert result["handle_type"] == "dict"


def test_default_env_not_opt_in() -> None:
    assert LANGGRAPH_ENV not in os.environ or os.environ.get(LANGGRAPH_ENV) != LANGGRAPH_ENV_VALUE
    assert langgraph_opt_in_enabled() is False
