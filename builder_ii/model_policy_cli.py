from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.model_client_registry import (
    MODEL_CLIENT_REGISTRY_KIND,
    create_model_client_registry,
    dumps_model_client_registry,
    validate_model_client_registry,
    write_model_client_registry,
)
from builder_ii.model_routing_policy import (
    MODEL_ROUTING_POLICY_KIND,
    MODEL_ROUTING_RECOMMENDATION_KIND,
    create_model_routing_policy,
    create_model_routing_recommendation,
    dumps_model_routing_policy,
    dumps_model_routing_recommendation,
    validate_model_routing_policy,
    validate_model_routing_recommendation,
    write_model_routing_recommendation,
)

model_policy_app = typer.Typer(help="Passive governed model/client registry and routing policy CLI.")
console = Console()


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


@model_policy_app.command("validate")
def validate(
    path: Path = typer.Argument(..., help="Path to model registry, routing policy, or recommendation artifact JSON"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write validation result JSON to this path"),
) -> None:
    """Validate a model client registry, routing policy, or recommendation artifact."""
    data = _read_json(path)
    kind = data.get("kind")
    errors: list[str] = []

    if kind == MODEL_CLIENT_REGISTRY_KIND:
        errors = validate_model_client_registry(data)
    elif kind == MODEL_ROUTING_POLICY_KIND:
        errors = validate_model_routing_policy(data)
    elif kind == MODEL_ROUTING_RECOMMENDATION_KIND:
        errors = validate_model_routing_recommendation(data)
    else:
        errors = [f"Unknown artifact kind '{kind}'; expected model registry, policy, or recommendation"]

    report = {
        "valid": len(errors) == 0,
        "subject_kind": kind,
        "subject_path": str(path),
        "errors": errors,
    }

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_lib.dumps(report, indent=2) + "\n", encoding="utf-8")

    if errors:
        for err in errors:
            console.print(f"[red]Validation error: {err}[/]")
        raise typer.Exit(1)

    console.print(f"[green]Artifact {path} ({kind}) is valid.[/]")


@model_policy_app.command("render")
def render(
    policy_path: Path | None = typer.Option(None, "--policy", help="Optional path to model routing policy JSON"),
    registry_path: Path | None = typer.Option(None, "--registry", help="Optional path to model client registry JSON"),
    task_intent: str = typer.Option("coding", "--task-intent", help="Task intent: coding or reasoning"),
    max_risk: str = typer.Option("local_offline", "--max-risk", help="Max allowed risk classification"),
    requires_tools: bool = typer.Option(True, "--requires-tools/--no-tools", help="Whether tool use is required"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write recommendation report JSON to this path"),
) -> None:
    """Render a passive model routing recommendation report."""
    policy = _read_json(policy_path) if policy_path else create_model_routing_policy()
    registry = _read_json(registry_path) if registry_path else create_model_client_registry()

    request = {
        "task_intent": task_intent,
        "max_risk_classification": max_risk,
        "requires_tool_use": requires_tools,
    }

    try:
        rec = create_model_routing_recommendation(
            policy=policy,
            registry=registry,
            request=request,
            policy_path=policy_path,
            registry_path=registry_path,
        )
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    errors = validate_model_routing_recommendation(rec)
    if errors:
        for err in errors:
            console.print(f"[red]Generated recommendation validation error: {err}[/]")
        raise typer.Exit(1)

    if output is not None:
        write_model_routing_recommendation(rec, output)
        console.print(f"[green]Model routing recommendation written to {output}[/]")
    else:
        console.out(dumps_model_routing_recommendation(rec), end="")


@model_policy_app.command("dry-run")
def dry_run(
    policy_path: Path | None = typer.Option(None, "--policy", help="Optional path to model routing policy JSON"),
    registry_path: Path | None = typer.Option(None, "--registry", help="Optional path to model client registry JSON"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write dry-run recommendation report JSON to this path"),
) -> None:
    """Perform a passive routing recommendation dry-run without execution."""
    # Delegate dry-run to render with default coding offline parameters
    render(
        policy_path=policy_path,
        registry_path=registry_path,
        task_intent="coding",
        max_risk="local_offline",
        requires_tools=True,
        output=output,
    )


if __name__ == "__main__":
    model_policy_app()
