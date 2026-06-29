from pathlib import Path

from builder_ii.config_sources import resolve_config_sources, validate_config_resolution_artifact


def _missing_config(tmp_path: Path) -> Path:
    return tmp_path / "missing-builder-config.json"


def _repo(tmp_path: Path, name: str = "target") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    return repo


def test_generic_env_names_resolve_correctly(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    env = {
        "BUILDER_TARGET_REPO": str(repo),
        "BUILDER_TARGET_PROFILE": "generic",
        "BUILDER_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        "BUILDER_MODEL_BACKEND": "mlx-lm",
        "BUILDER_MODEL_ALIAS": "qwen-coder",
        "BUILDER_RUNTIME_MODE": "passive",
    }

    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ=env,
        builder_config_file=_missing_config(tmp_path),
    )
    artifact = resolution.to_jsonable()

    assert not resolution.errors
    assert not validate_config_resolution_artifact(artifact)
    assert resolution.fields["target_repo"].source.key == "BUILDER_TARGET_REPO"
    assert resolution.fields["target_repo"].legacy_alias_used is False
    assert resolution.value("target_repo") == str(repo.resolve())
    assert resolution.value("active_target_profile") == "generic"


def test_legacy_core_alias_resolves_with_compatibility_warning(tmp_path: Path) -> None:
    repo = _repo(tmp_path)

    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={"CORE_REPO_PATH": str(repo)},
        builder_config_file=_missing_config(tmp_path),
    )

    assert not resolution.errors
    field = resolution.fields["target_repo"]
    assert field.source.key == "CORE_REPO_PATH"
    assert field.legacy_alias_used is True
    assert any("legacy alias" in warning for warning in field.warnings)


def test_generic_env_wins_over_legacy_alias_in_same_source(tmp_path: Path) -> None:
    generic_repo = _repo(tmp_path, "generic")
    legacy_repo = _repo(tmp_path, "legacy")

    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(generic_repo),
            "CORE_REPO_PATH": str(legacy_repo),
        },
        builder_config_file=_missing_config(tmp_path),
    )

    assert not resolution.errors
    field = resolution.fields["target_repo"]
    assert field.source.key == "BUILDER_TARGET_REPO"
    assert field.legacy_alias_used is False
    assert resolution.value("target_repo") == str(generic_repo.resolve())
    assert any("overrides legacy alias" in warning for warning in field.warnings)


def test_process_environment_wins_over_dotenv(tmp_path: Path) -> None:
    env_repo = _repo(tmp_path, "env-repo")
    dotenv_repo = _repo(tmp_path, "dotenv-repo")
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text(f"BUILDER_TARGET_REPO={dotenv_repo}\n", encoding="utf-8")

    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={"BUILDER_TARGET_REPO": str(env_repo)},
        dotenv_path=dotenv_path,
        builder_config_file=_missing_config(tmp_path),
    )

    assert not resolution.errors
    assert resolution.fields["target_repo"].source.kind == "process_environment"
    assert resolution.value("target_repo") == str(env_repo.resolve())


def test_cli_override_wins_over_environment(tmp_path: Path) -> None:
    cli_repo = _repo(tmp_path, "cli-repo")
    env_repo = _repo(tmp_path, "env-repo")

    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={"BUILDER_TARGET_REPO": str(env_repo)},
        cli_overrides={"target_repo": str(cli_repo)},
        builder_config_file=_missing_config(tmp_path),
    )

    assert not resolution.errors
    assert resolution.fields["target_repo"].source.kind == "cli_override"
    assert resolution.value("target_repo") == str(cli_repo.resolve())


def test_secret_values_are_redacted_in_artifact(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(repo),
            "BUILDER_MODEL_API_TOKEN": "sk-test-secret",
        },
        builder_config_file=_missing_config(tmp_path),
    )

    model_token = resolution.to_jsonable()["resolved"]["model_api_token"]
    assert model_token["value"] == "<redacted>"
    assert model_token["redacted_value"] == "<redacted>"
    assert model_token["value_redacted"] is True
    assert "sk-test-secret" not in str(resolution.to_jsonable())


def test_path_normalization_uses_project_root_for_relative_paths(tmp_path: Path) -> None:
    repo = _repo(tmp_path, "relative-target")

    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={"BUILDER_TARGET_REPO": "relative-target"},
        builder_config_file=_missing_config(tmp_path),
    )

    assert not resolution.errors
    assert resolution.value("target_repo") == str(repo.resolve())


def test_unsafe_artifact_root_inside_target_requires_explicit_policy(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    unsafe = repo / "src" / "artifacts"

    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(repo),
            "BUILDER_ARTIFACT_ROOT": str(unsafe),
        },
        builder_config_file=_missing_config(tmp_path),
    )

    assert any("platform_artifact_root is inside target_repo" in error for error in resolution.errors)


def test_artifact_root_inside_target_can_be_explicitly_allowed(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    unsafe = repo / "src" / "artifacts"

    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(repo),
            "BUILDER_ARTIFACT_ROOT": str(unsafe),
            "BUILDER_ALLOW_ARTIFACT_ROOT_INSIDE_TARGET": "true",
        },
        builder_config_file=_missing_config(tmp_path),
    )

    assert not resolution.errors
    assert any("explicit path policy opt-in" in warning for warning in resolution.warnings)
