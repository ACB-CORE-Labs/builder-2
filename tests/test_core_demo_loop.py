"""Tests for the CORE target demo loop phase-machine boundary.

The production module intentionally preserves the original public
``run_core_demo_loop(core_repo, output_dir, phase, approve, force,
cleanup_worktree)`` contract. These tests exercise that restored contract and
verify that CORE-specific strings are adapter-owned rather than duplicated
throughout the phase helpers.
"""

from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path

from builder_ii.core_demo_loop import (
    CoreDemoAdapter,
    CoreDemoPaths,
    _reverse_diff_for_marker,
    _unified_diff_for_marker,
    _write_planner,
    create_core_demo_approval,
    create_core_demo_report,
    dumps_core_demo_report,
    run_core_demo_loop,
    validate_core_demo_approval,
    validate_core_demo_planner,
    validate_core_demo_report,
)


def test_run_core_demo_loop_public_signature_is_preserved() -> None:
    sig = inspect.signature(run_core_demo_loop)
    params = sig.parameters
    assert list(params) == [
        "core_repo",
        "output_dir",
        "phase",
        "approve",
        "force",
        "cleanup_worktree",
    ]
    assert params["core_repo"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["output_dir"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["phase"].default == "all"
    assert params["approve"].default is False
    assert params["force"].default is False
    assert params["cleanup_worktree"].default is False


def test_core_demo_adapter_owns_real_lowercase_fields() -> None:
    adapter = CoreDemoAdapter()
    assert adapter.target_name == "core"
    assert adapter.repo_remote_hint == "AssetOverflow/core"
    assert adapter.marker_path == Path("docs/builder_ii_core_demo_marker.md")
    assert "core/cognition/" in adapter.sensitive_modules
    assert adapter.invariant_policy_note
    assert adapter.worktree_source_note
    assert adapter.workbench_coupling == "NONE"
    assert adapter.worktree_description.startswith("AssetOverflow/core")
    assert "AssetOverflow/core" in adapter.task_description


def test_core_demo_adapter_is_data_only() -> None:
    public_methods = [
        name
        for name, _ in inspect.getmembers(CoreDemoAdapter, predicate=inspect.isfunction)
        if not name.startswith("_")
    ]
    assert public_methods == []


def test_diff_helpers_use_adapter_marker_path() -> None:
    adapter = CoreDemoAdapter(marker_path=Path("docs/custom_demo_marker.md"))
    unified = _unified_diff_for_marker(adapter)
    reverse = _reverse_diff_for_marker(adapter)
    assert "docs/custom_demo_marker.md" in unified
    assert "docs/custom_demo_marker.md" in reverse
    assert "docs/builder_ii_core_demo_marker.md" not in unified
    assert "docs/builder_ii_core_demo_marker.md" not in reverse


def test_write_planner_uses_default_adapter_values(tmp_path: Path) -> None:
    paths = CoreDemoPaths(tmp_path)
    worktree = tmp_path / "core-worktree"
    worktree.mkdir()

    planner = _write_planner(paths, worktree, "a" * 64)

    assert paths.planner.is_file()
    assert not validate_core_demo_planner(planner)
    assert planner["target"]["name"] == "core"
    assert planner["target"]["source"] == "AssetOverflow/core temporary detached worktree"
    assert planner["selected_change"]["path"] == "docs/builder_ii_core_demo_marker.md"
    assert planner["core_invariant_policy"]["sensitive_modules_untouched"] == list(
        CoreDemoAdapter().sensitive_modules
    )
    assert planner["governance"]["core_workbench_coupling"] == "NONE"


def test_write_planner_accepts_custom_adapter_without_phase_refactor(tmp_path: Path) -> None:
    paths = CoreDemoPaths(tmp_path)
    worktree = tmp_path / "custom-worktree"
    worktree.mkdir()
    adapter = CoreDemoAdapter(
        target_name="sample",
        repo_remote_hint="Org/sample",
        marker_path=Path("docs/sample_marker.md"),
        sensitive_modules=("sample_sensitive/",),
        invariant_policy_note="sample invariant not exercised",
        worktree_source_note="Org/sample temporary detached worktree",
        workbench_coupling="NONE",
    )

    planner = _write_planner(paths, worktree, "b" * 64, adapter)

    assert planner["target"]["name"] == "sample"
    assert planner["target"]["source"] == "Org/sample temporary detached worktree"
    assert planner["selected_change"]["path"] == "docs/sample_marker.md"
    assert planner["core_invariant_policy"]["sensitive_modules_untouched"] == [
        "sample_sensitive/"
    ]
    assert planner["core_invariant_policy"]["versor_condition_boundary"] == (
        "sample invariant not exercised"
    )


def test_create_core_demo_approval_remains_digest_bound(tmp_path: Path) -> None:
    proposal = {
        "kind": "builder_ii.hitl_patch_proposal",
        "patch_digest": "c" * 64,
    }
    approval = create_core_demo_approval(
        proposal,
        proposal_path=tmp_path / "hitl-patch-proposal.json",
        approved=True,
    )

    assert not validate_core_demo_approval(approval)
    assert approval["patch_digest"] == "c" * 64
    assert approval["proposal_ref"]["sha256"]
    assert approval["grants_runtime_authority"] is False
    assert approval["governance"]["core_workbench_coupling"] == "NONE"
    assert approval["governance"]["source_writes"] == (
        "APPROVED_TEMPORARY_CORE_WORKTREE_PATCH_ONLY"
    )


def test_create_core_demo_report_is_valid_and_serializable(tmp_path: Path) -> None:
    paths = CoreDemoPaths(tmp_path)
    source_repo = tmp_path / "source-core"
    worktree = tmp_path / "core-worktree"
    source_repo.mkdir()
    worktree.mkdir()

    report = create_core_demo_report(
        paths=paths,
        source_repo=source_repo,
        worktree=worktree,
        phase="prepare",
        completed_steps=["preflight recorded"],
        chain_report=None,
        artifact_paths=[],
        ready_for_recording=True,
        next_command="Run the next demo phase explicitly.",
    )

    assert not validate_core_demo_report(report)
    dumped = dumps_core_demo_report(report)
    loaded = json.loads(dumped)
    assert loaded["kind"] == "builder_ii.core_demo_loop_report"
    assert loaded["target"]["name"] == "core"
    assert loaded["governance"]["core_workbench_coupling"] == "NONE"
    assert loaded["report_digest"] == report["report_digest"]


def test_core_demo_adapter_strings_not_duplicated_outside_adapter() -> None:
    """Prevent CORE target details from drifting back into phase helpers."""
    import builder_ii.core_demo_loop as cdl_mod

    source = inspect.getsource(cdl_mod)
    tree = ast.parse(source)

    adapter_class_lines: set[int] = set()
    marker_assign_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "CoreDemoAdapter":
            for child in ast.walk(node):
                if hasattr(child, "lineno"):
                    adapter_class_lines.add(child.lineno)
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_DEMO_MARKER_PATH"
                for target in node.targets
            )
        ):
            for child in ast.walk(node):
                if hasattr(child, "lineno"):
                    marker_assign_lines.add(child.lineno)

    forbidden_outside_adapter = [
        "algebra/",
        "field/",
        "generate/",
        "core/cognition/",
        "vault/",
        "teaching/",
        "calibration/",
        "sensorium/",
        "AssetOverflow/core",
        "builder_ii_core_demo_marker.md",
    ]

    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        lineno = getattr(node, "lineno", -1)
        if lineno in adapter_class_lines or lineno in marker_assign_lines:
            continue
        for forbidden in forbidden_outside_adapter:
            if forbidden in node.value:
                violations.append(
                    f"line {lineno}: {forbidden!r} found outside CoreDemoAdapter/"
                    "_DEMO_MARKER_PATH"
                )

    assert not violations, "\n".join(violations)
