import json as json_lib
from pathlib import Path
from types import SimpleNamespace

from builder_ii.bundle_cli import bundle_app
from typer.testing import CliRunner

from builder_ii.bundles import create_target_bundle, dumps_bundle, validate_target_bundle, validate_target_bundle_file


def _settings(tmp_path: Path):
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("core", encoding="utf-8")
    (builder / "README.md").write_text("builder", encoding="utf-8")
    return SimpleNamespace(target_repo=core, project_root=builder)


def test_create_target_bundle_shape(tmp_path: Path) -> None:
    bundle = create_target_bundle(
        _settings(tmp_path),
        target_name="builder",
        agent_profile="patch_planner",
        task="plan the next bounded PR",
    )

    assert bundle["kind"] == "builder_ii.target_profile_bundle"
    assert bundle["schema_version"] == 1
    assert bundle["task"]["description"] == "plan the next bounded PR"
    assert bundle["target"]["name"] == "builder"
    assert bundle["agent_profile"]["name"] == "patch_planner"
    assert bundle["bridge_spec"]["kind"] == "builder_ii.deepagents_bridge_spec"
    assert bundle["bridge_spec"]["runtime_enabled"] is False
    assert bundle["deepagents_readiness"]["kind"] == "builder_ii.deepagents_smoke"
    assert bundle["governance"]["capability_state"] == "validation_only"
    assert bundle["governance"]["artifacts_are_authority"] is False
    assert validate_target_bundle(bundle) == []


def test_bundle_json_round_trip(tmp_path: Path) -> None:
    bundle = create_target_bundle(_settings(tmp_path), target_name="builder", agent_profile="repo_mapper")
    text = dumps_bundle(bundle)
    data = json_lib.loads(text)

    assert data["kind"] == "builder_ii.target_profile_bundle"
    assert data["agent_profile"]["hitl_required_for"] == ["none; profile is read-only"]
    assert validate_target_bundle(data) == []


def test_validate_target_bundle_rejects_runtime_authority(tmp_path: Path) -> None:
    bundle = create_target_bundle(_settings(tmp_path), target_name="builder", agent_profile="patch_planner")
    bundle["bridge_spec"]["runtime_enabled"] = True
    bundle["governance"]["runtime_execution"] = "ENABLED"
    bundle["governance"]["artifacts_are_authority"] = True

    errors = validate_target_bundle(bundle)

    assert "bridge_spec.runtime_enabled must be false or NOT_AUTHORIZED" in errors
    assert "governance.runtime_execution must be DISABLED or NOT_AUTHORIZED" in errors
    assert "governance.artifacts_are_authority must be false or NOT_AUTHORIZED" in errors


def test_validate_target_bundle_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_target_bundle_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_target_bundle_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "bundle must be a JSON object" in validate_target_bundle_file(not_object)


def test_cli_bundle_create_stdout(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("builder_ii.bundle_cli.load_settings", lambda: settings)

    runner = CliRunner()
    result = runner.invoke(
        bundle_app, ["create", "--target", "builder", "--agent", "patch_planner", "--task", "test task"]
    )

    assert result.exit_code == 0
    data = json_lib.loads(result.stdout)
    assert data["kind"] == "builder_ii.target_profile_bundle"
    assert data["task"]["description"] == "test task"
    assert data["governance"]["runtime_execution"] == "DISABLED"


def test_cli_bundle_create_output_and_validate(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("builder_ii.bundle_cli.load_settings", lambda: settings)

    out_file = tmp_path / "artifacts" / "target-bundle.json"
    runner = CliRunner()
    create_result = runner.invoke(
        bundle_app,
        ["create", "--target", "builder", "--agent", "patch_planner", "--output", str(out_file)],
    )

    assert create_result.exit_code == 0
    assert out_file.exists()
    assert "Bundle written" in create_result.stdout

    validate_result = runner.invoke(bundle_app, ["validate", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_bundle_default_does_not_write(monkeypatch, tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    monkeypatch.setattr("builder_ii.bundle_cli.load_settings", lambda: settings)

    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(bundle_app, ["create", "--target", "builder", "--agent", "repo_mapper"])
        assert result.exit_code == 0
        assert list(Path(".").iterdir()) == []
