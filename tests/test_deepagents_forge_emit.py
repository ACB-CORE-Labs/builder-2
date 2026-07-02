"""
tests/test_deepagents_forge_emit.py

Tests for deepagents_forge_emit.py — governed profile emission safety.
"""

from pathlib import Path

import yaml

from builder_ii.deepagents_forge_emit import emit_agent
from builder_ii.deepagents_forge_schema import DeepAgentSpec


def _valid_spec(**overrides) -> DeepAgentSpec:
    spec = DeepAgentSpec(
        name="safe agent",
        slug="safe_agent",
        description="A safe test agent.",
        persona="You are an agent that prepares governed test artifacts.",
        target_profile="generic",
        capabilities=["read_files"],
        hitl_gates=[],
        verification_profile="default",
        output_artifact="artifacts/safe_agent/",
        rollback_path="rollback/safe_agent/",
        approval_required=True,
    )
    for key, value in overrides.items():
        setattr(spec, key, value)
    return spec


def test_emit_dry_run_has_no_side_effects(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = emit_agent(_valid_spec(), dry_run=True)

    assert result.ok is True
    assert result.dry_run is True
    assert result.profile_path == "profiles/deepagents/safe_agent.yaml"
    assert not Path("profiles/deepagents/safe_agent.yaml").exists()


def test_emit_writes_only_profiles_deepagents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = emit_agent(_valid_spec(), dry_run=False)

    assert result.ok is True
    profile_path = Path("profiles/deepagents/safe_agent.yaml")
    assert profile_path.exists()
    parsed = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    assert parsed["slug"] == "safe_agent"
    assert parsed["created_at"]


def test_emit_rejects_path_traversal_slug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = emit_agent(_valid_spec(slug="../escape"), dry_run=False)

    assert result.ok is False
    assert "slug" in (result.error or "")
    assert not Path("escape.yaml").exists()
    assert not Path("profiles/escape.yaml").exists()
