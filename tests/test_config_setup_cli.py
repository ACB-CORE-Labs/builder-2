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


def test_builder_setup_overlay_and_rollback_cli_write_only_requested_artifacts(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    output_plan = tmp_path / "setup-plan.json"
    output_overlay = tmp_path / "setup-overlay.json"
    output_snapshot = tmp_path / "setup-rollback-snapshot.json"
    home = tmp_path / "home"
    env = {"HOME": str(home)}

    plan_result = runner.invoke(
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
            str(output_plan),
        ],
        env=env,
    )
    assert plan_result.exit_code == 0, plan_result.output
    before = sorted(path.relative_to(target) for path in target.rglob("*"))

    overlay_result = runner.invoke(
        setup_app,
        ["overlay-plan", str(output_plan), "--output", str(output_overlay)],
        env=env,
    )
    assert overlay_result.exit_code == 0, overlay_result.output
    assert output_overlay.exists()
    overlay_data = json.loads(output_overlay.read_text(encoding="utf-8"))
    assert overlay_data["kind"] == "builder_ii.setup_overlay_plan"
    assert overlay_data["artifact_is_authority"] is False
    assert all(change["planned_only"] is True for change in overlay_data["planned_changes"])

    validate_overlay_result = runner.invoke(setup_app, ["validate-overlay-plan", str(output_overlay)], env=env)
    assert validate_overlay_result.exit_code == 0, validate_overlay_result.output
    assert json.loads(validate_overlay_result.output)["valid"] is True

    snapshot_result = runner.invoke(
        setup_app,
        ["rollback-snapshot", str(output_overlay), "--output", str(output_snapshot)],
        env=env,
    )
    assert snapshot_result.exit_code == 0, snapshot_result.output
    assert output_snapshot.exists()
    snapshot_data = json.loads(output_snapshot.read_text(encoding="utf-8"))
    assert snapshot_data["kind"] == "builder_ii.setup_rollback_snapshot"
    assert snapshot_data["snapshot_only"] is True
    assert snapshot_data["artifact_is_authority"] is False

    validate_snapshot_result = runner.invoke(setup_app, ["validate-rollback-snapshot", str(output_snapshot)], env=env)
    assert validate_snapshot_result.exit_code == 0, validate_snapshot_result.output
    assert json.loads(validate_snapshot_result.output)["valid"] is True

    after = sorted(path.relative_to(target) for path in target.rglob("*"))
    assert after == before


def test_new_commands_are_tier1_without_runtime_authority() -> None:
    by_name = {record.name: record for record in COMMAND_AUTHORITY_REGISTRY}
    for name in (
        "builder-config",
        "builder-config schema",
        "builder-config resolve",
        "builder-config validate",
        "builder setup",
        "builder-setup",
        "builder-setup plan",
        "builder-setup validate-plan",
        "builder-setup overlay-plan",
        "builder-setup validate-overlay-plan",
        "builder-setup rollback-snapshot",
        "builder-setup validate-rollback-snapshot",
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
    assert by_name["builder setup"].allows_artifact_writes is False
    assert by_name["builder-setup plan"].allows_artifact_writes is True
    assert by_name["builder-setup validate-plan"].allows_artifact_writes is False
    assert by_name["builder-setup overlay-plan"].allows_artifact_writes is True
    assert by_name["builder-setup validate-overlay-plan"].allows_artifact_writes is False
    assert by_name["builder-setup rollback-snapshot"].allows_artifact_writes is True
    assert by_name["builder-setup validate-rollback-snapshot"].allows_artifact_writes is False


def test_legacy_builder_setup_registry_record_is_redirect_only() -> None:
    record = {item.name: item for item in COMMAND_AUTHORITY_REGISTRY}["builder setup"]
    assert record.tier == TIER_1
    assert record.approval_mode == MODE_NONE
    assert "redirects operators" in record.runtime_boundary
    assert not record.allows_runtime_start
    assert not record.allows_model_execution
    assert not record.allows_shell_execution
    assert not record.allows_source_writes
    assert not record.allows_artifact_writes
