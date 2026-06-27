from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.config import load_settings
from builder_ii.context_pack import (
    ContextPackSelection,
    ContextPackResult,
    RepoTarget,
    build_context_pack,
    create_context_pack_record,
    dumps_context_pack_record,
    write_context_pack_record,
    validate_context_pack_record,
    validate_context_pack_record_file,
)


context_app = typer.Typer(help="Build task-scoped context packs for local agents.")
console = Console()
_VALID_TARGETS: set[str] = {"core", "builder", "generic"}



def _normalize_target(value: str) -> RepoTarget:
    if value not in _VALID_TARGETS:
        raise typer.BadParameter("--target must be one of: core, builder, or generic")
    return value  # type: ignore[return-value]


def _print_result(result: ContextPackResult) -> None:
    table = Table("Artifact", "Path")
    table.add_row("manifest", str(result.markdown_path))
    if result.repomix_path:
        table.add_row("repomix", str(result.repomix_path))
    console.print(table)
    console.print(f"target: {result.target}")
    console.print(f"repo: {result.repo}")
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


@context_app.command("pack")
def pack(
    task: str | None = typer.Option(None, "--task", "-t", help="Task description to include in the manifest"),
    module: str | None = typer.Option(None, "--module", "-m", help="Repo file or directory to include"),
    changed: bool = typer.Option(False, "--changed", help="Include changed and untracked files"),
    target: str = typer.Option("core", "--target", help="Repository target: core, builder, or generic"),
    no_repomix: bool = typer.Option(False, "--no-repomix", help="Write manifest only; do not invoke repomix"),
    markdown_output: Path = typer.Option(Path(".builder/context-pack.md"), "--markdown-output"),
    repomix_output: Path = typer.Option(Path(".builder/context-pack.xml"), "--repomix-output"),
) -> None:
    """Build a context-pack manifest and optional Repomix repository pack."""
    settings = load_settings()
    try:
        result = build_context_pack(
            settings,
            ContextPackSelection(task=task, module=module, changed=changed),
            target=_normalize_target(target),
            markdown_output=markdown_output,
            repomix_output=repomix_output,
            run_repomix=not no_repomix,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    _print_result(result)


@context_app.command("changed")
def changed(
    task: str | None = typer.Option(None, "--task", "-t"),
    target: str = typer.Option("core", "--target", help="Repository target: core, builder, or generic"),
    no_repomix: bool = typer.Option(False, "--no-repomix"),
) -> None:
    """Shortcut for pack --changed."""
    settings = load_settings()
    result = build_context_pack(
        settings,
        ContextPackSelection(task=task, module=None, changed=True),
        target=_normalize_target(target),
        markdown_output=Path(".builder/context-pack.md"),
        repomix_output=Path(".builder/context-pack.xml"),
        run_repomix=not no_repomix,
    )
    _print_result(result)


@context_app.command("artifact")
def artifact(
    task: str | None = typer.Option(None, "--task", "-t", help="Task description to include in the manifest"),
    module: str | None = typer.Option(None, "--module", "-m", help="Repo file or directory to include"),
    changed: bool = typer.Option(False, "--changed", help="Include changed and untracked files"),
    target: str = typer.Option("core", "--target", help="Repository target: core, builder, or generic"),
    no_repomix: bool = typer.Option(True, "--no-repomix", help="Write manifest only; do not invoke repomix"),
    markdown_output: Path = typer.Option(Path(".builder/context-pack.md"), "--markdown-output"),
    repomix_output: Path = typer.Option(Path(".builder/context-pack.xml"), "--repomix-output"),
    output: Path | None = typer.Option(None, "--output", help="Write JSON artifact to path"),
) -> None:
    """Emit a no-runtime context pack record artifact."""
    settings = load_settings()
    try:
        result = build_context_pack(
            settings,
            ContextPackSelection(task=task, module=module, changed=changed),
            target=_normalize_target(target),
            markdown_output=markdown_output,
            repomix_output=repomix_output,
            run_repomix=not no_repomix,
        )
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc

    record = create_context_pack_record(result, task=task)
    errors = validate_context_pack_record(record)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_context_pack_record(record, output)
        console.print(f"Context pack record written to {output}")
    else:
        console.out(dumps_context_pack_record(record), end="")


@context_app.command("validate")
def validate(path: Path = typer.Argument(..., help="Path to context pack record JSON file")) -> None:
    """Validate a context pack record artifact file."""
    errors = validate_context_pack_record_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Context pack record {path} is valid.")
