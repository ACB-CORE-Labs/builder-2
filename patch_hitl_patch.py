
content = open("builder_ii/cli/hitl_patch_cli.py").read()

content = content.replace(
    "def approve_patch(\n        proposal: Path = typer.Option(..., \"--proposal\", help=\"Proposal JSON path\"),",
    "def approve_patch(\n        proposal: Path | None = typer.Option(None, \"--proposal\", help=\"Proposal JSON path\"),\n        from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest proposal\"),"
)

content = content.replace(
    "enforce_command_authority(\"builder-hitl approve-patch\", requested_effects=(\"artifact_write\",))\n",
    "enforce_command_authority(\"builder-hitl approve-patch\", requested_effects=(\"artifact_write\",))\n\n        from builder_ii.cli._chain_resolve import resolve_path_or_last\n        proposal = resolve_path_or_last(proposal, from_last, \"hitl_patch_proposal\", \"proposal\")\n"
)

content = content.replace(
    "def apply_patch_cmd(\n        approval: Path = typer.Option(..., \"--approval\", help=\"Approval JSON path\"),",
    "def apply_patch_cmd(\n        approval: Path | None = typer.Option(None, \"--approval\", help=\"Approval JSON path\"),\n        from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest approval\"),"
)

content = content.replace(
    "enforce_command_authority(\"builder-hitl apply-patch\", requested_effects=(\"system_write\",))\n",
    "enforce_command_authority(\"builder-hitl apply-patch\", requested_effects=(\"system_write\",))\n\n        from builder_ii.cli._chain_resolve import resolve_path_or_last\n        approval = resolve_path_or_last(approval, from_last, \"hitl_patch_approval\", \"approval\")\n"
)

content = content.replace(
    "def approve_rollback(\n        rollback_plan: Path = typer.Option(..., \"--rollback-plan\", help=\"Rollback plan JSON path\"),",
    "def approve_rollback(\n        rollback_plan: Path | None = typer.Option(None, \"--rollback-plan\", help=\"Rollback plan JSON path\"),\n        from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest plan\"),"
)
content = content.replace(
    "enforce_command_authority(\"builder-hitl approve-rollback\", requested_effects=(\"artifact_write\",))\n",
    "enforce_command_authority(\"builder-hitl approve-rollback\", requested_effects=(\"artifact_write\",))\n\n        from builder_ii.cli._chain_resolve import resolve_path_or_last\n        rollback_plan = resolve_path_or_last(rollback_plan, from_last, \"rollback_plan\", \"rollback-plan\")\n"
)

content = content.replace(
    "def rollback_cmd(\n        approval: Path = typer.Option(..., \"--approval\", help=\"Rollback approval JSON path\"),",
    "def rollback_cmd(\n        approval: Path | None = typer.Option(None, \"--approval\", help=\"Rollback approval JSON path\"),\n        from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest approval\"),"
)
content = content.replace(
    "enforce_command_authority(\"builder-hitl rollback\", requested_effects=(\"system_write\",))\n",
    "enforce_command_authority(\"builder-hitl rollback\", requested_effects=(\"system_write\",))\n\n        from builder_ii.cli._chain_resolve import resolve_path_or_last\n        approval = resolve_path_or_last(approval, from_last, \"rollback_approval\", \"approval\")\n"
)

open("builder_ii/cli/hitl_patch_cli.py", "w").write(content)
