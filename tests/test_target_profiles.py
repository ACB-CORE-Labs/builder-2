from pathlib import Path
from types import SimpleNamespace

from builder_ii.target_profiles import (
    build_target_profiles,
    render_target_profile,
    target_names,
    target_profile,
    validate_target_profiles,
)


def _settings(tmp_path: Path):
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("core", encoding="utf-8")
    (builder / "README.md").write_text("builder", encoding="utf-8")
    (builder / "builder_ii").mkdir()
    return SimpleNamespace(core_repo=core, project_root=builder)


def test_target_names_are_stable() -> None:
    assert target_names() == ("generic", "builder", "core")


def test_profiles_resolve_repositories(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    generic = tmp_path / "generic"
    generic.mkdir()
    profiles = {profile.name: profile for profile in build_target_profiles(settings, generic_repo=generic)}

    assert profiles["generic"].repo == generic.resolve()
    assert profiles["builder"].repo == settings.project_root.resolve()
    assert profiles["core"].repo == settings.core_repo.resolve()


def test_builder_profile_stays_generic_first(tmp_path: Path) -> None:
    profile = target_profile(_settings(tmp_path), "builder")

    assert "generic-first" in " ".join(profile.principles)
    assert "builder_ii" in profile.context_defaults


def test_core_profile_is_isolated_target(tmp_path: Path) -> None:
    profile = target_profile(_settings(tmp_path), "core")

    assert "target profile" in profile.description
    assert profile.notes


def test_validate_profiles_passes_for_existing_repos(tmp_path: Path) -> None:
    assert validate_target_profiles(_settings(tmp_path)) == ()


def test_validate_profiles_reports_missing_core_repo(tmp_path: Path) -> None:
    builder = tmp_path / "builder"
    builder.mkdir()
    settings = SimpleNamespace(core_repo=tmp_path / "missing-core", project_root=builder)

    assert any("core repo missing" in error for error in validate_target_profiles(settings))


def test_render_profile_has_expected_sections(tmp_path: Path) -> None:
    rendered = render_target_profile(target_profile(_settings(tmp_path), "builder"))

    assert "# Target profile: builder" in rendered
    assert "## Repository" in rendered
    assert "## Context defaults" in rendered
    assert "## Verification hints" in rendered
    assert "## Principles" in rendered


def test_target_profile_to_artifact_dict(tmp_path: Path) -> None:
    from builder_ii.target_profiles import (
        TARGET_PROFILE_ARTIFACT_KIND,
        TARGET_PROFILE_SCHEMA_VERSION,
        validate_target_profile_artifact,
        validate_target_profile_artifact_file,
        write_target_profile_artifact,
    )

    settings = _settings(tmp_path)
    profile = target_profile(settings, "builder")

    art_dict = profile.to_artifact_dict()
    assert art_dict["kind"] == TARGET_PROFILE_ARTIFACT_KIND
    assert art_dict["schema_version"] == TARGET_PROFILE_SCHEMA_VERSION
    assert art_dict["name"] == "builder"
    assert art_dict["governance"]["runtime_execution"] == "DISABLED"

    errors = validate_target_profile_artifact(art_dict)
    assert not errors, f"Should be valid: {errors}"

    # Test file-based validation
    output_file = tmp_path / "target_profile.json"
    write_target_profile_artifact(profile, output_file)
    assert output_file.exists()

    file_errors = validate_target_profile_artifact_file(output_file)
    assert not file_errors, f"File should be valid: {file_errors}"


def test_target_profile_validation_failures(tmp_path: Path) -> None:
    from builder_ii.target_profiles import validate_target_profile_artifact, validate_target_profile_artifact_file

    # Non-dict validation
    assert any("must be a JSON object" in err for err in validate_target_profile_artifact([]))

    # Missing kind / schema version
    bad_dict = {
        "kind": "wrong_kind",
        "schema_version": 1,
        "name": "builder",
    }
    errors = validate_target_profile_artifact(bad_dict)
    assert any("kind must be" in err for err in errors)

    # Missing list fields
    bad_fields = {
        "kind": "builder_ii.target_profile",
        "schema_version": 1,
        "name": "builder",
        "description": 123,  # should be string
        "repo": "path/to/repo",
        "context_defaults": "not a list",
        "verification_hints": [],
        "principles": [],
        "notes": [],
    }
    errors = validate_target_profile_artifact(bad_fields)
    assert any("description must be a non-empty string" in err for err in errors)
    assert any("context_defaults must be a list" in err for err in errors)

    # Bad governance
    bad_gov = {
        "kind": "builder_ii.target_profile",
        "schema_version": 1,
        "name": "builder",
        "description": "desc",
        "repo": "path",
        "context_defaults": [],
        "verification_hints": [],
        "principles": [],
        "notes": [],
        "governance": {
            "runtime_execution": "ENABLED",
            "shell_execution": "DISABLED",
            "writes": "DISABLED",
            "artifact_is_authority": True,
        },
    }
    errors = validate_target_profile_artifact(bad_gov)
    assert any("runtime_execution must be DISABLED" in err for err in errors)
    assert any("artifact_is_authority must be false" in err for err in errors)

    # Missing file validation
    assert "file not found" in validate_target_profile_artifact_file(tmp_path / "non_existent.json")[0]

    # Invalid JSON file
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{invalid", encoding="utf-8")
    assert "invalid JSON" in validate_target_profile_artifact_file(bad_json)[0]
