import hashlib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.hitl_patch_apply import apply_hitl_patch, rollback_hitl_patch
from builder_ii.hitl_patch_proposal import create_hitl_patch_proposal, write_hitl_patch_proposal

console = Console()


def register_patch_commands(app: typer.Typer) -> None:
    @app.command("propose-patch")
    def propose_patch(
        diff_file: Path = typer.Option(..., "--diff-file", help="Path to diff/patch file"),
        output: Path = typer.Option(..., "--output", help="Output path for proposal JSON"),
        description: str = typer.Option(..., "--description", help="Description of patch"),
        reason: str = typer.Option(..., "--reason", help="Reason for patch"),
    ) -> None:
        """Create a patch proposal."""
        from builder_ii.command_authority import enforce_command_authority

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
        )
        write_hitl_patch_proposal(proposal, output)
        console.print(f"Proposal written to {output}")

    @app.command("apply-patch")
    def apply_patch_cmd(
        proposal: Path = typer.Option(..., "--proposal", help="Proposal JSON path"),
        approval: Path = typer.Option(..., "--approval", help="Approval JSON path"),
        verification_receipt: Path = typer.Option(..., "--verification-receipt", help="Verification receipt JSON path"),
        output_dir: Path = typer.Option(..., "--output-dir", help="Output directory for generated artifacts"),
    ) -> None:
        """Apply a patch governed by HITL approval."""
        from builder_ii.command_authority import enforce_command_authority

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

    @app.command("rollback")
    def rollback_cmd(
        rollback_plan: Path = typer.Option(..., "--rollback-plan", help="Rollback plan JSON path"),
        reverse_patch: Path = typer.Option(..., "--reverse-patch", help="Reverse patch file path"),
        output_dir: Path = typer.Option(..., "--output-dir", help="Output directory for generated artifacts"),
    ) -> None:
        """Execute a rollback."""
        from builder_ii.command_authority import enforce_command_authority

        enforce_command_authority(
            "builder-hitl rollback",
            requested_effects=("patch_application",),
            approval_ref=str(rollback_plan),
        )
        try:
            rollback_hitl_patch(
                rollback_plan_path=rollback_plan,
                reverse_patch_path=reverse_patch,
                output_dir=output_dir,
            )
            console.print(f"Rollback executed successfully. Artifacts written to {output_dir}")
        except Exception as e:
            console.print(f"Rollback failed: {e}")
            raise typer.Exit(1)
