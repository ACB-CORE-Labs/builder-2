content = open("builder_ii/cli/orchestration_cli.py").read()

content = content.replace(
    "def dry_run_assignment(\n    plan_path: Path = typer.Argument(\n        ...,\n        help=\"Path to the assignment plan JSON artifact\",\n    ),",
    "def dry_run_assignment(\n    plan_path: Path | None = typer.Argument(\n        None,\n        help=\"Path to the assignment plan JSON artifact\",\n    ),\n    from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest plan\"),"
)

content = content.replace(
    "    data = _read_json(plan_path)\n    errors = _assignment_validation_errors(data)",
    "    from builder_ii.cli._chain_resolve import resolve_path_or_last\n    plan_path = resolve_path_or_last(plan_path, from_last, \"agent_assignment_plan\", \"plan_path\")\n    data = _read_json(plan_path)\n    errors = _assignment_validation_errors(data)"
)

open("builder_ii/cli/orchestration_cli.py", "w").write(content)
