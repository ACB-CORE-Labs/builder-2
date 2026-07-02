from __future__ import annotations

import hashlib
import json as json_lib
import os
from pathlib import Path
from typing import Any

from builder_ii.target_profiles import target_names

REPO_MAP_KIND = "builder_ii.repo_map"
REPO_MAP_SCHEMA_VERSION = 1

IGNORED_DIRECTORIES: set[str] = {
    ".git",
    ".builder",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
    ".mypy_cache",
    ".ruff_cache",
}

VALID_ROLES: set[str] = {
    "source",
    "test",
    "docs",
    "config",
    "artifact",
    "unknown",
}


def _compute_sha256(path: Path) -> str | None:
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _classify_role(rel_path: Path) -> str:
    parts = rel_path.parts
    name = rel_path.name
    name_lower = name.lower()
    suffix = rel_path.suffix.lower()

    parent_dirs = set(parts[:-1])

    # Artifact check
    if (
        any(d in {"artifacts", ".artifacts", "brain", ".system_generated"} for d in parent_dirs)
        or name_lower
        in {
            "prepare-package.json",
            "repo-map.json",
            "context-pack.json",
            "session-workflow.json",
            "goose-readonly-session.json",
            "verification-profile-report.json",
            "handoff-note.json",
            "deepagents-bridge-readiness.json",
        }
        or name_lower.endswith(("-report.json", "-plan.json", "-note.json", "-package.json", "-map.json", "-pack.json"))
    ):
        return "artifact"

    # Test check
    if (
        any(d in {"tests", "test", "spec", "specs"} for d in parent_dirs)
        or name_lower.startswith("test_")
        or name_lower.endswith(("_test.py", ".test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts", "_spec.rb"))
    ):
        return "test"

    # Docs check
    if (
        any(d in {"docs", "doc", "documentation"} for d in parent_dirs)
        or suffix in {".md", ".rst", ".txt", ".adoc"}
        or name_lower in {"readme", "license", "notice", "changelog", "authors", "contributing"}
        or name_lower.startswith(("readme.", "license.", "notice.", "changelog.", "contributing."))
    ):
        return "docs"

    # Config check
    if (
        name_lower
        in {
            "pyproject.toml",
            "package.json",
            "tsconfig.json",
            "setup.py",
            "setup.cfg",
            "makefile",
            "justfile",
            "dockerfile",
            ".gitignore",
            ".dockerignore",
            ".editorconfig",
            "tox.ini",
        }
        or name_lower.endswith(".lock")
        or suffix in {".toml", ".ini", ".yaml", ".yml", ".cfg", ".env"}
    ):
        return "config"

    # Source check
    if suffix in {
        ".py",
        ".ts",
        ".js",
        ".tsx",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".kt",
        ".scala",
        ".sh",
        ".bash",
        ".zsh",
        ".sql",
        ".html",
        ".css",
        ".scss",
    } or any(d in {"src", "lib", "app", "pkg", "cmd", "builder_ii", "recipes"} for d in parent_dirs):
        return "source"

    return "unknown"


def create_repo_map(
    repo_path: Path | str,
    *,
    target_name: str,
    max_files: int = 500,
    max_file_bytes: int = 1_000_000,
) -> dict[str, Any]:
    """Create a bounded, read-only repo map foundation artifact.

    Strictly governed: no subprocess calls, no shell execution, no target-repo writes.
    """
    if target_name not in target_names():
        raise ValueError("target_name must be one of: generic, builder, core")

    root = Path(repo_path).resolve()
    if not root.exists() or not root.is_dir():
        raise ValueError(f"repo_path does not exist or is not a directory: {root}")

    files_list: list[dict[str, Any]] = []
    truncated_by_size = False

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORED_DIRECTORIES]

        for filename in filenames:
            if filename in IGNORED_DIRECTORIES:
                continue
            full_path = Path(dirpath) / filename
            try:
                rel_path = full_path.relative_to(root)
            except ValueError:
                continue

            if any(part in IGNORED_DIRECTORIES for part in rel_path.parts):
                continue

            try:
                resolved_full_path = full_path.resolve()
                resolved_root = root.resolve()
                resolved_full_path.relative_to(resolved_root)
            except (OSError, ValueError):
                continue

            if full_path.is_symlink():
                continue

            if not full_path.is_file():
                continue
            try:
                stat = full_path.stat()
            except OSError:
                continue

            size_bytes = stat.st_size
            if size_bytes > max_file_bytes:
                truncated_by_size = True
                continue

            sha = _compute_sha256(full_path)
            if sha is None:
                continue

            role = _classify_role(rel_path)
            files_list.append(
                {
                    "path": rel_path.as_posix(),
                    "suffix": rel_path.suffix,
                    "size_bytes": size_bytes,
                    "sha256": sha,
                    "role": role,
                }
            )

    files_list.sort(key=lambda x: str(x["path"]))
    truncated = truncated_by_size or len(files_list) > max_files
    selected_files = files_list[:max_files]

    summary_counts = {f"{role}_files": 0 for role in VALID_ROLES}
    for item in selected_files:
        role_key = f"{item['role']}_files"
        summary_counts[role_key] += 1

    data = {
        "kind": REPO_MAP_KIND,
        "schema_version": REPO_MAP_SCHEMA_VERSION,
        "repo_path": str(root),
        "target_name": target_name,
        "scan_state": "READ_ONLY",
        "file_count": len(selected_files),
        "truncated": truncated,
        "ignored_directories": sorted(list(IGNORED_DIRECTORIES)),
        "files": selected_files,
        "summary_counts": summary_counts,
        "governance": {
            "capability_state": "repo_map",
            "runtime_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "subprocess_backed_authority": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT EXPLICIT ARTIFACT OUTPUT PATH",
            "target_repo_writes": "DISABLED",
            "memory_mutation": "DISABLED",
            "goose_activation": "DISABLED",
            "deepagents_delegation": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }

    errors = validate_repo_map(data)
    if errors:
        raise ValueError("created invalid repo map: " + "; ".join(errors))

    return data


def validate_repo_map(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["repo map must be a JSON object"]

    if data.get("kind") != REPO_MAP_KIND:
        errors.append(f"kind must be {REPO_MAP_KIND}")
    if data.get("schema_version") != REPO_MAP_SCHEMA_VERSION:
        errors.append(f"schema_version must be {REPO_MAP_SCHEMA_VERSION}")

    if data.get("target_name") not in target_names():
        errors.append("target_name must be one of: generic, builder, core")

    if not isinstance(data.get("repo_path"), str) or not data["repo_path"]:
        errors.append("repo_path must be a non-empty string")

    if data.get("scan_state") != "READ_ONLY":
        errors.append("scan_state must be READ_ONLY")

    if not isinstance(data.get("truncated"), bool):
        errors.append("truncated must be a boolean")

    ignored_dirs = data.get("ignored_directories")
    if not isinstance(ignored_dirs, list) or any(not isinstance(d, str) for d in ignored_dirs):
        errors.append("ignored_directories must be a list of strings")

    files = data.get("files")
    if not isinstance(files, list):
        errors.append("files must be a list")
    else:
        if data.get("file_count") != len(files):
            errors.append("file_count must match length of files list")

        role_counts = {role: 0 for role in VALID_ROLES}
        for index, f in enumerate(files):
            prefix = f"files[{index}]"
            if not isinstance(f, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if not isinstance(f.get("path"), str) or not f["path"]:
                errors.append(f"{prefix}.path must be a non-empty string")
            if not isinstance(f.get("suffix"), str):
                errors.append(f"{prefix}.suffix must be a string")
            if not isinstance(f.get("size_bytes"), int) or f["size_bytes"] < 0:
                errors.append(f"{prefix}.size_bytes must be a non-negative integer")
            if not isinstance(f.get("sha256"), str) or len(f["sha256"]) != 64:
                errors.append(f"{prefix}.sha256 must be a 64-character hex string")
            role = f.get("role")
            if role not in VALID_ROLES:
                errors.append(f"{prefix}.role must be one of: {', '.join(sorted(VALID_ROLES))}")
            else:
                role_counts[str(role)] += 1

        summary_counts = data.get("summary_counts")
        if not isinstance(summary_counts, dict):
            errors.append("summary_counts must be an object")
        else:
            for role in VALID_ROLES:
                expected = role_counts[role]
                actual = summary_counts.get(f"{role}_files")
                if actual != expected:
                    errors.append(f"summary_counts.{role}_files mismatch: expected {expected}, got {actual}")

    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        for key in (
            "runtime_execution",
            "shell_execution",
            "subprocess_backed_authority",
            "model_execution",
            "target_repo_writes",
        ):
            if governance.get(key) != "DISABLED":
                errors.append(f"governance.{key} must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")

    return errors


def validate_repo_map_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"failed to read or decode file: {exc}"]
    return validate_repo_map(data)


def dumps_repo_map(data: dict[str, Any]) -> str:
    errors = validate_repo_map(data)
    if errors:
        raise ValueError("invalid repo map: " + "; ".join(errors))
    return json_lib.dumps(data, indent=2, sort_keys=True) + "\n"
