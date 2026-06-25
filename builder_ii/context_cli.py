from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.config import load_settings
from builder_ii.context_pack import ContextPackSelection, build_context_pack

context_app = typer.Typer(help="Build task-scoped CORE context packs for local agents.")
console = Console()


@context_app.command("pack")
def pack(
    task: str | None = typer.Option(None, "--task", "-t", help="Task description to include in the manifest"),
    module: str | None = typer.Option(None, "--module", "-m", help="Repo file or directory to include"),
    changed: bool = typer.Option(False, "--changed", help="Include changed and untracked files"),
    no_repomix: bool = typer.Option(False, "--no-repomix", help="Write manifest only; do not invoke repomix"),
    markdown_output: Path = typer.Option(Path(".builder/context-pack.md"), "--markdown-output"),
    repomix_output: Path = typer.Option(Path(".builder/context-pack.xml"), "--repomix-output"),
) -> None:
    """Build a context-pack manifest and optional Repomix repository pack."""
    settings = load_settings()
    result = build_context_pack(
        settings,
        ContextPackSelection(task=task, module=module, changed=changed),
        markdown_output=markdown_output,
        repomix_output=repomix_output,
        run_repomix=not no_repomix,
    )
    table = Table("Artifact", "Path")
    table.add_row("manifest", str(result.markdown_path))
    if result.repomix_path:
        table.add_row("repomix", str(result.repomix_path))
    console.print(table)
    console.print(f"selected files: {len(result.selected_files)}")
    if result.command:
        console.print("repomix command: " + " ".join(result.command))
    if result.ran_repomix and not result.ok:
        console.print("[red]Repomix failed[/]")
        if result.stderr:
            console.print(result.stderr)
        raise typer.Exit(result.returncode or 1)
    if result.ran_repomix:
        console.print("[green]Repomix complete[/]")
    else:
        console.print("[yellow]Manifest only[/]")


@context_app.command("changed")
def changed(task: str | None = typer.Option(None, "--task", "-t"), no_repomix: bool = typer.Option(False, "--no-repomix")) -> None:
    """Shortcut for pack --changed."""
    pack(task=task, module=None, changed=True, no_repomix=no_repomix)
