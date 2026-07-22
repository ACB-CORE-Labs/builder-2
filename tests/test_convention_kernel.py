"""Tests for Convention Layer Kernel per Issue #115."""

import pytest

from builder_ii.governance.authority.convention_kernel import (
    AuthorityMode,
    ConventionKernel,
    GooseNativeProjection,
    GovernanceBlock,
    ResolvedSessionSpine,
)


def test_governance_block_is_safe_for_projection():
    block = GovernanceBlock(
        runtime_execution="DISABLED",
        model_execution="DISABLED",
        artifact_is_authority=False,
    )
    assert block.is_safe_for_projection() is True


def test_governance_block_rejects_authority():
    block = GovernanceBlock(artifact_is_authority=True)
    assert block.is_safe_for_projection() is False


def test_resolve_spine_basic():
    kernel = ConventionKernel()
    spine = kernel.resolve_spine(
        target_profile="generic",
        repo_path=".",
        agent_profile="default",
    )
    assert spine.target_profile == "generic"
    assert spine.authority_mode == AuthorityMode.PLANNED_ONLY
    assert spine.governance.is_safe_for_projection()


def test_project_to_goose_safe():
    kernel = ConventionKernel()
    spine = kernel.resolve_spine("generic", ".", "default")
    projection = kernel.project_to_goose(spine)
    assert isinstance(projection, GooseNativeProjection)
    assert projection.governance.is_safe_for_projection()


def test_project_to_goose_rejects_unsafe_governance():
    kernel = ConventionKernel()
    # Manually create unsafe spine
    unsafe_governance = GovernanceBlock(artifact_is_authority=True)
    spine = ResolvedSessionSpine(
        target_profile="generic",
        repo_path=".",
        agent_profile="default",
        prompt_profile=None,
        verification_profile="default",
        authority_mode=AuthorityMode.PLANNED_ONLY,
        context_pack_ref=None,
        model_policy={},
        goose_projection_policy={},
        governance=unsafe_governance,
    )
    with pytest.raises(ValueError, match="safe projection"):
        kernel.project_to_goose(spine)


def test_spine_validation_fails_on_authority():
    unsafe_governance = GovernanceBlock(artifact_is_authority=True)
    spine = ResolvedSessionSpine(
        target_profile="generic",
        repo_path=".",
        agent_profile="default",
        prompt_profile=None,
        verification_profile="default",
        authority_mode=AuthorityMode.PLANNED_ONLY,
        context_pack_ref=None,
        model_policy={},
        goose_projection_policy={},
        governance=unsafe_governance,
    )
    errors = spine.validate()
    assert any("artifact_is_authority" in e for e in errors)
