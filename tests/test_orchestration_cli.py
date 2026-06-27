from __future__ import annotations

import json as json_lib

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
