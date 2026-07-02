"""
tests/test_deepagents_forge_schema.py

Tests for deepagents_forge_schema.py — DeepAgentSpec dataclass and helpers.
"""

import yaml
import pytest

from builder_ii.deepagents_forge_schema import DeepAgentSpec, derive_slug


# ---------------------------------------------------------------------------
# derive_slug
# ---------------------------------------------------------------------------

class TestDeriveSlug:
    def test_basic(self):
        assert derive_slug("PR Reviewer") == "pr_reviewer"

    def test_already_snake(self):
        assert derive_slug("my_agent") == "my_agent"

    def test_hyphens_and_spaces(self):
        assert derive_slug("My-Cool Agent!") == "my_cool_agent_"

    def test_leading_trailing_underscores_stripped(self):
        result = derive_slug("  agent  ")
        assert result == "agent"

    def test_numbers_preserved(self):
        assert derive_slug("agent_v2") == "agent_v2"

    def test_empty_string(self):
        assert derive_slug("") == ""


# ---------------------------------------------------------------------------
# DeepAgentSpec construction
# ---------------------------------------------------------------------------

class TestDeepAgentSpecConstruction:
    def test_default_construction(self):
        spec = DeepAgentSpec()
        assert spec.name == ""
        assert spec.slug == ""
        assert spec.target_profile == "generic"
        assert spec.approval_required is True
        assert spec.schema_version == "1.0"
        assert spec.capabilities == []
        assert spec.hitl_gates == []
        assert spec.mcp_tools == []
        assert spec.memory_routes == []

    def test_custom_construction(self):
        spec = DeepAgentSpec(
            name="test_agent",
            slug="test_agent",
            persona="You are an agent that runs tests.",
            target_profile="builder",
        )
        assert spec.name == "test_agent"
        assert spec.target_profile == "builder"


# ---------------------------------------------------------------------------
# auto_derive_slug
# ---------------------------------------------------------------------------

class TestAutoSlug:
    def test_derives_from_name(self):
        spec = DeepAgentSpec(name="PR Reviewer")
        spec.auto_derive_slug()
        assert spec.slug == "pr_reviewer"

    def test_does_not_overwrite_existing_slug(self):
        spec = DeepAgentSpec(name="PR Reviewer", slug="custom_slug")
        spec.auto_derive_slug()
        assert spec.slug == "custom_slug"

    def test_no_name_no_slug(self):
        spec = DeepAgentSpec()
        spec.auto_derive_slug()
        assert spec.slug == ""


# ---------------------------------------------------------------------------
# is_emit_ready
# ---------------------------------------------------------------------------

class TestIsEmitReady:
    def _full_spec(self) -> DeepAgentSpec:
        return DeepAgentSpec(
            name="test_agent",
            slug="test_agent",
            persona="You are an agent that does testing.",
            verification_profile="default",
            output_artifact="artifacts/test_agent/",
            rollback_path="rollback/test_agent/",
        )

    def test_returns_false_when_empty(self):
        spec = DeepAgentSpec()
        ready, missing = spec.is_emit_ready()
        assert ready is False
        assert len(missing) > 0

    def test_returns_false_missing_persona(self):
        spec = self._full_spec()
        spec.persona = ""
        ready, missing = spec.is_emit_ready()
        assert ready is False
        assert "persona" in missing

    def test_returns_false_missing_output_artifact(self):
        spec = self._full_spec()
        spec.output_artifact = ""
        ready, missing = spec.is_emit_ready()
        assert ready is False
        assert "output_artifact" in missing

    def test_returns_false_missing_rollback_path(self):
        spec = self._full_spec()
        spec.rollback_path = ""
        ready, missing = spec.is_emit_ready()
        assert ready is False
        assert "rollback_path" in missing

    def test_returns_true_all_required_present(self):
        spec = self._full_spec()
        ready, missing = spec.is_emit_ready()
        assert ready is True
        assert missing == []

    def test_whitespace_only_counts_as_missing(self):
        spec = self._full_spec()
        spec.persona = "   "
        ready, missing = spec.is_emit_ready()
        assert ready is False
        assert "persona" in missing


# ---------------------------------------------------------------------------
# to_yaml
# ---------------------------------------------------------------------------

class TestToYaml:
    def test_produces_valid_yaml(self):
        spec = DeepAgentSpec(
            name="yaml_agent",
            slug="yaml_agent",
            persona="You are an agent that validates YAML.",
        )
        result = spec.to_yaml()
        parsed = yaml.safe_load(result)
        assert isinstance(parsed, dict)
        assert parsed["name"] == "yaml_agent"
        assert parsed["slug"] == "yaml_agent"

    def test_no_private_fields_in_yaml(self):
        spec = DeepAgentSpec()
        result = spec.to_yaml()
        assert "_REQUIRED_FIELDS" not in result

    def test_lists_preserved(self):
        spec = DeepAgentSpec(
            name="cap_agent",
            slug="cap_agent",
            capabilities=["read_files", "run_tests"],
            hitl_gates=["before_write"],
        )
        parsed = yaml.safe_load(spec.to_yaml())
        assert parsed["capabilities"] == ["read_files", "run_tests"]
        assert parsed["hitl_gates"] == ["before_write"]


# ---------------------------------------------------------------------------
# summary_lines
# ---------------------------------------------------------------------------

class TestSummaryLines:
    def test_empty_spec_returns_empty(self):
        spec = DeepAgentSpec()
        assert spec.summary_lines() == []

    def test_name_appears_in_summary(self):
        spec = DeepAgentSpec(name="my_agent", slug="my_agent")
        lines = spec.summary_lines()
        assert any("my_agent" in line for line in lines)

    def test_long_persona_truncated(self):
        spec = DeepAgentSpec(
            name="a",
            persona="x" * 100,
        )
        lines = spec.summary_lines()
        persona_line = next((l for l in lines if "persona" in l), None)
        assert persona_line is not None
        assert len(persona_line) < 120  # truncated
