from pathlib import Path

from builder_ii.config_sources import resolve_config_sources
from builder_ii.setup_plan import create_setup_plan, validate_setup_plan_artifact


def _resolution(tmp_path: Path):
    target = tmp_path / "target"
    target.mkdir()
    return resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(target),
            "BUILDER_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
            "BUILDER_TARGET_PROFILE": "builder",
        },
        builder_config_file=tmp_path / "missing.json",
    )


def test_setup_plan_is_passive_and_not_authority(tmp_path: Path) -> None:
    resolution = _resolution(tmp_path)
    plan = create_setup_plan(resolution)

    assert not validate_setup_plan_artifact(plan)
    assert plan["artifact_is_authority"] is False
    assert plan["governance"]["artifact_is_authority"] is False
    assert plan["capability_map"]["runtime_execution"] == "disabled"
    assert plan["capability_map"]["model_execution"] == "disabled"
    assert plan["capability_map"]["shell_execution"] == "disabled"
    assert plan["capability_map"]["goose_runtime"] == "disabled"
    assert plan["capability_map"]["deepagents_runtime"] == "disabled"
    assert plan["capability_map"]["mcp_tool_invocation"] == "disabled"
    assert plan["capability_map"]["patch_authority"] == "disabled"
    assert plan["capability_map"]["setup_apply"] == "disabled"
    assert plan["no_mutation_proof"]["target_repo_writes"] is False
    assert plan["no_mutation_proof"]["goose_config_writes"] is False


def test_setup_plan_has_deterministic_digest(tmp_path: Path) -> None:
    resolution = _resolution(tmp_path)

    first = create_setup_plan(resolution)
    second = create_setup_plan(resolution)

    assert first["plan_digest"] == second["plan_digest"]


def test_setup_plan_generation_writes_no_target_files(tmp_path: Path) -> None:
    resolution = _resolution(tmp_path)
    target = Path(resolution.value("target_repo"))
    before = sorted(path.relative_to(target) for path in target.rglob("*"))

    create_setup_plan(resolution)

    after = sorted(path.relative_to(target) for path in target.rglob("*"))
    assert after == before


def test_setup_plan_records_expected_passive_setup_fields(tmp_path: Path) -> None:
    resolution = _resolution(tmp_path)
    plan = create_setup_plan(resolution)

    assert plan["target_repo_canonical_path"] == resolution.value("target_repo")
    assert plan["artifact_root_canonical_path"] == resolution.value("platform_artifact_root")
    assert plan["config_source_resolution_ref"]["digest"] == resolution.to_jsonable()["digest"]
    assert plan["selected_target_profile"] == "builder"
    assert plan["selected_agent_profile"] == "patch_planner"
    assert plan["selected_verification_profile"] == "builder_full"
    assert plan["selected_model"]["backend"] == "mlx-lm"
    assert plan["goose_config_target_path"].endswith(".config/goose/config.yaml")
    assert plan["skills_destination_policy"] == "plan_only_target_agents_skills"
    assert plan["deepagents_mode"] == "disabled"
    assert plan["planned_writes_if_later_applied"]
    assert all(write["r1_1_performs_write"] is False for write in plan["planned_writes_if_later_applied"])
