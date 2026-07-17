from __future__ import annotations

import json as json_lib
from pathlib import Path
from types import SimpleNamespace
import pytest

from builder_ii.profile_resolution import (
    ProfileResolver,
    ResolutionResult,
    ProfileResolutionError,
    UnknownProfileError,
    MissingFileError,
    ValidationError,
    PromptProfile,
    get_prompt_profile,
    prompt_profiles,
)

def _mock_settings(tmp_path: Path):
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("core", encoding="utf-8")
    (builder / "README.md").write_text("builder", encoding="utf-8")
    (builder / "builder_ii").mkdir()
    return SimpleNamespace(target_repo=core, project_root=builder)


def test_prompt_profiles_resolution() -> None:
    profiles = prompt_profiles()
    assert len(profiles) == 3
    names = {p.name for p in profiles}
    assert "generic_default" in names
    assert "builder_default" in names
    assert "core_default" in names

    with pytest.raises(ValueError, match="unknown prompt profile"):
        get_prompt_profile("non_existent")


def test_resolver_generic_defaults(tmp_path: Path) -> None:
    settings = _mock_settings(tmp_path)
    generic_repo = tmp_path / "generic"
    generic_repo.mkdir()
    (generic_repo / "README.md").write_text("generic", encoding="utf-8")

    resolver = ProfileResolver(settings, generic_repo=generic_repo)
    result = resolver.resolve("generic")

    assert result.target_profile.name == "generic"
    assert result.agent_profile.name == "repo_mapper"
    assert result.prompt_profile.name == "generic_default"
    assert result.verification_profile.name == "generic_basic"
    assert result.repo_path == str(generic_repo.resolve())
    assert "README.md" in result.context_defaults


def test_resolver_builder_defaults(tmp_path: Path) -> None:
    settings = _mock_settings(tmp_path)
    resolver = ProfileResolver(settings)
    result = resolver.resolve("builder")

    assert result.target_profile.name == "builder"
    assert result.agent_profile.name == "context_planner"
    assert result.prompt_profile.name == "builder_default"
    assert result.verification_profile.name == "builder_fast"
    assert result.repo_path == str(settings.project_root.resolve())
    assert "README.md" in result.context_defaults


def test_resolver_core_defaults(tmp_path: Path) -> None:
    settings = _mock_settings(tmp_path)
    resolver = ProfileResolver(settings)
    result = resolver.resolve("core")

    assert result.target_profile.name == "core"
    assert result.agent_profile.name == "code_reviewer"
    assert result.prompt_profile.name == "core_default"
    assert result.verification_profile.name == "core_smoke"
    assert result.repo_path == str(settings.target_repo.resolve())
    assert "README.md" in result.context_defaults


def test_resolver_unknown_profile_names(tmp_path: Path) -> None:
    settings = _mock_settings(tmp_path)
    resolver = ProfileResolver(settings)

    # Unknown target
    with pytest.raises(UnknownProfileError, match="unknown target profile"):
        resolver.resolve("unknown_target")

    # Unknown agent profile
    with pytest.raises(UnknownProfileError, match="unknown agent profile"):
        resolver.resolve("generic", agent_profile_name="unknown_agent")

    # Unknown prompt profile
    with pytest.raises(UnknownProfileError, match="unknown prompt profile"):
        resolver.resolve("generic", prompt_profile_name="unknown_prompt")

    # Unknown verification profile
    with pytest.raises(UnknownProfileError, match="unknown verification profile"):
        resolver.resolve("generic", verification_profile_name="unknown_verification")


def test_resolver_incompatible_profiles(tmp_path: Path) -> None:
    settings = _mock_settings(tmp_path)
    resolver = ProfileResolver(settings)

    # Incompatible agent profile (though base agent profiles are generic-compatible, we validate compatibility checking)
    # Let's verify prompt compatibility mismatch
    with pytest.raises(ValidationError, match="is not compatible with target"):
        resolver.resolve("generic", prompt_profile_name="core_default")

    # Verification compatibility mismatch
    with pytest.raises(ValidationError, match="is not compatible with target"):
        resolver.resolve("generic", verification_profile_name="builder_fast")

    with pytest.raises(ValidationError, match="is not compatible with target"):
        resolver.resolve("core", verification_profile_name="builder_fast")


def test_resolver_missing_files(tmp_path: Path) -> None:
    settings = _mock_settings(tmp_path)
    # Delete core directory to simulate missing repository path
    import shutil
    shutil.rmtree(settings.target_repo)

    resolver = ProfileResolver(settings)
    with pytest.raises(MissingFileError, match="repository path does not exist"):
        resolver.resolve("core")

    # Override with a non-existent path
    with pytest.raises(MissingFileError, match="repository path does not exist"):
        resolver.resolve("generic", repo_path=tmp_path / "non_existent_override")


def test_resolver_repo_path_is_file(tmp_path: Path) -> None:
    settings = _mock_settings(tmp_path)
    fake_file = tmp_path / "some_file.txt"
    fake_file.write_text("not a directory", encoding="utf-8")

    resolver = ProfileResolver(settings)
    with pytest.raises(ValidationError, match="repository path is not a directory"):
        resolver.resolve("generic", repo_path=fake_file)


def test_resolver_serialization(tmp_path: Path) -> None:
    settings = _mock_settings(tmp_path)
    resolver = ProfileResolver(settings)
    result = resolver.resolve("builder")

    serialized = result.to_dict()
    assert isinstance(serialized, dict)
    assert serialized["target_profile"]["name"] == "builder"
    assert serialized["selected_agent_profile"]["name"] == "context_planner"
    assert serialized["selected_prompt_profile"]["name"] == "builder_default"
    assert serialized["selected_verification_profile"]["name"] == "builder_fast"
    assert serialized["repo_path"] == str(settings.project_root.resolve())
    assert isinstance(serialized["context_defaults"], list)

    # Check JSON serializability
    json_str = json_lib.dumps(serialized)
    assert isinstance(json_str, str)
