import json
from pathlib import Path

from builder_ii.config_sources import resolve_config_sources
from builder_ii.setup_overlay import create_setup_overlay_plan
from builder_ii.setup_plan import create_setup_plan
from builder_ii.setup_rollback import (
    create_setup_rollback_snapshot,
    validate_setup_rollback_snapshot_artifact,
)


def _seed_source_tree(root: Path) -> None:
    (root / "recipes").mkdir(parents=True)
    (root / "recipes" / "example.yaml").write_text("name: example\n", encoding="utf-8")
    skill = root / ".agents" / "skills" / "alpha"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")


def _overlay(tmp_path: Path) -> dict:
    _seed_source_tree(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
    (target / ".agents" / "skills").mkdir(parents=True)
    home = tmp_path / "home"
    goose_config = home / ".config" / "goose" / "config.yaml"
    resolution = resolve_config_sources(
        project_root=tmp_path,
        environ={
            "BUILDER_TARGET_REPO": str(target),
            "BUILDER_ARTIFACT_ROOT": str(tmp_path / "artifacts"),
            "BUILDER_GOOSE_CONFIG_PATH": str(goose_config),
            "BUILDER_GOOSE_RECIPE_PATH": str(tmp_path / "recipes"),
            "BUILDER_GOOSE_SKILLS_SOURCE": str(tmp_path / ".agents" / "skills"),
        },
        builder_config_file=tmp_path / "missing.json",
    )
    assert not resolution.errors
    plan = create_setup_plan(resolution)
    return create_setup_overlay_plan(plan, user_config_dir=tmp_path / "home" / ".config")


def test_rollback_snapshot_validates_and_is_not_authority(tmp_path: Path) -> None:
    snapshot = create_setup_rollback_snapshot(_overlay(tmp_path))

    assert not validate_setup_rollback_snapshot_artifact(snapshot)
    assert snapshot["artifact_is_authority"] is False
    assert snapshot["snapshot_only"] is True
    assert snapshot["governance"]["artifact_is_authority"] is False
    assert snapshot["secret_policy"]["raw_secrets_stored_in_json"] is False
    assert snapshot["secret_policy"]["raw_prior_content_stored_in_json"] is False
    assert all(state["snapshot_only"] is True for state in snapshot["target_path_states"])
    assert all(state["raw_content_included"] is False for state in snapshot["target_path_states"])


def test_rollback_snapshot_has_deterministic_digest(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)

    first = create_setup_rollback_snapshot(overlay)
    second = create_setup_rollback_snapshot(overlay)

    assert first["snapshot_id"] == second["snapshot_id"]
    assert first["snapshot_digest"] == second["snapshot_digest"]


def test_secret_bearing_prior_file_is_redacted(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)
    target = Path(overlay["target_repo_canonical_path"])
    (target / ".env").write_text("BUILDER_MODEL_API_TOKEN=super-secret-value\nSAFE=yes\n", encoding="utf-8")

    snapshot = create_setup_rollback_snapshot(overlay)
    env_state = next(state for state in snapshot["target_path_states"] if state["target_path"] == str((target / ".env").resolve()))

    assert env_state["prior_existence_state"] == "file"
    assert env_state["prior_content_digest"]
    assert env_state["secret_redaction_state"] == "redacted_secret_like_content"
    assert "super-secret-value" not in env_state["prior_redacted_preview"]
    assert "BUILDER_MODEL_API_TOKEN=<redacted>" in env_state["prior_redacted_preview"]
    assert "super-secret-value" not in json.dumps(snapshot)


def test_snapshot_records_missing_directory_and_file_states(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)
    snapshot = create_setup_rollback_snapshot(overlay)
    by_path = {state["target_path"]: state for state in snapshot["target_path_states"]}
    target = Path(overlay["target_repo_canonical_path"])

    assert by_path[str((target / ".agents" / "skills").resolve())]["directory_marker"] is True
    assert by_path[str((target / ".goosehints").resolve())]["missing_file_marker"] is True


def test_snapshot_records_symlink_marker_without_following(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)
    target = Path(overlay["target_repo_canonical_path"])
    outside = tmp_path / "outside.env"
    outside.write_text("TOKEN=do-not-read-through-link\n", encoding="utf-8")
    (target / ".env").symlink_to(outside)

    snapshot = create_setup_rollback_snapshot(overlay)
    env_state = next(state for state in snapshot["target_path_states"] if state["target_path"] == str(target / ".env"))

    assert env_state["prior_existence_state"] == "symlink"
    assert env_state["symlink_marker"] is True
    assert env_state["prior_content_digest"] == ""
    assert "do-not-read-through-link" not in json.dumps(env_state)


def test_snapshot_requires_future_secure_storage_for_existing_files(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)
    target = Path(overlay["target_repo_canonical_path"])
    (target / ".goosehints").write_text("existing hints\n", encoding="utf-8")

    snapshot = create_setup_rollback_snapshot(overlay)
    state = next(
        item for item in snapshot["target_path_states"] if item["target_path"] == str((target / ".goosehints").resolve())
    )

    assert state["prior_existence_state"] == "file"
    assert state["prior_content_storage_policy"] == "digest_size_redacted_preview_only_future_secure_snapshot_required"
    assert state["future_rollback_operation_needed"] == "restore_prior_file_from_future_secure_snapshot"
