from __future__ import annotations

import copy
from pathlib import Path

from builder_ii.config import load_settings
from builder_ii.goose_projection import create_goose_projection, validate_goose_projection
from builder_ii.goose_wrapper_plan import create_goose_wrapper_plan, validate_goose_wrapper_plan
from builder_ii.session_config import create_session_configuration, validate_session_configuration


def _generic_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "generic-repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "README.md").write_text("# Generic repo\n", encoding="utf-8")
    (repo / "pyproject.toml").write_text("[project]\nname = 'generic-repo'\n", encoding="utf-8")
    return repo


def test_config_to_goose_projection_to_wrapper_plan_preserves_no_runtime_authority(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)

    config = create_session_configuration(
        settings,
        "generic",
        agent_profile_name="patch_planner",
        verification_profile_name="generic_basic",
        repo_path=str(repo),
        task="prepare config-to-Goose projection scenario",
        authority_mode="read_only",
        model_alias="qwen-coder",
        context_pack=".builder/artifacts/context-pack.json",
        generic_repo=repo,
    )
    projection = create_goose_projection(settings, config)
    wrapper_plan = create_goose_wrapper_plan(projection)

    assert validate_session_configuration(config) == []
    assert validate_goose_projection(projection) == []
    assert validate_goose_wrapper_plan(wrapper_plan) == []

    assert config["kind"] == "builder_ii.session_configuration"
    assert projection["kind"] == "builder_ii.goose_projection"
    assert wrapper_plan["kind"] == "builder_ii.goose_wrapper_plan"

    assert config["target_profile"]["name"] == "generic"
    assert projection["target"] == "generic"
    assert wrapper_plan["target"] == "generic"
    assert "CORE" not in config["selected_prompt_profile"]["system_prompt"]

    assert projection["goose_native_surface"]["working_directory"] == str(repo.resolve())
    assert wrapper_plan["operator_launch"]["working_directory"] == str(repo.resolve())
    assert wrapper_plan["operator_launch"]["argv"][:3] == ["goose", "session", "--recipe"]
    assert wrapper_plan["operator_launch"]["executes_now"] is False
    assert wrapper_plan["operator_launch"]["requires_operator_execution"] is True

    for record in (config, projection, wrapper_plan):
        governance = record["governance"]
        assert governance["runtime_execution"] == "DISABLED"
        assert governance["model_execution"] == "DISABLED"
        assert governance["shell_execution"] == "DISABLED"
        assert governance["source_writes"] == "DISABLED"
        assert governance["memory_mutation"] == "DISABLED"
        assert governance["artifact_is_authority"] is False
        assert governance["core_workbench_coupling"] == "NONE"

    assert config["governance"]["goose_runtime_start"] == "DISABLED"
    assert projection["governance"]["goose_runtime_start"] == "DISABLED"
    assert wrapper_plan["governance"]["goose_runtime_start"] == "DISABLED"


def test_config_to_goose_projection_flow_rejects_late_authority_escalation(tmp_path: Path) -> None:
    settings = load_settings(project_root=tmp_path / "builder-II")
    repo = _generic_repo(tmp_path)
    config = create_session_configuration(settings, "generic", repo_path=str(repo), generic_repo=repo)
    projection = create_goose_projection(settings, config)
    wrapper_plan = create_goose_wrapper_plan(projection)

    bad_config = copy.deepcopy(config)
    bad_config["governance"]["goose_runtime_start"] = "ENABLED"
    assert "governance.goose_runtime_start must be DISABLED" in validate_session_configuration(bad_config)

    bad_projection = copy.deepcopy(projection)
    bad_projection["projection_state"] = "EXECUTED"
    bad_projection["governance"]["model_execution"] = "ENABLED"
    projection_errors = validate_goose_projection(bad_projection)
    assert "projection_state must be PLANNED_ONLY" in projection_errors
    assert "governance.model_execution must be DISABLED" in projection_errors

    bad_wrapper = copy.deepcopy(wrapper_plan)
    bad_wrapper["operator_launch"]["executes_now"] = True
    bad_wrapper["governance"]["runtime_execution"] = "ENABLED"
    wrapper_errors = validate_goose_wrapper_plan(bad_wrapper)
    assert "operator_launch.executes_now must be false" in wrapper_errors
    assert "governance.runtime_execution must be DISABLED" in wrapper_errors
