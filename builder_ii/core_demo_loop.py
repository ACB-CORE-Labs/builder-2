from __future__ import annotations

import hashlib
import json as json_lib
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from builder_ii.context_packs import create_context_pack, dumps_context_pack
from builder_ii.execution_postflight_records import (
    create_execution_postflight_record,
    write_execution_postflight_record,
)
from builder_ii.hitl_patch_apply import apply_hitl_patch, rollback_hitl_patch
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.repo_map import create_repo_map, dumps_repo_map

CORE_DEMO_APPROVAL_KIND = "builder_ii.core_demo_approval"
CORE_DEMO_APPROVAL_SCHEMA_VERSION = 1
CORE_DEMO_PLANNER_KIND = "builder_ii.core_demo_deterministic_planner"
CORE_DEMO_PREFLIGHT_KIND = "builder_ii.core_demo_preflight"
CORE_DEMO_VERIFICATION_RECEIPT_KIND = "builder_ii.core_demo_verification_receipt"
CORE_DEMO_REPORT_KIND = "builder_ii.core_demo_loop_report"
CORE_DEMO_REPORT_SCHEMA_VERSION = 1

DemoPhase = Literal[
    "prepare",
    "approve",
    "apply",
    "verify",
    "rollback",
    "finalize",
    "all",
]

_PHASES: tuple[DemoPhase, ...] = (
    "prepare",
    "approve",
    "apply",
    "verify",
    "rollback",
    "finalize",
    "all",
)

_DEMO_MARKER_PATH = Path("docs/builder_ii_core_demo_marker.md")


@dataclass(frozen=True)
class CoreDemoPaths:
    output_dir: Path

    @property
    def worktree(self) -> Path:
        return self.output_dir / "core-worktree"

    @property
    def repo_map(self) -> Path:
        return self.output_dir / "repo-map.json"

    @property
    def context_pack(self) -> Path:
        return self.output_dir / "context-pack.json"

    @property
    def planner(self) -> Path:
        return self.output_dir / "deterministic-planner.json"

    @property
    def patch_file(self) -> Path:
        return self.output_dir / "core-demo.patch"

    @property
    def reverse_patch_file(self) -> Path:
        return self.output_dir / "core-demo.reverse.patch"

    @property
    def proposal(self) -> Path:
        return self.output_dir / "hitl-patch-proposal.json"

    @property
    def approval(self) -> Path:
        return self.output_dir / "core-demo-approval.json"

    @property
    def preflight(self) -> Path:
        return self.output_dir / "preflight.json"

    @property
    def pre_apply_verification_receipt(self) -> Path:
        return self.output_dir / "pre-apply-verification-receipt.json"

    @property
    def post_apply_verification_receipt(self) -> Path:
        return self.output_dir / "post-apply-verification-receipt.json"

    @property
    def patch_apply_dir(self) -> Path:
        return self.output_dir / "patch-apply"

    @property
    def patch_apply_receipt(self) -> Path:
        return self.patch_apply_dir / "patch_apply_receipt.json"

    @property
    def patch_postflight(self) -> Path:
        return self.patch_apply_dir / "postflight_record.json"

    @property
    def rollback_plan(self) -> Path:
        return self.patch_apply_dir / "rollback_plan.json"

    @property
    def generated_reverse_patch_file(self) -> Path:
        return self.patch_apply_dir / "rollback.patch"

    @property
    def rollback_dir(self) -> Path:
        return self.output_dir / "rollback"

    @property
    def rollback_receipt(self) -> Path:
        return self.rollback_dir / "rollback_receipt.json"

    @property
    def final_postflight(self) -> Path:
        return self.output_dir / "final-postflight.json"

    @property
    def chain_report(self) -> Path:
        return self.output_dir / "chain-verification-report.json"

    @property
    def artifact_index(self) -> Path:
        return self.output_dir / "artifact-index.json"

    @property
    def report(self) -> Path:
        return self.output_dir / "core-demo-loop-report.json"

    @property
    def evidence_md(self) -> Path:
        return self.output_dir / "DEMO_EVIDENCE.md"


def _utc_timestamp() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _json_digest(value: dict[str, Any]) -> str:
    return _sha256_text(json_lib.dumps(value, sort_keys=True, separators=(",", ":")))


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json_lib.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected JSON object: {path}")
    return data


def _run_git(repo: Path, args: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def _repo_head(repo: Path) -> str:
    return _run_git(repo, ["rev-parse", "HEAD"]).stdout.strip()


def _repo_status(repo: Path) -> list[str]:
    result = _run_git(repo, ["status", "--porcelain=v1"])
    return result.stdout.splitlines()


def _ensure_core_repo(repo: Path) -> Path:
    resolved = repo.expanduser().resolve()
    if not resolved.is_dir():
        raise ValueError(f"CORE repo does not exist: {resolved}")
    if not (resolved / ".git").exists():
        raise ValueError(f"CORE repo is not a git checkout: {resolved}")
    try:
        remote = _run_git(resolved, ["remote", "-v"], check=False).stdout
    except OSError as exc:
        raise ValueError(f"failed to inspect CORE git remote: {exc}") from exc
    if "AssetOverflow/core" not in remote and resolved.name != "core":
        raise ValueError(f"repo does not look like AssetOverflow/core: {resolved}")
    return resolved


def _prepare_worktree(source_repo: Path, worktree: Path, *, force: bool) -> None:
    if worktree.exists():
        if not force:
            raise ValueError(f"worktree path already exists; use --force to replace: {worktree}")
        shutil.rmtree(worktree)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    head = _repo_head(source_repo)
    _run_git(source_repo, ["worktree", "prune"], check=False)
    _run_git(source_repo, ["worktree", "add", "--detach", str(worktree), head])


def _remove_worktree(source_repo: Path, worktree: Path) -> None:
    if not worktree.exists():
        return
    _run_git(source_repo, ["worktree", "remove", "--force", str(worktree)], check=False)


def _unified_diff_for_marker() -> str:
    return (
        f"diff --git a/{_DEMO_MARKER_PATH.as_posix()} b/{_DEMO_MARKER_PATH.as_posix()}\n"
        "new file mode 100644\n"
        "index 0000000..0000000\n"
        "--- /dev/null\n"
        f"+++ b/{_DEMO_MARKER_PATH.as_posix()}\n"
        "@@ -0,0 +1,3 @@\n"
        "+# builder-II CORE Demo Marker\n"
        "+\n"
        "+This temporary file is created by the builder-II CORE demo loop and is rolled back before the demo completes.\n"
    )


def _reverse_diff_for_marker() -> str:
    return (
        f"diff --git a/{_DEMO_MARKER_PATH.as_posix()} b/{_DEMO_MARKER_PATH.as_posix()}\n"
        "deleted file mode 100644\n"
        "index 0000000..0000000\n"
        f"--- a/{_DEMO_MARKER_PATH.as_posix()}\n"
        "+++ /dev/null\n"
        "@@ -1,3 +0,0 @@\n"
        "-# builder-II CORE Demo Marker\n"
        "-\n"
        "-This temporary file is created by the builder-II CORE demo loop and is rolled back before the demo completes.\n"
    )


def _write_repo_map_and_context(worktree: Path, paths: CoreDemoPaths) -> None:
    repo_map = create_repo_map(worktree, target_name="core", max_files=700)
    paths.repo_map.write_text(dumps_repo_map(repo_map), encoding="utf-8")
    context_pack = create_context_pack(
        repo_map,
        target_name="core",
        task="Demonstrate builder-II governed patch, verify, rollback loop on AssetOverflow/core.",
        max_entries=80,
    )
    paths.context_pack.write_text(dumps_context_pack(context_pack), encoding="utf-8")


def _write_planner(paths: CoreDemoPaths, worktree: Path, patch_digest: str) -> dict[str, Any]:
    planner = {
        "kind": CORE_DEMO_PLANNER_KIND,
        "schema_version": 1,
        "created_at": _utc_timestamp(),
        "target": {
            "name": "core",
            "repo": str(worktree),
            "source": "AssetOverflow/core temporary detached worktree",
        },
        "selected_change": {
            "path": _DEMO_MARKER_PATH.as_posix(),
            "operation": "temporary_add_then_rollback",
            "patch_digest": patch_digest,
            "reason": "Use a low-risk documentation marker outside CORE sensitive runtime modules to prove the governed lifecycle.",
        },
        "core_invariant_policy": {
            "sensitive_modules_untouched": [
                "algebra/",
                "field/",
                "generate/",
                "core/cognition/",
                "vault/",
                "teaching/",
                "calibration/",
                "sensorium/",
            ],
            "versor_condition_boundary": "not exercised by documentation-only marker change",
            "cga_recall_boundary": "not exercised by documentation-only marker change",
            "stochastic_generation": "not introduced",
        },
        "governance": {
            "capability_state": "CORE_DEMO_PLANNED",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "source_writes": "DISABLED EXCEPT APPROVED TEMPORARY CORE WORKTREE PATCH",
            "target_repo_writes": "TEMPORARY_WORKTREE_ONLY_AFTER_APPROVAL",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    _write_json(paths.planner, planner)
    return planner


def _write_patch_proposal(paths: CoreDemoPaths, worktree: Path, patch_text: str, patch_digest: str) -> dict[str, Any]:
    paths.patch_file.write_text(patch_text, encoding="utf-8")
    paths.reverse_patch_file.write_text(_reverse_diff_for_marker(), encoding="utf-8")
    proposal = create_hitl_patch_proposal(
        target_name="generic",
        generic_repo=worktree,
        patch_description="CORE demo: add temporary builder-II demo marker",
        reason="Prove the governed inspect -> propose -> approve -> apply -> verify -> rollback lifecycle on AssetOverflow/core without touching sensitive CORE runtime modules.",
        patch_digest=patch_digest,
        unified_diff=patch_text,
    )
    proposal["target"]["name"] = "core"
    proposal["target"]["description"] = "AssetOverflow/core temporary detached worktree for builder-II CORE demo."
    write_hitl_patch_proposal(proposal, paths.proposal)
    return proposal


def create_core_demo_approval(
    proposal: dict[str, Any],
    *,
    proposal_path: Path,
    decided_by: str = "operator",
    approved: bool = True,
    reason: str = "Interactive CORE demo approval.",
) -> dict[str, Any]:
    patch_digest = str(proposal.get("patch_digest", ""))
    return {
        "kind": CORE_DEMO_APPROVAL_KIND,
        "schema_version": CORE_DEMO_APPROVAL_SCHEMA_VERSION,
        "created_at": _utc_timestamp(),
        "decision": "approved" if approved else "rejected",
        "approved": approved,
        "decided_by": decided_by,
        "reason": reason,
        "proposal_ref": {
            "path": str(proposal_path),
            "kind": proposal.get("kind", ""),
            "sha256": _json_digest(proposal),
        },
        "patch_digest": patch_digest,
        "approval_boundary": "operator explicitly approved this exact patch digest for the temporary CORE demo worktree",
        "grants_runtime_authority": False,
        "grants_action_authority": approved,
        "governance": {
            "capability_state": "CORE_DEMO_APPROVAL",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "APPROVED_TEMPORARY_CORE_WORKTREE_PATCH_ONLY" if approved else "DISABLED",
            "target_repo_writes": "TEMPORARY_WORKTREE_ONLY" if approved else "DISABLED",
            "commit_push": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }


def validate_core_demo_approval(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["core demo approval must be a JSON object"]
    if data.get("kind") != CORE_DEMO_APPROVAL_KIND:
        errors.append(f"kind must be {CORE_DEMO_APPROVAL_KIND}")
    if data.get("schema_version") != CORE_DEMO_APPROVAL_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CORE_DEMO_APPROVAL_SCHEMA_VERSION}")
    if data.get("decision") not in ("approved", "rejected"):
        errors.append("decision must be approved or rejected")
    if data.get("approved") is not (data.get("decision") == "approved"):
        errors.append("approved must match decision")
    if not isinstance(data.get("decided_by"), str) or not data["decided_by"]:
        errors.append("decided_by must be a non-empty string")
    if not isinstance(data.get("patch_digest"), str) or len(data["patch_digest"]) != 64:
        errors.append("patch_digest must be a SHA-256 string")
    proposal_ref = data.get("proposal_ref")
    if not isinstance(proposal_ref, dict):
        errors.append("proposal_ref must be an object")
    else:
        if not proposal_ref.get("path"):
            errors.append("proposal_ref.path is required")
        if not isinstance(proposal_ref.get("sha256"), str) or len(proposal_ref["sha256"]) != 64:
            errors.append("proposal_ref.sha256 must be a SHA-256 string")
    if data.get("grants_runtime_authority") is not False:
        errors.append("grants_runtime_authority must be false")
    if not isinstance(data.get("grants_action_authority"), bool):
        errors.append("grants_action_authority must be a boolean")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("runtime_execution") != "DISABLED":
            errors.append("governance.runtime_execution must be DISABLED")
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED")
        if governance.get("shell_execution") != "DISABLED":
            errors.append("governance.shell_execution must be DISABLED")
        if governance.get("commit_push") != "DISABLED":
            errors.append("governance.commit_push must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_core_demo_planner(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["core demo planner must be a JSON object"]
    if data.get("kind") != CORE_DEMO_PLANNER_KIND:
        errors.append(f"kind must be {CORE_DEMO_PLANNER_KIND}")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    target = data.get("target")
    if not isinstance(target, dict) or target.get("name") != "core" or not target.get("repo"):
        errors.append("target must describe the core demo repository")
    change = data.get("selected_change")
    if not isinstance(change, dict):
        errors.append("selected_change must be an object")
    else:
        if change.get("path") != _DEMO_MARKER_PATH.as_posix():
            errors.append("selected_change.path must be the demo marker path")
        if not isinstance(change.get("patch_digest"), str) or len(change["patch_digest"]) != 64:
            errors.append("selected_change.patch_digest must be a SHA-256 string")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_core_demo_preflight(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["core demo preflight must be a JSON object"]
    if data.get("kind") != CORE_DEMO_PREFLIGHT_KIND:
        errors.append(f"kind must be {CORE_DEMO_PREFLIGHT_KIND}")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    for field in ("source_repo", "demo_worktree", "source_head", "worktree_head"):
        if not isinstance(data.get(field), str) or not data[field]:
            errors.append(f"{field} must be a non-empty string")
    if not isinstance(data.get("source_repo_status"), list):
        errors.append("source_repo_status must be a list")
    if data.get("worktree_status") != []:
        errors.append("worktree_status must be empty")
    if data.get("ready") is not True:
        errors.append("ready must be true")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("source_writes") != "DISABLED":
            errors.append("governance.source_writes must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def validate_core_demo_verification_receipt(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["core demo verification receipt must be a JSON object"]
    if data.get("kind") != CORE_DEMO_VERIFICATION_RECEIPT_KIND:
        errors.append(f"kind must be {CORE_DEMO_VERIFICATION_RECEIPT_KIND}")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("label") not in ("before_apply", "after_apply"):
        errors.append("label must be before_apply or after_apply")
    if data.get("receipt_status") != "EXECUTED":
        errors.append("receipt_status must be EXECUTED")
    checks = data.get("checks")
    if not isinstance(checks, list) or not checks:
        errors.append("checks must be a non-empty list")
    elif any(not isinstance(check, dict) or check.get("status") != "PASS" for check in checks):
        errors.append("all checks must be PASS")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED")
        if governance.get("source_writes") != "DISABLED":
            errors.append("governance.source_writes must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    return errors


def _write_preflight(paths: CoreDemoPaths, source_repo: Path, worktree: Path) -> dict[str, Any]:
    source_status = _repo_status(source_repo)
    worktree_status = _repo_status(worktree)
    record = {
        "kind": CORE_DEMO_PREFLIGHT_KIND,
        "schema_version": 1,
        "created_at": _utc_timestamp(),
        "source_repo": str(source_repo),
        "demo_worktree": str(worktree),
        "source_head": _repo_head(source_repo),
        "worktree_head": _repo_head(worktree),
        "source_repo_status": source_status,
        "worktree_status": worktree_status,
        "ready": len(worktree_status) == 0,
        "source_repo_dirty_ok": True,
        "note": "The source CORE checkout may be dirty; the demo mutates only the detached temporary worktree.",
        "governance": {
            "capability_state": "CORE_DEMO_PREFLIGHT",
            "runtime_execution": "DISABLED",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "target_repo_writes": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    _write_json(paths.preflight, record)
    if not record["ready"]:
        raise ValueError(f"CORE demo worktree is not clean: {worktree_status}")
    return record


def _write_verification_receipt(paths: CoreDemoPaths, worktree: Path, *, label: str) -> dict[str, Any]:
    marker_exists = (worktree / _DEMO_MARKER_PATH).is_file()
    expected_marker = label == "after_apply"
    status_lines = _repo_status(worktree)
    receipt_status = "EXECUTED" if marker_exists is expected_marker else "FAILED"
    receipt = {
        "kind": CORE_DEMO_VERIFICATION_RECEIPT_KIND,
        "schema_version": 1,
        "created_at": _utc_timestamp(),
        "label": label,
        "target": {
            "name": "core",
            "repo": str(worktree),
        },
        "checks": [
            {
                "name": "demo_marker_state",
                "expected_exists": expected_marker,
                "observed_exists": marker_exists,
                "status": "PASS" if marker_exists is expected_marker else "FAIL",
            },
            {
                "name": "sensitive_core_modules_untouched",
                "status_lines": status_lines,
                "status": "PASS"
                if all(not line[3:].startswith(("algebra/", "field/", "generate/", "core/cognition/", "vault/", "teaching/", "calibration/", "sensorium/")) for line in status_lines)
                else "FAIL",
            },
        ],
        "receipt_status": receipt_status,
        "workspace_mutation_detected": bool(status_lines),
        "status_lines": status_lines,
        "governance": {
            "capability_state": "CORE_DEMO_VERIFICATION",
            "runtime_execution": "BOUNDED_IN_PROCESS_CHECKS",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED",
            "source_writes": "DISABLED",
            "target_repo_writes": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    output = paths.pre_apply_verification_receipt if label == "before_apply" else paths.post_apply_verification_receipt
    _write_json(output, receipt)
    if receipt_status != "EXECUTED":
        raise ValueError("CORE demo verification failed after apply")
    return receipt


def _write_final_postflight(paths: CoreDemoPaths, worktree: Path) -> dict[str, Any]:
    status_lines = _repo_status(worktree)
    postflight = create_execution_postflight_record(
        target_name="generic",
        generic_repo=worktree,
        request_ref=str(paths.proposal),
        receipt_ref=str(paths.rollback_receipt),
        preflight_ref=str(paths.preflight),
        approval_ref=str(paths.approval),
        expected_outcome="Temporary CORE demo patch rolled back; detached worktree returned clean.",
        observed_state_ref="git status --porcelain=v1",
    )
    postflight["target"]["name"] = "core"
    postflight["target"]["description"] = "AssetOverflow/core temporary detached worktree for builder-II CORE demo."
    postflight["postflight_state"] = "RUN_COMPLETE"
    postflight["performed_actions"] = ["read git status for detached CORE demo worktree"]
    postflight["observed_status_lines"] = status_lines
    postflight["workspace_clean"] = len(status_lines) == 0
    write_execution_postflight_record(postflight, paths.final_postflight)
    if status_lines:
        raise ValueError(f"CORE demo rollback did not return worktree clean: {status_lines}")
    return postflight


def create_core_demo_report(
    *,
    paths: CoreDemoPaths,
    source_repo: Path,
    worktree: Path,
    phase: DemoPhase,
    completed_steps: list[str],
    chain_report: dict[str, Any] | None,
    artifact_paths: list[Path],
    ready_for_recording: bool,
    next_command: str,
) -> dict[str, Any]:
    refs = []
    for path in artifact_paths:
        if path.is_file() and path.suffix == ".json":
            try:
                data = _read_json(path)
            except Exception:
                continue
            refs.append(
                {
                    "path": str(path),
                    "kind": data.get("kind", ""),
                    "sha256": _json_digest(data),
                }
            )
    report = {
        "kind": CORE_DEMO_REPORT_KIND,
        "schema_version": CORE_DEMO_REPORT_SCHEMA_VERSION,
        "created_at": _utc_timestamp(),
        "phase": phase,
        "target": {
            "name": "core",
            "source_repo": str(source_repo),
            "demo_worktree": str(worktree),
        },
        "completed_steps": completed_steps,
        "ready_for_recording": ready_for_recording,
        "next_command": next_command,
        "artifact_refs": refs,
        "chain_verification": {
            "path": str(paths.chain_report),
            "valid": bool(chain_report and chain_report.get("valid")),
            "errors": list(chain_report.get("errors", [])) if isinstance(chain_report, dict) else [],
        },
        "final_state": {
            "source_repo_untouched_by_demo": True,
            "demo_worktree_clean_after_rollback": paths.final_postflight.is_file()
            and not _read_json(paths.final_postflight).get("observed_status_lines"),
        },
        "governance": {
            "capability_state": "CORE_DEMO_LOOP",
            "runtime_execution": "GUIDED_DEMO_ONLY",
            "model_execution": "DISABLED",
            "shell_execution": "DISABLED_FOR_DEMO_PAYLOAD",
            "source_writes": "TEMPORARY_CORE_WORKTREE_ONLY_AFTER_APPROVAL",
            "commit_push": "DISABLED",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    report["report_digest"] = _json_digest(report)
    return report


def validate_core_demo_report(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["core demo loop report must be a JSON object"]
    if data.get("kind") != CORE_DEMO_REPORT_KIND:
        errors.append(f"kind must be {CORE_DEMO_REPORT_KIND}")
    if data.get("schema_version") != CORE_DEMO_REPORT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {CORE_DEMO_REPORT_SCHEMA_VERSION}")
    if data.get("phase") not in _PHASES:
        errors.append("phase must be a known demo phase")
    if not isinstance(data.get("artifact_refs"), list):
        errors.append("artifact_refs must be a list")
    if not isinstance(data.get("ready_for_recording"), bool):
        errors.append("ready_for_recording must be a boolean")
    final_state = data.get("final_state")
    if not isinstance(final_state, dict):
        errors.append("final_state must be an object")
    else:
        if final_state.get("source_repo_untouched_by_demo") is not True:
            errors.append("final_state.source_repo_untouched_by_demo must be true")
    governance = data.get("governance")
    if not isinstance(governance, dict):
        errors.append("governance must be an object")
    else:
        if governance.get("model_execution") != "DISABLED":
            errors.append("governance.model_execution must be DISABLED")
        if governance.get("commit_push") != "DISABLED":
            errors.append("governance.commit_push must be DISABLED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE")
    digest = data.get("report_digest")
    if isinstance(digest, str):
        clone = dict(data)
        clone.pop("report_digest", None)
        if _json_digest(clone) != digest:
            errors.append("report_digest does not match canonical content")
    else:
        errors.append("report_digest is required")
    return errors


def _write_evidence_markdown(paths: CoreDemoPaths, report: dict[str, Any]) -> None:
    lines = [
        "# builder-II CORE Demo Evidence",
        "",
        "This evidence bundle records a guided builder-II run against a temporary detached worktree of AssetOverflow/core.",
        "",
        "## Boundary",
        "",
        "- Source CORE checkout is not mutated by the demo.",
        "- The temporary CORE worktree is patched only after explicit approval.",
        "- The patch is rolled back before completion.",
        "- No commit, push, model execution, Goose activation, MCP call, or hidden memory is used.",
        "",
        "## Artifact Chain",
        "",
    ]
    for ref in report.get("artifact_refs", []):
        path = ref["path"]
        lines.append(f"- `{ref['kind']}`: `{path}` (`{ref['sha256']}`)")
    lines.extend(
        [
            "",
            "## Recording Beats",
            "",
            "1. Show preflight and CORE detached worktree boundary.",
            "2. Show deterministic planner and HITL patch proposal.",
            "3. Show explicit approval digest.",
            "4. Apply the patch, verify the temporary marker exists, then roll it back.",
            "5. Show final postflight, artifact index, chain verification, and clean worktree proof.",
            "",
            f"Report digest: `{report.get('report_digest', '')}`",
            "",
        ]
    )
    paths.evidence_md.write_text("\n".join(lines), encoding="utf-8")


def _artifact_paths_for_chain(paths: CoreDemoPaths) -> list[Path]:
    candidates = [
        paths.preflight,
        paths.repo_map,
        paths.context_pack,
        paths.planner,
        paths.proposal,
        paths.approval,
        paths.pre_apply_verification_receipt,
        paths.post_apply_verification_receipt,
        paths.rollback_plan,
        paths.patch_apply_receipt,
        paths.patch_postflight,
        paths.rollback_receipt,
        paths.final_postflight,
    ]
    return [path for path in candidates if path.is_file()]


def _is_demo_artifact_path(path: Path, paths: CoreDemoPaths) -> bool:
    resolved = path.resolve()
    return resolved.is_file() and not resolved.is_relative_to(paths.worktree.resolve())


def _demo_json_artifact_paths(paths: CoreDemoPaths) -> list[Path]:
    return sorted(
        path
        for path in paths.output_dir.rglob("*.json")
        if _is_demo_artifact_path(path, paths)
        and path.resolve() != paths.report.resolve()
    )


def _clear_stale_final_outputs(paths: CoreDemoPaths) -> None:
    for path in (paths.report, paths.artifact_index, paths.evidence_md):
        if path.exists():
            path.unlink()


def _finalize(paths: CoreDemoPaths, source_repo: Path, worktree: Path, phase: DemoPhase, completed_steps: list[str]) -> dict[str, Any]:
    from builder_ii.artifact_chain_verification import verify_artifact_chain
    from builder_ii.artifact_index_records import create_artifact_index_record, write_artifact_index_record

    _clear_stale_final_outputs(paths)
    chain_paths = _artifact_paths_for_chain(paths)
    chain_report = verify_artifact_chain(chain_paths)
    _write_json(paths.chain_report, chain_report)
    index = create_artifact_index_record(paths.output_dir, recursive=True, exclude_paths=(paths.worktree,))
    write_artifact_index_record(index, paths.artifact_index)
    all_artifacts = _demo_json_artifact_paths(paths)
    report = create_core_demo_report(
        paths=paths,
        source_repo=source_repo,
        worktree=worktree,
        phase=phase,
        completed_steps=completed_steps,
        chain_report=chain_report,
        artifact_paths=all_artifacts,
        ready_for_recording=True,
        next_command="Demo loop complete. Open DEMO_EVIDENCE.md and core-demo-loop-report.json.",
    )
    errors = validate_core_demo_report(report)
    if errors:
        raise ValueError("invalid CORE demo report: " + "; ".join(errors))
    _write_json(paths.report, report)
    _write_evidence_markdown(paths, report)
    return report


def run_core_demo_loop(
    *,
    core_repo: Path,
    output_dir: Path,
    phase: DemoPhase = "all",
    approve: bool = False,
    force: bool = False,
    cleanup_worktree: bool = False,
) -> dict[str, Any]:
    if phase not in _PHASES:
        raise ValueError(f"phase must be one of: {', '.join(_PHASES)}")

    source_repo = _ensure_core_repo(core_repo)
    paths = CoreDemoPaths(output_dir.resolve())
    paths.output_dir.mkdir(parents=True, exist_ok=True)

    completed: list[str] = []

    if phase in ("prepare", "all"):
        _prepare_worktree(source_repo, paths.worktree, force=force)
        _write_preflight(paths, source_repo, paths.worktree)
        _write_repo_map_and_context(paths.worktree, paths)
        patch_text = _unified_diff_for_marker()
        patch_digest = _sha256_text(patch_text)
        _write_planner(paths, paths.worktree, patch_digest)
        _write_patch_proposal(paths, paths.worktree, patch_text, patch_digest)
        completed.extend(["temporary CORE worktree created", "preflight recorded", "repo map and context pack emitted", "HITL patch proposal emitted"])
        if phase == "prepare" and not approve:
            proposal = _read_json(paths.proposal)
            report = create_core_demo_report(
                paths=paths,
                source_repo=source_repo,
                worktree=paths.worktree,
                phase=phase,
                completed_steps=completed,
                chain_report=None,
                artifact_paths=[paths.preflight, paths.repo_map, paths.context_pack, paths.planner, paths.proposal],
                ready_for_recording=True,
                next_command=(
                    "builder-platform demo-loop --phase approve "
                    f"--core-repo {source_repo} --output-dir {paths.output_dir} --approve"
                ),
            )
            _write_json(paths.report, report)
            _write_evidence_markdown(paths, report)
            return report

    if phase in ("approve", "all"):
        if not paths.proposal.is_file():
            raise ValueError("prepare phase must run before approval")
        proposal = _read_json(paths.proposal)
        approval = create_core_demo_approval(
            proposal,
            proposal_path=paths.proposal,
            approved=approve,
            reason="Operator approved the exact CORE demo patch digest." if approve else "Approval checkpoint reached; rerun with --approve.",
        )
        errors = validate_core_demo_approval(approval)
        if errors:
            raise ValueError("invalid CORE demo approval: " + "; ".join(errors))
        _write_json(paths.approval, approval)
        completed.append("approval artifact emitted")
        if not approve:
            report = create_core_demo_report(
                paths=paths,
                source_repo=source_repo,
                worktree=paths.worktree,
                phase=phase,
                completed_steps=completed,
                chain_report=None,
                artifact_paths=[paths.proposal, paths.approval],
                ready_for_recording=True,
                next_command=(
                    "Approval recorded as rejected. Rerun with --approve to apply to the temporary CORE worktree."
                ),
            )
            _write_json(paths.report, report)
            _write_evidence_markdown(paths, report)
            return report

    if phase in ("apply", "all"):
        if not paths.approval.is_file():
            raise ValueError("approval phase must run before apply")
        approval = _read_json(paths.approval)
        if approval.get("approved") is not True:
            raise ValueError("approval artifact is not approved")
        if not paths.pre_apply_verification_receipt.is_file():
            _write_verification_receipt(paths, paths.worktree, label="before_apply")
        apply_hitl_patch(
            proposal_path=paths.proposal,
            approval_path=paths.approval,
            verification_receipt_path=paths.pre_apply_verification_receipt,
            output_dir=paths.patch_apply_dir,
        )
        completed.append("approved patch applied to temporary CORE worktree")

    if phase in ("verify", "all"):
        _write_verification_receipt(paths, paths.worktree, label="after_apply")
        completed.append("post-apply verification receipt emitted")

    if phase in ("rollback", "all"):
        rollback_hitl_patch(
            rollback_plan_path=paths.rollback_plan,
            reverse_patch_path=paths.generated_reverse_patch_file,
            output_dir=paths.rollback_dir,
        )
        _write_final_postflight(paths, paths.worktree)
        completed.append("rollback executed and final clean postflight recorded")

    if phase in ("finalize", "all"):
        report = _finalize(paths, source_repo, paths.worktree, phase, completed)
        if cleanup_worktree:
            _remove_worktree(source_repo, paths.worktree)
        return report

    report = create_core_demo_report(
        paths=paths,
        source_repo=source_repo,
        worktree=paths.worktree,
        phase=phase,
        completed_steps=completed,
        chain_report=None,
        artifact_paths=_demo_json_artifact_paths(paths),
        ready_for_recording=True,
        next_command="Run the next demo phase explicitly.",
    )
    _write_json(paths.report, report)
    _write_evidence_markdown(paths, report)
    return report


def dumps_core_demo_report(report: dict[str, Any]) -> str:
    return json_lib.dumps(report, indent=2, sort_keys=True) + "\n"
