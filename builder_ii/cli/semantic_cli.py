"""CLI: builder-semantic doctor|map|preview — V.1 semantic/structural RO."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.semantic_readonly import (
    doctor_semantic,
    map_semantic,
    preview_semantic,
    validate_semantic_doctor,
    validate_semantic_map,
    validate_semantic_preview,
)

semantic_app = typer.Typer(
    help=(
        "Semantic/structural read-only lane: doctor (detect tools), map (repo_map), "
        "preview (path substring). No rewrites, no target mutation, no authority."
    ),
)
console = Console()


def _emit(data: dict[str, Any], output: Path | None) -> None:
    text = json_lib.dumps(data, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]Wrote {output}[/]")
    else:
        echo_stdout(text)


@semantic_app.command("doctor")
def doctor_cmd(
    repo: Path = typer.Option(Path("."), "--repo", exists=True, file_okay=False),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Detect-only health for semantic RO stack (serena/ast-grep optional)."""
    art = doctor_semantic(repo_path=repo)
    _emit(art, output)
    if not art.get("ok"):
        console.print("[red]semantic doctor: in-process repo_map path failed[/]")
        raise typer.Exit(1)
    console.print(
        f"[green]semantic doctor ok "
        f"serena={art.get('serena_status')} ast-grep={art.get('ast_grep_status')}[/]"
    )


@semantic_app.command("map")
def map_cmd(
    repo: Path = typer.Option(Path("."), "--repo", exists=True, file_okay=False),
    target: str = typer.Option("builder", "--target"),
    max_files: int = typer.Option(200, "--max-files", min=1, max=500),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Emit bounded read-only semantic/structural map (create_repo_map based)."""
    try:
        art = map_semantic(repo, target_name=target, max_files=max_files)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    _emit(art, output)
    console.print(f"[green]semantic map files={art.get('file_count')} digest={str(art.get('digest'))[:12]}…[/]")


@semantic_app.command("preview")
def preview_cmd(
    query: str = typer.Option(..., "--query", "-q", help="Substring over path/role"),
    repo: Path = typer.Option(Path("."), "--repo", exists=True, file_okay=False),
    target: str = typer.Option("builder", "--target"),
    max_hits: int = typer.Option(25, "--max-hits", min=1, max=200),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Dry-run path/role preview — no Serena rewrite, no ast-grep apply."""
    try:
        art = preview_semantic(repo, query=query, target_name=target, max_hits=max_hits)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    _emit(art, output)
    console.print(f"[green]preview hits={art.get('hit_count')} query={query!r}[/]")


@semantic_app.command("validate")
def validate_cmd(
    path: Path = typer.Argument(..., exists=True, dir_okay=False),
) -> None:
    """Validate a semantic doctor/map/preview artifact file."""
    data = json_lib.loads(path.read_text(encoding="utf-8"))
    kind = data.get("kind")
    if kind == "builder_ii.semantic_doctor_report":
        errors = validate_semantic_doctor(data)
    elif kind == "builder_ii.semantic_map":
        errors = validate_semantic_map(data)
    elif kind == "builder_ii.semantic_preview":
        errors = validate_semantic_preview(data)
    else:
        console.print(f"[red]unknown kind {kind!r}[/]")
        raise typer.Exit(1)
    if errors:
        for e in errors:
            console.print(f"[red]{e}[/]")
        raise typer.Exit(1)
    console.print(f"[green]valid {kind}[/]")
