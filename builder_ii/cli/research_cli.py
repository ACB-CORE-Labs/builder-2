from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.research_adapters import (
    create_research_adapter_artifact,
    dumps_research_adapter_artifact,
    validate_research_adapter_artifact,
    validate_research_adapter_artifact_file,
    write_research_adapter_artifact,
)
from builder_ii.research_plans import (
    create_research_plan_artifact,
    dumps_research_plan_artifact,
    get_research_profile,
    research_profile_names,
    research_profiles,
    validate_research_plan_artifact,
    validate_research_plan_artifact_file,
    validate_research_profiles,
    write_research_plan_artifact,
)
from builder_ii.target_profiles import TargetName, target_names

research_app = typer.Typer(help="Create and validate no-execution research planning artifacts.")
console = Console()
_VALID_PROFILES = set(research_profile_names())
_VALID_TARGETS = set(target_names())


def _target(value: str) -> TargetName:
    if value not in _VALID_TARGETS:
        console.print("target must be one of: generic, builder, core")
        raise typer.Exit(1)
    return value  # type: ignore[return-value]


def _profile(value: str):
    if value not in _VALID_PROFILES:
        console.print("unknown research profile")
        raise typer.Exit(1)
    return value


@research_app.command("profiles")
def profiles() -> None:
    """List research planning profiles."""
    for profile in research_profiles():
        console.print(f"{profile.name}: {profile.description}")


@research_app.command("show")
def show(profile: str) -> None:
    """Show a research planning profile."""
    selected = get_research_profile(_profile(profile))
    console.print(f"# Research profile: {selected.name}")
    console.print(selected.description)
    console.print("\nSource strategy:")
    for item in selected.source_strategy:
        console.print(f"- {item}")
    console.print("\nEvidence requirements:")
    for item in selected.evidence_requirements:
        console.print(f"- {item}")
    console.print("\nReport contract:")
    for item in selected.report_contract:
        console.print(f"- {item}")
    console.print("\nGovernance: no runtime, model, search, MCP, source collection, or shell execution.")


@research_app.command("validate-profiles")
def validate_profiles_command() -> None:
    """Validate built-in research planning profiles."""
    errors = validate_research_profiles()
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print("Research planning profiles are valid.")


@research_app.command("plan")
def plan(
    target: str = typer.Option("generic", "--target", help="Target profile: generic, builder, core"),
    profile: str = typer.Option("research_planner", "--profile", help="Research planning profile"),
    task: str = typer.Option(..., "--task", help="Research planning task"),
    topic: str = typer.Option("", "--topic", help="Optional topic label"),
    source_hint: list[str] = typer.Option([], "--source-hint", help="Repeatable source category hint"),
    output: Path | None = typer.Option(None, "--output", help="Write research plan JSON artifact to path"),
) -> None:
    """Create a research plan artifact without collecting sources."""
    artifact = create_research_plan_artifact(
        target=_target(target),
        profile_name=_profile(profile),
        task=task,
        topic=topic,
        source_hint=tuple(source_hint),
    )
    errors = validate_research_plan_artifact(artifact)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)

    if output is not None:
        write_research_plan_artifact(artifact, output)
        console.print(f"Research plan artifact written to {output}")
    else:
        echo_stdout(dumps_research_plan_artifact(artifact))


@research_app.command("validate")
def validate(path: Path) -> None:
    """Validate a research plan artifact without executing it."""
    errors = validate_research_plan_artifact_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Research plan artifact {path} is valid.")


@research_app.command("adapter")
def adapter(
    target: str = typer.Option("generic", "--target"),
    topic: str = typer.Option(..., "--topic"),
    research_question: str = typer.Option(..., "--research-question"),
    plan_path: Path = typer.Option(..., "--plan-path"),
    plan_sha256: str = typer.Option(..., "--plan-sha256"),
    output_contract: list[str] = typer.Option([], "--output-contract"),
    review_note: list[str] = typer.Option([], "--review-note"),
    output: Path | None = typer.Option(None, "--output"),
) -> None:
    """Create a research adapter artifact without invoking external research."""
    artifact = create_research_adapter_artifact(
        target=_target(target),
        topic=topic,
        research_question=research_question,
        plan_path=plan_path,
        plan_sha256=plan_sha256,
        output_contract=tuple(output_contract),
        review_notes=tuple(review_note),
    )
    errors = validate_research_adapter_artifact(artifact)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    if output is not None:
        write_research_adapter_artifact(artifact, output)
        console.print(f"Research adapter artifact written to {output}")
    else:
        echo_stdout(dumps_research_adapter_artifact(artifact))


@research_app.command("validate-adapter")
def validate_adapter(path: Path) -> None:
    """Validate a research adapter artifact without invoking it."""
    errors = validate_research_adapter_artifact_file(path)
    if errors:
        for error in errors:
            console.print(f"Validation error: {error}")
        raise typer.Exit(1)
    console.print(f"Research adapter artifact {path} is valid.")
