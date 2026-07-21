import json
from pathlib import Path

from builder_ii.core.config_schema import attach_digest
from builder_ii.core.config_sources import resolve_config_sources
from builder_ii.lifecycle.setup.setup_overlay import create_setup_overlay_plan, validate_setup_overlay_plan_artifact
from builder_ii.lifecycle.setup.setup_plan import create_setup_plan


def _seed_source_tree(root: Path) -> None:
    (root / "recipes").mkdir(parents=True)
    (root / "recipes" / "example.yaml").write_text("name: example\n", encoding="utf-8")
    skill = root / ".agents" / "skills" / "alpha"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("# Alpha\n", encoding="utf-8")


def _plan(tmp_path: Path) -> dict:
    _seed_source_tree(tmp_path)
    target = tmp_path / "target"
    target.mkdir()
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
    return create_setup_plan(resolution)


def _overlay(tmp_path: Path) -> dict:
    return create_setup_overlay_plan(_plan(tmp_path), user_config_dir=tmp_path / "home" / ".config")


def test_overlay_plan_validates_and_is_not_authority(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)

    assert not validate_setup_overlay_plan_artifact(overlay)
    assert overlay["artifact_is_authority"] is False
    assert overlay["planned_only"] is True
    assert overlay["governance"]["artifact_is_authority"] is False
    assert overlay["safety_summary"]["all_changes_planned_only"] is True
    assert overlay["safety_summary"]["planned_write_paths_all_within_declared_scopes"] is True
    assert all(change["planned_only"] is True for change in overlay["planned_changes"])

    kinds = {change["change_kind"] for change in overlay["planned_changes"]}
    assert {
        "builder_config_file_candidate",
        "env_recommendation_candidate",
        "goose_config_overlay_candidate",
        "goosehints_candidate",
        "moim_session_context_candidate",
        "recipe_path_registration_candidate",
        "skill_install_plan_candidate",
        "target_profile_reference_materialization_candidate",
    } <= kinds


def test_overlay_plan_has_deterministic_digest(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    first = create_setup_overlay_plan(plan, user_config_dir=tmp_path / "home" / ".config")
    second = create_setup_overlay_plan(plan, user_config_dir=tmp_path / "home" / ".config")

    assert first["overlay_plan_digest"] == second["overlay_plan_digest"]


def test_overlay_classifies_declared_setup_scopes(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)
    by_id = {change["change_id"]: change for change in overlay["planned_changes"]}

    assert by_id["builder_config_file_candidate"]["path_scope_classification"] == "artifact_root"
    assert by_id["builder_config_file_candidate"]["inside_artifact_root"] is True
    assert by_id["env_recommendation_candidate"]["path_scope_classification"] == "target_repo"
    assert by_id["env_recommendation_candidate"]["inside_target_repo"] is True
    assert by_id["goose_config_overlay_candidate"]["path_scope_classification"] == "user_config_dir"
    assert by_id["goose_config_overlay_candidate"]["inside_user_config_dir"] is True


def test_goose_overlay_preserves_credentials_policy(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)
    goose = overlay["goose_overlay_candidate"]

    assert goose["config_target_path"].endswith(".config/goose/config.yaml")
    assert "recipes.builder_ii.path" in goose["overlay_keys"]
    assert goose["slash_command_recipe_paths"]
    assert goose["extension_policy"] == "preserve_existing_extensions_and_merge_builder_ii_keys_only"
    assert goose["secrets_preservation_policy"] == "do_not_copy_credentials_or_secret_values_into_overlay_artifact"
    assert "credential" not in json.dumps(goose).lower() or "do_not_copy_credentials" in json.dumps(goose)


def test_skill_install_plan_detects_destination_conflict_without_copying(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    target = Path(plan["target_repo_canonical_path"])
    destination = target / ".agents" / "skills"
    destination.mkdir(parents=True)
    (destination / "alpha").write_text("not a directory\n", encoding="utf-8")

    overlay = create_setup_overlay_plan(plan, user_config_dir=tmp_path / "home" / ".config")
    entry = overlay["skill_install_plan"]["entries"][0]

    assert entry["skill_id"] == "alpha"
    assert entry["operation_type"] == "replace"
    assert entry["conflict_classification"] == "destination_file_conflict"
    assert entry["planned_only"] is True
    assert (destination / "alpha").read_text(encoding="utf-8") == "not a directory\n"


def test_path_traversal_is_denied_by_overlay_validation(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    bad_plan = dict(plan)
    bad_plan["goose_config_target_path"] = str(tmp_path / "target" / ".." / "escape.yaml")
    bad_plan = attach_digest(bad_plan, digest_key="plan_digest")

    overlay = create_setup_overlay_plan(bad_plan, user_config_dir=tmp_path / "home" / ".config")
    errors = validate_setup_overlay_plan_artifact(overlay)

    assert any("path traversal" in error for error in errors)
    by_id = {change["change_id"]: change for change in overlay["planned_changes"]}
    assert by_id["goose_config_overlay_candidate"]["conflict_classification"] == "unsafe_path_traversal"


def test_planned_write_outside_declared_scopes_is_denied(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    bad_plan = dict(plan)
    bad_plan["goose_config_target_path"] = str(tmp_path.parent / "outside-goose.yaml")
    bad_plan = attach_digest(bad_plan, digest_key="plan_digest")

    overlay = create_setup_overlay_plan(bad_plan, user_config_dir=tmp_path / "home" / ".config")
    errors = validate_setup_overlay_plan_artifact(overlay)
    by_id = {change["change_id"]: change for change in overlay["planned_changes"]}

    assert by_id["goose_config_overlay_candidate"]["conflict_classification"] == "outside_declared_setup_scopes"
    assert any("declared setup scope" in error for error in errors)


def test_symlink_target_is_classified_as_unsafe_without_following(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    target = Path(plan["target_repo_canonical_path"])
    outside = tmp_path / "outside.env"
    outside.write_text("SAFE=1\n", encoding="utf-8")
    (target / ".env").symlink_to(outside)

    overlay = create_setup_overlay_plan(plan, user_config_dir=tmp_path / "home" / ".config")
    by_id = {change["change_id"]: change for change in overlay["planned_changes"]}

    assert by_id["env_recommendation_candidate"]["conflict_classification"] == "symlink_path"
    assert any("symlink_path" in error for error in validate_setup_overlay_plan_artifact(overlay))
    assert outside.read_text(encoding="utf-8") == "SAFE=1\n"


def test_directory_file_conflict_is_classified(tmp_path: Path) -> None:
    plan = _plan(tmp_path)
    target = Path(plan["target_repo_canonical_path"])
    (target / ".goosehints").mkdir()

    overlay = create_setup_overlay_plan(plan, user_config_dir=tmp_path / "home" / ".config")
    by_id = {change["change_id"]: change for change in overlay["planned_changes"]}

    assert by_id["target_goosehints_candidate"]["conflict_classification"] == "directory_file_conflict"
    assert any("directory_file_conflict" in error for error in validate_setup_overlay_plan_artifact(overlay))


def test_missing_parent_is_classified_but_allowed_for_future_atomic_apply(tmp_path: Path) -> None:
    overlay = _overlay(tmp_path)
    by_id = {change["change_id"]: change for change in overlay["planned_changes"]}

    assert by_id["builder_config_file_candidate"]["conflict_classification"] == "missing_parent"
    assert not validate_setup_overlay_plan_artifact(overlay)


def test_every_real_planner_materialization_change_can_be_applied_byte_for_byte(tmp_path: Path) -> None:
    """Apply must be able to reconstruct exactly the bytes the plan digested -- for the REAL planner.

    `setup_apply` grew a digest-parity preflight that refuses to write bytes the plan did not
    digest. Good. But every test that exercised it built its own change dicts, so nothing ever
    asked whether the *planner's own* changes survive it. Two did not:

    - `builder_config_file_candidate` digested `content` and stored `metadata={"candidate": content}`
    - `moim_session_context_candidate` digested `content` and stored a two-key *label*

    `setup_apply._content_text` reconstructs the file body from `metadata`, so apply would have
    written a wrapper -- or a label -- into the target in place of the document the plan digested.
    Silently, under a green `applied` receipt, because `content` is never carried in the artifact
    and nothing compared the two.

    This pin closes the whole class: for every create/replace change the real planner emits, the
    bytes apply would write must hash to the change's own `content_digest`.
    """
    from builder_ii.lifecycle.setup.setup_apply import _content_text, _sha256_bytes

    overlay = _overlay(tmp_path)
    materializations = [c for c in overlay["planned_changes"] if c["operation_type"] in {"create", "replace"}]
    assert materializations, "the planner must emit at least one materialization change"

    mismatched = [
        c["change_id"]
        for c in materializations
        if c.get("content_digest") != _sha256_bytes(_content_text(c).encode("utf-8"))
    ]
    assert not mismatched, (
        f"apply would write bytes these planner changes never digested: {mismatched}. "
        "For a materialization change, `metadata` must BE the digested `content`."
    )
