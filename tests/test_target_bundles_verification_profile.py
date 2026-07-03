from pathlib import Path
from types import SimpleNamespace

from builder_ii.bundles import create_target_bundle, validate_target_bundle


def _settings(tmp_path: Path):
    core = tmp_path / "core"
    builder = tmp_path / "builder"
    core.mkdir()
    builder.mkdir()
    (core / "README.md").write_text("core", encoding="utf-8")
    (builder / "README.md").write_text("builder", encoding="utf-8")
    return SimpleNamespace(core_repo=core, project_root=builder)


def test_target_bundle_embeds_default_verification_profile(tmp_path: Path) -> None:
    bundle = create_target_bundle(
        _settings(tmp_path),
        target_name="builder",
        agent_profile="patch_planner",
        task="verify target bundle work",
    )

    assert bundle["verification_profile"]["kind"] == "builder_ii.verification_profile"
    assert bundle["verification_profile"]["name"] == "builder_full"
    assert bundle["verification_profile"]["target"] == "builder"
    assert bundle["verification_profile"]["governance"]["executes_commands"] is False
    assert bundle["verification_profile_validation_errors"] == []
    assert validate_target_bundle(bundle) == []


def test_target_bundle_rejects_executable_verification_profile(tmp_path: Path) -> None:
    bundle = create_target_bundle(_settings(tmp_path), target_name="builder", agent_profile="patch_planner")
    bundle["verification_profile"]["governance"]["executes_commands"] = True

    errors = validate_target_bundle(bundle)

    assert "verification_profile: governance.executes_commands must be false or NOT_AUTHORIZED" in errors
