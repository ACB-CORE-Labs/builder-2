from __future__ import annotations

import json as json_lib
from pathlib import Path
import pytest
from typer.testing import CliRunner

from builder_ii.config import load_settings
from builder_ii.session_workflow import (
    create_session_workflow_plan,
    validate_session_workflow_plan,
    validate_session_workflow_plan_file,
    get_prompt_profile,
    prompt_profiles,
    SESSION_WORKFLOW_PLAN_KIND,
)
from builder_ii.session_cli import session_app

runner = CliRunner()


def test_prompt_profiles() -> None:
    profiles = prompt_profiles()
    assert len(profiles) == 3
    names = {p.name for p in profiles}
    assert "generic_default" in names
    assert "builder_default" in names
    assert "core_default" in names

    with pytest.raises(ValueError, match="unknown prompt profile"):
        get_prompt_profile("non_existent")


def test_create_session_workflow_plan_defaults() -> None:
    settings = load_settings()

    # Generic defaults
    plan_generic = create_session_workflow_plan(settings, "generic")
    assert plan_generic["kind"] == SESSION_WORKFLOW_PLAN_KIND
    assert plan_generic["target_profile"]["name"] == "generic"
    assert plan_generic["selected_agent_profile"]["name"] == "repo_mapper"
    assert plan_generic["selected_prompt_profile"]["name"] == "generic_default"
    assert plan_generic["selected_verification_profile"]["name"] == "generic_basic"
    assert not validate_session_workflow_plan(plan_generic)

    # Builder defaults
    plan_builder = create_session_workflow_plan(settings, "builder")
    assert plan_builder["target_profile"]["name"] == "builder"
    assert plan_builder["selected_agent_profile"]["name"] == "context_planner"
    assert plan_builder["selected_prompt_profile"]["name"] == "builder_default"
    assert plan_builder["selected_verification_profile"]["name"] == "builder_fast"
    assert not validate_session_workflow_plan(plan_builder)

    # Core defaults
    plan_core = create_session_workflow_plan(settings, "core")
    assert plan_core["target_profile"]["name"] == "core"
    assert plan_core["selected_agent_profile"]["name"] == "code_reviewer"
    assert plan_core["selected_prompt_profile"]["name"] == "core_default"
    assert plan_core["selected_verification_profile"]["name"] == "core_smoke"
    assert not validate_session_workflow_plan(plan_core)


def test_create_session_workflow_plan_incompatibilities() -> None:
    settings = load_settings()

    # Incompatible agent profile
    with pytest.raises(ValueError, match="is not compatible with target"):
        # Currently agent profiles are compatible with all base targets, but let's test if we force a mismatch.
        # Let's mock or use a verification profile mismatch which is strictly constrained.
        create_session_workflow_plan(settings, "generic", verification_profile_name="builder_fast")

    # Incompatible prompt profile
    with pytest.raises(ValueError, match="is not compatible with target"):
        create_session_workflow_plan(settings, "generic", prompt_profile_name="core_default")

    # Incompatible verification profile
    with pytest.raises(ValueError, match="is not compatible with target"):
        create_session_workflow_plan(settings, "core", verification_profile_name="builder_fast")


def test_validation_functions(tmp_path: Path) -> None:
    settings = load_settings()
    plan = create_session_workflow_plan(settings, "generic")

    # Valid plan
    assert validate_session_workflow_plan(plan) == []

    # Invalid JSON schema format
    assert "session workflow plan must be a JSON object" in validate_session_workflow_plan([])

    # Invalid kind
    bad_plan = plan.copy()
    bad_plan["kind"] = "invalid_kind"
    assert any("kind must be" in e for e in validate_session_workflow_plan(bad_plan))

    # Invalid governance block
    bad_gov = plan.copy()
    bad_gov["governance"] = plan["governance"].copy()
    bad_gov["governance"]["runtime_execution"] = "ENABLED"
    assert any("governance.runtime_execution must be DISABLED" in e for e in validate_session_workflow_plan(bad_gov))

    # File validation
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json_lib.dumps(plan), encoding="utf-8")
    assert validate_session_workflow_plan_file(plan_file) == []

    bad_plan_file = tmp_path / "bad_plan.json"
    bad_plan_file.write_text(json_lib.dumps(bad_gov), encoding="utf-8")
    assert len(validate_session_workflow_plan_file(bad_plan_file)) > 0

    assert any("file not found" in e for e in validate_session_workflow_plan_file(tmp_path / "non_existent.json"))


def test_cli_plan() -> None:
    # Test stdout generation
    result = runner.invoke(session_app, ["plan", "generic"])
    assert result.exit_code == 0
    data = json_lib.loads(result.output)
    assert data["kind"] == SESSION_WORKFLOW_PLAN_KIND
    assert data["target_profile"]["name"] == "generic"

    # Test unknown target profile
    result = runner.invoke(session_app, ["plan", "unknown_target"])
    assert result.exit_code != 0
    assert "target must be one of" in result.output


def test_cli_plan_overrides_and_output(tmp_path: Path) -> None:
    custom_repo = tmp_path / "custom_repo"
    custom_repo.mkdir()
    (custom_repo / "README.md").write_text("custom", encoding="utf-8")
    output_file = tmp_path / "session-plan.json"
    result = runner.invoke(
        session_app,
        [
            "plan",
            "builder",
            "--agent",
            "code_reviewer",
            "--prompt",
            "builder_default",
            "--verification",
            "builder_full",
            "--repo-path",
            str(custom_repo),
            "--output",
            str(output_file),
        ],
    )
    assert result.exit_code == 0
    assert "Session plan written to" in result.output

    # Check written file
    data = json_lib.loads(output_file.read_text(encoding="utf-8"))
    assert data["target_profile"]["name"] == "builder"
    assert data["selected_agent_profile"]["name"] == "code_reviewer"
    assert data["selected_verification_profile"]["name"] == "builder_full"
    assert data["repo_path"] == str(custom_repo.resolve())

    # Validate output file via CLI
    validate_result = runner.invoke(session_app, ["validate", str(output_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.output


def test_cli_validate_error(tmp_path: Path) -> None:
    bad_file = tmp_path / "bad.json"
    bad_file.write_text('{"kind": "builder_ii.session_workflow_plan", "schema_version": 1}', encoding="utf-8")

    result = runner.invoke(session_app, ["validate", str(bad_file)])
    assert result.exit_code != 0
    assert "Validation error" in result.output
