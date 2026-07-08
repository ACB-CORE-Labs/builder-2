from __future__ import annotations

import hashlib
import json as json_lib
import subprocess
import time
from pathlib import Path
from typing import Any

from builder_ii.config import Settings, load_settings
from builder_ii.execution_postflight_records import (
    create_execution_postflight_record,
    write_execution_postflight_record,
)
from builder_ii.governance_standard import build_standard_governance
from builder_ii.hitl_patch_approval import (
    approval_binding_errors,
    approval_is_expired,
    canonical_json_digest,
    validate_hitl_patch_approval_file,
)
from builder_ii.hitl_patch_ledger import (
    EVENT_PATCH_APPLIED,
    EVENT_PATCH_ROLLED_BACK,
    create_hitl_patch_ledger_record,
    hitl_patch_ledger_subject_ref,
    write_hitl_patch_ledger_record,
)
from builder_ii.hitl_patch_proposal import validate_hitl_patch_proposal_file
from builder_ii.hitl_rollback_approval import (
    rollback_approval_binding_errors,
    validate_hitl_rollback_approval_file,
)
from builder_ii.rollback_artifacts import (
    ROLLBACK_PLAN_KIND,
    ROLLBACK_RECEIPT_KIND,
    create_rollback_plan,
    create_rollback_receipt,
    write_rollback_plan,
    write_rollback_receipt,
)
from builder_ii.target_profiles import TargetName, target_profile
from builder_ii.verification_execution_receipt import validate_verification_execution_receipt_file

# Constants
PATCH_APPLY_RECEIPT_KIND = "builder_ii.hitl_patch_apply_receipt"
PATCH_APPLY_RECEIPT_SCHEMA_VERSION = 1
ROLLBACK_BUNDLE_KIND = "builder_ii.rollback_bundle"
ROLLBACK_BUNDLE_SCHEMA_VERSION = 1


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


def _worktree_delta_digest(repo_path: Path) -> str:
    """Deterministic fingerprint of a repo's working-tree delta from HEAD.

    Combines ``git diff HEAD`` (tracked-file content: modifications, deletions, and staged
    additions) with ``git status --porcelain`` (which also names untracked files). It is
    computed identically at apply time (recorded on the rollback plan as
    ``post_apply_worktree_digest``) and again at rollback preflight; a mismatch means the tree
    was touched between apply and rollback, so the reverse patch can no longer be trusted to
    restore the pre-apply state.

    Honest boundary: a *content* edit to a still-untracked file the patch added is not caught
    here (its path is unchanged in porcelain). That residual case is caught by ``git apply -R``
    rejecting the mismatched reverse hunk — whose failure path also emits a recovery-bearing
    receipt. This digest is a drift *alarm*, not a replacement for git's own apply check.

    The raw subprocess bytes are hashed directly (no text decoding): a repo may hold non-UTF-8
    paths or content, and decoding could raise on a tree we have already mutated — see the
    guarded call site in ``apply_hitl_patch``.
    """
    diff = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    ).stdout
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_path,
        check=True,
        capture_output=True,
    ).stdout
    return hashlib.sha256(b"\x00".join((diff, status))).hexdigest()


def compute_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _json_digest(data: Any) -> str:
    # Delegate to the approval module so the proposal-content binding is computed with
    # one identical algorithm on both the mint (approve) and verify (apply) sides.
    return canonical_json_digest(data)


def _file_digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _artifact_ref(*, kind: str, path: Path, sha256: str, role: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "path": str(path),
        "sha256": sha256,
        "role": role,
        "required": True,
    }


def _emit_patch_ledger_record(
    *,
    output_dir: Path,
    filename: str,
    event_type: str,
    target: dict[str, Any],
    patch_digest: str,
    pre_head: str,
    ref_specs: list[tuple[str, str, Path]],
) -> None:
    """Emit the passive patch-lane ledger record, guarded against stranding.

    This runs strictly AFTER the mutation and its authoritative receipt are already durably
    written, and it re-reads caller-owned input files (proposal/approval/verification receipt)
    to fingerprint them. A failure here — an input file moved between apply and emission, a
    disk error — must never surface as an apply/rollback *failure*: the CLIs wrap the whole
    call in a blanket ``except`` and would report a successful, fully-receipted mutation as
    failed, stranding the operator. The ledger is supplementary evidence, so on failure we
    record a durable, non-authoritative note beside the receipt and return normally.
    """
    try:
        record = create_hitl_patch_ledger_record(
            event_type=event_type,
            target=target,
            patch_digest=patch_digest,
            pre_head=pre_head,
            subject_refs=[
                hitl_patch_ledger_subject_ref(role=role, kind=kind, path=path)
                for role, kind, path in ref_specs
            ],
        )
        write_hitl_patch_ledger_record(record, output_dir / filename)
    except (OSError, ValueError) as exc:
        try:
            (output_dir / f"{filename}.emission_error.txt").write_text(
                f"ledger emission failed after a successful {event_type}; the authoritative "
                f"receipt in this directory stands and the mutation completed. cause: {exc}\n",
                encoding="utf-8",
            )
        except OSError:
            pass


def _validate_core_demo_verification_receipt(data: Any, *, target_repo: Path | None) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["core demo verification receipt must be a JSON object"]
    if data.get("kind") != "builder_ii.core_demo_verification_receipt":
        errors.append("kind must be builder_ii.core_demo_verification_receipt")
    if data.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if data.get("label") != "before_apply":
        errors.append("label must be before_apply for HITL patch application")
    if data.get("receipt_status") != "EXECUTED":
        errors.append("receipt_status must be EXECUTED")

    target = data.get("target")
    if not isinstance(target, dict):
        errors.append("target must be an object")
    else:
        if target.get("name") != "core":
            errors.append("target.name must be core")
        target_path = target.get("repo")
        if not isinstance(target_path, str) or not target_path:
            errors.append("target.repo must be a non-empty string")
        elif target_repo is not None:
            try:
                if Path(target_path).expanduser().resolve() != target_repo.expanduser().resolve():
                    errors.append("target.repo must match proposal target repo")
            except OSError as exc:
                errors.append(f"target.repo could not be resolved: {exc}")

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
            errors.append("governance.model_execution must be DISABLED or NOT_AUTHORIZED")
        if governance.get("source_writes") != "DISABLED":
            errors.append("governance.source_writes must be DISABLED or NOT_AUTHORIZED")
        if governance.get("artifact_is_authority") is not False:
            errors.append("governance.artifact_is_authority must be false or NOT_AUTHORIZED")
        if governance.get("core_workbench_coupling") != "NONE":
            errors.append("governance.core_workbench_coupling must be NONE or NOT_AUTHORIZED")
    return errors


def _verification_receipt_errors(path: Path, *, target_repo: Path | None = None) -> list[str]:
    errors = validate_verification_execution_receipt_file(path)
    if not errors:
        return []
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return errors
    if isinstance(data, dict) and data.get("kind") == "builder_ii.core_demo_verification_receipt":
        return _validate_core_demo_verification_receipt(data, target_repo=target_repo)
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
        "artifact_is_authority": False,
        # Matches the platform truth matrix's current pinned state for the "HITL patch
        # application" capability (MERGED_BUT_NOT_OPERATIONAL) -- this receipt is evidence,
        # not a self-declared promotion to OPERATIONALLY_VERIFIED. Update only via the 1.7
        # flip, in lockstep with every other pinned site.
        "governance": build_standard_governance("MERGED_BUT_NOT_OPERATIONAL"),
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
    # 0. Consult the command-authority gate at the execution boundary itself, not just
    #    at the CLI. apply_hitl_patch is the write lane the matrix cites as promoted;
    #    if only the CLI enforced authority, any direct caller (demo loop, a future
    #    orchestrator, a test) would bypass the gate. Fail closed here, first — before
    #    settings resolution or any other IO.
    from builder_ii.command_authority import enforce_command_authority

    enforce_command_authority(
        "builder-hitl apply-patch",
        requested_effects=("patch_application", "artifact_write"),
        approval_ref=str(approval_path),
    )

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
    pre_head = get_git_head_sha(target_repo)

    # 3. Read and validate verification receipt
    v_errors = _verification_receipt_errors(verification_receipt_path, target_repo=target_repo)
    if v_errors:
        raise ValueError(f"Invalid verification receipt: {v_errors}")

    # 4. Validate the approval as a governed artifact — NOT merely any JSON that happens
    #    to echo a matching patch_digest. This closes the weak-approval gap: an approval
    #    only authorizes a mutation when it is a schema-valid hitl_patch_approval, bound
    #    to THIS proposal's content digest and patch digest, and not expired.
    #    Doctrine: artifact != authority. The approval is durable evidence a human
    #    engaged the boundary; only a well-formed, bound, live one authorizes.
    if not approval_path.exists():
        raise ValueError("Approval file does not exist")
    approval_errors = validate_hitl_patch_approval_file(approval_path)
    if approval_errors:
        raise ValueError(f"Invalid patch approval: {approval_errors}")
    approval = json_lib.loads(approval_path.read_text())
    binding_errors = approval_binding_errors(
        approval,
        proposal_digest=canonical_json_digest(proposal),
        patch_digest=patch_digest,
    )
    if binding_errors:
        raise ValueError(f"Approval is not bound to this proposal: {binding_errors}")
    if approval_is_expired(approval, now=int(time.time())):
        raise ValueError("Patch approval has expired")
    verification_receipt = json_lib.loads(verification_receipt_path.read_text(encoding="utf-8"))
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
    rollback_plan["patch_digest"] = patch_digest
    rollback_plan["pre_head"] = pre_head
    rollback_plan_path = output_dir / "rollback_plan.json"

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
        failure_receipt = create_patch_apply_receipt(
            settings=settings,
            target_name=target_name,
            proposal_ref=str(proposal_path),
            # rollback_plan_path is only written after a successful `git apply` (below);
            # on this failure path the file does not exist yet, so referencing it here
            # would be a dangling ref. Leave it empty like postflight_ref.
            rollback_plan_ref="",
            postflight_ref="",
            generic_repo=target_repo if target_name == "generic" else None,
        )
        failure_receipt["target"] = dict(proposal["target"])
        failure_receipt["status"] = "failed"
        failure_receipt["error_summary"] = (e.stderr or str(e))[:500]
        failure_receipt["patch_digest"] = patch_digest
        failure_receipt["pre_head"] = pre_head
        write_patch_apply_receipt(failure_receipt, output_dir / "patch_apply_failure_receipt.json")
        raise RuntimeError(f"Patch application failed: {e.stderr}")

    reverse_diff_path.write_text(unified_diff, encoding="utf-8")
    reverse_digest = _file_digest(reverse_diff_path)
    # Fingerprint the working tree the moment the patch is applied. The rollback lane
    # re-derives this digest at preflight and refuses (with a recovery block) if the tree
    # drifted in between -- so `git apply -R` never runs against a tree it can no longer
    # faithfully reverse. See _worktree_delta_digest and rollback_hitl_patch.
    #
    # This runs AFTER the mutating `git apply` succeeded, so a failure here would otherwise
    # strand a mutated tree with no receipt. Guard it: on failure, emit an apply-failure
    # receipt carrying pre_head for recovery, mirroring the git-apply except above.
    try:
        post_apply_worktree_digest = _worktree_delta_digest(target_repo)
    except (subprocess.SubprocessError, OSError) as exc:
        failure_receipt = create_patch_apply_receipt(
            settings=settings,
            target_name=target_name,
            proposal_ref=str(proposal_path),
            rollback_plan_ref="",
            postflight_ref="",
            generic_repo=target_repo if target_name == "generic" else None,
        )
        failure_receipt["target"] = dict(proposal["target"])
        failure_receipt["status"] = "failed"
        failure_receipt["error_summary"] = f"post-apply fingerprint failed after mutation: {exc}"[:500]
        failure_receipt["patch_digest"] = patch_digest
        failure_receipt["pre_head"] = pre_head
        write_patch_apply_receipt(failure_receipt, output_dir / "patch_apply_failure_receipt.json")
        raise RuntimeError(
            f"Post-apply fingerprint failed; the tree is mutated. Recover with "
            f"`git reset --hard {pre_head}` (discards uncommitted changes). Cause: {exc}"
        )
    rollback_plan["rollback_patch_apply_mode"] = "git_apply_reverse_flag"
    rollback_plan["rollback_patch_ref"] = _artifact_ref(
        kind="unified_diff_reverse_patch",
        path=reverse_diff_path,
        sha256=reverse_digest,
        role="rollback_reverse_patch",
    )
    rollback_plan["post_apply_worktree_digest"] = post_apply_worktree_digest
    write_rollback_plan(rollback_plan, rollback_plan_path)

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
    # Honest platform-matrix state for "HITL patch application" (MERGED_BUT_NOT_OPERATIONAL),
    # not a self-declared OPERATIONALLY_VERIFIED promotion -- see 1.7 for the evidence-gated flip.
    postflight["governance"]["capability_state"] = "MERGED_BUT_NOT_OPERATIONAL"
    postflight_path = output_dir / "postflight_record.json"
    write_execution_postflight_record(postflight, postflight_path)
    postflight_digest = _file_digest(postflight_path)

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
    receipt["status"] = "succeeded"
    receipt["patch_digest"] = patch_digest
    receipt["pre_head"] = pre_head
    receipt["proposal_digest"] = _json_digest(proposal)
    receipt["approval_digest"] = _json_digest(approval)
    receipt["verification_receipt_digest"] = _json_digest(verification_receipt)
    receipt["postflight_digest"] = postflight_digest
    receipt["rollback_patch_ref"] = rollback_plan["rollback_patch_ref"]
    receipt["post_apply_worktree_digest"] = post_apply_worktree_digest
    receipt_path = output_dir / "patch_apply_receipt.json"
    write_patch_apply_receipt(receipt, receipt_path)

    bundle = {
        "kind": ROLLBACK_BUNDLE_KIND,
        "schema_version": ROLLBACK_BUNDLE_SCHEMA_VERSION,
        "target": dict(proposal["target"]),
        "patch_digest": patch_digest,
        "pre_head": pre_head,
        "proposal_ref": _artifact_ref(
            kind=proposal.get("kind", "builder_ii.hitl_patch_proposal"),
            path=proposal_path,
            sha256=_json_digest(proposal),
            role="patch_proposal",
        ),
        "approval_ref": _artifact_ref(
            kind=approval.get("kind", "builder_ii.approval_record"),
            path=approval_path,
            sha256=_json_digest(approval),
            role="patch_approval",
        ),
        "verification_receipt_ref": _artifact_ref(
            kind=verification_receipt.get("kind", "builder_ii.verification_execution_receipt"),
            path=verification_receipt_path,
            sha256=_json_digest(verification_receipt),
            role="pre_apply_verification_receipt",
        ),
        "rollback_plan_ref": _artifact_ref(
            kind=ROLLBACK_PLAN_KIND,
            path=rollback_plan_path,
            sha256=_file_digest(rollback_plan_path),
            role="rollback_plan",
        ),
        "rollback_patch_ref": rollback_plan["rollback_patch_ref"],
        "postflight_ref": _artifact_ref(
            kind="builder_ii.execution_postflight_record",
            path=postflight_path,
            sha256=postflight_digest,
            role="patch_apply_postflight",
        ),
        "patch_apply_receipt_ref": _artifact_ref(
            kind=PATCH_APPLY_RECEIPT_KIND,
            path=receipt_path,
            sha256=_file_digest(receipt_path),
            role="patch_apply_receipt",
        ),
        "governance": {
            # MUTATION_WITH_ROLLBACK_VERIFIED is a derived *assurance_state* value
            # (builder_ii/assurance.py) that only applies once the underlying matrix row is
            # OPERATIONALLY_VERIFIED (builder_ii/platform_completion_audit.py:assurance_state_for_row).
            # Today that row is MERGED_BUT_NOT_OPERATIONAL, so self-stamping the post-flip value
            # here would be a truth-matrix bypass. Mirror the matrix's actual pinned state instead.
            "capability_state": "MERGED_BUT_NOT_OPERATIONAL",
            "artifact_is_authority": False,
            "core_workbench_coupling": "NONE",
        },
    }
    write_rollback_bundle(bundle, output_dir / "rollback_bundle.json")

    # 9. Emit a passive ledger record for this apply event, binding the governing chain's
    #    on-disk digests. Written to the builder-side output_dir (never the target repo,
    #    which would dirty the tree and corrupt the post-apply drift fingerprint). Strictly
    #    after the mutation and its receipt: the ledger is evidence the event happened, not
    #    authority for it. Guarded so an emission failure never reports the successful apply
    #    as a failure (see _emit_patch_ledger_record).
    _emit_patch_ledger_record(
        output_dir=output_dir,
        filename="patch_ledger_record.json",
        event_type=EVENT_PATCH_APPLIED,
        target=dict(proposal["target"]),
        patch_digest=patch_digest,
        pre_head=pre_head,
        ref_specs=[
            ("patch_proposal", proposal.get("kind", "builder_ii.hitl_patch_proposal"), proposal_path),
            ("patch_approval", approval.get("kind", "builder_ii.hitl_patch_approval"), approval_path),
            (
                "pre_apply_verification_receipt",
                verification_receipt.get("kind", "builder_ii.verification_execution_receipt"),
                verification_receipt_path,
            ),
            ("patch_apply_receipt", PATCH_APPLY_RECEIPT_KIND, receipt_path),
            ("rollback_plan", ROLLBACK_PLAN_KIND, rollback_plan_path),
        ],
    )


def validate_patch_apply_receipt(artifact: Any) -> list[str]:
    errors = []
    if not isinstance(artifact, dict):
        return ["receipt must be a dict"]
    if artifact.get("kind") != PATCH_APPLY_RECEIPT_KIND:
        errors.append(f"kind must be {PATCH_APPLY_RECEIPT_KIND}")
    if artifact.get("schema_version") != PATCH_APPLY_RECEIPT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PATCH_APPLY_RECEIPT_SCHEMA_VERSION}")
    if artifact.get("status") not in (None, "succeeded", "failed"):
        errors.append("status must be succeeded or failed")
    if "patch_digest" in artifact and (
        not isinstance(artifact["patch_digest"], str) or len(artifact["patch_digest"]) != 64
    ):
        errors.append("patch_digest must be a SHA-256 hex digest")
    return errors


def validate_patch_apply_receipt_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid json: {exc}"]
    return validate_patch_apply_receipt(data)


def _rollback_recovery_block(*, pre_head: Any, reason: str) -> dict[str, Any]:
    """Build the recovery block attached to a rollback-failure receipt.

    A failed rollback must *instruct*, never strand. The block names the exact command that
    restores the pre-apply state, warns about its data-loss cost, and records that the
    apply->rollback chain is now invalid (so no downstream reader mistakes the tree for cleanly
    rolled back). ``pre_head`` is the HEAD SHA captured at apply time (plan item 1.2b) and
    carried on the rollback plan; if it is absent we degrade to a reflog-based instruction
    rather than emit a command with no target.
    """
    if isinstance(pre_head, str) and pre_head:
        recommended_command = f"git reset --hard {pre_head}"
        pre_apply_head = pre_head
    else:
        recommended_command = "git reflog  # find the pre-apply commit, then: git reset --hard <sha>"
        pre_apply_head = ""
    return {
        "reason": reason,
        "pre_apply_head": pre_apply_head,
        "recommended_command": recommended_command,
        "data_loss_warning": (
            "This command discards ALL uncommitted changes in the target working tree, "
            "including any work done since the patch was applied. Run 'git status' and back "
            "up anything you want to keep before running it."
        ),
        "chain_invalidation": {
            "invalidated": True,
            "note": (
                "The apply->rollback chain is broken: the working tree no longer matches the "
                "post-apply state this rollback plan was minted for. Any receipt claiming a "
                "clean rollback from here would be false."
            ),
        },
    }


def _write_rollback_failure_receipt(
    *,
    settings: Settings,
    target: dict[str, Any],
    rollback_plan_ref: str,
    output_dir: Path,
    outcome: str,
    reason: str,
    pre_head: Any,
    error_summary: str,
) -> Path:
    """Emit a rollback-failure receipt with a recovery block.

    The receipt stays a schema-valid ``builder_ii.rollback_receipt`` in the NOT_EXECUTED state
    (honest: no reverse patch was applied); ``rollback_outcome``, ``error_summary``, and
    ``recovery`` are informal extension fields, mirroring the apply-failure receipt pattern.
    """
    target_name = target.get("name", "generic")
    failure_receipt = create_rollback_receipt(
        settings=settings,
        target_name=target_name,
        rollback_plan_ref=rollback_plan_ref,
        generic_repo=Path(target["repo"]) if target_name == "generic" else None,
    )
    failure_receipt["target"] = dict(target)
    failure_receipt["rollback_outcome"] = outcome
    failure_receipt["error_summary"] = error_summary[:500]
    failure_receipt["recovery"] = _rollback_recovery_block(pre_head=pre_head, reason=reason)
    path = output_dir / "rollback_failure_receipt.json"
    write_rollback_receipt(failure_receipt, path)
    return path


def _rollback_drift_reason(repo_path: Path, *, pre_head: Any, expected_delta: Any) -> str | None:
    """Return a human reason string if the tree drifted since apply, else None.

    Refusing here -- before any ``git apply -R`` -- turns a confusing partial/failed reverse
    into a clean, instructive refusal. Two checks: HEAD must not have moved (a commit since
    apply rebases the reverse patch onto the wrong base), and the working-tree delta digest
    must still match the one recorded at apply time. The caller (``rollback_hitl_patch``)
    guarantees both ``pre_head`` and ``expected_delta`` are present before calling; the
    ``isinstance`` guards below are defensive only.
    """
    if isinstance(pre_head, str) and pre_head:
        current_head = get_git_head_sha(repo_path)
        if current_head != pre_head:
            return f"HEAD moved since apply (expected {pre_head[:12]}, found {current_head[:12]})"
    if isinstance(expected_delta, str) and expected_delta:
        if _worktree_delta_digest(repo_path) != expected_delta:
            return "working tree changed since apply (post-apply fingerprint mismatch)"
    return None


def rollback_hitl_patch(
    rollback_plan_path: Path,
    reverse_patch_path: Path,
    output_dir: Path,
    *,
    approval_path: Path,
    settings: Settings | None = None,
) -> None:
    # Gate the rollback write lane at the execution boundary too (see apply_hitl_patch);
    # fail closed before settings resolution or any other IO.
    from builder_ii.command_authority import enforce_command_authority

    enforce_command_authority(
        "builder-hitl rollback",
        requested_effects=("patch_application",),
        approval_ref=str(approval_path),
    )

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

    # 1. Authority: a rollback is itself a source mutation. It requires its own governed
    #    approval bound to THIS plan -- not merely the machine-generated plan existing (which
    #    apply_hitl_patch wrote automatically). artifact != authority; planned != approved.
    if not approval_path.exists():
        raise ValueError("Rollback approval file does not exist")
    approval_errors = validate_hitl_rollback_approval_file(approval_path)
    if approval_errors:
        raise ValueError(f"Invalid rollback approval: {approval_errors}")
    approval = json_lib.loads(approval_path.read_text())
    binding_errors = rollback_approval_binding_errors(
        approval,
        rollback_plan_digest=canonical_json_digest(plan),
        patch_digest=str(plan.get("patch_digest", "")),
    )
    if binding_errors:
        raise ValueError(f"Rollback approval is not bound to this plan: {binding_errors}")
    if approval_is_expired(approval, now=int(time.time())):
        raise ValueError("Rollback approval has expired")

    # 2. Input integrity: the reverse patch must be exactly the one this plan bound.
    rollback_ref = plan.get("rollback_patch_ref")
    if isinstance(rollback_ref, dict):
        expected_digest = rollback_ref.get("sha256")
        if expected_digest and _file_digest(reverse_patch_path) != expected_digest:
            raise ValueError("Reverse patch digest does not match rollback plan binding")

    # 3. Drift-verifiability precondition (fail closed). The drift preflight below is an
    #    INVARIANT of this lane, not a best-effort default: a plan that reached the execution
    #    boundary without both drift-protection fields cannot be checked against the post-apply
    #    tree, so we refuse rather than silently skip the check and run `git apply -R` blind.
    #    apply_hitl_patch always records both fields; a plan lacking them did not come from a
    #    governed apply and must not authorize a mutation.
    pre_head = plan.get("pre_head")
    expected_delta = plan.get("post_apply_worktree_digest")
    if not (isinstance(pre_head, str) and pre_head):
        raise ValueError("Rollback plan is missing pre_head; cannot verify the tree before rollback")
    if not (isinstance(expected_delta, str) and expected_delta):
        raise ValueError(
            "Rollback plan is missing post_apply_worktree_digest; cannot drift-check the tree before rollback"
        )

    # 4. Drift preflight: refuse (with a recovery block) rather than run `git apply -R` against
    #    a tree that no longer matches the post-apply state this plan was minted for. Failure
    #    must instruct, never strand.
    drift_reason = _rollback_drift_reason(
        target_repo,
        pre_head=pre_head,
        expected_delta=expected_delta,
    )
    if drift_reason is not None:
        _write_rollback_failure_receipt(
            settings=settings,
            target=plan["target"],
            rollback_plan_ref=str(rollback_plan_path),
            output_dir=output_dir,
            outcome="REFUSED_TREE_DRIFT",
            reason="working_tree_drift_since_apply",
            pre_head=pre_head,
            error_summary=drift_reason,
        )
        raise RuntimeError(
            f"Rollback refused: {drift_reason}. A recovery block was written to "
            f"{output_dir / 'rollback_failure_receipt.json'}."
        )

    before_status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=target_repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.splitlines()

    try:
        command = (
            ["git", "apply", "-R", str(reverse_patch_path)]
            if plan.get("rollback_patch_apply_mode") == "git_apply_reverse_flag"
            else ["git", "apply", str(reverse_patch_path)]
        )
        subprocess.run(
            command,
            cwd=target_repo,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        # The reverse patch itself did not apply cleanly (the residual case the fingerprint
        # alarm cannot see). Emit the same recovery-bearing failure receipt so the operator is
        # never stranded without a restore command.
        _write_rollback_failure_receipt(
            settings=settings,
            target=plan["target"],
            rollback_plan_ref=str(rollback_plan_path),
            output_dir=output_dir,
            outcome="REVERSE_PATCH_FAILED",
            reason="reverse_patch_apply_failed",
            pre_head=pre_head,
            error_summary=(e.stderr or str(e)),
        )
        raise RuntimeError(f"Rollback application failed: {e.stderr}")

    receipt = create_rollback_receipt(
        settings=settings,
        target_name=target_name,
        rollback_plan_ref=str(rollback_plan_path),
        generic_repo=target_repo if target_name == "generic" else None,
    )
    receipt["target"] = dict(plan["target"])
    # Bind the approval that authorized this rollback into the receipt as durable evidence,
    # mirroring the apply receipt's approval_digest. artifact != authority, but the receipt
    # records which approval stood for the human decision.
    receipt["rollback_approval_digest"] = _json_digest(approval)
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
    receipt["rollback_patch_ref"] = _artifact_ref(
        kind="unified_diff_reverse_patch",
        path=reverse_patch_path,
        sha256=_file_digest(reverse_patch_path),
        role="rollback_reverse_patch",
    )

    receipt_path = output_dir / "rollback_receipt.json"
    write_rollback_receipt(receipt, receipt_path)

    # Emit a passive ledger record for this rollback event, binding the governing chain
    # (plan, rollback approval, reverse patch, rollback receipt). Same guarded posture as the
    # apply side: builder-side output_dir only, strictly after the mutation and its receipt.
    _emit_patch_ledger_record(
        output_dir=output_dir,
        filename="rollback_ledger_record.json",
        event_type=EVENT_PATCH_ROLLED_BACK,
        target=dict(plan["target"]),
        patch_digest=str(plan.get("patch_digest", "")),
        pre_head=str(pre_head),
        ref_specs=[
            ("rollback_plan", plan.get("kind", ROLLBACK_PLAN_KIND), rollback_plan_path),
            ("rollback_approval", approval.get("kind", "builder_ii.hitl_rollback_approval"), approval_path),
            ("rollback_reverse_patch", "unified_diff_reverse_patch", reverse_patch_path),
            ("rollback_receipt", ROLLBACK_RECEIPT_KIND, receipt_path),
        ],
    )


def dumps_rollback_bundle(bundle: dict[str, Any]) -> str:
    return json_lib.dumps(bundle, indent=2, sort_keys=True) + "\n"


def write_rollback_bundle(bundle: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(dumps_rollback_bundle(bundle), encoding="utf-8")


def validate_rollback_bundle(bundle: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(bundle, dict):
        return ["rollback bundle must be a JSON object"]
    if bundle.get("kind") != ROLLBACK_BUNDLE_KIND:
        errors.append(f"kind must be {ROLLBACK_BUNDLE_KIND}")
    if bundle.get("schema_version") != ROLLBACK_BUNDLE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {ROLLBACK_BUNDLE_SCHEMA_VERSION}")
    for field in (
        "proposal_ref",
        "approval_ref",
        "verification_receipt_ref",
        "rollback_plan_ref",
        "rollback_patch_ref",
        "postflight_ref",
        "patch_apply_receipt_ref",
    ):
        ref = bundle.get(field)
        if not isinstance(ref, dict):
            errors.append(f"{field} must be an object")
            continue
        sha = ref.get("sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            errors.append(f"{field}.sha256 must be a SHA-256 hex digest")
    return errors


def validate_rollback_bundle_file(path: Path) -> list[str]:
    if not path.exists():
        return [f"file not found: {path}"]
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"invalid json: {exc}"]
    return validate_rollback_bundle(data)
