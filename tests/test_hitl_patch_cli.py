import hashlib
import json
from pathlib import Path
from unittest.mock import patch

from hitl_patch_lane_helpers import PATCH_DIFF, init_target_repo, real_verification_receipt
from typer.testing import CliRunner

from builder_ii.cli.hitl_execution_cli import hitl_app
from builder_ii.governance.authority import CommandAuthorityError
from builder_ii.governance.hitl.hitl_patch_apply import apply_hitl_patch
from builder_ii.governance.hitl.hitl_patch_approval import (
    create_hitl_patch_approval,
    validate_hitl_patch_approval_file,
    write_hitl_patch_approval,
)
from builder_ii.governance.hitl.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal
from builder_ii.governance.hitl.hitl_rollback_approval import (
    canonical_digest,
    create_hitl_rollback_approval,
    validate_hitl_rollback_approval_file,
    write_hitl_rollback_approval,
)
from builder_ii.lifecycle.candidate.rollback_artifacts import create_rollback_plan, write_rollback_plan

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
    return plan_path, canonical_digest(plan)


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


# ---------------------------------------------------------------------------
# CLI-level denial tests (plan item 1.6): prove the mutation commands fail closed
# at the CLI surface — a denial is a nonzero exit with NO mutation and NO receipt.
# ---------------------------------------------------------------------------


@patch("builder_ii.command_authority.enforce_command_authority", side_effect=CommandAuthorityError("denied"))
def test_apply_patch_cli_denied_by_command_authority_gate(_gate, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        hitl_app,
        [
            "apply-patch",
            "--proposal",
            str(tmp_path / "p.json"),
            "--approval",
            str(tmp_path / "a.json"),
            "--verification-receipt",
            str(tmp_path / "vr.json"),
            "--output-dir",
            str(out),
        ],
    )
    assert result.exit_code != 0
    assert not out.exists()  # gate refused before any IO


@patch("builder_ii.command_authority.enforce_command_authority", side_effect=CommandAuthorityError("denied"))
def test_rollback_cli_denied_by_command_authority_gate(_gate, tmp_path: Path) -> None:
    out = tmp_path / "out"
    result = runner.invoke(
        hitl_app,
        [
            "rollback",
            "--rollback-plan",
            str(tmp_path / "plan.json"),
            "--reverse-patch",
            str(tmp_path / "rev.patch"),
            "--approval",
            str(tmp_path / "a.json"),
            "--output-dir",
            str(out),
        ],
    )
    assert result.exit_code != 0
    assert not out.exists()


def test_apply_patch_cli_denies_forged_approval_without_mutation(tmp_path: Path) -> None:
    """A bare JSON echoing the patch digest must NOT authorize a mutation at the CLI —
    exit 1, the target tree is untouched, and no apply receipt is written."""
    repo = init_target_repo(tmp_path)
    patch_digest = hashlib.sha256(PATCH_DIFF.encode("utf-8")).hexdigest()
    prop_path = tmp_path / "prop.json"
    write_hitl_patch_proposal(
        create_hitl_patch_proposal(generic_repo=repo, patch_digest=patch_digest, unified_diff=PATCH_DIFF),
        prop_path,
    )
    vr_path = real_verification_receipt(tmp_path)

    forged = tmp_path / "forged_approval.json"
    forged.write_text(json.dumps({"patch_digest": patch_digest}))  # not a governed approval

    out = tmp_path / "out"
    result = runner.invoke(
        hitl_app,
        [
            "apply-patch",
            "--proposal",
            str(prop_path),
            "--approval",
            str(forged),
            "--verification-receipt",
            str(vr_path),
            "--output-dir",
            str(out),
        ],
    )
    assert result.exit_code == 1
    assert (repo / "file.txt").read_text() == "Line 1\nLine 2\n"  # unchanged
    assert not (out / "patch_apply_receipt.json").exists()


def test_rollback_cli_denies_unbound_approval_without_reverting(tmp_path: Path) -> None:
    """After a real apply, a rollback approval bound to a *different* plan must not
    authorize the reverse — exit 1, and the applied change stays in place."""
    repo = init_target_repo(tmp_path)
    patch_digest = hashlib.sha256(PATCH_DIFF.encode("utf-8")).hexdigest()
    proposal = create_hitl_patch_proposal(generic_repo=repo, patch_digest=patch_digest, unified_diff=PATCH_DIFF)
    prop_path = tmp_path / "prop.json"
    write_hitl_patch_proposal(proposal, prop_path)
    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(
        create_hitl_patch_approval(proposal, confirmed_digest_prefix=patch_digest[:4]), approval_path
    )
    vr_path = real_verification_receipt(tmp_path)
    out = tmp_path / "out"
    apply_hitl_patch(prop_path, approval_path, vr_path, out)
    assert (repo / "file.txt").read_text() == "Line 1\nLine 2 modified\n"

    # Mint a rollback approval bound to a tampered plan (different pre_head).
    plan = json.loads((out / "rollback_plan.json").read_text())
    tampered = dict(plan)
    tampered["pre_head"] = "0" * 40
    unbound_approval = tmp_path / "rollback_approval.json"
    write_hitl_rollback_approval(
        create_hitl_rollback_approval(tampered, confirmed_digest_prefix=canonical_digest(tampered)[:4]),
        unbound_approval,
    )

    rollback_out = out / "rollback_out"
    result = runner.invoke(
        hitl_app,
        [
            "rollback",
            "--rollback-plan",
            str(out / "rollback_plan.json"),
            "--reverse-patch",
            str(out / "rollback.patch"),
            "--approval",
            str(unbound_approval),
            "--output-dir",
            str(rollback_out),
        ],
    )
    assert result.exit_code == 1
    assert (repo / "file.txt").read_text() == "Line 1\nLine 2 modified\n"  # not reverted
    assert not (rollback_out / "rollback_receipt.json").exists()
