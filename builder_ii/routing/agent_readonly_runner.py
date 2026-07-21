"""V.2 — Agent profile read-only runner candidate (no deepagents construction).

Runs **only** profiles with ``authority == "read_only"`` (e.g. code_reviewer,
repo_mapper). Emits a digest-bound receipt with capability_state
``read_only_runtime_candidate``.

Does **not**:
- construct deepagents or invoke ``delegate``
- execute shell, write/edit files, commit/push
- call live models (V.2 is inspection + structured findings without LLM)
- mutate target repo

Honesty: this is a **candidate** RO path (like Goose RO), not ``enabled`` multi-agent.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from builder_ii.core.repo_map import create_repo_map
from builder_ii.governance.ledger.workflow_records import canonical_digest
from builder_ii.routing.agent_profiles import AgentProfile, AgentProfileName, get_agent_profile

AGENT_RO_RECEIPT_KIND = "builder_ii.agent_readonly_run_receipt"
READ_ONLY_RUNTIME_CANDIDATE = "read_only_runtime_candidate"

# Match agent_profiles registry: every profile forbids these mutation tools.
_REQUIRED_FORBIDDEN = frozenset({"write_file", "edit_file", "execute_shell", "commit", "push"})


class AgentReadonlyError(ValueError):
    """Fail-closed RO runner refusal."""


def _assert_read_only_profile(profile: AgentProfile) -> None:
    if profile.authority != "read_only":
        raise AgentReadonlyError(
            f"profile {profile.name!r} has authority={profile.authority!r}; "
            "V.2 RO runner only allows authority=read_only "
            "(patch_planner stays proposal/artifact-only)"
        )
    forb = set(profile.forbidden_tools)
    missing = _REQUIRED_FORBIDDEN - forb
    if missing:
        raise AgentReadonlyError(
            f"profile {profile.name!r} must forbid {sorted(missing)} for RO run"
        )


def run_readonly_agent(
    *,
    profile_name: AgentProfileName | str,
    task: str,
    repo_path: Path | str,
    target_name: str = "builder",
    max_files: int = 100,
) -> dict[str, Any]:
    """Execute a bounded RO agent inspection and return a receipt artifact.

    Performs in-process repo_map + profile contract checks only — no LLM, no shell.
    """
    if not task or not str(task).strip():
        raise AgentReadonlyError("task must be non-empty")

    profile = get_agent_profile(profile_name)  # type: ignore[arg-type]
    _assert_read_only_profile(profile)

    root = Path(repo_path).resolve()
    if not root.is_dir():
        raise AgentReadonlyError(f"repo_path is not a directory: {root}")

    repo_map = create_repo_map(root, target_name=target_name, max_files=max_files)
    files = repo_map.get("files") if isinstance(repo_map.get("files"), list) else []
    source_files = [f for f in files if isinstance(f, dict) and f.get("role") == "source"]

    findings = [
        {
            "severity": "info",
            "summary": "RO inspection completed without target mutation",
            "evidence": f"repo_map file_count={repo_map.get('file_count')} source_files={len(source_files)}",
            "tool": "repo_map",
        },
        {
            "severity": "info",
            "summary": f"Profile {profile.name} allowed_tools={list(profile.allowed_tools)}",
            "evidence": "profile contract",
            "tool": "agent_profile",
        },
        {
            "severity": "info",
            "summary": f"Task recorded (no model invoke): {task.strip()[:200]}",
            "evidence": "task_text",
            "tool": "none",
        },
    ]

    receipt: dict[str, Any] = {
        "kind": AGENT_RO_RECEIPT_KIND,
        "schema_version": 1,
        "status": "succeeded",
        "artifact_state": "RECORDED_ONLY",
        "capability_state": READ_ONLY_RUNTIME_CANDIDATE,
        "runtime_mode": "read_only",
        "profile_name": profile.name,
        "profile_authority": profile.authority,
        "task": task.strip(),
        "target_name": target_name,
        "repo_path": str(root),
        "repo_map_digest": repo_map.get("digest"),
        "file_count": repo_map.get("file_count"),
        "findings": findings,
        "allowed_tools": list(profile.allowed_tools),
        "forbidden_tools": list(profile.forbidden_tools),
        "constructs_deepagents": False,
        "invokes_delegate": False,
        "executes_shell": False,
        "executes_model": False,
        "mutates_target_repo": False,
        "mutates_memory": False,
        "invokes_mcp": False,
        "grants_authority": False,
        "artifact_is_authority": False,
        "notes": (
            "V.2 RO candidate: in-process inspection only. Not deepagents construction, "
            "not delegate, not LLM review, not enabled multi-agent."
        ),
    }
    receipt["digest"] = canonical_digest(receipt)
    return receipt


def validate_agent_readonly_receipt(record: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(record, dict):
        return ["agent RO receipt must be an object"]
    if record.get("kind") != AGENT_RO_RECEIPT_KIND:
        errors.append(f"kind must be {AGENT_RO_RECEIPT_KIND}")
    if record.get("capability_state") != READ_ONLY_RUNTIME_CANDIDATE:
        errors.append(f"capability_state must be {READ_ONLY_RUNTIME_CANDIDATE}")
    if record.get("runtime_mode") != "read_only":
        errors.append("runtime_mode must be read_only")
    for key in (
        "constructs_deepagents",
        "invokes_delegate",
        "executes_shell",
        "executes_model",
        "mutates_target_repo",
        "grants_authority",
    ):
        if record.get(key) is not False:
            errors.append(f"{key} must be false")
    return errors


__all__ = [
    "AGENT_RO_RECEIPT_KIND",
    "AgentReadonlyError",
    "READ_ONLY_RUNTIME_CANDIDATE",
    "run_readonly_agent",
    "validate_agent_readonly_receipt",
]
