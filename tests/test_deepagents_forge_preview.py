"""
tests/test_deepagents_forge_preview.py

Tests for deepagents_forge_preview.py — governance checker and dry-run renderer.
"""

import pytest

from builder_ii.deepagents_forge_schema import DeepAgentSpec
from builder_ii.deepagents_forge_preview import (
    check_governance,
    collect_warnings,
    render_preview,
    render_bridge_spec,
    spec_to_yaml,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_spec(**overrides) -> DeepAgentSpec:
    """Return a fully valid spec that passes all governance checks."""
    spec = DeepAgentSpec(
        name="test_agent",
        slug="test_agent",
        description="A test agent for governance checks.",
        persona="You are an agent that runs tests.",
        target_profile="generic",
        capabilities=["read_files", "run_tests"],
        hitl_gates=["before_shell"],
        verification_profile="default",
        output_artifact="artifacts/test_agent/",
        rollback_path="rollback/test_agent/",
        approval_required=True,
    )
    for k, v in overrides.items():
        setattr(spec, k, v)
    return spec


# ---------------------------------------------------------------------------
# check_governance — passing cases
# ---------------------------------------------------------------------------

class TestCheckGovernancePassing:
    def test_fully_valid_spec_passes(self):
        spec = _valid_spec()
        result = check_governance(spec)
        assert result.all_pass is True
        assert result.failing == []

    def test_no_write_cap_passes_without_before_write(self):
        spec = _valid_spec(capabilities=["read_files"], hitl_gates=[])
        result = check_governance(spec)
        assert result.checks["hitl_for_write"] is True

    def test_no_shell_cap_passes_without_before_shell(self):
        spec = _valid_spec(capabilities=["read_files"], hitl_gates=[])
        result = check_governance(spec)
        assert result.checks["hitl_for_shell"] is True

    def test_write_cap_with_before_write_passes(self):
        spec = _valid_spec(
            capabilities=["write_files"],
            hitl_gates=["before_write"],
        )
        result = check_governance(spec)
        assert result.checks["hitl_for_write"] is True

    def test_shell_cap_with_before_shell_passes(self):
        spec = _valid_spec(
            capabilities=["run_shell"],
            hitl_gates=["before_shell"],
        )
        result = check_governance(spec)
        assert result.checks["hitl_for_shell"] is True


# ---------------------------------------------------------------------------
# check_governance — failing cases
# ---------------------------------------------------------------------------

class TestCheckGovernanceFailing:
    def test_write_cap_without_hitl_fails(self):
        spec = _valid_spec(
            capabilities=["write_files"],
            hitl_gates=[],
        )
        result = check_governance(spec)
        assert result.checks["hitl_for_write"] is False
        assert "hitl_for_write" in result.failing
        assert result.all_pass is False

    def test_shell_cap_without_hitl_fails(self):
        spec = _valid_spec(
            capabilities=["run_shell"],
            hitl_gates=[],
        )
        result = check_governance(spec)
        assert result.checks["hitl_for_shell"] is False
        assert result.all_pass is False

    def test_missing_output_artifact_fails(self):
        spec = _valid_spec(output_artifact="")
        result = check_governance(spec)
        assert result.checks["has_output_artifact"] is False
        assert result.all_pass is False

    def test_missing_rollback_path_fails(self):
        spec = _valid_spec(rollback_path="")
        result = check_governance(spec)
        assert result.checks["has_rollback_path"] is False
        assert result.all_pass is False

    def test_missing_description_fails_docs_check(self):
        spec = _valid_spec(description="")
        result = check_governance(spec)
        assert result.checks["has_docs"] is False
        assert result.all_pass is False

    def test_approval_required_false_fails(self):
        spec = _valid_spec(approval_required=False)
        result = check_governance(spec)
        assert result.checks["approval_boundary"] is False
        assert result.all_pass is False

    def test_missing_verification_profile_fails(self):
        spec = _valid_spec(verification_profile="")
        result = check_governance(spec)
        assert result.checks["has_verification_profile"] is False
        assert result.all_pass is False


# ---------------------------------------------------------------------------
# collect_warnings
# ---------------------------------------------------------------------------

class TestCollectWarnings:
    def test_no_warnings_for_complete_spec(self):
        spec = _valid_spec(
            context_pack="generic_context",
            mcp_tools=["github"],
            hitl_gates=["before_shell", "on_error"],
            description="A fully described agent.",
        )
        warnings = collect_warnings(spec)
        assert warnings == []

    def test_warns_when_no_context_pack(self):
        spec = _valid_spec(context_pack=None)
        warnings = collect_warnings(spec)
        assert any("context pack" in w.lower() for w in warnings)

    def test_warns_when_no_mcp_tools(self):
        spec = _valid_spec(mcp_tools=[])
        warnings = collect_warnings(spec)
        assert any("mcp" in w.lower() for w in warnings)

    def test_warns_when_no_description(self):
        spec = _valid_spec(description="")
        warnings = collect_warnings(spec)
        assert any("description" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# render_bridge_spec
# ---------------------------------------------------------------------------

class TestRenderBridgeSpec:
    def test_contains_required_keys(self):
        spec = _valid_spec()
        bridge = render_bridge_spec(spec)
        for key in ["slug", "name", "persona", "capabilities", "hitl_gates",
                    "verification_profile", "output_artifact", "rollback_path"]:
            assert key in bridge

    def test_values_match_spec(self):
        spec = _valid_spec()
        bridge = render_bridge_spec(spec)
        assert bridge["slug"] == spec.slug
        assert bridge["capabilities"] == spec.capabilities


# ---------------------------------------------------------------------------
# render_preview
# ---------------------------------------------------------------------------

class TestRenderPreview:
    def test_returns_forge_preview(self):
        from builder_ii.deepagents_forge_preview import ForgePreview
        spec = _valid_spec()
        preview = render_preview(spec)
        assert isinstance(preview, ForgePreview)

    def test_preview_has_yaml(self):
        spec = _valid_spec()
        preview = render_preview(spec)
        assert "test_agent" in preview.yaml_preview

    def test_preview_has_governance_check(self):
        spec = _valid_spec()
        preview = render_preview(spec)
        assert preview.governance_check is not None

    def test_preview_governance_passes_for_valid_spec(self):
        spec = _valid_spec()
        preview = render_preview(spec)
        assert preview.governance_check.all_pass is True

    def test_preview_lists_exact_bounded_files(self):
        spec = _valid_spec()
        preview = render_preview(spec)
        assert "profiles/deepagents/test_agent.yaml" in preview.files_to_write
        assert "profiles/deepagents/forge_test_agent.handoff.json" in preview.files_to_write

    def test_preview_reports_runtime_not_promoted(self):
        spec = _valid_spec()
        preview = render_preview(spec)
        assert "runtime disabled" in preview.runtime_status
        assert "promotion not granted" in preview.runtime_status

    def test_preview_exposes_validation_blockers(self):
        spec = _valid_spec(slug="../escape")
        preview = render_preview(spec)
        assert preview.governance_check.all_pass is False
        assert any("slug" in blocker for blocker in preview.blockers)
