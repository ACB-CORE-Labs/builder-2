from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.profile_pack_dry_run import (
    create_profile_pack_dry_run,
    dumps_profile_pack_dry_run,
    validate_profile_pack_dry_run,
    write_profile_pack_dry_run,
)
from builder_ii.profile_pack_manifest import (
    create_profile_pack_manifest,
    dumps_profile_pack_manifest,
    validate_profile_pack_manifest,
    write_profile_pack_manifest,
)
from builder_ii.profile_pack_render_plan import (
    create_profile_pack_render_plan,
    dumps_profile_pack_render_plan,
    validate_profile_pack_render_plan,
    write_profile_pack_render_plan,
)
from builder_ii.profile_pack_validation_report import (
    create_profile_pack_validation_report,
    dumps_profile_pack_validation_report,
    validate_profile_pack_validation_report,
    write_profile_pack_validation_report,
)

profile_pack_app = typer.Typer(help="Create and validate passive profile-pack artifacts.")
console = Console()
_VALID_TARGETS = {"generic", "builder", "core"}


def _normalize_target(value: str) -> str:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value


def _read_json(path: Path) -> dict:
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        console.print(f"[red]invalid JSON in {path}: {exc}[/]")
        raise typer.Exit(1)
    except Exception as exc:
        console.print(f"[red]failed to read {path}: {exc}[/]")
        raise typer.Exit(1)
    if not isinstance(data, dict):
        console.print(f"[red]{path} must contain a JSON object[/]")
        raise typer.Exit(1)
    return data


@profile_pack_app.command("scaffold")
def scaffold(
    pack_id: str = typer.Option("builder-passive-profile-pack", "--pack-id", help="Stable profile pack id"),
    target: str = typer.Option("builder", "--target", help="Target profile: generic, builder, core"),
    task: str = typer.Option("render passive profile-pack substrate", "--task", help="Task description"),
    project_root: Path = typer.Option(Path.cwd(), "--project-root", help="builder-II project root for source refs"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write manifest JSON to this path"),
) -> None:
    """Scaffold a passive profile-pack manifest."""

    manifest = create_profile_pack_manifest(
        pack_id=pack_id,
        target_profile=_normalize_target(target),
        task=task,
        project_root=project_root,
    )
    errors = validate_profile_pack_manifest(manifest)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    if output is not None:
        write_profile_pack_manifest(manifest, output)
        console.print(f"[green]Profile pack manifest written to {output}[/]")
    else:
        echo_stdout(dumps_profile_pack_manifest(manifest))


@profile_pack_app.command("render")
def render(
    manifest_path: Path = typer.Argument(..., help="Profile pack manifest JSON path"),
    output_root: str = typer.Option("profile-pack-rendered", "--output-root", help="Planned render output root"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write render-plan JSON to this path"),
) -> None:
    """Render a passive profile-pack render plan from a manifest."""

    manifest = _read_json(manifest_path)
    try:
        plan = create_profile_pack_render_plan(manifest, manifest_path=manifest_path, output_root=output_root)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    errors = validate_profile_pack_render_plan(plan)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    if output is not None:
        write_profile_pack_render_plan(plan, output)
        console.print(f"[green]Profile pack render plan written to {output}[/]")
    else:
        echo_stdout(dumps_profile_pack_render_plan(plan))


@profile_pack_app.command("dry-run")
def dry_run(
    manifest_path: Path = typer.Argument(..., help="Profile pack manifest JSON path"),
    render_plan_path: Path | None = typer.Option(None, "--render-plan", help="Optional render-plan JSON path"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write dry-run JSON to this path"),
) -> None:
    """Create a passive dry-run artifact without executing the pack."""

    manifest = _read_json(manifest_path)
    render_plan = _read_json(render_plan_path) if render_plan_path else None
    try:
        dry_run_artifact = create_profile_pack_dry_run(
            manifest,
            render_plan,
            manifest_path=manifest_path,
            render_plan_path=render_plan_path,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)
    errors = validate_profile_pack_dry_run(dry_run_artifact)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    if output is not None:
        write_profile_pack_dry_run(dry_run_artifact, output)
        console.print(f"[green]Profile pack dry-run written to {output}[/]")
    else:
        echo_stdout(dumps_profile_pack_dry_run(dry_run_artifact))


@profile_pack_app.command("validate")
def validate(
    path: Path = typer.Argument(..., help="Profile pack artifact JSON path"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write validation report JSON to this path"),
) -> None:
    """Validate a profile-pack lifecycle artifact and optionally emit a report."""

    subject = _read_json(path)
    report = create_profile_pack_validation_report(subject, subject_path=path)
    report_errors = validate_profile_pack_validation_report(report)
    if report_errors:
        for error in report_errors:
            console.print(f"[red]Validation report error: {error}[/]")
        raise typer.Exit(1)

    if output is not None:
        write_profile_pack_validation_report(report, output)

    if report["valid"]:
        if output is not None:
            console.print(f"[green]Profile pack artifact {path} is valid. Report written to {output}[/]")
        else:
            echo_stdout(dumps_profile_pack_validation_report(report))
        return

    for error in report["errors"]:
        console.print(f"[red]Validation error: {error}[/]")
    if output is not None:
        console.print(f"[yellow]Validation report written to {output}[/]")
    raise typer.Exit(1)


if __name__ == "__main__":
    profile_pack_app()
