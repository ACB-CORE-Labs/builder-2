from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

from builder_ii.core.repo_map import validate_repo_map
from builder_ii.lifecycle.setup.target_profiles import target_names

CONTEXT_PACK_KIND = "builder_ii.context_pack"
CONTEXT_PACK_SCHEMA_VERSION = 1

ROLE_PRIORITY: dict[str, int] = {
    "docs": 0,
    "config": 1,
    "test": 2,
    "source": 3,
    "artifact": 4,
    "unknown": 5,
}


def create_context_pack(
    repo_map: dict[str, Any],
    *,
    target_name: str,
    task: str = "",
    max_entries: int = 100,
) -> dict[str, Any]:
    """Create a bounded read-only context pack foundation artifact from a repo map.

    Strictly governed: no subprocess calls, no shell execution, no target-repo writes.
    """
    map_errors = validate_repo_map(repo_map)
    if map_errors:
        raise ValueError("invalid repo map passed to create_context_pack: " + "; ".join(map_errors))

    if target_name not in target_names():
        raise ValueError("target_name must be one of: generic, builder, core")

    if repo_map.get("target_name") != target_name:
        raise ValueError(f"target_name mismatch: repo map has {repo_map.get('target_name')}, requested {target_name}")

    files = list(repo_map.get("files", []))
    files.sort(key=lambda f: (ROLE_PRIORITY.get(str(f.get("role", "unknown")), 99), str(f.get("path", ""))))

    selected_files = files[:max_entries]
    total_file_count = int(repo_map.get("file_count", len(files)))
    omitted_file_count = max(0, total_file_count - len(selected_files))

    source_info = {
        "repo_path": repo_map.get("repo_path", ""),
        "file_count": total_file_count,
        "summary_counts": repo_map.get("summary_counts", {}),
    }

    data = {
        "kind": CONTEXT_PACK_KIND,
        "schema_version": CONTEXT_PACK_SCHEMA_VERSION,
        "target_name": target_name,
        "task": task,
        "source": source_info,
        "selected_files": selected_files,
        "omitted_file_count": omitted_file_count,
        "operator_guidance": {
            "inspection": "Inspect selected files to understand repository structure and relevant context.",
            "manual_verification": "Run verification commands manually out-of-band.",
            "caution": "Do not treat context pack as proof of correctness.",
        },
        "verification_boundary": {
            "read_only": "Context pack is read-only context.",
            "proof": "It does not prove tests passed.",
            "evidence_conversion": "It does not convert planned verification into evidence.",
        },
        "governance": {
            "capability_state": "context_pack",
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

    errors = validate_context_pack(data)
    if errors:
        raise ValueError("created invalid context pack: " + "; ".join(errors))

    return data


def validate_context_pack(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["context pack must be a JSON object"]

    if data.get("kind") != CONTEXT_PACK_KIND:
        errors.append(f"kind must be {CONTEXT_PACK_KIND}")
    if data.get("schema_version") != CONTEXT_PACK_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CONTEXT_PACK_SCHEMA_VERSION}")

    if data.get("target_name") not in target_names():
        errors.append("target_name must be one of: generic, builder, core")

    if not isinstance(data.get("task", ""), str):
        errors.append("task must be a string")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")

    selected_files = data.get("selected_files")
    if not isinstance(selected_files, list):
        errors.append("selected_files must be a list")
    else:
        for index, f in enumerate(selected_files):
            prefix = f"selected_files[{index}]"
            if not isinstance(f, dict):
                errors.append(f"{prefix} must be an object")
                continue
            if not isinstance(f.get("path"), str) or not f["path"]:
                errors.append(f"{prefix}.path must be a non-empty string")
            if not isinstance(f.get("role"), str):
                errors.append(f"{prefix}.role must be a string")

    if not isinstance(data.get("omitted_file_count"), int) or data.get("omitted_file_count", -1) < 0:
        errors.append("omitted_file_count must be a non-negative integer")

    if not isinstance(data.get("operator_guidance"), dict):
        errors.append("operator_guidance must be an object")

    if not isinstance(data.get("verification_boundary"), dict):
        errors.append("verification_boundary must be an object")

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
                errors.append(f"governance.{key} must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")

    return errors


def validate_context_pack_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"failed to read or decode file: {exc}"]
    return validate_context_pack(data)


def dumps_context_pack(data: dict[str, Any]) -> str:
    errors = validate_context_pack(data)
    if errors:
        raise ValueError("invalid context pack: " + "; ".join(errors))
    return json_lib.dumps(data, indent=2, sort_keys=True) + "\n"
