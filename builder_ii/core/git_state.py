from __future__ import annotations

import json as json_lib
import re
import subprocess
from pathlib import Path
from typing import Any, Literal

RepoTarget = Literal["core", "builder", "generic"]
GitState = Literal["clean", "dirty"]

GIT_STATE_RECORD_KIND = "builder_ii.git_state_record"
GIT_STATE_RECORD_SCHEMA_VERSION = 1


def create_git_state_record(
    target: RepoTarget,
    branch: str,
    commit_sha: str,
    state: GitState,
    modified_files: list[str] | tuple[str, ...],
    untracked_files: list[str] | tuple[str, ...],
) -> dict[str, Any]:
    """Create a validated git state record JSON-serializable dictionary."""
    return {
        "kind": GIT_STATE_RECORD_KIND,
        "schema_version": GIT_STATE_RECORD_SCHEMA_VERSION,
        "target": target,
        "branch": branch,
        "commit_sha": commit_sha,
        "state": state,
        "modified_files": list(modified_files),
        "untracked_files": list(untracked_files),
        "governance": {
            "capability_state": "git_state_record",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def capture_git_state(target_repo: Path, target: RepoTarget) -> dict[str, Any]:
    """Capture the canonical read-only Git projection used by all operator lanes."""
    try:
        branch = subprocess.run(
            ["git", "symbolic-ref", "--short", "-q", "HEAD"], cwd=target_repo,
            check=True, capture_output=True, text=True,
        ).stdout.strip() or "(detached HEAD)"
        commit_sha = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=target_repo,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        lines = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=target_repo,
            check=True, capture_output=True, text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError(f"read-only Git state capture failed: {exc}") from exc
    modified = sorted(line[3:] for line in lines if len(line) >= 4 and line[:2] != "??")
    untracked = sorted(line[3:] for line in lines if line.startswith("?? "))
    record = create_git_state_record(target, branch, commit_sha, "dirty" if lines else "clean", modified, untracked)
    errors = validate_git_state_record(record)
    if errors:
        raise ValueError("canonical Git state record validation failed: " + "; ".join(errors))
    return record


def dumps_git_state_record(record: dict[str, Any]) -> str:
    """Serialize git state record to a formatted JSON string."""
    return json_lib.dumps(record, indent=2, sort_keys=True) + "\n"


def write_git_state_record(record: dict[str, Any], output: Path) -> None:
    """Write git state record to a file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_git_state_record(record), encoding="utf-8")


def _string_list_errors(value: Any, *, field: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{field} must be a list"]
    if any(not isinstance(item, str) or not item for item in value):
        return [f"{field} must be a list of non-empty strings"]
    return []


def validate_git_state_record(data: Any) -> list[str]:
    """Validate a git state record's structure and invariants."""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["git state record must be a JSON object"]

    if data.get("kind") != GIT_STATE_RECORD_KIND:
        errors.append(f"kind must be {GIT_STATE_RECORD_KIND}")
    if data.get("schema_version") != GIT_STATE_RECORD_SCHEMA_VERSION:
        errors.append(f"schema_version must be {GIT_STATE_RECORD_SCHEMA_VERSION}")

    target = data.get("target")
    if target not in ("core", "builder", "generic"):
        errors.append("target must be one of: core, builder, generic")

    branch = data.get("branch")
    if not isinstance(branch, str) or not branch:
        errors.append("branch must be a non-empty string")

    commit_sha = data.get("commit_sha")
    if not isinstance(commit_sha, str) or not re.match(r"^[0-9a-fA-F]{40}$", commit_sha):
        errors.append("commit_sha must be 40 lowercase/uppercase hex chars")

    state = data.get("state")
    if state not in ("clean", "dirty"):
        errors.append("state must be clean or dirty")

    modified = data.get("modified_files")
    untracked = data.get("untracked_files")

    errors.extend(_string_list_errors(modified, field="modified_files"))
    errors.extend(_string_list_errors(untracked, field="untracked_files"))

    # Consistency rules between clean/dirty state and modified/untracked files
    if isinstance(modified, list) and isinstance(untracked, list):
        if state == "clean":
            if modified or untracked:
                errors.append("if state is clean, modified_files and untracked_files must both be empty")
        elif state == "dirty":
            if not modified and not untracked:
                errors.append("if state is dirty, at least one modified or untracked file must be present")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("capability_state") != "git_state_record":
            errors.append("governance.capability_state must be git_state_record")
        for key in ("runtime_execution", "model_execution", "shell_execution", "source_writes", "memory_mutation"):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def validate_git_state_record_file(path: Path) -> list[str]:
    """Read and validate a git state record file."""
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        return [f"invalid JSON: {exc}"]
    except Exception as exc:
        return [f"failed to read file: {exc}"]
    return validate_git_state_record(data)
