from __future__ import annotations

import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.orchestration_cli import orchestration_app
from builder_ii.orchestration_plan import ORCHESTRATION_PLAN_KIND

runner = CliRunner()


def test_orchestration_cli_stdout() -> None:
    result = runner.invoke(
        orchestration_app,
        ["plan", "generic", "--task", "coordinate local agent planning"],
    )

    assert result.exit_code == 0
    plan = json_lib.loads(result.output)
    assert plan["kind"] == ORCHESTRATION_PLAN_KIND
    assert plan["target"] == "generic"
    assert plan["governance"]["deepagents_runtime_start"] == "DISABLED"
    assert plan["roles"][0]["role"] == "repo_mapper"


def test_orchestration_cli_output_and_validate(tmp_path) -> None:
    output = tmp_path / "orchestration-plan.json"
    create_result = runner.invoke(
        orchestration_app,
        [
            "plan",
            "builder",
            "--task",
            "review builder session config",
            "--roles",
            "code_reviewer,verification_planner,handoff_scribe",
            "--output",
            str(output),
        ],
    )

    assert create_result.exit_code == 0
    assert output.exists()
    assert "Orchestration plan written" in create_result.stdout

    validate_result = runner.invoke(orchestration_app, ["validate", str(output)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout

    plan = json_lib.loads(output.read_text(encoding="utf-8"))
    assert [step["role"] for step in plan["roles"]] == ["code_reviewer", "verification_planner", "handoff_scribe"]


def test_orchestration_cli_render_assignment_sibling_output_and_chain(tmp_path: Path) -> None:
    from orchestration_assignment_fixtures import build_goal2_assignment_fixture

    from builder_ii.artifact_chain_verification import verify_artifact_chain

    # 1. Build all fixture source artifacts in tmp_path/artifacts/
    fixture = build_goal2_assignment_fixture(tmp_path)
    paths = fixture["paths"]

    # 2. Run render-assignment with --output, omitting --assignment-output
    output_plan_path = tmp_path / "plan.json"
    expected_sibling_path = tmp_path / "plan.json.agent-assignment-plan.json"

    result = runner.invoke(
        orchestration_app,
        [
            "render-assignment",
            "--target-profile",
            str(paths["target_profile"]),
            "--agent-profile",
            str(paths["agent_profile"]),
            "--context-pack",
            str(paths["context_pack"]),
            "--verification-profile",
            str(paths["verification_profile"]),
            "--model-registry",
            str(paths["model_registry"]),
            "--model-policy",
            str(paths["model_policy"]),
            "--model-recommendation",
            str(paths["model_recommendation"]),
            "--profile-pack-manifest",
            str(paths["profile_pack_manifest"]),
            "--profile-pack-render-plan",
            str(paths["profile_pack_render_plan"]),
            "--profile-pack-dry-run",
            str(paths["profile_pack_dry_run"]),
            "--profile-pack-validation-report",
            str(paths["profile_pack_validation_report"]),
            "--profile-pack",
            str(paths["profile_pack"]),
            "--task",
            "test passive assignment sibling CLI output",
            "--output",
            str(output_plan_path),
        ],
    )

    assert result.exit_code == 0
    assert output_plan_path.exists()
    assert expected_sibling_path.exists()

    # 3. Load generated orchestration plan and verify that assignment_plan_ref.path points to sibling
    plan = json_lib.loads(output_plan_path.read_text(encoding="utf-8"))
    assert plan["assignment_plan_ref"]["path"] == str(expected_sibling_path)

    # 4. Verify artifact-chain closure over all fixture source paths + sibling assignment path + orchestration assignment plan path
    chain_result = verify_artifact_chain([output_plan_path])
    assert chain_result["valid"] is True
    assert chain_result["errors"] == []
