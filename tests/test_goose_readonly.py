import json as json_lib
from pathlib import Path

from builder_ii.goose_cli import goose_app
from typer.testing import CliRunner

from builder_ii.adapters.goose.goose_readonly import (
    create_readonly_runtime_audit,
    create_readonly_runtime_audit_from_manifest_file,
    dumps_readonly_runtime_audit,
    validate_readonly_runtime_audit,
    validate_readonly_runtime_audit_file,
)
from builder_ii.adapters.goose.goose_session import create_goose_session_manifest, dumps_goose_session_manifest
from builder_ii.core.config import load_settings


def _read_only_manifest() -> dict:
    return create_goose_session_manifest(
        load_settings(),
        target_name="builder",
        agent_profile="patch_planner",
        runtime_mode="read_only",
        task="inspect repo state",
        target_bundle=".builder/artifacts/target-bundle.json",
        verification_profile=".builder/artifacts/verification-profile.json",
        quality_gate=".builder/artifacts/quality-gate.json",
        handoff=".builder/artifacts/handoff.json",
        context_pack=".builder/context-pack.md",
    )


def test_create_readonly_runtime_audit_shape() -> None:
    manifest = _read_only_manifest()
    audit = create_readonly_runtime_audit(
        manifest,
        manifest_path=".builder/artifacts/goose-session.json",
        output_path=".builder/artifacts/goose-runtime-audit.json",
        created_at_utc="2026-06-26T00:00:00Z",
    )

    assert audit["kind"] == "builder_ii.goose_readonly_runtime_audit"
    assert audit["schema_version"] == 1
    assert audit["runtime_mode"] == "read_only"
    assert audit["capability_state"] == "read_only_runtime_candidate"
    assert audit["current_runtime_state"] == "DISABLED"
    assert audit["runtime_started"] is False
    assert audit["goose_process_started"] is False
    assert audit["manifest_requested_runtime_mode"] == "read_only"
    assert audit["target"]["name"] == "builder"
    assert audit["agent_profile"]["name"] == "patch_planner"
    assert audit["actual_audit_artifact"] == ".builder/artifacts/goose-runtime-audit.json"
    assert audit["repository_files_read"] == []
    assert audit["target_artifacts_read"] == []
    assert audit["git_status_inspected"] is False
    assert audit["commands_executed"] == []
    assert audit["shell_commands_executed"] == []
    assert audit["source_writes_applied"] == []
    assert audit["patches_applied"] == []
    assert audit["model_calls"] == []
    assert audit["deepagents_constructed"] is False
    assert audit["governance"]["runtime_execution"] == "DISABLED"
    assert audit["governance"]["goose_runtime_start"] == "DISABLED"
    assert audit["governance"]["repository_file_reads"] == "DISABLED_IN_THIS_CANDIDATE_ARTIFACT"
    assert audit["governance"]["artifact_is_authority"] is False
    assert "start_goose_runtime" in audit["denied_actions"]
    assert "read_repository_files" in audit["denied_actions"]
    assert "execute_shell" in audit["denied_actions"]
    assert validate_readonly_runtime_audit(audit) == []


def test_readonly_audit_json_round_trip() -> None:
    audit = create_readonly_runtime_audit(
        _read_only_manifest(),
        manifest_path="goose-session.json",
        created_at_utc="2026-06-26T00:00:00Z",
    )
    data = json_lib.loads(dumps_readonly_runtime_audit(audit))

    assert data["kind"] == "builder_ii.goose_readonly_runtime_audit"
    assert data["runtime_started"] is False
    assert validate_readonly_runtime_audit(data) == []


def test_create_from_manifest_file_requires_read_only(tmp_path: Path) -> None:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="builder",
        agent_profile="patch_planner",
        runtime_mode="disabled",
        task="inspect repo state",
    )
    manifest_path = tmp_path / "goose-session.json"
    manifest_path.write_text(dumps_goose_session_manifest(manifest), encoding="utf-8")

    audit, errors = create_readonly_runtime_audit_from_manifest_file(manifest_path)

    assert audit is None
    assert errors == ["manifest.requested_runtime_mode must be read_only for read-only audit"]


def test_validate_rejects_runtime_authority() -> None:
    audit = create_readonly_runtime_audit(
        _read_only_manifest(),
        manifest_path="goose-session.json",
        created_at_utc="2026-06-26T00:00:00Z",
    )
    audit["current_runtime_state"] = "RUNNING"
    audit["runtime_started"] = True
    audit["goose_process_started"] = True
    audit["repository_files_read"] = ["README.md"]
    audit["target_artifacts_read"] = [".builder/artifacts/target-bundle.json"]
    audit["git_status_inspected"] = True
    audit["commands_executed"] = ["uv run pytest"]
    audit["shell_commands_executed"] = ["uv run pytest"]
    audit["source_writes_applied"] = ["README.md"]
    audit["patches_applied"] = ["patch.diff"]
    audit["model_calls"] = ["qwen-coder"]
    audit["deepagents_constructed"] = True
    audit["governance"]["runtime_execution"] = "ENABLED"
    audit["governance"]["goose_runtime_start"] = "ENABLED"
    audit["governance"]["command_execution"] = "ENABLED"
    audit["governance"]["source_writes"] = "ENABLED"
    audit["governance"]["artifact_is_authority"] = True
    audit["denied_actions"].remove("execute_shell")

    errors = validate_readonly_runtime_audit(audit)

    assert "current_runtime_state must be DISABLED or NOT_AUTHORIZED" in errors
    assert "runtime_started must be false or NOT_AUTHORIZED" in errors
    assert "goose_process_started must be false or NOT_AUTHORIZED" in errors
    assert "repository_files_read must be empty" in errors
    assert "target_artifacts_read must be empty" in errors
    assert "git_status_inspected must be false or NOT_AUTHORIZED" in errors
    assert "commands_executed must be empty" in errors
    assert "shell_commands_executed must be empty" in errors
    assert "source_writes_applied must be empty" in errors
    assert "patches_applied must be empty" in errors
    assert "model_calls must be empty" in errors
    assert "deepagents_constructed must be false or NOT_AUTHORIZED" in errors
    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.goose_runtime_start must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.command_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.source_writes must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifact_is_authority must be false or NOT_AUTHORIZED" in errors
    assert "denied_actions must include execute_shell" in errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_readonly_runtime_audit_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_readonly_runtime_audit_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "Goose read-only audit must be a JSON object" in validate_readonly_runtime_audit_file(not_object)


def test_cli_readonly_audit_stdout(tmp_path: Path) -> None:
    manifest_path = tmp_path / "goose-session.json"
    manifest_path.write_text(dumps_goose_session_manifest(_read_only_manifest()), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(goose_app, ["readonly-audit", str(manifest_path)])

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.goose_readonly_runtime_audit"
    assert data["runtime_started"] is False
    assert data["goose_process_started"] is False
    assert data["manifest_path"] == str(manifest_path)


def test_cli_readonly_audit_output_and_validate(tmp_path: Path) -> None:
    manifest_path = tmp_path / "goose-session.json"
    audit_path = tmp_path / "artifacts" / "goose-runtime-audit.json"
    manifest_path.write_text(dumps_goose_session_manifest(_read_only_manifest()), encoding="utf-8")
    runner = CliRunner()

    create_result = runner.invoke(
        goose_app,
        ["readonly-audit", str(manifest_path), "--output", str(audit_path)],
    )

    assert create_result.exit_code == 0
    assert audit_path.exists()
    assert "Goose read-only audit written" in create_result.stdout

    validate_result = runner.invoke(goose_app, ["validate-audit", str(audit_path)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_readonly_audit_rejects_disabled_manifest(tmp_path: Path) -> None:
    manifest = create_goose_session_manifest(
        load_settings(),
        target_name="builder",
        agent_profile="patch_planner",
        runtime_mode="disabled",
        task="inspect repo state",
    )
    manifest_path = tmp_path / "goose-session.json"
    manifest_path.write_text(dumps_goose_session_manifest(manifest), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(goose_app, ["readonly-audit", str(manifest_path)])

    assert result.exit_code == 1
    assert "manifest.requested_runtime_mode must be read_only" in result.stdout
