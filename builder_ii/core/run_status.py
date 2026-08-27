"""Deterministic status projection over the governed run registry.

This module performs no writes, launches no process, and grants no authority.
It is shared by the root CLI, the Run Lens, and future inspection adapters.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from builder_ii.core.run_registry import RunRegistryEntry, RunRegistryView, project_run_registry
from builder_ii.core.run_view import RunView, project_run_view


class RunSelectionError(ValueError):
    """An explicit run id did not resolve; no fallback selection is allowed."""


@dataclass(frozen=True)
class RunStatusView:
    artifact_root: Path
    registry: RunRegistryView
    selected: RunRegistryEntry | None
    run: RunView | None

    @property
    def has_run(self) -> bool:
        return self.selected is not None and self.run is not None

    @property
    def is_corrupt(self) -> bool:
        return bool(
            self.selected is not None
            and (self.selected.chain_valid is not True or (self.run and self.run.evidence_health == "CORRUPT"))
        )

    def to_jsonable(self) -> dict[str, Any]:
        return {
            "artifact_is_authority": False,
            "artifact_root": str(self.artifact_root),
            "grants_authority": False,
            "kind": "builder_ii.run_status_view",
            "registry": self.registry.to_jsonable(),
            "run": self.run.to_jsonable() if self.run is not None else None,
            "schema_version": 1,
            "selected_run_id": self.selected.run_id if self.selected is not None else None,
        }


def project_run_status(artifact_root: Path, requested_run_id: str | None = None) -> RunStatusView:
    """Project an exact run, or deterministically select the most recent run."""
    root = artifact_root.resolve(strict=False)
    registry = project_run_registry(root)
    selected = registry.select(requested_run_id)
    if requested_run_id is not None and selected is None:
        raise RunSelectionError(f"run not found in the admitted artifact root: {requested_run_id}")
    run = project_run_view(root, session_id=selected.run_id) if selected is not None else None
    return RunStatusView(artifact_root=root, registry=registry, selected=selected, run=run)


def render_run_status(view: RunStatusView) -> str:
    """Render the calm five-question operator grammar without ANSI dependency."""
    if not view.has_run:
        return "NO RUN\nnext: builder start --task \"...\"\nproof: no ledgered run exists"

    assert view.selected is not None
    assert view.run is not None
    run = view.run
    chain = "valid" if view.selected.chain_valid is True else "CORRUPT"
    attention_items = (*view.selected.errors, *run.attention_items)
    attention = "; ".join(attention_items) if attention_items else "none"
    goal = run.goal or "not recorded in validated run evidence"
    return "\n".join(
        (
            f"RUN {view.selected.run_id} | {run.canonical_stage} | evidence {run.evidence_health}",
            f"goal: {goal}",
            f"now: {run.activity_label}",
            f"needs-you: {attention}",
            f"next: {run.recommended_action or 'none'}",
            f"proof: ledger {chain}; {view.selected.event_count} validated chain record(s)",
        )
    )
