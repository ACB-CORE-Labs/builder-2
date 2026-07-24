import json
from pathlib import Path

from builder_ii.core.config_schema import attach_digest
from builder_ii.lifecycle.candidate.verification_execution_approval import finalize_verification_execution_approval
from builder_ii.lifecycle.candidate.verification_execution_plan import finalize_verification_execution_plan
from builder_ii.lifecycle.candidate.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    finalize_verification_execution_receipt,
    validate_verification_execution_receipt_file,
)


def write_core_demo_verification_receipt(path: Path, repo: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "kind": "builder_ii.core_demo_verification_receipt",
                "schema_version": 1,
                "label": "before_apply",
                "receipt_status": "EXECUTED",
                "target": {"name": "core", "repo": str(repo.resolve())},
                "checks": [{"status": "PASS", "name": "preflight"}],
                "governance": {
                    "model_execution": "DISABLED",
                    "source_writes": "DISABLED",
                    "artifact_is_authority": False,
                    "core_workbench_coupling": "NONE",
                },
            }
        ),
        encoding="utf-8",
    )


def write_executed_verification_receipt(path: Path, repo: Path) -> None:
    """Write a schema-valid builder_ii.verification_execution_receipt with EXECUTED status."""
    plan_path = path.parent / "verification-plan.json"
    approval_path = path.parent / "verification-approval.json"
    plan = finalize_verification_execution_plan(
        target_head_sha="0000000000000000000000000000000000000000",
        tree_clean=True,
        target_profile="generic",
        verification_profile="builder_full",
        target_repo=str(repo.resolve()),
        artifact_root=str((repo / ".builder").resolve()),
    )
    plan_path.write_text(json.dumps(plan, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="patch-test",
        approval_reason="HITL patch apply test verification binding",
        expires_at="2099-01-01T00:00:00Z",
    )
    approval_path.write_text(json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        receipt_status="EXECUTED",
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        preflight_git_state={"clean": True},
        postflight_git_state={"clean": True},
    )
    receipt = attach_digest(receipt, digest_key="verification_execution_receipt_digest")
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    errors = validate_verification_execution_receipt_file(path)
    if errors:
        raise AssertionError(f"test helper produced invalid verification receipt: {errors}")
