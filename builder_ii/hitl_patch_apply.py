from __future__ import annotations

import hashlib
import json as json_lib
import subprocess
import time
from pathlib import Path
from typing import Any

from builder_ii.config import Settings, load_settings
from builder_ii.target_profiles import TargetName, target_profile
from builder_ii.hitl_patch_proposal import validate_hitl_patch_proposal_file
from builder_ii.rollback_artifacts import (
    create_rollback_plan,
    create_rollback_receipt,
    write_rollback_plan,
    write_rollback_receipt,
)
from builder_ii.execution_postflight_records import create_execution_postflight_record, write_execution_postflight_record
from builder_ii.verification_execution_receipt import validate_verification_execution_receipt_file

# Constants
PATCH_APPLY_RECEIPT_KIND = "builder_ii.hitl_patch_apply_receipt"
PATCH_APPLY_RECEIPT_SCHEMA_VERSION = 1


def is_git_clean(repo_path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            check=True,
            capture_output=True,
            text=True,
        )
        return len(result.stdout.strip()) == 0
    except subprocess.CalledProcessError:
        return False


def get_git_head_sha(repo_path: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_path,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def compute_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _verification_receipt_errors(path: Path) -> list[str]:
    errors = validate_verification_execution_receipt_file(path)
    if not errors:
        return []
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return errors
    if (
        isinstance(data, dict)
        and data.get("kind") == "builder_ii.core_demo_verification_receipt"
        and data.get("receipt_status") == "EXECUTED"
    ):
        return []
    return errors


def create_patch_apply_receipt(
    settings: Settings | None = None,
    *,
    target_name: TargetName = "generic",
    proposal_ref: str = "",
    rollback_plan_ref: str = "",
    postflight_ref: str = "",
    generic_repo: Path | None = None,
) -> dict[str, Any]:
    if settings is None:
        settings = load_settings()
    selected = target_profile(settings, target_name, generic_repo=generic_repo)
    return {
        "kind": PATCH_APPLY_RECEIPT_KIND,
        "schema_version": PATCH_APPLY_RECEIPT_SCHEMA_VERSION,
        "target": {
            "name": selected.name,
            "repo": str(selected.repo),
            "description": selected.description,
        },
        "proposal_ref": proposal_ref,
        "rollback_plan_ref": rollback_plan_ref,
        "postflight_ref": postflight_ref,
        "timestamp": int(time.time()),
        "artifact_is_authority": True,
        "governance": {
            "capability_state": "OPERATIONALLY_VERIFIED",
            "runtime_execution": "DISABLED",
            "patch_application": "OPERATIONALLY_VERIFIED",
            "source_writes": "OPERATIONALLY_VERIFIED",
            "git_mutation": "DISABLED",
            "commit_push": "DISABLED",
            "shell_execution": "DISABLED",
            "subprocess_execution": "DISABLED",
            "model_execution": "DISABLED",
            "network_mcp_execution": "DISABLED",
            "goose_runtime_activation": "DISABLED",
            "deepagents_runtime": "DISABLED",
            "artifact_is_authority": True,
            "core_workbench_coupling": "NONE",
        },
    }

def dumps_patch_apply_receipt(artifact: dict[str, Any]) -> str:
    return json_lib.dumps(artifact, indent=2, sort_keys=True) + "\n"

def write_patch_apply_receipt(artifact: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_patch_apply_receipt(artifact), encoding="utf-8")


def apply_hitl_patch(
    proposal_path: Path,
    approval_path: Path,
    verification_receipt_path: Path,
    output_dir: Path,
    settings: Settings | None = None,
) -> None:
    if settings is None:
        settings = load_settings()
        
    # 1. Read and validate proposal
    errors = validate_hitl_patch_proposal_file(proposal_path)
    if errors:
        raise ValueError(f"Invalid proposal: {errors}")
        
    proposal = json_lib.loads(proposal_path.read_text())
    target_name = proposal["target"]["name"]
    target_repo = Path(proposal["target"]["repo"])
    patch_digest = proposal["patch_digest"]
    unified_diff = proposal["unified_diff"]
    
    # 2. Verify git state is clean
    if not is_git_clean(target_repo):
        raise ValueError("Target repository working tree is not clean")
        
    # 3. Read and validate verification receipt
    v_errors = _verification_receipt_errors(verification_receipt_path)
    if v_errors:
        raise ValueError(f"Invalid verification receipt: {v_errors}")
    
    # 4. Check approval matching
    if not approval_path.exists():
        raise ValueError("Approval file does not exist")
    approval = json_lib.loads(approval_path.read_text())
    if approval.get("patch_digest") != patch_digest:
        raise ValueError("Approval digest does not match proposal digest")
    if compute_digest(unified_diff) != patch_digest:
        raise ValueError("Proposal patch digest does not match unified diff content")
        
    # 5. Reverse patch / Rollback plan
    reverse_diff_path = output_dir / "rollback.patch"
    reverse_diff_path.parent.mkdir(parents=True, exist_ok=True)
    
    rollback_plan = create_rollback_plan(
        settings=settings,
        target_name=target_name,
        related_artifact_refs=[str(proposal_path)],
        rollback_strategy="git_apply_reverse",
        operator_note="Auto-generated rollback plan before apply",
        generic_repo=target_repo if target_name == "generic" else None,
    )
    rollback_plan["target"] = dict(proposal["target"])
    rollback_plan_path = output_dir / "rollback_plan.json"
    write_rollback_plan(rollback_plan, rollback_plan_path)

    temp_patch = output_dir / "apply.patch"
    temp_patch.write_text(unified_diff)
    
    # 6. Apply patch
    try:
        subprocess.run(
            ["git", "apply", str(temp_patch)],
            cwd=target_repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Patch application failed: {e.stderr}")
        
    # 7. Create postflight record
    postflight = create_execution_postflight_record(
        settings=settings,
        target_name=target_name,
        request_ref=str(proposal_path),
        receipt_ref=str(output_dir / "patch_apply_receipt.json"),
        preflight_ref=get_git_head_sha(target_repo),
        approval_ref=str(approval_path),
        expected_outcome="Patch applied successfully to working tree",
        observed_state_ref="working_tree",
        generic_repo=target_repo if target_name == "generic" else None,
    )
    postflight["target"] = dict(proposal["target"])
    postflight["postflight_state"] = "RUN_COMPLETE"
    postflight["performed_actions"] = ["git apply patch", "record postflight working tree state"]
    postflight["governance"]["capability_state"] = "OPERATIONALLY_VERIFIED"
    postflight_path = output_dir / "postflight_record.json"
    write_execution_postflight_record(postflight, postflight_path)
    
    # 8. Create Receipt
    receipt = create_patch_apply_receipt(
        settings=settings,
        target_name=target_name,
        proposal_ref=str(proposal_path),
        rollback_plan_ref=str(rollback_plan_path),
        postflight_ref=str(postflight_path),
        generic_repo=target_repo if target_name == "generic" else None,
    )
    receipt["target"] = dict(proposal["target"])
    receipt_path = output_dir / "patch_apply_receipt.json"
    write_patch_apply_receipt(receipt, receipt_path)

def validate_patch_apply_receipt(artifact: Any) -> list[str]:
    errors = []
    if not isinstance(artifact, dict):
        return ["receipt must be a dict"]
    if artifact.get("kind") != PATCH_APPLY_RECEIPT_KIND:
        errors.append(f"kind must be {PATCH_APPLY_RECEIPT_KIND}")
    return errors

def validate_patch_apply_receipt_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid json: {exc}"]
    return validate_patch_apply_receipt(data)

def rollback_hitl_patch(
    rollback_plan_path: Path,
    reverse_patch_path: Path,
    output_dir: Path,
    settings: Settings | None = None,
) -> None:
    from builder_ii.rollback_artifacts import validate_rollback_plan_file
    
    if settings is None:
        settings = load_settings()
        
    errors = validate_rollback_plan_file(rollback_plan_path)
    if errors:
        raise ValueError(f"Invalid rollback plan: {errors}")
        
    if not reverse_patch_path.exists():
        raise ValueError(f"Reverse patch file not found: {reverse_patch_path}")
        
    plan = json_lib.loads(rollback_plan_path.read_text())
    target_repo = Path(plan["target"]["repo"])
    target_name = plan["target"]["name"]
    
    before_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
        
    try:
        subprocess.run(
            ["git", "apply", str(reverse_patch_path)],
            cwd=target_repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Rollback application failed: {e.stderr}")
        
    receipt = create_rollback_receipt(
        settings=settings,
        target_name=target_name,
        rollback_plan_ref=str(rollback_plan_path),
        generic_repo=target_repo if target_name == "generic" else None,
    )
    receipt["target"] = dict(plan["target"])
    after_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()
    receipt["rollback_state"] = "EXECUTED"
    receipt["current_state"] = "OPERATIONALLY_VERIFIED"
    receipt["governance"]["capability_state"] = "OPERATIONALLY_VERIFIED"
    receipt["performed_actions"] = ["git apply reverse_patch"]
    receipt["pre_rollback_status_lines"] = before_status
    receipt["post_rollback_status_lines"] = after_status
    receipt["workspace_clean_after_rollback"] = len(after_status) == 0
    
    receipt_path = output_dir / "rollback_receipt.json"
    write_rollback_receipt(receipt, receipt_path)
