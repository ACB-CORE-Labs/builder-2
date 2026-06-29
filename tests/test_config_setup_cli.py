import json
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY, MODE_NONE, TIER_1
from builder_ii.config_cli import config_app
from builder_ii.setup_cli import setup_app


runner = CliRunner()


def test_builder_config_schema_and_validate_cli(tmp_path: Path) -> None:
    schema_path = tmp_path / "schema.json"

    schema_result = runner.invoke(config_app, ["schema", "--output", str(schema_path)])
    assert schema_result.exit_code == 0, schema_result.output
    assert schema_path.exists()
    assert json.loads(schema_result.output)["kind"] == "builder_ii.config_schema"

    validate_result = runner.invoke(config_app, ["validate", str(schema_path)])
    assert validate_result.exit_code == 0, validate_result.output
    assert json.loads(validate_result.output)["valid"] is True


def test_builder_config_resolve_cli_writes_explicit_artifact(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    output = tmp_path / "resolution.json"

    result = runner.invoke(
        config_app,
        [
            "resolve",
            "--root",
            str(tmp_path),
            "--target-repo",
            str(target),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.config_source_resolution"
    assert data["resolved"]["target_repo"]["source_kind"] == "cli_override"
    assert data["resolved"]["target_repo"]["value"] == str(target.resolve())


def test_builder_setup_plan_and_validate_plan_cli(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    output = tmp_path / "setup-plan.json"

    result = runner.invoke(
        setup_app,
        [
            "plan",
            "--root",
            str(tmp_path),
            "--target-repo",
            str(target),
            "--artifact-root",
            str(tmp_path / "artifacts"),
            "--output",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["kind"] == "builder_ii.setup_plan"
    assert data["artifact_is_authority"] is False

    validate_result = runner.invoke(setup_app, ["validate-plan", str(output)])
    assert validate_result.exit_code == 0, validate_result.output
    assert json.loads(validate_result.output)["valid"] is True


def test_new_commands_are_tier1_without_runtime_authority() -> None:
    by_name = {record.name: record for record in COMMAND_AUTHORITY_REGISTRY}
    for name in (
        "builder-config",
        "builder-config schema",
        "builder-config resolve",
        "builder-config validate",
        "builder-setup",
        "builder-setup plan",
        "builder-setup validate-plan",
    ):
        record = by_name[name]
        assert record.tier == TIER_1
        assert record.approval_mode == MODE_NONE
        assert not record.allows_runtime_start
        assert not record.allows_model_execution
        assert not record.allows_shell_execution
        assert not record.allows_source_writes
        assert not record.allows_memory_mutation
        assert not record.allows_git_mutation
        assert not record.allows_state_writes
        assert not record.allows_readonly_subprocess
        assert not record.allows_external_tool_invocation

    assert by_name["builder-config schema"].allows_artifact_writes is True
    assert by_name["builder-config resolve"].allows_artifact_writes is True
    assert by_name["builder-config validate"].allows_artifact_writes is False
    assert by_name["builder-setup plan"].allows_artifact_writes is True
    assert by_name["builder-setup validate-plan"].allows_artifact_writes is False
