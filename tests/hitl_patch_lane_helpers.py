"""Shared builders for HITL patch-lane tests (plan item 1.6).

These construct *real* governed artifacts — a genuine verification_execution plan/approval/
receipt chain and a real git target repo — so tests can exercise the apply/rollback lane
without mocking validators. Imported by bare name (conftest puts ``tests/`` on ``sys.path``,
the same convention as ``orchestration_assignment_fixtures``).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from builder_ii.lifecycle.candidate.verification_execution_approval import (
    finalize_verification_execution_approval,
    write_verification_execution_approval,
)
from builder_ii.lifecycle.candidate.verification_execution_plan import (
    finalize_verification_execution_plan,
    write_verification_execution_plan,
)
from builder_ii.lifecycle.candidate.verification_execution_runner import run_approved_verification

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
    (repo / "test_smoke.py").write_text("def test_smoke():\n    assert True\n")
    subprocess.run(["git", "add", "file.txt", "test_smoke.py"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)
    (repo / ".git" / "info" / "exclude").write_text(".builder/\n", encoding="utf-8")
    return repo


def real_verification_receipt(tmp_path: Path, target_repo: Path | None = None) -> Path:
    """Obtain a runner-backed receipt for the actual target repository and HEAD."""
    target_repo = target_repo or tmp_path
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target_repo, check=True, capture_output=True, text=True).stdout.strip()
    root = target_repo / ".builder" / "verification"
    root.mkdir(parents=True, exist_ok=True)
    plan = finalize_verification_execution_plan(
        target_head_sha=head,
        tree_clean=True,
        target_profile="generic",
        verification_profile="generic_basic",
        target_repo=str(target_repo),
        artifact_root=".builder/verification",
        generated_at="2026-06-30T00:00:00+00:00",
    )
    plan_path = root / "verification-execution-plan.json"
    write_verification_execution_plan(plan, plan_path)

    approval = finalize_verification_execution_approval(expires_at="2030-01-01T00:00:00Z",
        plan=plan,
        plan_path=str(plan_path),
        approval_actor="Jane Operator",
        approval_reason="Approve bounded target-code verification runner proof.",
        approved_command_profiles=["pytest_full"],
        approved_step_ids=["pytest_full"],
        execution_risk_acknowledged=True,
        acknowledged_risk="The approved pytest_full profile executes target repository code.",
        generated_at="2026-06-30T00:01:00+00:00",
    )
    approval_path = root / "verification-execution-approval.json"
    write_verification_execution_approval(approval, approval_path)

    receipt_path = root / "verification-execution-receipt.json"
    run_approved_verification(plan_path=plan_path, approval_path=approval_path,
        output=receipt_path, requested_profile="pytest_full")
    return receipt_path
