import re
content = open("builder_ii/cli/hitl_promotion_cli.py").read()

content = content.replace(
    "def promotion_request(\n    proposal_path: Path = typer.Option(..., \"--proposal-path\", help=\"Path to Goal 2 or Goal 3 proposal artifact\"),",
    "def promotion_request(\n    proposal_path: Path | None = typer.Option(None, \"--proposal-path\", help=\"Path to Goal 2 or Goal 3 proposal artifact\"),\n    from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest proposal\"),"
)
content = content.replace(
    "enforce_command_authority(\"builder-hitl promotion-request\", requested_effects=(\"artifact_write\",))\n",
    "enforce_command_authority(\"builder-hitl promotion-request\", requested_effects=(\"artifact_write\",))\n\n    from builder_ii.cli._chain_resolve import resolve_path_or_last\n    proposal_path = resolve_path_or_last(proposal_path, from_last, \"promotion_proposal\", \"proposal-path\")\n"
)

content = content.replace(
    "def promotion_review(\n    request_path: Path = typer.Option(..., \"--request-path\", help=\"Path to promotion request artifact\"),",
    "def promotion_review(\n    request_path: Path | None = typer.Option(None, \"--request-path\", help=\"Path to promotion request artifact\"),\n    from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest request\"),"
)
content = content.replace(
    "enforce_command_authority(\"builder-hitl promotion-review\", requested_effects=(\"artifact_write\",))\n",
    "enforce_command_authority(\"builder-hitl promotion-review\", requested_effects=(\"artifact_write\",))\n\n    from builder_ii.cli._chain_resolve import resolve_path_or_last\n    request_path = resolve_path_or_last(request_path, from_last, \"promotion_request\", \"request-path\")\n"
)

content = content.replace(
    "def promotion_decision(\n    request_path: Path = typer.Option(..., \"--request-path\", help=\"Path to promotion request artifact\"),\n    review_path: Path = typer.Option(..., \"--review-path\", help=\"Path to promotion review artifact\"),",
    "def promotion_decision(\n    request_path: Path | None = typer.Option(None, \"--request-path\", help=\"Path to promotion request artifact\"),\n    review_path: Path | None = typer.Option(None, \"--review-path\", help=\"Path to promotion review artifact\"),\n    from_last: bool = typer.Option(False, \"--from-last\", help=\"Auto-resolve latest request and review\"),"
)
content = content.replace(
    "enforce_command_authority(\"builder-hitl promotion-decision\", requested_effects=(\"artifact_write\",))\n",
    "enforce_command_authority(\"builder-hitl promotion-decision\", requested_effects=(\"artifact_write\",))\n\n    from builder_ii.cli._chain_resolve import resolve_path_or_last\n    request_path = resolve_path_or_last(request_path, from_last, \"promotion_request\", \"request-path\")\n    review_path = resolve_path_or_last(review_path, from_last, \"promotion_review\", \"review-path\")\n"
)

open("builder_ii/cli/hitl_promotion_cli.py", "w").write(content)
