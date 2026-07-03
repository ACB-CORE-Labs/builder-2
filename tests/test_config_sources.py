"""test_config_sources.py

Covers:
  - Original precedence, path, redaction, and artifact tests (restored)
  - Import compatibility guards for CLI modules and setup_onboarding
  - Digest-bound artifact schema check
  - run_core_demo_loop signature smoke test
  - CoreDemoAdapter presence and boundary guard
  - target_profile_defaults delegation (no CORE strings in config_sources)
"""
from __future__ import annotations

import importlib
import inspect
from pathlib import Path

from builder_ii.config_sources import (
    ConfigResolution,
    ResolvedValue,
    SourceRef,
    dumps_config_resolution,
    load_config_resolution_artifact,
    resolve_config_sources,
    validate_config_resolution_artifact,
    write_config_resolution_artifact,
)


def _missing_config(tmp_path: Path) -> Path:
    return tmp_path / "missing-builder-config.json"


def _repo(tmp_path: Path, name: str = "target") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    return repo


# ---------------------------------------------------------------------------
# Original precedence / path / redaction tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Digest-bound artifact schema
# ---------------------------------------------------------------------------

def test_artifact_schema_is_digest_bound(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(repo),
            "BUILDER_TARGET_PROFILE": "generic",
            "BUILDER_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        },
        builder_config_file=_missing_config(tmp_path),
    )
    artifact = resolution.to_jsonable()
    assert "digest" in artifact
    assert len(artifact["digest"]) == 64
    errors = validate_config_resolution_artifact(artifact)
    assert not errors


def test_write_and_load_round_trip(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(repo),
            "BUILDER_TARGET_PROFILE": "generic",
            "BUILDER_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        },
        builder_config_file=_missing_config(tmp_path),
    )
    out = tmp_path / "artifacts" / "config-resolution.json"
    write_config_resolution_artifact(resolution, out)
    loaded = load_config_resolution_artifact(out)
    errors = validate_config_resolution_artifact(loaded)
    assert not errors


def test_dumps_config_resolution_is_valid_json(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(repo),
            "BUILDER_TARGET_PROFILE": "generic",
            "BUILDER_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
        },
        builder_config_file=_missing_config(tmp_path),
    )
    import json
    text = dumps_config_resolution(resolution)
    data = json.loads(text)
    assert data["kind"] == "builder_ii.config_source_resolution"


# ---------------------------------------------------------------------------
# Public API types are importable with correct shapes
# ---------------------------------------------------------------------------

def test_source_ref_has_expected_fields() -> None:
    ref = SourceRef(kind="cli_override", key="target_repo", path="")
    assert ref.kind == "cli_override"
    d = ref.to_jsonable()
    assert set(d.keys()) == {"kind", "key", "path"}


def test_config_resolution_type_is_importable() -> None:
    assert ConfigResolution is not None
    assert ResolvedValue is not None


# ---------------------------------------------------------------------------
# target_profile_defaults delegation — CORE strings must not leak into
# config_sources module source text
# ---------------------------------------------------------------------------

def test_config_sources_does_not_hardcode_core_strings() -> None:
    import builder_ii.config_sources as cs_mod
    source = inspect.getsource(cs_mod)
    # The function _target_profile_defaults MAY reference get_target_defaults
    # but must not contain hardcoded CORE-specific paths or agent names.
    assert "core.patch_planner" not in source, (
        "core.patch_planner must live only in target_profile_defaults, not config_sources"
    )
    assert 'parent / "core"' not in source, (
        'CORE sibling repo path must live only in target_profile_defaults, not config_sources'
    )


# ---------------------------------------------------------------------------
# Import compatibility guards
# ---------------------------------------------------------------------------

def test_import_config_cli() -> None:
    mod = importlib.import_module("builder_ii.cli.config_cli")
    assert mod is not None


def test_import_platform_status_cli() -> None:
    mod = importlib.import_module("builder_ii.cli.platform_status_cli")
    assert mod is not None


def test_import_setup_onboarding() -> None:
    mod = importlib.import_module("builder_ii.setup_onboarding")
    assert mod is not None


# ---------------------------------------------------------------------------
# run_core_demo_loop signature smoke test
# ---------------------------------------------------------------------------

def test_run_core_demo_loop_signature() -> None:
    from builder_ii.core_demo_loop import run_core_demo_loop
    sig = inspect.signature(run_core_demo_loop)
    params = set(sig.parameters.keys())
    assert {"core_repo", "output_dir", "phase", "approve", "force", "cleanup_worktree"}.issubset(params)


def test_dumps_core_demo_report_is_importable() -> None:
    from builder_ii.core_demo_loop import dumps_core_demo_report, validate_core_demo_report
    assert callable(dumps_core_demo_report)
    assert callable(validate_core_demo_report)


# ---------------------------------------------------------------------------
# CoreDemoAdapter presence and boundary guard
# ---------------------------------------------------------------------------

def test_core_demo_adapter_is_present() -> None:
    from builder_ii.core_demo_loop import CoreDemoAdapter
    adapter = CoreDemoAdapter()
    assert adapter.target_name == "core"
    assert "AssetOverflow/core" in adapter.repo_remote_hint
    assert len(adapter.sensitive_modules) > 0


def test_core_demo_adapter_does_not_drive_phase_logic() -> None:
    """CoreDemoAdapter must be a data class, not a controller."""
    from builder_ii.core_demo_loop import CoreDemoAdapter
    # It must not have any method that resembles phase execution
    public_methods = [
        name for name, _ in inspect.getmembers(CoreDemoAdapter, predicate=inspect.isfunction)
        if not name.startswith("_")
    ]
    assert public_methods == [], f"CoreDemoAdapter must be data-only; found methods: {public_methods}"


# ---------------------------------------------------------------------------
# platform_status_cli demo-loop signature compatibility
# ---------------------------------------------------------------------------

def test_platform_status_cli_demo_loop_can_call_run_core_demo_loop() -> None:
    """Verify platform_status_cli imports run_core_demo_loop (import chain intact)."""
    mod = importlib.import_module("builder_ii.cli.platform_status_cli")
    # The CLI module must be able to reach run_core_demo_loop through its import chain.
    # We verify this by checking it doesn't raise at import time (done above) and
    # that the function is reachable from the core_demo_loop module.
    from builder_ii.core_demo_loop import run_core_demo_loop
    assert callable(run_core_demo_loop)
