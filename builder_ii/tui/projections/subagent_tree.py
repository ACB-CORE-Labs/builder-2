"""Projection: the deepagents subagent tree (T3).

Observe-only. Scans for ``deepagents_runtime_envelope`` artifacts and the
``deepagents_subagent_execution_receipt`` artifacts they reference, and projects them into a
tree: a run -> its subagents, and -- where a subagent's result is itself a child run
envelope -- that subagent's own subagents. This is the "deepagents as a subagent that has its
own subagents" structure, rendered from artifacts on disk. Synthesizes nothing: no
envelopes yields an empty tree.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    DEEPAGENTS_RUNTIME_ENVELOPE_KIND,
    DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND,
)


@dataclass(frozen=True)
class SubagentNode:
    profile: str
    receipt_state: str
    children: tuple["SubagentNode", ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SubagentRun:
    session_id: str
    envelope_state: str
    subagents: tuple[SubagentNode, ...]

    @property
    def subagent_count(self) -> int:
        return len(self.subagents)


@dataclass(frozen=True)
class SubagentTreeView:
    runs: tuple[SubagentRun, ...]

    @property
    def is_empty(self) -> bool:
        return not self.runs


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _ref_path(ref: Any) -> str | None:
    if isinstance(ref, dict):
        path = ref.get("path")
        if isinstance(path, str) and path:
            return path
    return None


def _build_node(
    receipt: dict[str, Any],
    envelopes_by_path: dict[str, dict[str, Any]],
    receipts_by_path: dict[str, dict[str, Any]],
    visited: set[str],
) -> SubagentNode:
    # A subagent whose result_ref points at a child run envelope carries its own subagents.
    children: tuple[SubagentNode, ...] = ()
    child_path = _ref_path(receipt.get("result_ref"))
    if child_path and child_path in envelopes_by_path and child_path not in visited:
        children = _run_subagents(
            envelopes_by_path[child_path], envelopes_by_path, receipts_by_path, visited | {child_path}
        )
    return SubagentNode(
        profile=str(receipt.get("subagent_profile") or "?"),
        receipt_state=str(receipt.get("receipt_state") or ""),
        children=children,
    )


def _run_subagents(
    envelope: dict[str, Any],
    envelopes_by_path: dict[str, dict[str, Any]],
    receipts_by_path: dict[str, dict[str, Any]],
    visited: set[str],
) -> tuple[SubagentNode, ...]:
    nodes: list[SubagentNode] = []
    for ref in envelope.get("execution_receipt_refs") or []:
        rpath = _ref_path(ref)
        receipt = receipts_by_path.get(rpath) if rpath else None
        if isinstance(receipt, dict):
            nodes.append(_build_node(receipt, envelopes_by_path, receipts_by_path, visited))
    return tuple(nodes)


def project_subagent_tree(builder_root: Path | None) -> SubagentTreeView:
    """Project deepagents run envelopes + subagent receipts under ``builder_root`` into trees."""
    if builder_root is None or not builder_root.is_dir():
        return SubagentTreeView(runs=())

    envelopes_by_path: dict[str, dict[str, Any]] = {}
    receipts_by_path: dict[str, dict[str, Any]] = {}
    for path in builder_root.rglob("*.json"):
        data = _read_json(path)
        if data is None:
            continue
        kind = data.get("kind")
        if kind == DEEPAGENTS_RUNTIME_ENVELOPE_KIND:
            envelopes_by_path[str(path)] = data
        elif kind == DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND:
            receipts_by_path[str(path)] = data

    # A run envelope is a root unless another envelope's subagent result points at it (a child).
    child_paths: set[str] = set()
    for env in envelopes_by_path.values():
        for ref in env.get("execution_receipt_refs") or []:
            rpath = _ref_path(ref)
            receipt = receipts_by_path.get(rpath) if rpath else None
            if isinstance(receipt, dict):
                cpath = _ref_path(receipt.get("result_ref"))
                if cpath and cpath in envelopes_by_path:
                    child_paths.add(cpath)

    runs: list[SubagentRun] = []
    for epath, env in sorted(envelopes_by_path.items()):
        if epath in child_paths:
            continue  # rendered under its parent, not as a root
        runs.append(
            SubagentRun(
                session_id=str(env.get("session_id") or ""),
                envelope_state=str(env.get("envelope_state") or ""),
                subagents=_run_subagents(env, envelopes_by_path, receipts_by_path, {epath}),
            )
        )
    return SubagentTreeView(runs=tuple(runs))
