from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.config import load_settings
from builder_ii.target_profile_demos import (
    get_target_profile_demo,
    render_target_profile_demo,
    validate_target_profile_demos,
)
from builder_ii.target_profiles import (
    TargetName,
    build_target_profiles,
    dumps_target_profile_artifact,
    render_target_profile,
    target_profile,
    validate_target_profile_artifact,
    validate_target_profile_artifact_file,
    validate_target_profiles,
    write_target_profile_artifact,
)

targets_app = typer.Typer(help="Inspect builder-II target profiles.")
console = Console()
_VALID_TARGETS: set[str] = {"generic", "builder", "core"}


def _normalize_target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


@targets_app.command("list")
def list_targets(
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
) -> None:
    """List available target profiles."""
    settings = load_settings()
    table = Table("Target", "Repository", "Context defaults", "Description")
    for profile in build_target_profiles(settings, generic_repo=generic_repo):
        table.add_row(profile.name, str(profile.repo), str(len(profile.context_defaults)), profile.description)
    console.print(table)


@targets_app.command("show")
def show_target(
    name: str, generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target")
) -> None:
    """Show one target profile."""
    settings = load_settings()
    profile = target_profile(settings, _normalize_target(name), generic_repo=generic_repo)
    console.print(render_target_profile(profile))


@targets_app.command("validate")
def validate(path: Path | None = typer.Argument(None, help="Validate target profile artifact file")) -> None:
    """Validate target profile registry consistency or an artifact file."""
    if path:
        errors = validate_target_profile_artifact_file(path)
        if errors:
            for error in errors:
                console.print(f"Validation error: {error}")
            raise typer.Exit(1)
        console.print(f"Target profile artifact {path} is valid.", soft_wrap=True)
        return

    errors = [*validate_target_profiles(load_settings()), *validate_target_profile_demos()]
    if not errors:
        console.print("[green]Target profiles valid[/]")
        return
    for error in errors:
        console.print(f"[red]{error}[/]")
    raise typer.Exit(1)


@targets_app.command("artifact")
def artifact(
    name: str,
    generic_repo: Path | None = typer.Option(None, "--generic-repo", help="Repo path for the generic target"),
    output: Path | None = typer.Option(None, "--output", help="Write JSON artifact to path"),
) -> None:
    """Emit a no-runtime target profile artifact."""
    settings = load_settings()
    profile = target_profile(settings, _normalize_target(name), generic_repo=generic_repo)
    errors = validate_target_profile_artifact(profile.to_artifact_dict())
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_target_profile_artifact(profile, output)
        console.print(f"Target profile artifact written to {output}")
    else:
        echo_stdout(dumps_target_profile_artifact(profile))


@targets_app.command("demo")
def demo(name: str) -> None:
    """Show a no-runtime target profile demo recipe."""
    errors = validate_target_profile_demos()
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(render_target_profile_demo(get_target_profile_demo(_normalize_target(name))))


@targets_app.command("doctor")
def doctor_target(
    name: str = typer.Argument("core", help="Target profile to doctor (V.4: core isolation)"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write doctor report JSON"),
) -> None:
    """Doctor target-profile isolation (CORE: catalog + coupling checks; no semgrep run)."""
    target = _normalize_target(name)
    if target != "core":
        console.print(
            f"[yellow]doctor for target={target} is not specialized; "
            "V.4 doctor checks apply to core only.[/]"
        )
        raise typer.Exit(2)
    settings = load_settings()
    from builder_ii.targets.core import doctor_core_profile

    report = doctor_core_profile(settings)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_lib.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        console.print(f"Target doctor report written to {output}")
    else:
        echo_stdout(json_lib.dumps(report, indent=2, sort_keys=True) + "\n")
    if not report.get("ok"):
        for check in report.get("checks") or []:
            if not check.get("ok"):
                console.print(f"[red]doctor {check.get('name')}: {check.get('errors')}[/]")
        raise typer.Exit(1)
    console.print(
        f"[green]doctor core ok workbench_coupling={report.get('workbench_coupling')} "
        f"semgrep_executed={report.get('semgrep_executed')}[/]"
    )


@targets_app.command("readonly-founder-demo")
def readonly_founder_demo(
    name: str,
    output: Path = typer.Option(None, "--output", "-o", help="Directory to write demo artifacts to"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force deletion and recreation of output directory if it exists"
    ),
) -> None:
    """Generate passive read-only founder demo artifacts."""
    from builder_ii.readonly_founder_demo import generate_readonly_founder_demo

    settings = load_settings()
    target = _normalize_target(name)
    try:
        paths = generate_readonly_founder_demo(settings, target=target, output_dir=output, force=force)
    except ValueError as e:
        console.print(f"[red]Error:[/] {e}")
        raise typer.Exit(1)
    console.print(
        f"Generated passive read-only founder demo for {target} to {output or '.builder/demos/' + target + '-readonly'}"
    )
    for key, path in sorted(paths.items()):
        console.print(f"  {key}: {path}")
