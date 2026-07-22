import json as json_lib
from pathlib import Path

from builder_ii.research_cli import research_app
from typer.testing import CliRunner

from builder_ii.core.research_plans import (
    create_research_plan_artifact,
    dumps_research_plan_artifact,
    research_profile_names,
    validate_research_plan_artifact,
    validate_research_plan_artifact_file,
    validate_research_profiles,
)


def test_research_profiles_validate() -> None:
    assert set(research_profile_names()) == {
        "research_planner",
        "source_mapper",
        "evidence_synthesizer",
        "report_reviewer",
    }
    assert validate_research_profiles() == ()


def test_create_research_plan_artifact_shape() -> None:
    artifact = create_research_plan_artifact(
        target="generic",
        profile_name="research_planner",
        task="map governed research architecture",
        topic="research runtime planning",
        source_hint=("repository docs",),
    )

    assert artifact["kind"] == "builder_ii.research_plan"
    assert artifact["schema_version"] == 1
    assert artifact["target"] == "generic"
    assert artifact["profile"]["name"] == "research_planner"
    assert artifact["topic"] == "research runtime planning"
    assert artifact["source_hints"] == ["repository docs"]
    assert artifact["source_strategy"]
    assert artifact["evidence_requirements"]
    assert artifact["report_contract"]
    assert artifact["known_unknowns"]
    assert artifact["governance"]["runtime_execution"] == "DISABLED"
    assert artifact["governance"]["model_execution"] == "DISABLED"
    assert artifact["governance"]["search_execution"] == "DISABLED"
    assert artifact["governance"]["mcp_execution"] == "DISABLED"
    assert artifact["governance"]["source_collection"] == "DISABLED"
    assert artifact["governance"]["artifact_is_authority"] is False
    assert validate_research_plan_artifact(artifact) == []


def test_research_plan_json_round_trip() -> None:
    artifact = create_research_plan_artifact(
        target="builder",
        profile_name="source_mapper",
        task="map research planning surfaces",
    )
    data = json_lib.loads(dumps_research_plan_artifact(artifact))

    assert data["kind"] == "builder_ii.research_plan"
    assert validate_research_plan_artifact(data) == []


def test_validate_research_plan_rejects_runtime_authority() -> None:
    artifact = create_research_plan_artifact(
        target="generic",
        profile_name="research_planner",
        task="map source categories",
    )
    artifact["governance"]["runtime_execution"] = "ENABLED"
    artifact["governance"]["model_execution"] = "ENABLED"
    artifact["governance"]["search_execution"] = "ENABLED"
    artifact["governance"]["mcp_execution"] = "ENABLED"
    artifact["governance"]["source_collection"] = "ENABLED"
    artifact["governance"]["artifact_is_authority"] = True

    errors = validate_research_plan_artifact(artifact)

    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.model_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.search_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.mcp_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.source_collection must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors


def test_validate_research_plan_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_research_plan_artifact_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_research_plan_artifact_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "research plan artifact must be a JSON object" in validate_research_plan_artifact_file(not_object)


def test_cli_plan_stdout() -> None:
    runner = CliRunner()
    result = runner.invoke(
        research_app,
        [
            "plan",
            "--target",
            "generic",
            "--profile",
            "research_planner",
            "--task",
            "map governed research architecture",
            "--topic",
            "research planning",
            "--source-hint",
            "repository docs",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.research_plan"
    assert data["target"] == "generic"
    assert data["source_hints"] == ["repository docs"]
    assert data["governance"]["search_execution"] == "DISABLED"


def test_cli_plan_output_and_validate(tmp_path: Path) -> None:
    out_file = tmp_path / "artifacts" / "research-plan.json"
    runner = CliRunner()
    create_result = runner.invoke(
        research_app,
        [
            "plan",
            "--target",
            "builder",
            "--profile",
            "source_mapper",
            "--task",
            "map research surfaces",
            "--output",
            str(out_file),
        ],
    )

    assert create_result.exit_code == 0
    assert out_file.exists()
    assert "Research plan artifact written" in create_result.stdout

    validate_result = runner.invoke(research_app, ["validate", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_plan_default_does_not_write() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            research_app,
            [
                "plan",
                "--target",
                "generic",
                "--profile",
                "report_reviewer",
                "--task",
                "review report contract",
            ],
        )
        assert result.exit_code == 0
        assert list(Path(".").iterdir()) == []


def test_cli_profiles_and_show() -> None:
    runner = CliRunner()
    profiles_result = runner.invoke(research_app, ["profiles"])
    assert profiles_result.exit_code == 0
    assert "research_planner" in profiles_result.stdout

    show_result = runner.invoke(research_app, ["show", "source_mapper"])
    assert show_result.exit_code == 0
    assert "Source strategy" in show_result.stdout


def test_cli_validate_profiles() -> None:
    runner = CliRunner()
    result = runner.invoke(research_app, ["validate-profiles"])
    assert result.exit_code == 0
    assert "Research planning profiles are valid" in result.stdout
