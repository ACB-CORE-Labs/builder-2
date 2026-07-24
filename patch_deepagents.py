content = open("builder_ii/cli/deepagents_cli.py").read()

content = content.replace(
    "def run_approved(\n    candidate: Path = typer.Option(..., \"--candidate\", help=\"Path to deepagents execution candidate JSON\"),\n    approval: Path = typer.Option(..., \"--approval\", help=\"Path to deepagents execution approval JSON\"),",
    "def run_approved(\n    candidate: Path | None = typer.Option(None, \"--candidate\", help=\"Path to deepagents execution candidate JSON\"),\n    approval: Path | None = typer.Option(None, \"--approval\", help=\"Path to deepagents execution approval JSON\"),\n    from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest candidate and approval\"),"
)

content = content.replace(
    "    if not candidate.exists():",
    "    from builder_ii.cli._chain_resolve import resolve_path_or_last\n    candidate = resolve_path_or_last(candidate, from_last, \"execution_candidate_manifest\", \"candidate\")\n    approval = resolve_path_or_last(approval, from_last, \"execution_approval_record\", \"approval\")\n\n    if not candidate.exists():"
)

open("builder_ii/cli/deepagents_cli.py", "w").write(content)
