"""tests/test_core_demo_loop.py

Tests for the CORE target demo loop and CoreDemoAdapter boundary.

Coverage
--------
1. CoreDemoAdapter owns all CORE-specific strings
2. GenericTargetDemoLoop base contract
3. CoreTargetDemoLoop step execution
4. run_core_demo_loop() public entry-point
5. Governance block completeness
6. Adapter boundary guard — CORE-specific strings are adapter-owned

Governance
----------
* No model execution.
* No commit/push authority.
* No shell execution.
* Pure unit tests using temporary directories.
"""

from __future__ import annotations

import inspect
import uuid
from pathlib import Path

import pytest

from builder_ii.core_demo_loop import (
    CoreDemoAdapter,
    CoreTargetDemoLoop,
    DemoLoopResult,
    DemoStepResult,
    GenericTargetDemoLoop,
    TargetDemoContext,
    run_core_demo_loop,
)


# ===========================================================================
# Helpers
# ===========================================================================


def _make_ctx(repo_path: Path, dry_run: bool = True) -> TargetDemoContext:
    return TargetDemoContext(
        target_name="core",
        target_repo=repo_path,
        session_id=str(uuid.uuid4()),
        dry_run=dry_run,
    )


def _make_valid_core_repo(tmp_path: Path) -> Path:
    """Create a minimal directory that passes CoreDemoAdapter.validate_repo."""
    repo = tmp_path / "core"
    repo.mkdir()
    (repo / "Cargo.toml").write_text("[package]\nname = \"core\"\n")
    return repo


# ===========================================================================
# 1. CoreDemoAdapter — string ownership
# ===========================================================================


class TestCoreDemoAdapterStringOwnership:
    def test_adapter_owns_target_name(self):
        a = CoreDemoAdapter()
        assert a.TARGET_NAME == "core"

    def test_adapter_owns_invariant_marker_prefix(self):
        a = CoreDemoAdapter()
        assert a.INVARIANT_MARKER_PREFIX  # non-empty
        assert "CORE" in a.INVARIANT_MARKER_PREFIX

    def test_adapter_owns_repo_validation_marker(self):
        a = CoreDemoAdapter()
        assert a.REPO_VALIDATION_MARKER  # non-empty string

    def test_adapter_owns_governance_note(self):
        a = CoreDemoAdapter()
        assert "adapter" in a.GOVERNANCE_NOTE.lower() or "CORE" in a.GOVERNANCE_NOTE

    def test_governance_block_structure(self):
        a = CoreDemoAdapter()
        block = a.governance_block()
        assert block["no_model_execution"] is True
        assert block["no_commit_push"] is True
        assert block["source_checkout_untouched"] is True
        assert block["temporary_worktree_requires_explicit_approval"] is True


# ===========================================================================
# 2. Repository validation
# ===========================================================================


class TestCoreDemoAdapterValidation:
    def test_missing_repo_fails(self, tmp_path):
        a = CoreDemoAdapter()
        ok, detail = a.validate_repo(tmp_path / "nonexistent")
        assert not ok
        assert "not exist" in detail

    def test_repo_without_marker_fails(self, tmp_path):
        repo = tmp_path / "core"
        repo.mkdir()
        a = CoreDemoAdapter()
        ok, detail = a.validate_repo(repo)
        assert not ok
        assert a.REPO_VALIDATION_MARKER in detail

    def test_valid_repo_passes(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        a = CoreDemoAdapter()
        ok, detail = a.validate_repo(repo)
        assert ok
        assert str(repo) in detail


# ===========================================================================
# 3. CoreTargetDemoLoop steps
# ===========================================================================


class TestCoreTargetDemoLoopSteps:
    def test_validate_repo_step_passes_valid_repo(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        loop = CoreTargetDemoLoop()
        ctx = _make_ctx(repo)
        result = loop._step_validate_repo(ctx)
        assert result.passed

    def test_validate_repo_step_fails_missing_repo(self, tmp_path):
        loop = CoreTargetDemoLoop()
        ctx = _make_ctx(tmp_path / "nonexistent")
        result = loop._step_validate_repo(ctx)
        assert not result.passed

    def test_check_governance_step_passes(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        loop = CoreTargetDemoLoop()
        ctx = _make_ctx(repo)
        result = loop._step_check_governance(ctx)
        assert result.passed

    def test_emit_context_artifact_step_passes(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        loop = CoreTargetDemoLoop()
        ctx = _make_ctx(repo)
        result = loop._step_emit_context_artifact(ctx)
        assert result.passed
        import json
        artifact = json.loads(result.detail)
        assert artifact["target"] == "core"
        assert artifact["governance"]["no_model_execution"] is True

    def test_full_loop_passes_valid_repo(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        loop = CoreTargetDemoLoop()
        ctx = _make_ctx(repo)
        result = loop.run(ctx)
        assert result.all_passed
        assert result.target_name == "core"

    def test_full_loop_fails_invalid_repo(self, tmp_path):
        loop = CoreTargetDemoLoop()
        ctx = _make_ctx(tmp_path / "nonexistent")
        result = loop.run(ctx)
        assert not result.all_passed
        assert result.steps[0].step_name == "validate_repo"
        assert not result.steps[0].passed


# ===========================================================================
# 4. Public entry-point
# ===========================================================================


class TestRunCoreDemoLoopPublicAPI:
    def test_returns_demo_loop_result(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        result = run_core_demo_loop(target_repo=repo, dry_run=True)
        assert isinstance(result, DemoLoopResult)

    def test_governance_block_present(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        result = run_core_demo_loop(target_repo=repo)
        assert result.governance_block["no_model_execution"] is True
        assert result.governance_block["no_commit_push"] is True

    def test_accepts_custom_session_id(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        sid = "test-session-abc"
        result = run_core_demo_loop(target_repo=repo, session_id=sid)
        assert result.session_id == sid

    def test_as_dict_structure(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        result = run_core_demo_loop(target_repo=repo)
        d = result.as_dict()
        assert "target_name" in d
        assert "all_passed" in d
        assert "governance_block" in d
        assert isinstance(d["steps"], list)


# ===========================================================================
# 5. Governance block completeness
# ===========================================================================


class TestGovernanceBlockCompleteness:
    REQUIRED_GOVERNANCE_KEYS = {
        "no_model_execution",
        "no_commit_push",
        "source_checkout_untouched",
        "temporary_worktree_requires_explicit_approval",
    }

    def test_adapter_governance_block_has_required_keys(self):
        a = CoreDemoAdapter()
        block = a.governance_block()
        for key in self.REQUIRED_GOVERNANCE_KEYS:
            assert key in block, f"Missing governance key: {key}"
            assert block[key] is True, f"Governance key '{key}' must be True"

    def test_loop_governance_block_has_required_keys(self, tmp_path):
        repo = _make_valid_core_repo(tmp_path)
        result = run_core_demo_loop(target_repo=repo)
        for key in self.REQUIRED_GOVERNANCE_KEYS:
            assert key in result.governance_block


# ===========================================================================
# 6. Adapter boundary guard
# ===========================================================================


class TestCoreDemoAdapterBoundaryGuard:
    """Structural tests proving CORE-specific strings are adapter-owned."""

    @staticmethod
    def _get_module_source(mod) -> str:
        return inspect.getsource(mod)

    def test_core_specific_strings_in_adapter_not_generic_loop(self):
        """CORE_INVARIANT and Cargo.toml must live in CoreDemoAdapter, not in
        GenericTargetDemoLoop."""
        generic_src = inspect.getsource(GenericTargetDemoLoop)
        assert "CORE_INVARIANT" not in generic_src
        assert "Cargo.toml" not in generic_src

    def test_adapter_is_injected_not_hardcoded_in_loop(self):
        """CoreTargetDemoLoop must accept an adapter parameter."""
        import inspect as _inspect
        sig = _inspect.signature(CoreTargetDemoLoop.__init__)
        assert "adapter" in sig.parameters

    def test_generic_loop_has_no_core_strings(self):
        import builder_ii.core_demo_loop as cdl_mod
        generic_src = inspect.getsource(GenericTargetDemoLoop)
        core_specific = ["core.patch_planner", "CORE Workbench", "AssetOverflow/core"]
        for s in core_specific:
            assert s not in generic_src, (
                f"GenericTargetDemoLoop source contains CORE-specific string: {s!r}"
            )
