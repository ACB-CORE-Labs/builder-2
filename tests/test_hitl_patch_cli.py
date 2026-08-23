import hashlib
import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from hitl_patch_lane_helpers import PATCH_DIFF, init_target_repo, real_verification_receipt
from typer.testing import CliRunner

from builder_ii.cli.hitl_execution_cli import hitl_app
from builder_ii.governance.authority import CommandAuthorityError
from builder_ii.governance.hitl.hitl_patch_apply import FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME, apply_hitl_patch
from builder_ii.governance.hitl.hitl_patch_approval import (
    create_hitl_patch_approval,
    validate_hitl_patch_approval_file,
    write_hitl_patch_approval,
)
from builder_ii.governance.hitl.hitl_patch_proposal import (
    MAX_CANONICAL_UNIFIED_DIFF_BYTES,
    create_hitl_patch_proposal,
    write_hitl_patch_proposal,
)
from builder_ii.governance.hitl.hitl_rollback_approval import (
    canonical_digest,
    create_hitl_rollback_approval,
    validate_hitl_rollback_approval_file,
    write_hitl_rollback_approval,
)
from builder_ii.lifecycle.candidate.rollback_artifacts import create_rollback_plan, write_rollback_plan

runner = CliRunner()


def _valid_diff_with_size(size: int) -> str:
    prefix = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+"
    suffix = "\n"
    filler_bytes = size - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
    assert filler_bytes >= 1
    diff = prefix + ("n" * filler_bytes) + suffix
    assert len(diff.encode("utf-8")) == size
    return diff


def _large_applicable_diff(size: int) -> str:
    prefix = "--- a/file.txt\n+++ b/file.txt\n@@ -1,2 +1,2 @@\n Line 1\n-Line 2\n+Line 2 "
    suffix = "\n"
    filler_bytes = size - len(prefix.encode("utf-8")) - len(suffix.encode("utf-8"))
    assert filler_bytes >= 1
    diff = prefix + ("n" * filler_bytes) + suffix
    assert len(diff.encode("utf-8")) == size
    return diff


def test_propose_patch_cli_uses_canonical_exact_binding(tmp_path: Path) -> None:
    diff_file = tmp_path / "change.diff"
    diff_file.write_text("--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new\n", encoding="utf-8")
    verification_receipt = tmp_path / "verification.json"
    verification_receipt.write_bytes(b'{"exact":"bytes"}\r\n')
    output = tmp_path / "proposal.json"

    result = runner.invoke(
        hitl_app,
        [
            "propose-patch",
            "--diff-file",
            str(diff_file),
            "--output",
            str(output),
            "--description",
            "change one line",
            "--reason",
            "qualification",
            "--target-head-sha",
            "a" * 40,
            "--verification-receipt",
            str(verification_receipt),
            "--target-repo",
            str(tmp_path),
        ],
    )

    assert result.exit_code == 0, result.output
    proposal = json.loads(output.read_text(encoding="utf-8"))
    assert proposal["patch_digest"] == hashlib.sha256(diff_file.read_bytes()).hexdigest()
    assert proposal["verification_receipt_file_sha256"] == hashlib.sha256(
        verification_receipt.read_bytes()
    ).hexdigest()
    assert proposal["exact_scope"]["files"] == [{"old_path": "file.txt", "new_path": "file.txt"}]


def test_operator_cli_admits_90_kib_and_exact_128_kib_but_refuses_one_byte_more(tmp_path: Path) -> None:
    verification_receipt = tmp_path / "verification.json"
    verification_receipt.write_bytes(b'{"exact":"bytes"}\n')

    proposals: list[dict[str, object]] = []
    for size in (90 * 1024, MAX_CANONICAL_UNIFIED_DIFF_BYTES):
        diff_file = tmp_path / f"change-{size}.diff"
        diff_file.write_text(_valid_diff_with_size(size), encoding="utf-8")
        output = tmp_path / f"proposal-{size}.json"
        result = runner.invoke(
            hitl_app,
            [
                "propose-patch",
                "--diff-file",
                str(diff_file),
                "--output",
                str(output),
                "--description",
                "qualify bounded operator envelope",
                "--reason",
                "boundary qualification",
                "--target-head-sha",
                "a" * 40,
                "--verification-receipt",
                str(verification_receipt),
                "--target-repo",
                str(tmp_path),
            ],
        )
        assert result.exit_code == 0, result.output
        proposal = json.loads(output.read_text(encoding="utf-8"))
        assert proposal["patch_digest"] == hashlib.sha256(diff_file.read_bytes()).hexdigest()
        assert proposal["exact_scope"]["files"] == [{"old_path": "file.txt", "new_path": "file.txt"}]
        proposals.append(proposal)

    mutated = str(proposals[0]["unified_diff"]).replace("n", "m", 1)
    assert hashlib.sha256(mutated.encode("utf-8")).hexdigest() != proposals[0]["patch_digest"]

    oversized_diff = tmp_path / "change-oversized.diff"
    oversized_diff.write_text(_valid_diff_with_size(MAX_CANONICAL_UNIFIED_DIFF_BYTES + 1), encoding="utf-8")
    oversized_output = tmp_path / "proposal-oversized.json"
    result = runner.invoke(
        hitl_app,
        [
            "propose-patch",
            "--diff-file",
            str(oversized_diff),
            "--output",
            str(oversized_output),
            "--description",
            "refuse oversized operator input",
            "--reason",
            "boundary qualification",
            "--target-head-sha",
            "a" * 40,
            "--verification-receipt",
            str(verification_receipt),
            "--target-repo",
            str(tmp_path),
        ],
    )
    assert result.exit_code == 1
    assert f"exceeds the {MAX_CANONICAL_UNIFIED_DIFF_BYTES}-byte limit" in result.output
    assert not oversized_output.exists()


def _proposal_file(tmp_path: Path) -> tuple[Path, str]:
    diff = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-a\n+b\n"
    digest = hashlib.sha256(diff.encode("utf-8")).hexdigest()
    prop_path = tmp_path / "prop.json"
    write_hitl_patch_proposal(
        create_hitl_patch_proposal(generic_repo=tmp_path, patch_digest=digest, unified_diff=diff,
                                   target_head_sha="0" * 40, verification_receipt_file_sha256="0" * 64),
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


def test_large_operator_proposal_preserves_approval_apply_and_rollback_bindings(tmp_path: Path) -> None:
    repo = init_target_repo(tmp_path)
    original_bytes = (repo / "file.txt").read_bytes()
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    verification_receipt = real_verification_receipt(tmp_path, repo)
    diff_file = tmp_path / "large-change.diff"
    large_diff = _large_applicable_diff(90 * 1024)
    diff_file.write_text(large_diff, encoding="utf-8")
    proposal_path = tmp_path / "large-proposal.json"

    propose = runner.invoke(
        hitl_app,
        [
            "propose-patch",
            "--diff-file",
            str(diff_file),
            "--output",
            str(proposal_path),
            "--description",
            "qualify large operator patch lifecycle",
            "--reason",
            "bounded envelope qualification",
            "--target-head-sha",
            head,
            "--verification-receipt",
            str(verification_receipt),
            "--target-repo",
            str(repo),
        ],
    )
    assert propose.exit_code == 0, propose.output
    proposal = json.loads(proposal_path.read_text(encoding="utf-8"))
    patch_digest = hashlib.sha256(diff_file.read_bytes()).hexdigest()
    assert proposal["patch_digest"] == patch_digest
    assert proposal["exact_scope"]["files"] == [{"old_path": "file.txt", "new_path": "file.txt"}]

    approval_path = tmp_path / "large-approval.json"
    approve = runner.invoke(
        hitl_app,
        ["approve-patch", "--proposal", str(proposal_path), "--output", str(approval_path)],
        input=patch_digest[:4] + "\n",
    )
    assert approve.exit_code == 0, approve.output
    assert validate_hitl_patch_approval_file(approval_path) == []

    substituted_receipt = tmp_path / "substituted-verification-receipt.json"
    substituted_receipt.write_bytes(verification_receipt.read_bytes() + b"\n")
    substitution_output = tmp_path / "substitution-refusal"
    substitution_result = runner.invoke(
        hitl_app,
        [
            "apply-patch",
            "--proposal",
            str(proposal_path),
            "--approval",
            str(approval_path),
            "--verification-receipt",
            str(substituted_receipt),
            "--output-dir",
            str(substitution_output),
        ],
    )
    assert substitution_result.exit_code == 1
    assert "verification_receipt_file_sha256 does not match" in substitution_result.output
    assert "the supplied receipt" in substitution_result.output
    assert (repo / "file.txt").read_bytes() == original_bytes
    assert not (substitution_output / "patch_apply_receipt.json").exists()

    apply_output = tmp_path / "large-apply"
    apply_result = runner.invoke(
        hitl_app,
        [
            "apply-patch",
            "--proposal",
            str(proposal_path),
            "--approval",
            str(approval_path),
            "--verification-receipt",
            str(verification_receipt),
            "--output-dir",
            str(apply_output),
        ],
    )
    assert apply_result.exit_code == 0, apply_result.output
    assert (repo / "file.txt").read_text(encoding="utf-8").startswith("Line 1\nLine 2 nnnn")
    stored_patch = apply_output / FORWARD_PATCH_FOR_REVERSE_APPLY_FILENAME
    assert stored_patch.read_bytes() == diff_file.read_bytes()
    apply_receipt = json.loads((apply_output / "patch_apply_receipt.json").read_text(encoding="utf-8"))
    assert apply_receipt["patch_digest"] == patch_digest
    assert apply_receipt["post_apply_path_digests"]["file.txt"] == hashlib.sha256(
        (repo / "file.txt").read_bytes()
    ).hexdigest()

    rollback_plan_path = apply_output / "rollback_plan.json"
    rollback_plan = json.loads(rollback_plan_path.read_text(encoding="utf-8"))
    rollback_approval_path = tmp_path / "large-rollback-approval.json"
    approve_rollback = runner.invoke(
        hitl_app,
        [
            "approve-rollback",
            "--rollback-plan",
            str(rollback_plan_path),
            "--output",
            str(rollback_approval_path),
        ],
        input=canonical_digest(rollback_plan)[:4] + "\n",
    )
    assert approve_rollback.exit_code == 0, approve_rollback.output

    rollback_output = apply_output / "rollback-output"
    rollback_result = runner.invoke(
        hitl_app,
        [
            "rollback",
            "--rollback-plan",
            str(rollback_plan_path),
            "--reverse-patch",
            str(stored_patch),
            "--approval",
            str(rollback_approval_path),
            "--output-dir",
            str(rollback_output),
        ],
    )
    assert rollback_result.exit_code == 0, rollback_result.output
    assert (repo / "file.txt").read_bytes() == original_bytes
    assert subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout == ""
    rollback_receipt = json.loads((rollback_output / "rollback_receipt.json").read_text(encoding="utf-8"))
    assert rollback_receipt["rollback_equivalence_verified"] is True

    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "head drift"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    drift_output = tmp_path / "head-drift-refusal"
    drift_result = runner.invoke(
        hitl_app,
        [
            "apply-patch",
            "--proposal",
            str(proposal_path),
            "--approval",
            str(approval_path),
            "--verification-receipt",
            str(verification_receipt),
            "--output-dir",
            str(drift_output),
        ],
    )
    assert drift_result.exit_code == 1
    assert "target_head_sha does not match current target" in drift_result.output
    assert "HEAD" in drift_result.output
    assert (repo / "file.txt").read_bytes() == original_bytes
    assert not (drift_output / "patch_apply_receipt.json").exists()


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
    vr_path = real_verification_receipt(tmp_path, repo)

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
    vr_path = real_verification_receipt(tmp_path, repo)
    proposal = create_hitl_patch_proposal(generic_repo=repo, patch_digest=patch_digest, unified_diff=PATCH_DIFF,
        target_head_sha=subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip(),
        verification_receipt_file_sha256=hashlib.sha256(vr_path.read_bytes()).hexdigest())
    prop_path = tmp_path / "prop.json"
    write_hitl_patch_proposal(proposal, prop_path)
    approval_path = tmp_path / "approval.json"
    write_hitl_patch_approval(
        create_hitl_patch_approval(proposal, confirmed_digest_prefix=patch_digest[:4]), approval_path
    )
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
