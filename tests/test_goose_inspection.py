import hashlib
import json as json_lib
from pathlib import Path

from builder_ii.goose_cli import goose_app
from typer.testing import CliRunner

from builder_ii.config import load_settings
from builder_ii.goose_inspection import (
    create_readonly_inspection_audit,
    create_readonly_inspection_audit_from_manifest_file,
    dumps_readonly_inspection_audit,
    validate_readonly_inspection_audit,
    validate_readonly_inspection_audit_file,
)
from builder_ii.goose_session import create_goose_session_manifest, dumps_goose_session_manifest


def _manifest(repo: Path, *, mode: str = "read_only") -> dict:
    return create_goose_session_manifest(
        load_settings(),
        target_name="generic",
        agent_profile="repo_mapper",
        runtime_mode=mode,  # type: ignore[arg-type]
        task="inspect explicit file",
        generic_repo=repo,
    )


def test_create_readonly_inspection_audit_shape(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("hello\nworld\n", encoding="utf-8")
    manifest = _manifest(tmp_path)

    audit, errors = create_readonly_inspection_audit(
        manifest,
        manifest_path=".builder/artifacts/goose-session.json",
        read_paths=["README.md"],
        output_path=".builder/artifacts/goose-readonly-inspection.json",
        created_at_utc="2026-06-26T00:00:00Z",
    )

    assert errors == []
    assert audit is not None
    assert audit["kind"] == "builder_ii.goose_readonly_inspection_audit"
    assert audit["schema_version"] == 1
    assert audit["runtime_mode"] == "read_only"
    assert audit["capability_state"] == "read_only_runtime_candidate"
    assert audit["current_runtime_state"] == "CANDIDATE_INSPECTION"
    assert audit["runtime_started"] is False
    assert audit["goose_process_started"] is False
    assert audit["manifest_requested_runtime_mode"] == "read_only"
    assert audit["target"]["name"] == "generic"
    assert audit["agent_profile"]["name"] == "repo_mapper"
    assert audit["actual_audit_artifact"] == ".builder/artifacts/goose-readonly-inspection.json"
    assert audit["repository_file_contents_recorded"] is False
    assert audit["target_artifacts_read"] == []
    assert audit["git_status_inspected"] is False
    assert audit["commands_executed"] == []
    assert audit["shell_commands_executed"] == []
    assert audit["source_writes_applied"] == []
    assert audit["patches_applied"] == []
    assert audit["model_calls"] == []
    assert audit["deepagents_constructed"] is False
    assert audit["governance"]["runtime_execution"] == "READ_ONLY_CANDIDATE_INSPECTION"
    assert audit["governance"]["goose_runtime_start"] == "DISABLED"
    assert audit["governance"]["repository_file_reads"] == "ENABLED_FOR_EXPLICIT_OPERATOR_PATHS_ONLY"
    assert audit["governance"]["target_artifact_reads"] == "DISABLED_IN_THIS_CANDIDATE"
    assert audit["governance"]["git_status_inspection"] == "DISABLED_IN_THIS_CANDIDATE"
    assert audit["governance"]["artifact_is_authority"] is False
    assert "start_goose_runtime" in audit["denied_actions"]
    assert "execute_shell" in audit["denied_actions"]

    entry = audit["repository_files_read"][0]
    assert entry["path"] == "README.md"
    assert entry["bytes_read"] == len(b"hello\nworld\n")
    assert entry["sha256"] == hashlib.sha256(b"hello\nworld\n").hexdigest()
    assert entry["line_count"] == 2
    assert entry["content_recorded"] is False
    assert validate_readonly_inspection_audit(audit) == []


def test_readonly_inspection_json_round_trip(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    audit, errors = create_readonly_inspection_audit(
        _manifest(tmp_path),
        manifest_path="goose-session.json",
        read_paths=["a.txt"],
        created_at_utc="2026-06-26T00:00:00Z",
    )

    assert errors == []
    assert audit is not None
    data = json_lib.loads(dumps_readonly_inspection_audit(audit))
    assert data["kind"] == "builder_ii.goose_readonly_inspection_audit"
    assert data["runtime_started"] is False
    assert validate_readonly_inspection_audit(data) == []


def test_create_from_manifest_file_requires_read_only(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha\n", encoding="utf-8")
    manifest_path = tmp_path / "goose-session.json"
    manifest_path.write_text(dumps_goose_session_manifest(_manifest(tmp_path, mode="disabled")), encoding="utf-8")

    audit, errors = create_readonly_inspection_audit_from_manifest_file(manifest_path, read_paths=["a.txt"])

    assert audit is None
    assert errors == ["manifest.requested_runtime_mode must be read_only for read-only inspection"]


def test_rejects_unsafe_or_invalid_paths(tmp_path: Path) -> None:
    (tmp_path / "safe.txt").write_text("safe", encoding="utf-8")
    manifest = _manifest(tmp_path)

    for bad_path, expected in [
        ("../outside.txt", "read path must not contain '..'"),
        (".git/config", "read path must not enter .git"),
        ("missing.txt", "read path not found"),
        (".", "read path must name a file"),
    ]:
        audit, errors = create_readonly_inspection_audit(
            manifest,
            manifest_path="goose-session.json",
            read_paths=[bad_path],
            created_at_utc="2026-06-26T00:00:00Z",
        )
        assert audit is None
        assert any(expected in error for error in errors)


def test_rejects_oversized_file(tmp_path: Path) -> None:
    (tmp_path / "big.txt").write_text("too big", encoding="utf-8")

    audit, errors = create_readonly_inspection_audit(
        _manifest(tmp_path),
        manifest_path="goose-session.json",
        read_paths=["big.txt"],
        max_bytes=3,
        created_at_utc="2026-06-26T00:00:00Z",
    )

    assert audit is None
    assert any("read path exceeds max bytes" in error for error in errors)


def test_validate_rejects_runtime_authority(tmp_path: Path) -> None:
    (tmp_path / "a.txt").write_text("alpha", encoding="utf-8")
    audit, errors = create_readonly_inspection_audit(
        _manifest(tmp_path),
        manifest_path="goose-session.json",
        read_paths=["a.txt"],
        created_at_utc="2026-06-26T00:00:00Z",
    )
    assert errors == []
    assert audit is not None
    audit["runtime_started"] = True
    audit["goose_process_started"] = True
    audit["repository_file_contents_recorded"] = True
    audit["target_artifacts_read"] = [".builder/artifacts/target-bundle.json"]
    audit["git_status_inspected"] = True
    audit["commands_executed"] = ["uv run pytest"]
    audit["shell_commands_executed"] = ["uv run pytest"]
    audit["source_writes_applied"] = ["README.md"]
    audit["patches_applied"] = ["patch.diff"]
    audit["model_calls"] = ["qwen-coder"]
    audit["deepagents_constructed"] = True
    audit["repository_files_read"][0]["content_recorded"] = True
    audit["governance"]["goose_runtime_start"] = "ENABLED"
    audit["governance"]["command_execution"] = "ENABLED"
    audit["governance"]["source_writes"] = "ENABLED"
    audit["governance"]["artifact_is_authority"] = True
    audit["denied_actions"].remove("execute_shell")

    validation_errors = validate_readonly_inspection_audit(audit)

    assert "runtime_started must be false" in validation_errors
    assert "goose_process_started must be false" in validation_errors
    assert "repository_file_contents_recorded must be false" in validation_errors
    assert "target_artifacts_read must be empty" in validation_errors
    assert "git_status_inspected must be false" in validation_errors
    assert "commands_executed must be empty" in validation_errors
    assert "shell_commands_executed must be empty" in validation_errors
    assert "source_writes_applied must be empty" in validation_errors
    assert "patches_applied must be empty" in validation_errors
    assert "model_calls must be empty" in validation_errors
    assert "deepagents_constructed must be false" in validation_errors
    assert "repository_files_read[0].content_recorded must be false" in validation_errors
    assert "governance.goose_runtime_start must be DISABLED" in validation_errors
    assert "governance.command_execution must be DISABLED" in validation_errors
    assert "governance.source_writes must be DISABLED" in validation_errors
    assert "governance.artifact_is_authority must be false" in validation_errors
    assert "denied_actions must include execute_shell" in validation_errors


def test_validate_file_errors(tmp_path: Path) -> None:
    assert any(
        "file not found" in error for error in validate_readonly_inspection_audit_file(tmp_path / "missing.json")
    )

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_readonly_inspection_audit_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "Goose read-only inspection audit must be a JSON object" in validate_readonly_inspection_audit_file(
        not_object
    )


def test_cli_inspect_readonly_stdout(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    manifest_path = tmp_path / "goose-session.json"
    manifest_path.write_text(dumps_goose_session_manifest(_manifest(tmp_path)), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(goose_app, ["inspect-readonly", str(manifest_path), "--read-file", "README.md"])

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.goose_readonly_inspection_audit"
    assert data["runtime_started"] is False
    assert data["goose_process_started"] is False
    assert data["repository_files_read"][0]["path"] == "README.md"
    assert data["repository_file_contents_recorded"] is False


def test_cli_inspect_readonly_output_and_validate(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("hello\n", encoding="utf-8")
    manifest_path = tmp_path / "goose-session.json"
    audit_path = tmp_path / "artifacts" / "goose-readonly-inspection.json"
    manifest_path.write_text(dumps_goose_session_manifest(_manifest(tmp_path)), encoding="utf-8")
    runner = CliRunner()

    create_result = runner.invoke(
        goose_app,
        ["inspect-readonly", str(manifest_path), "--read-file", "README.md", "--output", str(audit_path)],
    )

    assert create_result.exit_code == 0
    assert audit_path.exists()
    assert "Goose read-only inspection audit written" in create_result.stdout

    validate_result = runner.invoke(goose_app, ["validate-inspection", str(audit_path)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_inspect_readonly_requires_read_file(tmp_path: Path) -> None:
    manifest_path = tmp_path / "goose-session.json"
    manifest_path.write_text(dumps_goose_session_manifest(_manifest(tmp_path)), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(goose_app, ["inspect-readonly", str(manifest_path)])

    assert result.exit_code == 1
    assert "at least one --read-file path is required" in result.stdout
