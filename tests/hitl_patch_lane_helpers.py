"""Shared builders for HITL patch-lane tests (plan item 1.6).

These construct *real* governed artifacts — a genuine verification_execution plan/approval/
receipt chain and a real git target repo — so tests can exercise the apply/rollback lane
without mocking validators. Imported by bare name (conftest puts ``tests/`` on ``sys.path``,
the same convention as ``orchestration_assignment_fixtures``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from builder_ii.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.verification_execution_receipt import (
    RUNNER_MODE_BOUNDED_APPROVED,
    SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    finalize_verification_execution_receipt,
    write_verification_execution_receipt,
)

PATCH_DIFF = (
    "diff --git a/file.txt b/file.txt\n"
    "index 273b063..843d1a8 100644\n"
    "--- a/file.txt\n"
    "+++ b/file.txt\n"
    "@@ -1,2 +1,2 @@\n"
    " Line 1\n"
    "-Line 2\n"
    "+Line 2 modified\n"
)


def init_target_repo(root: Path) -> Path:
    """A committed git repo with ``file.txt`` = ``Line 1\\nLine 2\\n`` that PATCH_DIFF applies to."""
    repo = root / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    (repo / "file.txt").write_text("Line 1\nLine 2\n")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    return repo


def real_verification_receipt(tmp_path: Path) -> Path:
    """A genuine, schema-valid verification_execution receipt built from a real plan and
    approval — it passes ``validate_verification_execution_receipt_file`` with no mock."""
    root = tmp_path / ".builder" / "verification"
    root.mkdir(parents=True, exist_ok=True)
    plan = finalize_verification_execution_plan(
        target_profile="builder",
        verification_profile="builder_full",
        target_repo=str(tmp_path),
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = root / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Jane Operator",
        approval_reason="Approve bounded platform_status verification runner proof.",
        approved_command_profiles=["platform_status"],
        approved_step_ids=["platform_status"],
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = root / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)

    receipt = finalize_verification_execution_receipt(
        plan=plan,
        approval=approval,
        plan_path=str(plan_path),
        approval_path=str(approval_path),
        runner_mode=RUNNER_MODE_BOUNDED_APPROVED,
        generated_at="2026-06-30T00:02:00+00:00",
        receipt_status="EXECUTED",
        executed_steps=[{"step_id": "platform_status", "status": "success", "profile": "platform_status"}],
        skipped_steps=[],
        process_results=[
            {
                "step_id": "platform_status",
                "profile": "platform_status",
                "command_profile_ref": "verification_profiles.builder_full.platform_status",
                "status": "success",
                "returncode": 0,
                "timeout_seconds": 30,
                "shell": False,
                "argv_digest": "0" * 64,
                "stdout_sha256": "1" * 64,
                "stderr_sha256": "2" * 64,
                "stdout_excerpt": "builder-II platform status\n",
                "stderr_excerpt": "",
                "stdout_truncated": False,
                "stderr_truncated": False,
            }
        ],
        preflight_git_state={
            "state_label": "preflight",
            "captured": True,
            "returncode": 0,
            "porcelain_sha256": "3" * 64,
            "porcelain_lines": [],
            "stderr_sha256": "4" * 64,
        },
        postflight_git_state={
            "state_label": "postflight",
            "captured": True,
            "returncode": 0,
            "porcelain_sha256": "3" * 64,
            "porcelain_lines": [],
            "stderr_sha256": "4" * 64,
        },
        workspace_mutation_detected=False,
        execution_enabled=True,
        subprocess_mode=SUBPROCESS_MODE_SHELL_FALSE_BOUNDED,
    )
    receipt_path = root / "verification-execution-receipt.json"
    write_verification_execution_receipt(receipt, receipt_path)
    return receipt_path
