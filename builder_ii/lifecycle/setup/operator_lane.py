from __future__ import annotations

import hashlib
import json as json_lib
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

from builder_ii.core.config import Settings, load_settings
from builder_ii.core.config_sources import (
    CONFIG_SOURCE_RESOLUTION_KIND,
    resolve_config_sources,
    write_config_resolution_artifact,
)
from builder_ii.core.context_packs import create_context_pack, dumps_context_pack
from builder_ii.core.git_state import create_git_state_record, write_git_state_record
from builder_ii.core.handoff_artifacts import create_handoff_artifact, write_handoff_artifact
from builder_ii.core.platform_completion_audit import DEFAULT_OPERATOR_LANE_READ_PATHS
from builder_ii.core.readonly_inspection_reports import (
    create_readonly_inspection_report,
    write_readonly_inspection_report,
)
from builder_ii.core.repo_map import create_repo_map, dumps_repo_map
from builder_ii.governance.authority.readonly_authority import (
    CONTENT_READ_RECEIPT_KIND,
    DEFAULT_MAX_CONTENT_READ_FILES,
    create_read_policy,
    execute_content_read,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.lifecycle.setup.operator_golden_path import (
    create_operator_golden_path_report,
    write_operator_golden_path_report,
)
from builder_ii.lifecycle.setup.target_profiles import TargetName, target_profile
from builder_ii.routing.model_client_registry import create_model_client_registry
from builder_ii.lifecycle.candidate.verification_execution_runner import _git_commit_identity
from builder_ii.routing.model_routing_policy import (
    create_model_routing_policy,
    create_model_routing_recommendation,
    write_model_routing_recommendation,
)

OPERATOR_LANE_REPORT_KIND = "builder_ii.operator_lane_report"
OPERATOR_LANE_REPORT_SCHEMA_VERSION = 1


def _digest(data: dict[str, Any]) -> str:
    raw = json_lib.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _artifact_ref(*, kind: str, path: Path, role: str) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8") if path.is_file() else ""
    sha = hashlib.sha256(content.encode("utf-8")).hexdigest() if content else ""
    return {
        "kind": kind,
        "path": str(path),
        "sha256": sha,
        "role": role,
        "required": True,
    }


def _capture_git_state(target_repo: Path, target_name: TargetName) -> dict[str, Any]:
    if not (target_repo / ".git").exists():
        return create_git_state_record(
            target=target_name,
            branch="unknown",
            commit_sha="0" * 40,
            state="dirty",  # type: ignore[arg-type]
            modified_files=["non_git_target"],
            untracked_files=[],
        )
    branch = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    commit_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    modified: list[str] = []
    untracked: list[str] = []
    for line in status:
        if len(line) < 4:
            continue
        path_part = line[3:].strip()
        if line.startswith("??"):
            untracked.append(path_part)
        else:
            modified.append(path_part)
    state = "clean" if not status else "dirty"
    return create_git_state_record(
        target=target_name,
        branch=branch,
        commit_sha=commit_sha,
        state=state,  # type: ignore[arg-type]
        modified_files=modified,
        untracked_files=untracked,
    )


def run_operator_lane(
    *,
    target_name: TargetName = "generic",
    output_dir: Path,
    dry_run: bool = True,
    explicit_paths: list[Path] | None = None,
    content_read_paths: list[Path] | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Compose governed platform capabilities into one evidence directory without widening authority."""
    if settings is None:
        settings = load_settings()

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    selected = target_profile(settings, target_name)
    target_repo = selected.repo.resolve()
    artifact_refs: list[dict[str, Any]] = []
    session_id = f"operator_lane_{uuid.uuid4().hex[:12]}"

    resolution = resolve_config_sources(project_root=settings.project_root)
    config_path = output_dir / "config-resolution.json"
    write_config_resolution_artifact(resolution, config_path)
    artifact_refs.append(_artifact_ref(kind=CONFIG_SOURCE_RESOLUTION_KIND, path=config_path, role="config_resolution"))

    git_record = _capture_git_state(target_repo, target_name)
    git_path = output_dir / "git-state.json"
    write_git_state_record(git_record, git_path)
    artifact_refs.append(_artifact_ref(kind=git_record["kind"], path=git_path, role="git_state"))

    if explicit_paths is None and content_read_paths is None:
        default_paths = [target_repo / rel for rel in DEFAULT_OPERATOR_LANE_READ_PATHS if (target_repo / rel).is_file()]
        explicit_paths = default_paths
        content_read_paths = list(default_paths)

    inspection_paths = explicit_paths or []
    if inspection_paths:
        inspection = create_readonly_inspection_report(
            target=target_name,
            purpose="operator_lane",
            paths=inspection_paths,
            root=target_repo,
            operator_note="operator-lane explicit path inspection",
        )
        inspection_path = output_dir / "readonly-inspection-report.json"
        write_readonly_inspection_report(inspection, inspection_path)
        artifact_refs.append(
            _artifact_ref(kind=inspection["kind"], path=inspection_path, role="readonly_inspection_report")
        )

    content_paths = content_read_paths or []
    if content_paths:
        if len(content_paths) > DEFAULT_MAX_CONTENT_READ_FILES:
            raise ValueError(f"content-read supports at most {DEFAULT_MAX_CONTENT_READ_FILES} explicit paths")
        allowed = [p.resolve().relative_to(target_repo).as_posix() for p in content_paths]
        policy = create_read_policy(
            target_name=target_name,
            target_repo=target_repo,
            allowed_paths=allowed,
            content_capture_allowed=True,
            operator_note="operator-lane bounded content-read",
        )
        policy_path = output_dir / "content-read-policy.json"
        policy_path.write_text(json_lib.dumps(policy, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        artifact_refs.append(_artifact_ref(kind=policy["kind"], path=policy_path, role="content_read_policy"))
        content_dir = output_dir / "content-read-receipts"
        content_dir.mkdir(parents=True, exist_ok=True)
        total_bytes = 0
        for idx, path in enumerate(content_paths):
            receipt = execute_content_read(policy, path, current_read_bytes=total_bytes)
            receipt_path = content_dir / f"content_read_{idx:03d}.json"
            receipt_path.write_text(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if receipt.get("kind") == CONTENT_READ_RECEIPT_KIND:
                total_bytes += int(receipt.get("bytes_read", 0))
            artifact_refs.append(_artifact_ref(kind=receipt.get("kind", "unknown"), path=receipt_path, role="content_read_receipt"))

    repo_map = create_repo_map(target_repo, target_name=target_name, max_files=64)
    repo_map_path = output_dir / "repo-map.json"
    repo_map_path.write_text(dumps_repo_map(repo_map), encoding="utf-8")
    artifact_refs.append(_artifact_ref(kind=repo_map["kind"], path=repo_map_path, role="repo_map"))

    context_pack = create_context_pack(repo_map, target_name=target_name, task="operator-lane", max_entries=32)
    context_path = output_dir / "context-pack.json"
    context_path.write_text(dumps_context_pack(context_pack), encoding="utf-8")
    artifact_refs.append(_artifact_ref(kind=context_pack["kind"], path=context_path, role="context_pack"))

    routing_policy = create_model_routing_policy()
    registry = create_model_client_registry()
    recommendation = create_model_routing_recommendation(routing_policy, registry)
    routing_path = output_dir / "model-routing-recommendation.json"
    write_model_routing_recommendation(recommendation, routing_path)
    artifact_refs.append(
        _artifact_ref(kind=recommendation["kind"], path=routing_path, role="model_routing_recommendation")
    )

    verification_plan = finalize_verification_execution_plan(
        target_profile=target_name,
        verification_profile="builder_full",
        target_repo=str(target_repo),
        target_head_sha=_git_commit_identity(target_repo)[0] or ("0"*40),
        tree_clean=True,
        artifact_root=str(output_dir),
        requested_by_command="builder-platform operator-lane",
    )
    plan_path = output_dir / "verification-execution-plan.json"
    write_verification_execution_plan(verification_plan, plan_path)
    artifact_refs.append(
        _artifact_ref(kind=verification_plan["kind"], path=plan_path, role="verification_execution_plan")
    )

    golden = create_operator_golden_path_report(target_profile=target_name, output_dir=output_dir / "golden-path")
    golden_path = output_dir / "golden-path" / "golden-path-report.json"
    write_operator_golden_path_report(golden, golden_path)
    artifact_refs.append(_artifact_ref(kind=golden["kind"], path=golden_path, role="operator_golden_path"))

    handoff = create_handoff_artifact(
        target=target_name,
        agent_profile="context_planner",
        task="operator-lane",
        summary="Governed operator lane evidence bundle composed without widening authority.",
        next_steps=(
            "Review verification execution plan and obtain HITL approval before run-approved.",
            "Use builder-hitl propose-patch/apply-patch only with verification receipt and approval digests.",
        ),
        blockers=() if dry_run else ("Non-dry-run execution requires explicit approval artifacts.",),
        verification=(
            "builder-verify run-approved",
            "builder-hitl apply-patch",
        ),
    )
    handoff_path = output_dir / "handoff.json"
    write_handoff_artifact(handoff, handoff_path)
    artifact_refs.append(_artifact_ref(kind=handoff["kind"], path=handoff_path, role="handoff"))

    report: dict[str, Any] = {
        "kind": OPERATOR_LANE_REPORT_KIND,
        "schema_version": OPERATOR_LANE_REPORT_SCHEMA_VERSION,
        "session_id": session_id,
        "target": {
            "name": selected.name,
            "repo": str(target_repo),
            "description": selected.description,
        },
        "dry_run": dry_run,
        "composed_at": int(time.time()),
        "artifact_refs": artifact_refs,
        "governance": {
            "capability_state": "OPERATIONALLY_VERIFIED",
            "runtime_execution": "DISABLED" if dry_run else "OPERATOR_MANAGED_COMPOSITION",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "mcp_tool_calls": "DISABLED",
            "goose_runtime_activation": "DISABLED",
            "deepagents_runtime": "DISABLED",
            "source_writes": "DISABLED",
            "git_mutation": "DISABLED",
            "commit_push": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
        "denied_in_lane": [
            "arbitrary_shell",
            "builder-hitl run-command",
            "live_mcp",
            "autonomous_writes",
            "commit_push",
        ],
    }
    report["report_digest"] = _digest(report)
    report_path = output_dir / "operator-lane-report.json"
    report_path.write_text(json_lib.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def dumps_operator_lane_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"


def validate_operator_lane_report(report: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(report, dict):
        return ["operator lane report must be a JSON object"]
    if report.get("kind") != OPERATOR_LANE_REPORT_KIND:
        errors.append(f"kind must be {OPERATOR_LANE_REPORT_KIND}")
    if report.get("schema_version") != OPERATOR_LANE_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {OPERATOR_LANE_REPORT_SCHEMA_VERSION}")
    if not isinstance(report.get("artifact_refs"), list) or not report["artifact_refs"]:
        errors.append("artifact_refs must be a non-empty list")
    if report.get("governance", {}).get("model_execution") != "DISABLED":
        errors.append("governance.model_execution must remain DISABLED in operator lane")
    return errors
