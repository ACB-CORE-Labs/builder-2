from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from builder_ii.agent_profiles import AgentProfileName
from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.orchestration_assignment import (
    AGENT_ASSIGNMENT_PLAN_KIND,
    ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
    ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
    ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND,
    create_agent_assignment_plan,
    create_orchestration_assignment_dry_run,
    create_orchestration_assignment_plan,
    create_orchestration_assignment_validation_report,
    dumps_orchestration_assignment_dry_run,
    dumps_orchestration_assignment_plan,
    validate_agent_assignment_plan,
    validate_orchestration_assignment_dry_run,
    validate_orchestration_assignment_plan,
    validate_orchestration_assignment_validation_report,
    write_agent_assignment_plan,
    write_orchestration_assignment_dry_run,
    write_orchestration_assignment_plan,
)
from builder_ii.orchestration_plan import (
    ORCHESTRATION_PLAN_KIND,
    create_orchestration_plan,
    dumps_orchestration_plan,
    validate_orchestration_plan,
    validate_orchestration_plan_file,
)
from builder_ii.target_profiles import TargetName

orchestration_app = typer.Typer(help="Create and validate governed agent orchestration plan artifacts.")
console = Console()
_VALID_TARGETS = {"generic", "builder", "core"}


def _normalize_target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("[red]target must be one of: generic, builder, core[/]")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _parse_roles(raw: Optional[str]) -> tuple[AgentProfileName, ...] | None:
    if not raw:
        return None
    roles = tuple(part.strip() for part in raw.split(",") if part.strip())
    return roles  # type: ignore[return-value]


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


def _assignment_validation_errors(data: dict) -> list[str]:
    kind = data.get("kind")
    if kind == AGENT_ASSIGNMENT_PLAN_KIND:
        return validate_agent_assignment_plan(data)
    if kind == ORCHESTRATION_ASSIGNMENT_PLAN_KIND:
        return validate_orchestration_assignment_plan(data)
    if kind == ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND:
        return validate_orchestration_assignment_dry_run(data)
    if kind == ORCHESTRATION_ASSIGNMENT_VALIDATION_REPORT_KIND:
        return validate_orchestration_assignment_validation_report(data)
    return [f"unsupported orchestration artifact kind: {kind}"]


@orchestration_app.command("plan")
def plan_orchestration(
    target: str = typer.Argument(..., help="Target profile name: generic | builder | core"),
    task: str = typer.Option("", "--task", help="Task description"),
    roles: Optional[str] = typer.Option(None, "--roles", help="Comma-separated agent role sequence"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write JSON artifact to this path"),
) -> None:
    """Create a governed orchestration plan artifact without constructing agents."""
    target_norm = _normalize_target(target)
    try:
        parsed_roles = _parse_roles(roles)
        if parsed_roles is None:
            plan = create_orchestration_plan(target=target_norm, task=task)
        else:
            plan = create_orchestration_plan(target=target_norm, task=task, roles=parsed_roles)
    except ValueError as exc:
        console.print(f"[red]Error creating orchestration plan: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_orchestration_plan(plan)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in generated plan: {error}[/]")
        raise typer.Exit(1)

    serialized = dumps_orchestration_plan(plan)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        console.print(f"[green]Orchestration plan written to {output}[/]")
    else:
        echo_stdout(serialized)


@orchestration_app.command("validate")
def validate_orchestration(
    path: Path = typer.Argument(..., help="Path to orchestration artifact JSON file"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write Goal 2 validation report JSON to this path"),
) -> None:
    """Validate a governed orchestration artifact file."""
    data = _read_json(path)
    report: dict | None = None
    if data.get("kind") == ORCHESTRATION_PLAN_KIND:
        errors = validate_orchestration_plan_file(path)
    else:
        errors = _assignment_validation_errors(data)
        if data.get("kind") in {
            AGENT_ASSIGNMENT_PLAN_KIND,
            ORCHESTRATION_ASSIGNMENT_PLAN_KIND,
            ORCHESTRATION_ASSIGNMENT_DRY_RUN_KIND,
        }:
            report = create_orchestration_assignment_validation_report(data, subject_path=path)

    if output is not None and report is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_lib.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        if output is not None and report is not None:
            console.print(f"[yellow]Validation report written to {output}[/]")
        raise typer.Exit(1)
    if output is not None and report is not None:
        console.print(f"[green]Validation report written to {output}[/]")
    console.print(f"[green]Orchestration artifact {path} is valid.[/]")


@orchestration_app.command("render-assignment")
def render_assignment(
    target_profile_path: Path = typer.Option(
        ...,
        "--target-profile",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    agent_profile_path: Path = typer.Option(
        ...,
        "--agent-profile",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    context_pack_path: Path = typer.Option(
        ...,
        "--context-pack",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    verification_profile_path: Path = typer.Option(
        ...,
        "--verification-profile",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    model_registry_path: Path = typer.Option(
        ...,
        "--model-registry",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    model_policy_path: Path = typer.Option(
        ...,
        "--model-policy",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    model_recommendation_path: Path = typer.Option(
        ...,
        "--model-recommendation",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    profile_pack_manifest_path: Path = typer.Option(
        ...,
        "--profile-pack-manifest",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    profile_pack_render_plan_path: Path = typer.Option(
        ...,
        "--profile-pack-render-plan",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    profile_pack_dry_run_path: Path = typer.Option(
        ...,
        "--profile-pack-dry-run",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    profile_pack_validation_report_path: Path = typer.Option(
        ...,
        "--profile-pack-validation-report",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    profile_pack_path: Path = typer.Option(
        ...,
        "--profile-pack",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    task: str = typer.Option(..., "--task", help="Task description to bind"),
    assignment_output: Path | None = typer.Option(
        None,
        "--assignment-output",
        help="Optional path for the assignment plan artifact",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write orchestration assignment plan JSON to this path",
    ),
) -> None:
    """Render a passive Goal 2 assignment and orchestration plan."""
    try:
        assignment = create_agent_assignment_plan(
            target_profile=_read_json(target_profile_path),
            agent_profile=_read_json(agent_profile_path),
            task=task,
            context_pack=_read_json(context_pack_path),
            verification_profile=_read_json(verification_profile_path),
            model_registry=_read_json(model_registry_path),
            model_policy=_read_json(model_policy_path),
            model_recommendation=_read_json(model_recommendation_path),
            profile_pack_manifest=_read_json(profile_pack_manifest_path),
            profile_pack_render_plan=_read_json(profile_pack_render_plan_path),
            profile_pack_dry_run=_read_json(profile_pack_dry_run_path),
            profile_pack_validation_report=_read_json(profile_pack_validation_report_path),
            profile_pack=_read_json(profile_pack_path),
            target_profile_path=target_profile_path,
            agent_profile_path=agent_profile_path,
            context_pack_path=context_pack_path,
            verification_profile_path=verification_profile_path,
            model_registry_path=model_registry_path,
            model_policy_path=model_policy_path,
            model_recommendation_path=model_recommendation_path,
            profile_pack_manifest_path=profile_pack_manifest_path,
            profile_pack_render_plan_path=profile_pack_render_plan_path,
            profile_pack_dry_run_path=profile_pack_dry_run_path,
            profile_pack_validation_report_path=profile_pack_validation_report_path,
            profile_pack_path=profile_pack_path,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    if assignment_output is not None:
        write_agent_assignment_plan(assignment, assignment_output)
        assignment_path = assignment_output
        console.print(f"[green]Agent assignment plan written to {assignment_output}[/]")
    elif output is not None:
        sibling_path = output.parent / (output.name + ".agent-assignment-plan.json")
        write_agent_assignment_plan(assignment, sibling_path)
        assignment_path = sibling_path
        console.print(f"[green]Agent assignment plan written to sibling {sibling_path}[/]")
    else:
        assignment_path = None

    try:
        plan = create_orchestration_assignment_plan(assignment, assignment_plan_path=assignment_path)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    if output is not None:
        write_orchestration_assignment_plan(plan, output)
        console.print(f"[green]Orchestration assignment plan written to {output}[/]")
    else:
        echo_stdout(dumps_orchestration_assignment_plan(plan))


@orchestration_app.command("dry-run")
def dry_run_assignment(
    plan_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Orchestration assignment plan JSON path",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write dry-run JSON to this path"),
) -> None:
    """Emit a passive dry-run for a Goal 2 orchestration assignment plan."""
    plan = _read_json(plan_path)
    try:
        dry_run = create_orchestration_assignment_dry_run(plan, orchestration_assignment_plan_path=plan_path)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    if output is not None:
        write_orchestration_assignment_dry_run(dry_run, output)
        console.print(f"[green]Orchestration assignment dry-run written to {output}[/]")
    else:
        echo_stdout(dumps_orchestration_assignment_dry_run(dry_run))


if __name__ == "__main__":
    orchestration_app()
