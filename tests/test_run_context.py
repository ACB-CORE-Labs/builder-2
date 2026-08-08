from __future__ import annotations

from pathlib import Path

import pytest

from builder_ii.adapters.goose.run_context import RunContext


def test_default_run_ids_are_collision_resistant(tmp_path: Path) -> None:
    first = RunContext.create(target_root=tmp_path)
    second = RunContext.create(target_root=tmp_path)

    assert first.run_id != second.run_id
    assert first.session_id != second.session_id
    assert first.session_id == f"goose_{first.run_id}"
    assert first.builder_root == tmp_path.resolve() / ".builder"


def test_explicit_builder_root_is_preserved(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    evidence = tmp_path / "evidence"

    context = RunContext.create(
        target_root=target,
        builder_root=evidence,
        run_id="deterministic-test-run",
    )

    assert context.run_id == "deterministic-test-run"
    assert context.session_id == "goose_deterministic-test-run"
    assert context.target_root == target.resolve()
    assert context.builder_root == evidence.resolve()


@pytest.mark.parametrize("bad", ["", "../escape", "a/b", "a b", "run:1"])
def test_run_id_is_path_safe(tmp_path: Path, bad: str) -> None:
    with pytest.raises(ValueError):
        RunContext.create(target_root=tmp_path, run_id=bad)
