import json as json_lib
from pathlib import Path

from builder_ii.goose_cli import goose_app
from typer.testing import CliRunner

from builder_ii.adapters.goose.goose_session import (
    create_goose_session_manifest,
    dumps_goose_session_manifest,
    validate_goose_session_manifest,
    validate_goose_session_manifest_file,
)
from builder_ii.core.config import load_settings


def test_create_goose_session_manifest_shape() -> None:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="builder",
        agent_profile="patch_planner",
        runtime_mode="read_only",
        task="inspect repo state",
        target_bundle=".builder/artifacts/target-bundle.json",
        verification_profile=".builder/artifacts/verification-profile.json",
        quality_gate=".builder/artifacts/quality-gate.json",
        research_plan=".builder/artifacts/research-plan.json",
        handoff=".builder/artifacts/handoff.json",
        context_pack=".builder/context-pack.md",
    )

    assert manifest["kind"] == "builder_ii.goose_session_manifest"
    assert manifest["schema_version"] == 1
    assert manifest["target"]["name"] == "builder"
    assert manifest["agent_profile"]["name"] == "patch_planner"
    assert manifest["requested_runtime_mode"] == "read_only"
    assert manifest["current_runtime_state"] == "DISABLED"
    assert manifest["manifest_starts_goose"] is False
    assert manifest["links"]["target_bundle"] == ".builder/artifacts/target-bundle.json"
    assert manifest["expected_audit_artifact"] == ".builder/artifacts/goose-runtime-audit.json"
    assert "start_goose_runtime" in manifest["denied_actions"]
    assert "execute_commands" in manifest["denied_actions"]
    assert manifest["governance"]["runtime_execution"] == "DISABLED"
    assert manifest["governance"]["goose_runtime_start"] == "DISABLED"
    assert manifest["governance"]["artifact_is_authority"] is False
    assert validate_goose_session_manifest(manifest) == []


def test_goose_session_json_round_trip() -> None:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="repo_mapper",
        task="map target repo",
        runtime_mode="disabled",
        generic_repo=Path("."),
    )
    data = json_lib.loads(dumps_goose_session_manifest(manifest))

    assert data["kind"] == "builder_ii.goose_session_manifest"
    assert data["requested_runtime_mode"] == "disabled"
    assert validate_goose_session_manifest(data) == []


def test_validate_rejects_runtime_authority() -> None:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="builder",
        agent_profile="patch_planner",
        task="inspect repo state",
    )
    manifest["current_runtime_state"] = "RUNNING"
    manifest["manifest_starts_goose"] = True
    manifest["governance"]["runtime_execution"] = "ENABLED"
    manifest["governance"]["goose_runtime_start"] = "ENABLED"
    manifest["governance"]["command_execution"] = "ENABLED"
    manifest["governance"]["source_writes"] = "ENABLED"
    manifest["governance"]["artifact_is_authority"] = True
    manifest["denied_actions"].remove("execute_shell")

    errors = validate_goose_session_manifest(manifest)

    assert "current_runtime_state must be DISABLED or NOT_AUTHORIZED" in errors
    assert "manifest_starts_goose must be false or NOT_AUTHORIZED" in errors
    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.goose_runtime_start must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.command_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.source_writes must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors
    assert "denied_actions must include execute_shell" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_goose_session_manifest_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_goose_session_manifest_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "goose session manifest must be a JSON object" in validate_goose_session_manifest_file(not_object)


def test_cli_manifest_stdout() -> None:
    runner = CliRunner()
    result = runner.invoke(
        goose_app,
        [
            "manifest",
            "--target",
            "builder",
            "--agent",
            "patch_planner",
            "--mode",
            "read_only",
            "--task",
            "inspect repo state",
            "--bundle",
            ".builder/artifacts/target-bundle.json",
        ],
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.goose_session_manifest"
    assert data["requested_runtime_mode"] == "read_only"
    assert data["manifest_starts_goose"] is False
    assert data["links"]["target_bundle"] == ".builder/artifacts/target-bundle.json"


def test_cli_manifest_output_and_validate(tmp_path: Path) -> None:
    out_file = tmp_path / "artifacts" / "goose-session.json"
    runner = CliRunner()
    create_result = runner.invoke(
        goose_app,
        [
            "manifest",
            "--target",
            "builder",
            "--agent",
            "patch_planner",
            "--task",
            "inspect repo state",
            "--output",
            str(out_file),
        ],
    )

    assert create_result.exit_code == 0
    assert out_file.exists()
    assert "Goose session manifest written" in create_result.stdout

    validate_result = runner.invoke(goose_app, ["validate", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_manifest_default_does_not_write() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(
            goose_app,
            [
                "manifest",
                "--target",
                "builder",
                "--agent",
                "handoff_scribe",
                "--task",
                "prepare handoff",
            ],
        )
        assert result.exit_code == 0
        assert list(Path(".").iterdir()) == []


def test_cli_rejects_bad_mode() -> None:
    runner = CliRunner()
    result = runner.invoke(
        goose_app,
        [
            "manifest",
            "--target",
            "builder",
            "--agent",
            "patch_planner",
            "--mode",
            "hitl_write",
            "--task",
            "inspect repo state",
        ],
    )

    assert result.exit_code == 1
    assert "mode must be disabled or read_only" in result.stdout


def test_cli_rejects_unknown_agent() -> None:
    runner = CliRunner()
    result = runner.invoke(
        goose_app,
        [
            "manifest",
            "--target",
            "builder",
            "--agent",
            "unknown_agent",
            "--task",
            "inspect repo state",
        ],
    )

    assert result.exit_code == 1
    assert "unknown agent profile" in result.stdout
