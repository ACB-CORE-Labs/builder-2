from pathlib import Path
from types import SimpleNamespace

from builder_ii.agent_profiles import (
    agent_profile_names,
    agent_profiles,
    get_agent_profile,
    profiles_for_target,
    render_agent_profile,
    validate_agent_profiles,
)
from builder_ii.target_profiles import target_profile

BASE_AGENT_PROFILES = (
    "repo_mapper",
    "context_planner",
    "code_reviewer",
    "patch_planner",
    "verification_planner",
    "handoff_scribe",
)

CORE_AGENT_PROFILES = (
    "core.invariant_auditor",
    "core.patch_planner",
    "core.verification_planner",
)


def _settings(tmp_path: Path):
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("core", encoding="utf-8")
    (builder / "README.md").write_text("builder", encoding="utf-8")
    return SimpleNamespace(core_repo=core, project_root=builder)


def test_agent_profile_names_are_generic_base_profiles() -> None:
    assert agent_profile_names() == (*BASE_AGENT_PROFILES, *CORE_AGENT_PROFILES)


def test_all_profiles_forbid_shell_and_mutation_by_default() -> None:
    for profile in agent_profiles():
        assert "execute_shell" in profile.forbidden_tools
        assert "commit" in profile.forbidden_tools
        assert "push" in profile.forbidden_tools


def test_base_profiles_support_all_initial_targets() -> None:
    for profile in agent_profiles():
        if profile.name in BASE_AGENT_PROFILES:
            assert profile.compatible_targets == ("generic", "builder", "core")
        else:
            assert profile.compatible_targets == ("core",)


def test_profiles_for_target_returns_generic_profiles() -> None:
    assert {profile.name for profile in profiles_for_target("builder")} == set(BASE_AGENT_PROFILES)
    assert {profile.name for profile in profiles_for_target("core")} == set(agent_profile_names())


def test_validate_agent_profiles_passes() -> None:
    assert validate_agent_profiles() == ()


def test_patch_planner_is_proposal_only() -> None:
    profile = get_agent_profile("patch_planner")

    assert profile.authority == "proposal_only"
    assert "applying patches" in profile.hitl_required_for
    assert "write_file" in profile.forbidden_tools


def test_render_agent_profile_without_target() -> None:
    rendered = render_agent_profile(get_agent_profile("repo_mapper"))

    assert "# Agent profile: repo_mapper" in rendered
    assert "## Authority" in rendered
    assert "## Output contract" in rendered


def test_render_agent_profile_with_target(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    rendered = render_agent_profile(get_agent_profile("code_reviewer"), target_profile(settings, "builder"))

    assert "# Agent profile: code_reviewer" in rendered
    assert "## Selected target" in rendered
    assert "`builder`" in rendered
    assert "## Target principles" in rendered


def test_agent_profile_record_and_validation(tmp_path: Path) -> None:
    from builder_ii.agent_profiles import (
        AGENT_PROFILE_RECORD_KIND,
        AGENT_PROFILE_RECORD_SCHEMA_VERSION,
        create_agent_profile_record,
        get_agent_profile,
        validate_agent_profile_record,
        validate_agent_profile_record_file,
        write_agent_profile_record,
    )

    settings = _settings(tmp_path)
    profile = get_agent_profile("patch_planner")
    t_profile = target_profile(settings, "builder")

    record = create_agent_profile_record(profile, t_profile, task="test validation")
    assert record["kind"] == AGENT_PROFILE_RECORD_KIND
    assert record["schema_version"] == AGENT_PROFILE_RECORD_SCHEMA_VERSION
    assert record["name"] == "patch_planner"
    assert record["target"] == "builder"

    errors = validate_agent_profile_record(record)
    assert not errors, f"Record should be valid: {errors}"

    output_file = tmp_path / "agent-profile.json"
    write_agent_profile_record(record, output_file)
    assert output_file.exists()

    file_errors = validate_agent_profile_record_file(output_file)
    assert not file_errors, f"File should be valid: {file_errors}"


def test_agent_profile_validation_failures(tmp_path: Path) -> None:
    from builder_ii.agent_profiles import validate_agent_profile_record, validate_agent_profile_record_file

    assert "agent profile record must be a JSON object" in validate_agent_profile_record([])

    bad_dict = {
        "kind": "wrong_kind",
        "schema_version": 1,
        "name": "patch_planner",
    }
    errors = validate_agent_profile_record(bad_dict)
    assert any("kind must be" in err for err in errors)

    bad_target = {
        "kind": "builder_ii.agent_profile_record",
        "schema_version": 1,
        "name": "patch_planner",
        "target": "invalid_target",
        "compatible_targets": [],
        "required_context": [],
        "allowed_tools": [],
        "forbidden_tools": [],
        "hitl_required_for": [],
        "governance": {
            "capability_state": "agent_profile_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    errors = validate_agent_profile_record(bad_target)
    assert any("target must be one of" in err for err in errors)

    # bad core_workbench_coupling
    bad_coupling = {
        "kind": "builder_ii.agent_profile_record",
        "schema_version": 1,
        "name": "patch_planner",
        "target": "builder",
        "compatible_targets": [],
        "required_context": [],
        "allowed_tools": [],
        "forbidden_tools": [],
        "hitl_required_for": [],
        "governance": {
            "capability_state": "agent_profile_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "INVALID",
        },
    }
    errors = validate_agent_profile_record(bad_coupling)
    assert any("core_workbench_coupling must be NONE" in err for err in errors)

    # bad list entries in compatible_targets
    bad_lists = {
        "kind": "builder_ii.agent_profile_record",
        "schema_version": 1,
        "name": "patch_planner",
        "target": "builder",
        "compatible_targets": ["generic", "", 456],
        "required_context": [],
        "allowed_tools": [],
        "forbidden_tools": [],
        "hitl_required_for": [],
        "governance": {
            "capability_state": "agent_profile_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    errors = validate_agent_profile_record(bad_lists)
    assert any("compatible_targets must be a list of non-empty strings" in err for err in errors)

    assert "file not found" in validate_agent_profile_record_file(tmp_path / "missing.json")[0]


def test_agent_cli_commands(tmp_path: Path) -> None:
    import json as json_lib

    from builder_ii.agent_cli import agent_app
    from typer.testing import CliRunner

    runner = CliRunner()

    # Help command
    help_res = runner.invoke(agent_app, ["--help"])
    assert help_res.exit_code == 0
    assert "artifact" in help_res.stdout
    assert "validate" in help_res.stdout

    # Emit artifact to stdout
    result = runner.invoke(
        agent_app,
        [
            "artifact",
            "patch_planner",
            "--target",
            "builder",
            "--task",
            "cli test",
        ],
    )
    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.agent_profile_record"
    assert data["name"] == "patch_planner"
    assert data["task"] == "cli test"

    # Emit artifact to file
    out_file = tmp_path / "agent-profile-record.json"
    result_file = runner.invoke(
        agent_app,
        [
            "artifact",
            "patch_planner",
            "--target",
            "builder",
            "--task",
            "cli test file",
            "--output",
            str(out_file),
        ],
    )
    assert result_file.exit_code == 0
    assert out_file.exists()
    assert "Agent profile record written to" in result_file.stdout

    # Validate command
    val_res = runner.invoke(agent_app, ["validate", str(out_file)])
    assert val_res.exit_code == 0
    assert "is valid" in val_res.stdout

    # Validate invalid path
    val_bad = runner.invoke(agent_app, ["validate", str(tmp_path / "nonexistent.json")])
    assert val_bad.exit_code == 1
