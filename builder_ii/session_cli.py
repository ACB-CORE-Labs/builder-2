from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from builder_ii.config import load_settings
from builder_ii.goose_projection import (
    create_goose_projection,
    dumps_goose_projection,
    validate_goose_projection,
    validate_goose_projection_file,
)
from builder_ii.goose_wrapper_plan import (
    create_goose_wrapper_plan,
    dumps_goose_wrapper_plan,
    validate_goose_wrapper_plan,
    validate_goose_wrapper_plan_file,
)
from builder_ii.session_config import (
    create_session_configuration,
    dumps_session_configuration,
    validate_session_configuration,
    validate_session_configuration_file,
)
from builder_ii.session_workflow import (
    create_session_workflow_plan,
    validate_session_workflow_plan,
    validate_session_workflow_plan_file,
)

from builder_ii.governed_prepare_package import (
    create_governed_prepare_package,
    dumps_governed_prepare_package_summary,
    summarize_governed_prepare_package_directory,
    validate_governed_prepare_package_directory,
)

session_app = typer.Typer(help="Inspect and plan governed local developer sessions.")
console = Console()
_VALID_TARGETS: set[str] = {"generic", "builder", "core"}


def _normalize_target(value: str) -> str:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value


def _load_json_object(path: Path, label: str) -> dict:
    try:
        import json as json_lib

        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        console.print(f"[red]Failed to load {label}: {exc}[/]")
        raise typer.Exit(1)
    if not isinstance(data, dict):
        console.print(f"[red]{label} must be a JSON object[/]")
        raise typer.Exit(1)
    return data


@session_app.command("plan")
def plan_session(
    target: str = typer.Argument(..., help="Target profile name: generic | builder | core"),
    agent: Optional[str] = typer.Option(None, "--agent", help="Explicit agent profile name override"),
    prompt: Optional[str] = typer.Option(None, "--prompt", help="Explicit prompt profile name override"),
    verification: Optional[str] = typer.Option(None, "--verification", help="Explicit verification profile name override"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", help="Explicit target repo path override (metadata only)"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON plan artifact to this path"),
) -> None:
    """Generate a governed, local read-only session plan."""
    settings = load_settings()
    target_norm = _normalize_target(target)

    try:
        plan = create_session_workflow_plan(
            settings,
            target_norm,  # type: ignore[arg-type]
            agent_profile_name=agent,  # type: ignore[arg-type]
            prompt_profile_name=prompt,
            verification_profile_name=verification,  # type: ignore[arg-type]
            repo_path=repo_path,
        )
    except ValueError as exc:
        console.print(f"[red]Error resolving session plan parameters: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_session_workflow_plan(plan)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in generated plan: {error}[/]")
        raise typer.Exit(1)

    import json as json_lib
    serialized = json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"

    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
            console.print(f"[green]Session plan written to {output}[/]")
        except Exception as exc:
            console.print(f"[red]Failed to write output file: {exc}[/]")
            raise typer.Exit(1)
    else:
        console.out(serialized, end="")


@session_app.command("validate")
def validate_session(path: Path = typer.Argument(..., help="Path to session plan JSON file to validate")) -> None:
    """Validate a session plan artifact file."""
    errors = validate_session_workflow_plan_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Session plan artifact {path} is valid.[/]")


@session_app.command("config")
def session_config_cmd(
    target: str = typer.Argument(..., help="Target profile name: generic | builder | core"),
    agent: Optional[str] = typer.Option(None, "--agent", help="Explicit agent profile name override"),
    prompt: Optional[str] = typer.Option(None, "--prompt", help="Explicit prompt profile name override"),
    verification: Optional[str] = typer.Option(None, "--verification", help="Explicit verification profile name override"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", help="Explicit target repo path override"),
    task: str = typer.Option("", "--task", help="Optional task description"),
    authority_mode: str = typer.Option("read_only", "--authority-mode", help="Authority mode: read_only | planned_patch"),
    model_alias: Optional[str] = typer.Option(None, "--model", help="Explicit model alias override"),
    context_pack: Optional[str] = typer.Option(None, "--context-pack", help="Optional context pack artifact reference"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON config artifact to this path"),
) -> None:
    """Generate a governed session configuration spine artifact."""
    settings = load_settings()
    target_norm = _normalize_target(target)
    try:
        config = create_session_configuration(
            settings,
            target_norm,  # type: ignore[arg-type]
            agent_profile_name=agent,  # type: ignore[arg-type]
            prompt_profile_name=prompt,
            verification_profile_name=verification,  # type: ignore[arg-type]
            repo_path=repo_path,
            task=task,
            authority_mode=authority_mode,  # type: ignore[arg-type]
            model_alias=model_alias,
            context_pack=context_pack,
        )
    except ValueError as exc:
        console.print(f"[red]Error resolving session configuration: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_session_configuration(config)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in generated config: {error}[/]")
        raise typer.Exit(1)

    serialized = dumps_session_configuration(config)
    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
            console.print(f"[green]Session configuration written to {output}[/]")
        except Exception as exc:
            console.print(f"[red]Failed to write output file: {exc}[/]")
            raise typer.Exit(1)
    else:
        console.out(serialized, end="")


@session_app.command("validate-config")
def validate_session_config_cmd(path: Path = typer.Argument(..., help="Path to session configuration JSON file to validate")) -> None:
    """Validate a governed session configuration artifact file."""
    errors = validate_session_configuration_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Session configuration artifact {path} is valid.[/]")


@session_app.command("goose-projection")
def goose_projection_cmd(
    config_path: Path = typer.Argument(..., help="Path to a governed session configuration JSON file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON Goose projection artifact to this path"),
) -> None:
    """Project a session configuration into Goose-native surfaces without starting Goose."""
    settings = load_settings()
    session_config = _load_json_object(config_path, "session configuration")

    try:
        projection = create_goose_projection(settings, session_config)
    except ValueError as exc:
        console.print(f"[red]Error creating Goose projection: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_goose_projection(projection)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in generated Goose projection: {error}[/]")
        raise typer.Exit(1)

    serialized = dumps_goose_projection(projection)
    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
            console.print(f"[green]Goose projection written to {output}[/]")
        except Exception as exc:
            console.print(f"[red]Failed to write output file: {exc}[/]")
            raise typer.Exit(1)
    else:
        console.out(serialized, end="")


@session_app.command("validate-goose-projection")
def validate_goose_projection_cmd(path: Path = typer.Argument(..., help="Path to Goose projection JSON file to validate")) -> None:
    """Validate a Goose projection artifact file."""
    errors = validate_goose_projection_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Goose projection artifact {path} is valid.[/]")


@session_app.command("goose-wrapper-plan")
def goose_wrapper_plan_cmd(
    projection_path: Path = typer.Argument(..., help="Path to Goose projection JSON file"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON Goose wrapper plan artifact to this path"),
) -> None:
    """Render an operator-reviewed Goose wrapper plan artifact."""
    projection = _load_json_object(projection_path, "Goose projection")
    try:
        plan = create_goose_wrapper_plan(projection)
    except ValueError as exc:
        console.print(f"[red]Error creating Goose wrapper plan: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_goose_wrapper_plan(plan)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in generated Goose wrapper plan: {error}[/]")
        raise typer.Exit(1)

    serialized = dumps_goose_wrapper_plan(plan)
    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
            console.print(f"[green]Goose wrapper plan written to {output}[/]")
        except Exception as exc:
            console.print(f"[red]Failed to write output file: {exc}[/]")
            raise typer.Exit(1)
    else:
        console.out(serialized, end="")


@session_app.command("validate-goose-wrapper-plan")
def validate_goose_wrapper_plan_cmd(path: Path = typer.Argument(..., help="Path to Goose wrapper plan JSON file to validate")) -> None:
    """Validate a Goose wrapper plan artifact file."""
    errors = validate_goose_wrapper_plan_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Goose wrapper plan artifact {path} is valid.[/]")


@session_app.command("goose-readonly-plan")
def goose_readonly_plan(
    target: str = typer.Argument(..., help="Target profile name: generic | builder | core"),
    agent: Optional[str] = typer.Option(None, "--agent", help="Explicit agent profile name override"),
    prompt: Optional[str] = typer.Option(None, "--prompt", help="Explicit prompt profile name override"),
    verification: Optional[str] = typer.Option(None, "--verification", help="Explicit verification profile name override"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", help="Explicit target repo path override (metadata only)"),
    task: str = typer.Option("", "--task", help="Optional task description"),
    context_pack_path: Optional[Path] = typer.Option(None, "--context-pack", help="Optional path to a context pack record JSON to embed"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON plan artifact to this path"),
) -> None:
    """Generate a governed, read-only Goose session plan."""
    settings = load_settings()
    target_norm = _normalize_target(target)

    context_pack_record = None
    if context_pack_path is not None:
        try:
            import json as json_lib
            context_pack_record = json_lib.loads(context_pack_path.read_text(encoding="utf-8"))
        except Exception as exc:
            console.print(f"[red]Failed to load context pack record: {exc}[/]")
            raise typer.Exit(1)

    try:
        from builder_ii.goose_readonly_session import create_goose_readonly_session_plan, validate_goose_readonly_session_plan
        plan = create_goose_readonly_session_plan(
            settings,
            target_norm,  # type: ignore[arg-type]
            agent_profile_name=agent,  # type: ignore[arg-type]
            prompt_profile_name=prompt,
            verification_profile_name=verification,  # type: ignore[arg-type]
            repo_path=repo_path,
            context_pack_record=context_pack_record,
            task=task,
        )
    except ValueError as exc:
        console.print(f"[red]Error resolving profiles: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_goose_readonly_session_plan(plan)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in generated plan: {error}[/]")
        raise typer.Exit(1)

    import json as json_lib
    serialized = json_lib.dumps(plan, indent=2, sort_keys=True) + "\n"
    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
            console.print(f"[green]Goose read-only session plan written to {output}[/]")
        except Exception as exc:
            console.print(f"[red]Failed to write output file: {exc}[/]")
            raise typer.Exit(1)
    else:
        console.out(serialized, end="")


@session_app.command("validate-goose-readonly-plan")
def validate_goose_readonly_plan_cmd(path: Path = typer.Argument(..., help="Path to Goose read-only session plan JSON file to validate")) -> None:
    """Validate a Goose read-only session plan artifact file."""
    from builder_ii.goose_readonly_session import validate_goose_readonly_session_plan_file
    errors = validate_goose_readonly_session_plan_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Goose read-only session plan artifact {path} is valid.[/]")


@session_app.command("prepare-package")
def prepare_package_cmd(
    target: str = typer.Argument(..., help="Target profile name: generic | builder | core"),
    output_dir: Path = typer.Option(..., "--output-dir", "-o", help="Directory where governed preparation artifacts will be written"),
    repo_path: Optional[str] = typer.Option(None, "--repo-path", help="Explicit target repo path override"),
    agent: Optional[str] = typer.Option(None, "--agent", help="Explicit agent profile name override"),
    prompt: Optional[str] = typer.Option(None, "--prompt", help="Explicit prompt profile name override"),
    verification: Optional[str] = typer.Option(None, "--verification", help="Explicit verification profile name override"),
    task: str = typer.Option("", "--task", help="Optional task description"),
    include_deepagents_readiness: bool = typer.Option(True, "--deepagents-readiness/--no-deepagents-readiness", help="Include optional deepagents readiness artifact"),
) -> None:
    """Create a governed preparation package without executing target-repo work."""
    settings = load_settings()
    target_norm = _normalize_target(target)

    try:
        package = create_governed_prepare_package(
            settings,
            target_norm,
            output_dir=output_dir,
            repo_path=repo_path,
            agent_profile_name=agent,
            prompt_profile_name=prompt,
            verification_profile_name=verification,
            task=task,
            include_deepagents_readiness=include_deepagents_readiness,
        )
    except ValueError as exc:
        console.print(f"[red]Error creating governed prepare package: {exc}[/]")
        raise typer.Exit(1)

    console.print(f"[green]Governed prepare package written to {output_dir.resolve()}[/]")
    console.print(f"[green]Package manifest: {output_dir.resolve() / 'prepare-package.json'}[/]")
    console.print(f"[cyan]Artifacts: {len(package.get('artifact_refs', []))}[/]")


@session_app.command("validate-prepare-package")
def validate_prepare_package_cmd(
    path: Path = typer.Argument(..., help="Path to a prepare package directory or prepare-package.json manifest"),
) -> None:
    """Validate a governed prepare package manifest and referenced artifacts."""
    errors = validate_governed_prepare_package_directory(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Governed prepare package {path} is valid.[/]")


@session_app.command("summarize-prepare-package")
def summarize_prepare_package_cmd(
    path: Path = typer.Argument(..., help="Path to a prepare package directory or prepare-package.json manifest"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Optional path to write JSON summary artifact"),
) -> None:
    """Summarize a valid governed prepare package for human inspection."""
    try:
        summary = summarize_governed_prepare_package_directory(path)
        serialized = dumps_governed_prepare_package_summary(summary)
    except ValueError as exc:
        console.print(f"[red]Error summarizing governed prepare package: {exc}[/]")
        raise typer.Exit(1)

    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(serialized, encoding="utf-8")
            console.print(f"[green]Governed prepare package summary written to {output}[/]")
        except Exception as exc:
            console.print(f"[red]Failed to write summary output file: {exc}[/]")
            raise typer.Exit(1)
    else:
        console.out(serialized, end="")


if __name__ == "__main__":
    session_app()
