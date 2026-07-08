import hashlib
from pathlib import Path

from typer.testing import CliRunner

from builder_ii.cli.hitl_execution_cli import hitl_app
from builder_ii.hitl_patch_approval import validate_hitl_patch_approval_file
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.hitl_rollback_approval import canonical_json_digest, validate_hitl_rollback_approval_file
from builder_ii.rollback_artifacts import create_rollback_plan, write_rollback_plan

runner = CliRunner()


def _proposal_file(tmp_path: Path) -> tuple[Path, str]:
    diff = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-a\n+b\n"
    digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    prop_path = tmp_path / "prop.json"
    write_hitl_patch_proposal(
        create_hitl_patch_proposal(generic_repo=tmp_path, patch_digest=digest, unified_diff=diff),
        prop_path,
    )
    return prop_path, digest


def test_approve_patch_writes_approval_on_correct_prefix(tmp_path: Path):
    prop_path, digest = _proposal_file(tmp_path)
    out = tmp_path / "approval.json"

    result = runner.invoke(
        hitl_app,
        ["approve-patch", "--proposal", str(prop_path), "--output", str(out)],
        input=digest[:4] + "\n",
    )

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert validate_hitl_patch_approval_file(out) == []


def test_approve_patch_refuses_on_wrong_prefix(tmp_path: Path):
    prop_path, _ = _proposal_file(tmp_path)
    out = tmp_path / "approval.json"

    result = runner.invoke(
        hitl_app,
        ["approve-patch", "--proposal", str(prop_path), "--output", str(out)],
        input="zzzz\n",
    )

    assert result.exit_code == 1
    assert not out.exists()  # nothing authorized


def _rollback_plan_file(tmp_path: Path) -> tuple[Path, str]:
    plan = create_rollback_plan(
        target_name="generic",
        generic_repo=tmp_path,
        related_artifact_refs=["prop.json"],
        rollback_strategy="git_apply_reverse",
    )
    plan["patch_digest"] = "a" * 64
    plan_path = tmp_path / "rollback_plan.json"
    write_rollback_plan(plan, plan_path)
    return plan_path, canonical_json_digest(plan)


def test_approve_rollback_writes_approval_on_correct_prefix(tmp_path: Path):
    plan_path, plan_digest = _rollback_plan_file(tmp_path)
    out = tmp_path / "rollback_approval.json"

    result = runner.invoke(
        hitl_app,
        ["approve-rollback", "--rollback-plan", str(plan_path), "--output", str(out)],
        input=plan_digest[:4] + "\n",
    )

    assert result.exit_code == 0, result.output
    assert out.exists()
    assert validate_hitl_rollback_approval_file(out) == []


def test_approve_rollback_refuses_on_wrong_prefix(tmp_path: Path):
    plan_path, _ = _rollback_plan_file(tmp_path)
    out = tmp_path / "rollback_approval.json"

    result = runner.invoke(
        hitl_app,
        ["approve-rollback", "--rollback-plan", str(plan_path), "--output", str(out)],
        input="zzzz\n",
    )

    assert result.exit_code == 1
    assert not out.exists()  # nothing authorized
