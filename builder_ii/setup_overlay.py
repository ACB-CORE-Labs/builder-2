from __future__ import annotations

import hashlib
import json as json_lib
import os
from pathlib import Path
from typing import Any

from builder_ii.config_schema import CAPABILITY_DEFAULTS, attach_digest, digest_jsonable
from builder_ii.setup_plan import SETUP_PLAN_KIND, validate_setup_plan_artifact


SETUP_OVERLAY_PLAN_KIND = "builder_ii.setup_overlay_plan"
SETUP_OVERLAY_PLAN_SCHEMA_VERSION = 1

_DISABLED_CAPABILITY_MAP = {
    "runtime_execution": "disabled",
    "model_execution": "disabled",
    "shell_execution": "disabled",
    "source_writes": "disabled",
    "goose_runtime": "disabled",
    "deepagents_runtime": "disabled",
    "mcp_tool_invocation": "disabled",
    "patch_authority": "disabled",
    "autonomous_writes": "disabled",
    "setup_apply": "disabled",
    "setup_rollback_execution": "disabled",
    "artifact_output": "explicit_output_path_only",
}

_CHANGE_KINDS = {
    "builder_config_file_candidate",
    "env_recommendation_candidate",
    "goose_config_overlay_candidate",
    "goosehints_candidate",
    "moim_session_context_candidate",
    "recipe_path_registration_candidate",
    "skill_install_plan_candidate",
    "target_profile_reference_materialization_candidate",
}

_OPERATIONS = {"create", "replace", "merge", "copy", "mkdir", "no-op"}
_SCOPES = {
    "artifact_root",
    "user_config_dir",
    "target_repo",
    "builder_repo",
    "outside_declared_setup_scopes",
}
_UNSAFE_CONFLICTS = {
    "unsafe_path_traversal",
    "outside_declared_setup_scopes",
    "symlink_path",
    "parent_symlink",
    "parent_not_directory",
    "directory_file_conflict",
    "file_directory_conflict",
}
_SECRET_MARKERS = ("secret", "token", "api_key", "apikey", "password", "credential", "bearer")


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: str) -> str:
    return _sha256_bytes(text.encode("utf-8"))


def _json_preview(data: dict[str, Any] | list[Any]) -> str:
    return _redact_text(json_lib.dumps(data, indent=2, sort_keys=True))


def _canonical_json_text(data: dict[str, Any] | list[Any]) -> str:
    return json_lib.dumps(data, indent=2, sort_keys=True) + "\n"


def _redact_text(text: str, *, limit: int = 1200) -> str:
    redacted_lines: list[str] = []
    for line in text.splitlines():
        lower = line.lower()
        if any(marker in lower for marker in _SECRET_MARKERS):
            if "=" in line:
                key = line.split("=", 1)[0].strip()
                redacted_lines.append(f"{key}=<redacted>")
            elif ":" in line:
                key = line.split(":", 1)[0].strip()
                redacted_lines.append(f"{key}: <redacted>")
            else:
                redacted_lines.append("<redacted-secret-line>")
        else:
            redacted_lines.append(line)
    preview = "\n".join(redacted_lines)
    if len(preview) > limit:
        return preview[:limit] + "\n<truncated>"
    return preview


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _has_traversal(raw_path: str) -> bool:
    return any(part == ".." for part in Path(raw_path).expanduser().parts)


def _canonicalize_root(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _classify_scope(
    raw_path: str | Path,
    *,
    builder_repo: Path,
    target_repo: Path,
    artifact_root: Path,
    user_config_dir: Path,
) -> dict[str, Any]:
    raw = str(raw_path)
    errors: list[str] = []
    if not raw:
        errors.append("path is empty")
    if "\x00" in raw:
        errors.append("path contains NUL byte")
    traversal = _has_traversal(raw)
    if traversal:
        errors.append("path traversal segment '..' is forbidden")

    path = Path(raw).expanduser()
    if not path.is_absolute():
        errors.append("path must be absolute")
        path = builder_repo / path
    canonical = Path(os.path.abspath(str(path)))

    inside_artifact_root = _is_relative_to(canonical, artifact_root)
    inside_user_config_dir = _is_relative_to(canonical, user_config_dir)
    inside_target_repo = _is_relative_to(canonical, target_repo)
    inside_builder_repo = _is_relative_to(canonical, builder_repo)

    if inside_artifact_root:
        scope = "artifact_root"
    elif inside_user_config_dir:
        scope = "user_config_dir"
    elif inside_target_repo:
        scope = "target_repo"
    elif inside_builder_repo:
        scope = "builder_repo"
    else:
        scope = "outside_declared_setup_scopes"
        errors.append("path is outside builder repo, target repo, user config dir, and artifact root")

    return {
        "raw_target_path": raw,
        "target_path": str(canonical),
        "path_scope_classification": scope,
        "inside_builder_repo": inside_builder_repo,
        "inside_target_repo": inside_target_repo,
        "inside_user_config_dir": inside_user_config_dir,
        "inside_artifact_root": inside_artifact_root,
        "path_traversal_rejected": traversal,
        "path_safety_errors": errors,
    }


def _parent_conflict(path: Path) -> str | None:
    if path.parent.is_symlink():
        return "parent_symlink"
    if not path.parent.exists():
        return "missing_parent"
    if not path.parent.is_dir():
        return "parent_not_directory"
    for parent in [path.parent, *path.parent.parents]:
        if parent.exists() or parent.is_symlink():
            if parent.is_symlink():
                return "parent_symlink"
            if not parent.is_dir():
                return "parent_not_directory"
            return None
    return "missing_parent"


def _conflict_classification(
    scope: dict[str, Any],
    *,
    operation_type: str,
    expected_path_kind: str,
) -> str:
    path = Path(scope["target_path"])
    if scope["path_traversal_rejected"]:
        return "unsafe_path_traversal"
    if scope["path_scope_classification"] == "outside_declared_setup_scopes":
        return "outside_declared_setup_scopes"

    parent_conflict = _parent_conflict(path)
    if parent_conflict in {"parent_symlink", "parent_not_directory"}:
        return parent_conflict
    if path.is_symlink():
        return "symlink_path"
    if path.exists():
        if path.is_dir() and expected_path_kind == "file":
            return "directory_file_conflict"
        if path.is_file() and expected_path_kind == "directory":
            return "file_directory_conflict"
        if operation_type == "merge" and path.is_file():
            return "merge_existing_file"
        if operation_type == "replace" and path.is_file():
            return "replace_existing_file"
        if operation_type in {"create", "copy"}:
            return "unmanaged_existing_file" if path.is_file() else "existing_directory"
        if operation_type == "mkdir" and path.is_dir():
            return "none"
    if parent_conflict == "missing_parent":
        return "missing_parent"
    return "none"


def _operation_for_file(path: Path, *, merge: bool = False) -> str:
    if merge:
        return "merge"
    if path.exists() and not path.is_dir():
        return "replace"
    return "create"


def _rollback_requirement(operation_type: str, expected_path_kind: str) -> dict[str, Any]:
    if operation_type == "no-op":
        return {
            "required": False,
            "future_rollback_operation": "none",
            "reason": "No future mutation is planned for this change.",
        }
    if operation_type == "create":
        future = "delete_created_file" if expected_path_kind == "file" else "delete_created_directory"
    elif operation_type in {"replace", "merge"}:
        future = "restore_prior_file_from_snapshot"
    elif operation_type == "copy":
        future = "restore_or_delete_destination_from_snapshot"
    elif operation_type == "mkdir":
        future = "remove_created_directory_if_empty"
    else:
        future = "manual_review_required"
    return {
        "required": True,
        "future_rollback_operation": future,
        "reason": "A future setup apply would need a prior-state snapshot before mutation.",
    }


def _digest_path(path: Path) -> str:
    if path.is_symlink():
        return _sha256_text(f"symlink:{path}:{path.readlink()}")
    if path.is_file():
        return _sha256_bytes(path.read_bytes())
    if path.is_dir():
        records: list[str] = []
        for child in sorted(path.rglob("*"), key=lambda item: item.relative_to(path).as_posix()):
            rel = child.relative_to(path).as_posix()
            if child.is_symlink():
                records.append(f"symlink:{rel}:{child.readlink()}")
            elif child.is_file():
                records.append(f"file:{rel}:{_sha256_bytes(child.read_bytes())}")
            elif child.is_dir():
                records.append(f"dir:{rel}")
            else:
                records.append(f"unsupported:{rel}")
        return _sha256_text("\n".join(records))
    return _sha256_text(f"missing:{path}")


def _planned_change(
    *,
    change_id: str,
    change_kind: str,
    raw_target_path: str | Path,
    operation_type: str,
    expected_path_kind: str,
    content: dict[str, Any] | list[Any] | str | None,
    source_path: str | Path | None,
    builder_repo: Path,
    target_repo: Path,
    artifact_root: Path,
    user_config_dir: Path,
    metadata: dict[str, Any] | None = None,
    safety_notes: list[str] | None = None,
) -> dict[str, Any]:
    scope = _classify_scope(
        raw_target_path,
        builder_repo=builder_repo,
        target_repo=target_repo,
        artifact_root=artifact_root,
        user_config_dir=user_config_dir,
    )
    conflict = _conflict_classification(
        scope,
        operation_type=operation_type,
        expected_path_kind=expected_path_kind,
    )

    digest_fields: dict[str, str] = {}
    if content is not None:
        text = content if isinstance(content, str) else _canonical_json_text(content)
        digest_fields["content_digest"] = _sha256_text(text)
        redacted_preview = _redact_text(text)
    elif source_path is not None:
        source = Path(source_path).expanduser().resolve(strict=False)
        digest_fields["source_digest"] = _digest_path(source)
        redacted_preview = f"source_path={source}\nsource_digest={digest_fields['source_digest']}"
    else:
        digest_fields["content_digest"] = _sha256_text("")
        redacted_preview = ""

    notes = list(safety_notes or [])
    if conflict != "none":
        notes.append(f"path conflict classification: {conflict}")
    if scope["path_safety_errors"]:
        notes.extend(scope["path_safety_errors"])

    return {
        "change_id": change_id,
        "change_kind": change_kind,
        **scope,
        "operation_type": operation_type,
        "expected_path_kind": expected_path_kind,
        **digest_fields,
        "source_path": str(Path(source_path).expanduser().resolve(strict=False)) if source_path is not None else "",
        "redacted_preview": redacted_preview,
        "conflict_classification": conflict,
        "requires_future_approval": operation_type != "no-op",
        "rollback_requirement": _rollback_requirement(operation_type, expected_path_kind),
        "safety_notes": notes,
        "planned_only": True,
        "metadata": metadata or {},
    }


def _skill_entries(source_dir: Path, destination_dir: Path) -> list[dict[str, Any]]:
    if not source_dir.exists() or not source_dir.is_dir() or source_dir.is_symlink():
        return []

    entries: list[dict[str, Any]] = []
    for child in sorted(source_dir.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or child.is_symlink():
            continue
        manifest = child / "SKILL.md"
        if not manifest.exists():
            continue
        skill_id = child.name
        destination = destination_dir / skill_id
        source_digest = _digest_path(child)
        if destination.resolve(strict=False) == child.resolve(strict=False):
            operation = "no-op"
            conflict = "source_destination_same_path"
            notes = ["source and destination resolve to the same directory; no copy is planned"]
        elif destination.is_symlink():
            operation = "no-op"
            conflict = "destination_symlink"
            notes = ["destination is a symlink; future apply must not follow it without review"]
        elif destination.exists() and destination.is_dir():
            destination_digest = _digest_path(destination)
            operation = "no-op" if destination_digest == source_digest else "replace"
            conflict = "none" if operation == "no-op" else "destination_exists_requires_review"
            notes = [] if operation == "no-op" else ["destination exists and differs from source"]
        elif destination.exists():
            operation = "replace"
            conflict = "destination_file_conflict"
            notes = ["destination exists but is not a directory"]
        else:
            operation = "create"
            conflict = "none"
            notes = []
        entries.append(
            {
                "skill_id": skill_id,
                "source_directory": str(child.resolve(strict=False)),
                "destination_directory": str(destination.resolve(strict=False)),
                "manifest_path": str(manifest.resolve(strict=False)),
                "manifest_digest": _digest_path(manifest),
                "source_digest": source_digest,
                "operation_type": operation,
                "conflict_classification": conflict,
                "conflict_notes": notes,
                "rollback_requirement": _rollback_requirement(operation, "directory"),
                "planned_only": True,
            }
        )
    return entries


def _setup_plan_ref(plan: dict[str, Any]) -> dict[str, str]:
    return {
        "kind": SETUP_PLAN_KIND,
        "digest": str(plan["plan_digest"]),
    }


def _no_mutation_proof() -> dict[str, bool]:
    return {
        "overlay_plan_generation_performs_writes": False,
        "target_repo_writes": False,
        "goose_config_writes": False,
        "goosehints_writes": False,
        "skill_copy": False,
        "recipe_installation_writes": False,
        "runtime_start": False,
        "model_calls": False,
        "shell_execution": False,
        "mcp_tool_invocation": False,
        "patch_application": False,
        "deepagents_construction": False,
        "setup_apply": False,
        "setup_rollback_execution": False,
        "only_explicit_output_artifact_may_be_written_by_cli": True,
    }


def create_setup_overlay_plan(
    setup_plan: dict[str, Any],
    *,
    builder_repo: Path | None = None,
    user_config_dir: Path | None = None,
) -> dict[str, Any]:
    plan_errors = validate_setup_plan_artifact(setup_plan)
    if plan_errors:
        raise ValueError("invalid setup plan: " + "; ".join(plan_errors))

    builder_root = _canonicalize_root(setup_plan.get("builder_repo_canonical_path") or builder_repo or Path.cwd())
    target_repo = _canonicalize_root(str(setup_plan["target_repo_canonical_path"]))
    artifact_root = _canonicalize_root(str(setup_plan["artifact_root_canonical_path"]))
    config_root = _canonicalize_root(user_config_dir or (Path.home() / ".config"))

    goose_config_raw = str(setup_plan["goose_config_target_path"])
    goose_recipe_raw = str(setup_plan["goose_recipe_path"])
    skills_source_raw = str(setup_plan["skills_source_path"])
    goose_config_path = _canonicalize_root(goose_config_raw)
    goose_recipe_path = _canonicalize_root(goose_recipe_raw)
    skills_source_path = _canonicalize_root(skills_source_raw)
    skills_destination_policy = str(setup_plan["skills_destination_policy"])
    skills_destination = target_repo / ".agents" / "skills"

    builder_config_candidate = {
        "schema_version": setup_plan["config_schema_version"],
        "target_repo": str(target_repo),
        "platform_artifact_root": str(artifact_root),
        "active_target_profile": setup_plan["selected_target_profile"],
        "active_agent_profile": setup_plan["selected_agent_profile"],
        "active_verification_profile": setup_plan["selected_verification_profile"],
        "runtime_mode": "passive",
        "deepagents_mode": setup_plan["deepagents_mode"],
        "artifact_is_authority": False,
    }
    env_recommendation = "\n".join(
        [
            "# builder-II passive setup recommendation",
            f"BUILDER_TARGET_REPO={target_repo}",
            f"BUILDER_ARTIFACT_ROOT={artifact_root}",
            f"BUILDER_TARGET_PROFILE={setup_plan['selected_target_profile']}",
            f"BUILDER_AGENT_PROFILE={setup_plan['selected_agent_profile']}",
            f"BUILDER_VERIFICATION_PROFILE={setup_plan['selected_verification_profile']}",
            f"BUILDER_GOOSE_CONFIG_PATH={goose_config_path}",
            f"BUILDER_GOOSE_RECIPE_PATH={goose_recipe_path}",
            f"BUILDER_GOOSE_SKILLS_SOURCE={skills_source_path}",
            f"BUILDER_GOOSE_SKILLS_DESTINATION_POLICY={skills_destination_policy}",
            "BUILDER_RUNTIME_MODE=passive",
            "BUILDER_DEEPAGENTS_MODE=disabled",
            "",
        ]
    )
    goose_overlay = {
        "config_target_path": str(goose_config_path),
        "prior_config_path_expectation": {
            "path": str(goose_config_path),
            "may_exist": True,
            "must_preserve_unknown_keys": True,
        },
        "overlay_keys": [
            "extensions.builder_ii",
            "recipes.builder_ii.path",
            "slash_commands.builder_ii.recipe_path",
        ],
        "slash_command_recipe_paths": [str(goose_recipe_path)],
        "extension_policy": "preserve_existing_extensions_and_merge_builder_ii_keys_only",
        "recipe_path": str(goose_recipe_path),
        "conflict_warnings": [
            "future apply must preserve credentials and unknown Goose config keys",
            "future apply must use atomic write and a rollback snapshot before mutation",
        ],
        "secrets_preservation_policy": "do_not_copy_credentials_or_secret_values_into_overlay_artifact",
        "rollback_requirement": "restore prior Goose config from rollback snapshot if future apply mutates it",
        "planned_only": True,
    }
    goosehints = "\n".join(
        [
            "builder-II setup overlay is passive until an explicit future apply command exists.",
            "No runtime, model, Goose, deepagents, MCP/tool, shell, patch, or autonomous write authority is granted by this file.",
            "",
        ]
    )
    moim_session_context = {
        "artifact_is_authority": False,
        "planned_only": True,
        "target_repo": str(target_repo),
        "artifact_root": str(artifact_root),
        "target_profile": setup_plan["selected_target_profile"],
        "agent_profile": setup_plan["selected_agent_profile"],
        "verification_profile": setup_plan["selected_verification_profile"],
        "memory_policy": "reconstructive_reference_only",
        "runtime_execution": "disabled",
    }
    recipe_registration = {
        "recipe_path": str(goose_recipe_path),
        "registration_target": str(goose_config_path),
        "registration_kind": "slash_command_recipe_path_reference",
        "copy_recipe_files": False,
        "planned_only": True,
    }
    skill_entries = _skill_entries(skills_source_path, skills_destination)
    source_dest_same = skills_source_path == skills_destination.resolve(strict=False)
    skill_operation = "no-op" if skills_destination_policy == "disabled" or source_dest_same else "copy"
    skill_install_plan = {
        "source_directory": str(skills_source_path),
        "destination_directory": str(skills_destination.resolve(strict=False)),
        "destination_policy": skills_destination_policy,
        "copy_skills": False,
        "source_destination_same_path": source_dest_same,
        "entries": skill_entries,
        "planned_only": True,
    }
    target_profile_reference = {
        "target_profile": setup_plan["selected_target_profile"],
        "agent_profile": setup_plan["selected_agent_profile"],
        "verification_profile": setup_plan["selected_verification_profile"],
        "target_repo": str(target_repo),
        "artifact_is_authority": False,
        "planned_only": True,
    }

    changes = [
        _planned_change(
            change_id="builder_config_file_candidate",
            change_kind="builder_config_file_candidate",
            raw_target_path=artifact_root / "setup" / "builder.config.candidate.json",
            operation_type=_operation_for_file(artifact_root / "setup" / "builder.config.candidate.json"),
            expected_path_kind="file",
            content=builder_config_candidate,
            source_path=None,
            builder_repo=builder_root,
            target_repo=target_repo,
            artifact_root=artifact_root,
            user_config_dir=config_root,
            metadata={"candidate": builder_config_candidate},
        ),
        _planned_change(
            change_id="env_recommendation_candidate",
            change_kind="env_recommendation_candidate",
            raw_target_path=target_repo / ".env",
            operation_type="merge",
            expected_path_kind="file",
            content=env_recommendation,
            source_path=None,
            builder_repo=builder_root,
            target_repo=target_repo,
            artifact_root=artifact_root,
            user_config_dir=config_root,
            metadata={"env_keys": [line.split("=", 1)[0] for line in env_recommendation.splitlines() if line.startswith("BUILDER_")]},
        ),
        _planned_change(
            change_id="goose_config_overlay_candidate",
            change_kind="goose_config_overlay_candidate",
            raw_target_path=goose_config_raw,
            operation_type="merge",
            expected_path_kind="file",
            content=goose_overlay,
            source_path=None,
            builder_repo=builder_root,
            target_repo=target_repo,
            artifact_root=artifact_root,
            user_config_dir=config_root,
            metadata=goose_overlay,
        ),
        _planned_change(
            change_id="target_goosehints_candidate",
            change_kind="goosehints_candidate",
            raw_target_path=target_repo / ".goosehints",
            operation_type="merge",
            expected_path_kind="file",
            content=goosehints,
            source_path=None,
            builder_repo=builder_root,
            target_repo=target_repo,
            artifact_root=artifact_root,
            user_config_dir=config_root,
        ),
        _planned_change(
            change_id="moim_session_context_candidate",
            change_kind="moim_session_context_candidate",
            raw_target_path=artifact_root / "setup" / "moim-session-context.candidate.json",
            operation_type=_operation_for_file(artifact_root / "setup" / "moim-session-context.candidate.json"),
            expected_path_kind="file",
            content=moim_session_context,
            source_path=None,
            builder_repo=builder_root,
            target_repo=target_repo,
            artifact_root=artifact_root,
            user_config_dir=config_root,
            metadata={"context_kind": "moim_session_context"},
        ),
        _planned_change(
            change_id="recipe_path_registration_candidate",
            change_kind="recipe_path_registration_candidate",
            raw_target_path=goose_config_raw,
            operation_type="merge",
            expected_path_kind="file",
            content=recipe_registration,
            source_path=goose_recipe_path,
            builder_repo=builder_root,
            target_repo=target_repo,
            artifact_root=artifact_root,
            user_config_dir=config_root,
            metadata=recipe_registration,
        ),
        _planned_change(
            change_id="skill_install_plan_candidate",
            change_kind="skill_install_plan_candidate",
            raw_target_path=skills_destination,
            operation_type=skill_operation,
            expected_path_kind="directory",
            content=skill_install_plan,
            source_path=skills_source_path,
            builder_repo=builder_root,
            target_repo=target_repo,
            artifact_root=artifact_root,
            user_config_dir=config_root,
            metadata=skill_install_plan,
            safety_notes=["skill entries are planned only; no skill files are copied"],
        ),
        _planned_change(
            change_id="target_profile_reference_materialization_candidate",
            change_kind="target_profile_reference_materialization_candidate",
            raw_target_path=artifact_root / "setup" / "target-profile-reference.candidate.json",
            operation_type=_operation_for_file(artifact_root / "setup" / "target-profile-reference.candidate.json"),
            expected_path_kind="file",
            content=target_profile_reference,
            source_path=None,
            builder_repo=builder_root,
            target_repo=target_repo,
            artifact_root=artifact_root,
            user_config_dir=config_root,
            metadata=target_profile_reference,
        ),
    ]
    unsafe_changes = [change for change in changes if change["conflict_classification"] in _UNSAFE_CONFLICTS]
    outside_scope_changes = [
        change for change in changes if change["path_scope_classification"] == "outside_declared_setup_scopes"
    ]
    overlay = {
        "kind": SETUP_OVERLAY_PLAN_KIND,
        "schema_version": SETUP_OVERLAY_PLAN_SCHEMA_VERSION,
        "artifact_is_authority": False,
        "planned_only": True,
        "setup_plan_ref": _setup_plan_ref(setup_plan),
        "builder_repo_canonical_path": str(builder_root),
        "target_repo_canonical_path": str(target_repo),
        "artifact_root_canonical_path": str(artifact_root),
        "user_config_dir_canonical_path": str(config_root),
        "path_policy": {
            "declared_setup_scopes": {
                "builder_repo": str(builder_root),
                "target_repo": str(target_repo),
                "artifact_root": str(artifact_root),
                "user_config_dir": str(config_root),
            },
            "path_traversal_allowed": False,
            "symlink_following_allowed": False,
            "future_apply_requires_atomic_writes": True,
        },
        "capability_map": _DISABLED_CAPABILITY_MAP,
        "planned_changes": changes,
        "goose_overlay_candidate": goose_overlay,
        "skill_install_plan": skill_install_plan,
        "safety_summary": {
            "change_count": len(changes),
            "unsafe_change_count": len(unsafe_changes),
            "outside_declared_scope_count": len(outside_scope_changes),
            "planned_write_paths_all_within_declared_scopes": not outside_scope_changes,
            "all_changes_planned_only": all(change["planned_only"] is True for change in changes),
            "future_apply_requires_approval": True,
            "future_apply_requires_rollback_snapshot": True,
        },
        "no_mutation_proof": _no_mutation_proof(),
        "governance": {
            "artifact_is_authority": False,
            **CAPABILITY_DEFAULTS,
            "setup_apply": "disabled",
            "setup_rollback_execution": "disabled",
        },
    }
    return attach_digest(overlay, digest_key="overlay_plan_digest")


def dumps_setup_overlay_plan(plan: dict[str, Any]) -> str:
    return json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"


def write_setup_overlay_plan(plan: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_setup_overlay_plan(plan), encoding="utf-8")


def validate_setup_overlay_plan_artifact(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["setup overlay plan artifact must be a JSON object"]
    if data.get("kind") != SETUP_OVERLAY_PLAN_KIND:
        errors.append(f"kind must be {SETUP_OVERLAY_PLAN_KIND}")
    if data.get("schema_version") != SETUP_OVERLAY_PLAN_SCHEMA_VERSION:
        errors.append(f"schema_version must be {SETUP_OVERLAY_PLAN_SCHEMA_VERSION}")
    if data.get("artifact_is_authority") is not False:
        errors.append("artifact_is_authority must be false")
    if data.get("planned_only") is not True:
        errors.append("planned_only must be true")

    ref = data.get("setup_plan_ref")
    if not isinstance(ref, dict):
        errors.append("setup_plan_ref must be an object")
    else:
        if ref.get("kind") != SETUP_PLAN_KIND:
            errors.append(f"setup_plan_ref.kind must be {SETUP_PLAN_KIND}")
        if not _is_sha256(ref.get("digest")):
            errors.append("setup_plan_ref.digest must be a SHA-256 hex string")

    for path_field in (
        "builder_repo_canonical_path",
        "target_repo_canonical_path",
        "artifact_root_canonical_path",
        "user_config_dir_canonical_path",
    ):
        value = data.get(path_field)
        if not isinstance(value, str) or not value:
            errors.append(f"{path_field} must be a non-empty string")
        elif not Path(value).is_absolute():
            errors.append(f"{path_field} must be absolute")

    capability_map = data.get("capability_map")
    if not isinstance(capability_map, dict):
        errors.append("capability_map must be an object")
    else:
        for key, expected in _DISABLED_CAPABILITY_MAP.items():
            if capability_map.get(key) != expected:
                errors.append(f"capability_map.{key} must be {expected}")

    seen_ids: set[str] = set()
    changes = data.get("planned_changes")
    if not isinstance(changes, list) or not changes:
        errors.append("planned_changes must be a non-empty list")
    else:
        for idx, change in enumerate(changes):
            if not isinstance(change, dict):
                errors.append(f"planned_changes[{idx}] must be an object")
                continue
            change_id = change.get("change_id")
            if not isinstance(change_id, str) or not change_id:
                errors.append(f"planned_changes[{idx}].change_id must be a non-empty string")
            elif change_id in seen_ids:
                errors.append(f"planned_changes[{idx}].change_id must be unique")
            else:
                seen_ids.add(change_id)
            if change.get("change_kind") not in _CHANGE_KINDS:
                errors.append(f"planned_changes[{idx}].change_kind is unsupported")
            target_path = change.get("target_path")
            if not isinstance(target_path, str) or not Path(target_path).is_absolute():
                errors.append(f"planned_changes[{idx}].target_path must be absolute")
            if change.get("path_scope_classification") not in _SCOPES:
                errors.append(f"planned_changes[{idx}].path_scope_classification is unsupported")
            if not any(
                change.get(flag) is True
                for flag in (
                    "inside_builder_repo",
                    "inside_target_repo",
                    "inside_user_config_dir",
                    "inside_artifact_root",
                )
            ):
                errors.append(f"planned_changes[{idx}] must be inside at least one declared setup scope")
            if change.get("path_traversal_rejected") is True:
                errors.append(f"planned_changes[{idx}] contains forbidden path traversal")
            if change.get("operation_type") not in _OPERATIONS:
                errors.append(f"planned_changes[{idx}].operation_type is unsupported")
            if not (_is_sha256(change.get("content_digest")) or _is_sha256(change.get("source_digest"))):
                errors.append(f"planned_changes[{idx}] must include a content_digest or source_digest")
            if not isinstance(change.get("redacted_preview"), str):
                errors.append(f"planned_changes[{idx}].redacted_preview must be a string")
            conflict = change.get("conflict_classification")
            if not isinstance(conflict, str) or not conflict:
                errors.append(f"planned_changes[{idx}].conflict_classification must be a string")
            elif conflict in _UNSAFE_CONFLICTS:
                errors.append(f"planned_changes[{idx}] has unsafe conflict classification: {conflict}")
            if not isinstance(change.get("requires_future_approval"), bool):
                errors.append(f"planned_changes[{idx}].requires_future_approval must be boolean")
            rollback = change.get("rollback_requirement")
            if not isinstance(rollback, dict) or not isinstance(rollback.get("required"), bool):
                errors.append(f"planned_changes[{idx}].rollback_requirement must declare required boolean")
            if change.get("planned_only") is not True:
                errors.append(f"planned_changes[{idx}].planned_only must be true")
            if not isinstance(change.get("safety_notes"), list):
                errors.append(f"planned_changes[{idx}].safety_notes must be a list")

    skill_plan = data.get("skill_install_plan")
    if not isinstance(skill_plan, dict):
        errors.append("skill_install_plan must be an object")
    else:
        if skill_plan.get("copy_skills") is not False:
            errors.append("skill_install_plan.copy_skills must be false")
        entries = skill_plan.get("entries")
        if not isinstance(entries, list):
            errors.append("skill_install_plan.entries must be a list")
        else:
            for idx, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    errors.append(f"skill_install_plan.entries[{idx}] must be an object")
                    continue
                if entry.get("planned_only") is not True:
                    errors.append(f"skill_install_plan.entries[{idx}].planned_only must be true")
                if entry.get("operation_type") not in {"create", "replace", "no-op"}:
                    errors.append(f"skill_install_plan.entries[{idx}].operation_type is unsupported")
                if not _is_sha256(entry.get("source_digest")):
                    errors.append(f"skill_install_plan.entries[{idx}].source_digest must be SHA-256")
                if not _is_sha256(entry.get("manifest_digest")):
                    errors.append(f"skill_install_plan.entries[{idx}].manifest_digest must be SHA-256")

    proof = data.get("no_mutation_proof")
    if not isinstance(proof, dict):
        errors.append("no_mutation_proof must be an object")
    else:
        for key, value in proof.items():
            if key == "only_explicit_output_artifact_may_be_written_by_cli":
                if value is not True:
                    errors.append(f"no_mutation_proof.{key} must be true")
            elif value is not False:
                errors.append(f"no_mutation_proof.{key} must be false")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    elif governance.get("artifact_is_authority") is not False:
        errors.append("governance.artifact_is_authority must be false")

    digest = data.get("overlay_plan_digest")
    if not _is_sha256(digest):
        errors.append("overlay_plan_digest must be a SHA-256 hex string")
    elif digest != digest_jsonable(data, digest_key="overlay_plan_digest"):
        errors.append("overlay_plan_digest does not match canonical overlay payload")
    return errors


def validate_setup_overlay_plan_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    return validate_setup_overlay_plan_artifact(data)
