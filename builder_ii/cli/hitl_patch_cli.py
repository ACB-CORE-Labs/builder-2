import hashlib
import json
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.governance.hitl.hitl_patch_apply import apply_hitl_patch, rollback_hitl_patch
from builder_ii.governance.hitl.hitl_patch_approval import (
    APPROVAL_CONFIRMATION_PREFIX_LENGTH,
    DEFAULT_APPROVAL_TTL_SECONDS,
    create_hitl_patch_approval,
    write_hitl_patch_approval,
)
from builder_ii.governance.hitl.hitl_patch_proposal import (
    create_hitl_patch_proposal,
    validate_hitl_patch_proposal_file,
    write_hitl_patch_proposal,
)
from builder_ii.governance.hitl.hitl_rollback_approval import (
    canonical_digest,
    create_hitl_rollback_approval,
    write_hitl_rollback_approval,
)
from builder_ii.lifecycle.candidate.rollback_artifacts import validate_rollback_plan_file

console = Console()


def register_patch_commands(app: typer.Typer) -> None:
    @app.command("propose-patch")
    def propose_patch(
        diff_file: Path = typer.Option(..., "--diff-file", help="Path to diff/patch file"),
        output: Path = typer.Option(..., "--output", help="Output path for proposal JSON"),
        description: str = typer.Option(..., "--description", help="Description of patch"),
        reason: str = typer.Option(..., "--reason", help="Reason for patch"),
        target_head_sha: str = typer.Option(..., "--target-head-sha", help="Exact target HEAD verified before apply"),
        verification_receipt: Path = typer.Option(..., "--verification-receipt", help="Exact pre-apply verification receipt"),
        target_repo: Path = typer.Option(Path.cwd(), "--target-repo", help="Exact target repository for the proposal"),
    ) -> None:
        """Create a patch proposal."""
        from builder_ii.governance.authority import enforce_command_authority

        enforce_command_authority("builder-hitl propose-patch", requested_effects=("artifact_write",))
        if not diff_file.exists():
            console.print(f"File not found: {diff_file}")
            raise typer.Exit(1)

        diff_content = diff_file.read_text(encoding="utf-8")
        digest = hashlib.sha256(diff_content.encode("utf-8")).hexdigest()
        proposal = create_hitl_patch_proposal(
            patch_description=description,
            reason=reason,
            patch_digest=digest,
            unified_diff=diff_content,
            target_name="generic",
            generic_repo=target_repo,
            target_head_sha=target_head_sha,
            verification_receipt_file_sha256=hashlib.sha256(verification_receipt.read_bytes()).hexdigest(),
        )
        write_hitl_patch_proposal(proposal, output)
        console.print(f"Proposal written to {output}")
        console.print(f"Next: builder-hitl approve-patch --proposal {output} --output <approval.json>")

    @app.command("approve-patch")
    def approve_patch(
        proposal: Path | None = typer.Option(None, "--proposal", help="Proposal JSON path"),
        from_last: bool = typer.Option(False, "--from-last", help="Auto-resolve latest proposal"),
        output: Path = typer.Option(..., "--output", help="Output path for approval JSON"),
        approved_by: str = typer.Option("operator", "--approved-by", help="Identity recorded as the approver"),
        ttl_seconds: int = typer.Option(
            DEFAULT_APPROVAL_TTL_SECONDS, "--ttl-seconds", help="Approval validity window in seconds"
        ),
    ) -> None:
        """Approve a patch proposal at an interactive boundary.

        Shows the diff and the full patch digest, then requires the operator to
        transcribe the digest prefix. There is intentionally no ``--yes``/non-interactive
        mode: scripting the confirmation would collapse the planned-vs-approved boundary.
        Typing the prefix is an attention control, not a security control.
        """
        from builder_ii.governance.authority import enforce_command_authority

        enforce_command_authority("builder-hitl approve-patch", requested_effects=("artifact_write",))

        from builder_ii.cli._chain_resolve import resolve_path_or_last
        proposal = resolve_path_or_last(proposal, from_last, "hitl_patch_proposal", "proposal")

        errors = validate_hitl_patch_proposal_file(proposal)
        if errors:
            console.print(f"Invalid proposal: {errors}")
            raise typer.Exit(1)

        proposal_data = json.loads(proposal.read_text(encoding="utf-8"))
        patch_digest = str(proposal_data.get("patch_digest", ""))
        unified_diff = str(proposal_data.get("unified_diff", ""))
        if not patch_digest:
            console.print("Proposal has no patch_digest; cannot approve.")
            raise typer.Exit(1)

        expected_prefix = patch_digest[:APPROVAL_CONFIRMATION_PREFIX_LENGTH]

        console.print("─" * 60)
        console.print(proposal_data.get("patch_description") or "(no description)")
        console.print("─" * 60)
        console.print(unified_diff or "(empty diff)")
        console.print("─" * 60)
        console.print(f"patch digest: {patch_digest}")
        console.print(
            f"To approve this mutation, type the first {APPROVAL_CONFIRMATION_PREFIX_LENGTH} "
            "characters of the patch digest shown above."
        )
        typed = typer.prompt("digest prefix").strip()
        if typed != expected_prefix:
            console.print("Prefix did not match. No approval written; nothing is authorized.")
            raise typer.Exit(1)

        approval = create_hitl_patch_approval(
            proposal_data,
            confirmed_digest_prefix=typed,
            approved_by=approved_by,
            ttl_seconds=ttl_seconds,
        )
        write_hitl_patch_approval(approval, output)
        console.print(f"Approval written to {output}")
        console.print(
            f"Next: builder-hitl apply-patch --proposal {proposal} --approval {output} "
            "--verification-receipt <receipt.json> --output-dir <dir>"
        )

    @app.command("refuse-patch")
    def refuse_patch(
        proposal: Path = typer.Option(..., "--proposal", help="Proposal JSON path"),
        output: Path = typer.Option(..., "--output", help="Output path for refusal JSON"),
        rationale: str = typer.Option(..., "--rationale", help="Why the proposal is refused"),
        refused_by: str = typer.Option("operator", "--refused-by", help="Identity recorded as the refuser"),
    ) -> None:
        """Record a passive refusal of a patch proposal (no approval, no apply, no source mutation).

        This is the patch-reject ceremony complementary to approve-patch. It is not a promotion
        ``rejection-record`` (wrong kind for patch proposals).
        """
        from builder_ii.governance.authority import enforce_command_authority
        from builder_ii.governance.hitl.hitl_patch_refusal import create_hitl_patch_refusal, write_hitl_patch_refusal

        enforce_command_authority("builder-hitl refuse-patch", requested_effects=("artifact_write",))

        errors = validate_hitl_patch_proposal_file(proposal)
        if errors:
            console.print(f"Invalid proposal: {errors}")
            raise typer.Exit(1)

        proposal_data = json.loads(proposal.read_text(encoding="utf-8"))
        if not str(rationale).strip():
            console.print("rationale must be non-empty; nothing written.")
            raise typer.Exit(1)

        record = create_hitl_patch_refusal(
            proposal_data,
            proposal_path=proposal,
            rationale=rationale.strip(),
            refused_by=refused_by,
        )
        write_hitl_patch_refusal(record, output)
        console.print(f"Refusal written to {output}")
        console.print("No approval was minted; proposal remains unapproved. Source tree untouched.")

    @app.command("apply-patch")
    def apply_patch_cmd(
        proposal: Path = typer.Option(..., "--proposal", help="Proposal JSON path"),
        approval: Path = typer.Option(..., "--approval", help="Approval JSON path"),
        verification_receipt: Path = typer.Option(..., "--verification-receipt", help="Verification receipt JSON path"),
        output_dir: Path = typer.Option(..., "--output-dir", help="Output directory for generated artifacts"),
    ) -> None:
        """Apply a patch governed by HITL approval."""
        from builder_ii.governance.authority import enforce_command_authority

        enforce_command_authority(
            "builder-hitl apply-patch",
            requested_effects=("patch_application", "artifact_write"),
            approval_ref=str(approval),
        )
        try:
            apply_hitl_patch(
                proposal_path=proposal,
                approval_path=approval,
                verification_receipt_path=verification_receipt,
                output_dir=output_dir,
            )
            console.print(f"Patch applied. Artifacts written to {output_dir}")
        except Exception as e:
            console.print(f"Failed to apply patch: {e}")
            raise typer.Exit(1)

    @app.command("approve-rollback")
    def approve_rollback(
        rollback_plan: Path | None = typer.Option(None, "--rollback-plan", help="Rollback plan JSON path"),
        from_last: bool = typer.Option(False, "--from-last", help="Auto-resolve latest plan"),
        output: Path = typer.Option(..., "--output", help="Output path for rollback approval JSON"),
        approved_by: str = typer.Option("operator", "--approved-by", help="Identity recorded as the approver"),
        ttl_seconds: int = typer.Option(
            DEFAULT_APPROVAL_TTL_SECONDS, "--ttl-seconds", help="Approval validity window in seconds"
        ),
    ) -> None:
        """Approve a rollback at an interactive boundary.

        A rollback is itself a mutation (``git apply -R`` rewrites the working tree and can
        discard work done since the apply), so it gets its own approval — distinct from the
        machine-generated rollback plan. Shows the plan summary and its digest, then requires
        the operator to transcribe the digest prefix. There is intentionally no
        ``--yes``/non-interactive mode; typing the prefix is an attention control.
        """
        from builder_ii.governance.authority import enforce_command_authority

        enforce_command_authority("builder-hitl approve-rollback", requested_effects=("artifact_write",))

        from builder_ii.cli._chain_resolve import resolve_path_or_last
        rollback_plan = resolve_path_or_last(rollback_plan, from_last, "rollback_plan", "rollback-plan")

        errors = validate_rollback_plan_file(rollback_plan)
        if errors:
            console.print(f"Invalid rollback plan: {errors}")
            raise typer.Exit(1)

        plan_data = json.loads(rollback_plan.read_text(encoding="utf-8"))
        plan_digest = canonical_digest(plan_data)
        patch_digest = str(plan_data.get("patch_digest", ""))
        target = plan_data.get("target", {})
        expected_prefix = plan_digest[:APPROVAL_CONFIRMATION_PREFIX_LENGTH]

        drift_protected = bool(plan_data.get("pre_head")) and bool(plan_data.get("post_apply_worktree_digest"))
        console.print("─" * 60)
        console.print(f"target: {target.get('name')} @ {target.get('repo')}")
        console.print(f"rollback strategy: {plan_data.get('rollback_strategy') or '(unspecified)'}")
        console.print(f"pre-apply HEAD: {plan_data.get('pre_head') or '(not recorded)'}")
        console.print(f"patch digest: {patch_digest or '(none)'}")
        console.print(
            "drift protection: "
            + ("present" if drift_protected else "MISSING — rollback will refuse this plan")
        )
        console.print("─" * 60)
        console.print(f"rollback plan digest: {plan_digest}")
        console.print(
            "This rollback reverses an applied patch on the target working tree and can discard "
            "changes made since the apply."
        )
        console.print(
            f"To approve this rollback, type the first {APPROVAL_CONFIRMATION_PREFIX_LENGTH} "
            "characters of the rollback plan digest shown above."
        )
        typed = typer.prompt("digest prefix").strip()
        if typed != expected_prefix:
            console.print("Prefix did not match. No approval written; nothing is authorized.")
            raise typer.Exit(1)

        approval = create_hitl_rollback_approval(
            plan_data,
            confirmed_digest_prefix=typed,
            approved_by=approved_by,
            ttl_seconds=ttl_seconds,
        )
        write_hitl_rollback_approval(approval, output)
        console.print(f"Rollback approval written to {output}")
        console.print(
            f"Next: builder-hitl rollback --rollback-plan {rollback_plan} "
            f"--reverse-patch <rollback.patch> --approval {output} --output-dir <dir>"
        )

    @app.command("rollback")
    def rollback_cmd(
        rollback_plan: Path = typer.Option(..., "--rollback-plan", help="Rollback plan JSON path"),
        reverse_patch: Path = typer.Option(..., "--reverse-patch", help="Reverse patch file path"),
        approval: Path = typer.Option(..., "--approval", help="Rollback approval JSON path"),
        output_dir: Path = typer.Option(..., "--output-dir", help="Output directory for generated artifacts"),
    ) -> None:
        """Execute a rollback governed by a distinct rollback approval."""
        from builder_ii.governance.authority import enforce_command_authority

        enforce_command_authority(
            "builder-hitl rollback",
            requested_effects=("patch_application",),
            approval_ref=str(approval),
        )
        try:
            rollback_hitl_patch(
                rollback_plan_path=rollback_plan,
                reverse_patch_path=reverse_patch,
                output_dir=output_dir,
                approval_path=approval,
            )
            console.print(f"Rollback executed successfully. Artifacts written to {output_dir}")
        except Exception as e:
            console.print(f"Rollback failed: {e}")
            raise typer.Exit(1)
