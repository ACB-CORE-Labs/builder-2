import json as json_lib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.verification_cli import verification_app
from builder_ii.verification_profiles import (
    default_profile_for_target,
    dumps_profile_artifact,
    get_verification_profile,
    profiles_for_target,
    render_verification_profile,
    validate_profile_artifact,
    validate_profile_artifact_file,
    validate_verification_profiles,
    verification_profile_names,
)


def test_registry_contains_expected_profiles() -> None:
    assert set(verification_profile_names()) == {
        "generic_basic",
        "builder_fast",
        "builder_full",
        "core_smoke",
        "core_focused",
    }
    assert validate_verification_profiles() == ()


def test_profiles_are_target_scoped() -> None:
    assert default_profile_for_target("generic").name == "generic_basic"
    assert default_profile_for_target("builder").name == "builder_full"
    assert default_profile_for_target("core").name == "core_smoke"
    assert [profile.name for profile in profiles_for_target("builder")] == ["builder_fast", "builder_full"]


def test_profile_artifact_shape() -> None:
    profile = get_verification_profile("builder_full")
    data = profile.to_artifact_dict(target="builder", task="verify bundle surface")

    assert data["kind"] == "builder_ii.verification_profile"
    assert data["schema_version"] == 1
    assert data["name"] == "builder_full"
    assert data["target"] == "builder"
    assert data["task"] == "verify bundle surface"
    assert data["governance"]["runtime_execution"] == "DISABLED"
    assert data["governance"]["shell_execution"] == "DISABLED"
    assert data["governance"]["executes_commands"] is False
    assert data["governance"]["artifact_is_authority"] is False
    assert validate_profile_artifact(data) == []


def test_render_profile_contains_boundary() -> None:
    rendered = render_verification_profile(get_verification_profile("core_smoke"), target="core", task="smoke check")

    assert "# Verification profile: core_smoke" in rendered
    assert "## Proposed commands" in rendered
    assert "does not execute commands" in rendered
    assert "CORE Workbench" not in rendered


def test_profile_json_round_trip() -> None:
    text = dumps_profile_artifact(get_verification_profile("repo_mapper") if False else get_verification_profile("generic_basic"), target="generic")
    data = json_lib.loads(text)

    assert data["kind"] == "builder_ii.verification_profile"
    assert validate_profile_artifact(data) == []


def test_validate_profile_artifact_rejects_runtime_authority() -> None:
    data = get_verification_profile("builder_fast").to_artifact_dict(target="builder")
    data["governance"]["runtime_execution"] = "ENABLED"
    data["governance"]["shell_execution"] = "ENABLED"
    data["governance"]["executes_commands"] = True
    data["governance"]["artifact_is_authority"] = True

    errors = validate_profile_artifact(data)

    assert "governance.runtime_execution must be DISABLED" in errors
    assert "governance.shell_execution must be DISABLED" in errors
    assert "governance.executes_commands must be false" in errors
    assert "governance.artifact_is_authority must be false" in errors


def test_validate_profile_artifact_file_errors(tmp_path: Path) -> None:
    assert any("file not found" in error for error in validate_profile_artifact_file(tmp_path / "missing.json"))

    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{bad json", encoding="utf-8")
    assert any("invalid JSON" in error for error in validate_profile_artifact_file(bad_json))

    not_object = tmp_path / "array.json"
    not_object.write_text("[]", encoding="utf-8")
    assert "verification profile artifact must be a JSON object" in validate_profile_artifact_file(not_object)


def test_cli_list_show_and_registry_validate() -> None:
    runner = CliRunner()

    listed = runner.invoke(verification_app, ["list", "--target", "builder"])
    assert listed.exit_code == 0
    assert "builder_fast" in listed.stdout
    assert "builder_full" in listed.stdout

    shown = runner.invoke(verification_app, ["show", "builder_full", "--target", "builder", "--task", "verify"])
    assert shown.exit_code == 0
    assert "Verification profile: builder_full" in shown.stdout

    validated = runner.invoke(verification_app, ["validate"])
    assert validated.exit_code == 0
    assert "registry is valid" in validated.stdout


def test_cli_artifact_stdout_output_and_validate(tmp_path: Path) -> None:
    runner = CliRunner()

    stdout_result = runner.invoke(verification_app, ["artifact", "builder_full", "--target", "builder", "--task", "verify"])
    assert stdout_result.exit_code == 0
    data = json_lib.loads(stdout_result.stdout)
    assert data["name"] == "builder_full"
    assert data["governance"]["executes_commands"] is False

    out_file = tmp_path / "verification-profile.json"
    output_result = runner.invoke(
        verification_app,
        ["artifact", "builder_full", "--target", "builder", "--output", str(out_file)],
    )
    assert output_result.exit_code == 0
    assert out_file.exists()
    assert "written" in output_result.stdout

    validate_result = runner.invoke(verification_app, ["validate", str(out_file)])
    assert validate_result.exit_code == 0
    assert "is valid" in validate_result.stdout


def test_cli_artifact_default_does_not_write() -> None:
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(verification_app, ["artifact", "generic_basic", "--target", "generic"])
        assert result.exit_code == 0
        assert list(Path(".").iterdir()) == []
