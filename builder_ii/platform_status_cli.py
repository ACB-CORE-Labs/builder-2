from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.command_authority import COMMAND_AUTHORITY_REGISTRY
from builder_ii.platform_completion_audit import (
    dumps_docs_audit,
    dumps_matrix,
    render_docs_audit_jsonable,
    render_human_summary,
    validate_command_surfaces,
    validate_completion_matrix,
)


platform_app = typer.Typer(
    help="Render builder-II platform completion truth without runtime, model, tool, Goose, or deepagents execution.",
    no_args_is_help=True,
)
console = Console()


def _registry_names() -> set[str]:
    return {record.name for record in COMMAND_AUTHORITY_REGISTRY}


def _validate_or_exit(root: Path | None = None) -> None:
    errors = validate_completion_matrix(root=root)
    errors.extend(validate_command_surfaces(_registry_names()))
    if errors:
        for error in errors:
            console.print(f"[red]platform truth validation error:[/] {error}")
        raise typer.Exit(1)


@platform_app.command("matrix")
def matrix() -> None:
    """Print the source-derived platform capability matrix as JSON."""
    _validate_or_exit(root=Path.cwd())
    console.out(dumps_matrix(), end="")


@platform_app.command("status")
def status() -> None:
    """Print concise human-readable platform truth state."""
    _validate_or_exit(root=Path.cwd())
    console.out(render_human_summary(), end="")


@platform_app.command("audit-docs")
def audit_docs(
    root: Path = typer.Option(
        Path("."),
        "--root",
        "-r",
        exists=True,
        file_okay=False,
        dir_okay=True,
        readable=True,
        help="Repository root whose README.md and docs/**/*.md files should be audited.",
    ),
) -> None:
    """Scan docs for false operational completion language."""
    root = root.resolve()
    _validate_or_exit(root=root)
    report = render_docs_audit_jsonable(root)
    console.out(dumps_docs_audit(root), end="")
    if not report["valid"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    platform_app()
