"""
tests/test_deepagents_forge_emit.py

Tests for deepagents_forge_emit.py — governed profile emission safety.
"""

from pathlib import Path

import yaml

from builder_ii.deepagents_forge_emit import HookResult, emit_agent
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
    assert result.profile_written is False
    assert result.written_paths == []
    assert not Path("profiles/deepagents/safe_agent.yaml").exists()
    assert not Path("profiles/deepagents/forge_safe_agent.handoff.json").exists()


def test_emit_writes_only_profiles_deepagents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = emit_agent(_valid_spec(), dry_run=False)

    assert result.ok is True
    profile_path = Path("profiles/deepagents/safe_agent.yaml")
    assert profile_path.exists()
    parsed = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    assert parsed["slug"] == "safe_agent"
    assert parsed["created_at"]
    assert result.profile_written is True
    assert result.handoff_written is True
    assert result.handoff_path == "profiles/deepagents/forge_safe_agent.handoff.json"
    assert result.written_paths == [
        "profiles/deepagents/safe_agent.yaml",
        "profiles/deepagents/forge_safe_agent.handoff.json",
    ]


def test_emit_rejects_path_traversal_slug(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = emit_agent(_valid_spec(slug="../escape"), dry_run=False)

    assert result.ok is False
    assert "slug" in (result.error or "")
    assert not Path("escape.yaml").exists()
    assert not Path("profiles/escape.yaml").exists()


def test_emit_dry_run_invalid_spec_fails_before_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = emit_agent(_valid_spec(capabilities=["run_shell"], hitl_gates=[]), dry_run=True)

    assert result.ok is False
    assert any("before_shell" in blocker for blocker in result.blockers)
    assert not Path("profiles").exists()


def test_emit_reports_optional_hook_failure_without_hiding_profile_write(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    import builder_ii.deepagents_forge_emit as emit_mod

    monkeypatch.setattr(
        emit_mod,
        "register_bridge_spec",
        lambda spec: HookResult("deepagents_bridge.register_forge_spec", "failed", error="boom"),
    )

    result = emit_mod.emit_agent(_valid_spec(), dry_run=False)

    assert result.ok is True
    assert result.profile_written is True
    assert any(hook.status == "failed" for hook in result.hook_results)
    assert any("optional hook failed" in warning for warning in result.warnings)
