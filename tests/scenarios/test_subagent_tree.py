"""T3 — deepagents subagent tree projection + cockpit rendering.

A run envelope's subagent receipts form the tree; a subagent whose result_ref points at a
child run envelope carries that child's subagents (the "subagent with its own subagents"
recursion). Observe-only. Fixtures use the real deepagents constructors.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from builder_ii.adapters.deepagents.deepagents_runtime import (
    create_deepagents_runtime_envelope,
    create_deepagents_subagent_execution_receipt,
)
from builder_ii.adapters.deepagents.deepagents_work_artifacts import (
    DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND,
)
from builder_ii.tui.app import StratumApp
from builder_ii.tui.projections.subagent_tree import project_subagent_tree
from builder_ii.tui.widgets.stratum import StratumMode


def _ref(path: Path, *, kind: str = "builder_ii.ref", role: str = "ref") -> dict:
    return {"kind": kind, "path": str(path), "sha256": "0" * 64, "role": role, "name": role, "required": True}


def _write(path: Path, data: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def _make_flat_run(art: Path, session_id: str, profiles: tuple[str, ...]) -> None:
    receipt_refs = []
    for i, profile in enumerate(profiles):
        receipt = create_deepagents_subagent_execution_receipt(
            profile, _ref(art / f"assign-{session_id}-{i}.json"), _ref(art / f"result-{session_id}-{i}.json")
        )
        rp = _write(art / f"receipt-{session_id}-{i}.json", receipt)
        receipt_refs.append(_ref(rp, kind=DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND, role="receipt"))
    env = create_deepagents_runtime_envelope(session_id, _ref(art / f"plan-{session_id}.json"), receipt_refs)
    _write(art / f"envelope-{session_id}.json", env)


def test_tree_empty_without_envelopes(tmp_path: Path) -> None:
    assert project_subagent_tree(tmp_path).is_empty
    assert project_subagent_tree(None).is_empty


def test_flat_run_projects_its_subagents(tmp_path: Path) -> None:
    _make_flat_run(tmp_path / "artifacts", "run-flat", ("explorer", "implementer"))
    view = project_subagent_tree(tmp_path)
    assert len(view.runs) == 1
    run = view.runs[0]
    assert run.session_id == "run-flat"
    assert {n.profile for n in run.subagents} == {"explorer", "implementer"}
    assert all(not n.children for n in run.subagents)


def test_nested_run_projects_subagents_of_subagents(tmp_path: Path) -> None:
    art = tmp_path / "artifacts"
    # Child run with one leaf subagent.
    child_receipt = create_deepagents_subagent_execution_receipt("leaf", _ref(art / "ca.json"), _ref(art / "cr.json"))
    crp = _write(art / "child-receipt.json", child_receipt)
    child_env = create_deepagents_runtime_envelope(
        "child-run",
        _ref(art / "cplan.json"),
        [_ref(crp, kind=DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND, role="receipt")],
    )
    cep = _write(art / "child-envelope.json", child_env)

    # Parent run whose single subagent's result IS the child run envelope.
    parent_receipt = create_deepagents_subagent_execution_receipt(
        "orchestrator",
        _ref(art / "pa.json"),
        _ref(cep),  # result_ref -> child envelope
    )
    prp = _write(art / "parent-receipt.json", parent_receipt)
    parent_env = create_deepagents_runtime_envelope(
        "parent-run",
        _ref(art / "pplan.json"),
        [_ref(prp, kind=DEEPAGENTS_SUBAGENT_EXECUTION_RECEIPT_KIND, role="receipt")],
    )
    _write(art / "parent-envelope.json", parent_env)

    view = project_subagent_tree(tmp_path)
    # Only the parent is a root; the child is rendered under it.
    assert [r.session_id for r in view.runs] == ["parent-run"]
    root = view.runs[0]
    assert len(root.subagents) == 1
    orchestrator = root.subagents[0]
    assert orchestrator.profile == "orchestrator"
    assert [c.profile for c in orchestrator.children] == ["leaf"]


@pytest.mark.asyncio
async def test_cockpit_surfaces_the_subagent_tree(tmp_path: Path) -> None:
    _make_flat_run(tmp_path / ".builder" / "artifacts", "run-x", ("explorer",))
    with patch("builder_ii.tui.app.load_settings") as mock_settings:
        mock_settings.return_value.target_repo.name = "test"
        mock_settings.return_value.model_alias = "test"
        mock_settings.return_value.model_tier = "primary"
        mock_settings.return_value.backend = "test"
        mock_settings.return_value.project_root = tmp_path
        app = StratumApp(show_splash=False, skip_guide=True)

    async with app.run_test(headless=True) as pilot:
        await pilot.press("l")
        await pilot.pause()
        assert app.stratum is not None
        assert app.stratum.mode == StratumMode.RUN_COCKPIT
        tree = project_subagent_tree(app.stratum._builder_root())
        assert not tree.is_empty
        assert tree.runs[0].session_id == "run-x"
