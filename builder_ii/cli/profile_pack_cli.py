from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.profile_pack_decisions import (
    DEFAULT_PACK_ID,
    DEFAULT_TASK,
    profile_pack_wizard_steps,
    validate_target,
)
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


def _normalize_target(value: str) -> str:
    """Registry-validate a target profile against `target_names()`, read at call time.

    This used to compare against a set literal `{"generic", "builder", "core"}` and then repeat
    those three names inside its own error message: two transcriptions of the live registry, both
    silently stale the moment a fourth target profile is added. `validate_target` composes the
    message from the registry instead.
    """
    errors = validate_target(value)
    if errors:
        console.print(f"[red]{errors[0]}[/]")
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


def _emit_manifest(pack_id: str, target: str, task: str, project_root: Path, output: Path | None) -> None:
    """Build, validate, and emit the manifest. Shared by `scaffold` and `wizard` so the wizard
    cannot drift into emitting something `scaffold` would not."""
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
        console.out(dumps_profile_pack_manifest(manifest), end="")


@profile_pack_app.command("scaffold")
def scaffold(
    pack_id: str = typer.Option(DEFAULT_PACK_ID, "--pack-id", help="Stable profile pack id"),
    target: str = typer.Option("builder", "--target", help="Target profile (registry-validated)."),
    task: str = typer.Option(DEFAULT_TASK, "--task", help="Task description"),
    project_root: Path = typer.Option(Path.cwd(), "--project-root", help="builder-II project root for source refs"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write manifest JSON to this path"),
) -> None:
    """Scaffold a passive profile-pack manifest."""
    _emit_manifest(pack_id, target, task, project_root, output)


@profile_pack_app.command("wizard")
def wizard(
    pack_id: str | None = typer.Option(None, "--pack-id", help="Profile pack id (prompted when omitted)."),
    target: str | None = typer.Option(None, "--target", help="Target profile (prompted when omitted; validated)."),
    task: str | None = typer.Option(None, "--task", help="Task description (prompted when omitted)."),
    project_root: Path = typer.Option(Path.cwd(), "--project-root", help="builder-II project root for source refs"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write manifest JSON to this path"),
    non_interactive: bool = typer.Option(False, "--non-interactive", help="Never prompt; take the defaults."),
) -> None:
    """Prompt the scaffold decisions, then emit exactly what `scaffold` emits. Never applies.

    Prompt text renders from the live target-profile registry at prompt time; a rejected answer
    re-prompts and names the registry. Flags bypass exactly their own prompts.
    """
    from builder_ii.wizard_framework import WizardAborted, WizardEngine, run_typer_prompt_loop

    steps = profile_pack_wizard_steps()
    flag_answers: dict[str, str | None] = {
        "pack_id": pack_id,
        "target": target,
        "task": task,
        "output": str(output) if output is not None else None,
    }
    missing = {step.id for step in steps} - set(flag_answers)
    if missing:  # pragma: no cover - pinned by tests/test_profile_pack_wizard.py
        raise RuntimeError(f"wizard steps with no flag: {sorted(missing)}")

    # Each flag is validated by its own step's validator, so a flag answer and a typed answer are
    # held to the same boundary. Fail closed, before anything is written.
    by_id = {step.id: step for step in steps}
    for name, provided in flag_answers.items():
        if provided is None:
            continue
        errors = by_id[name].validate(provided)
        if errors:
            console.print(f"[red]invalid decision:[/] {errors[0]}")
            raise typer.Exit(2)

    engine = WizardEngine(steps=steps)
    for name, provided in flag_answers.items():
        if provided is not None:
            engine.preanswer(name, provided)

    if non_interactive:
        chosen = {step.id: engine.answers.get(step.id, step.default or "") for step in engine.steps}
    else:
        try:
            chosen, _ = run_typer_prompt_loop(
                engine,
                prompt_fn=typer.prompt,
                invalid_echo=lambda error: console.print(f"[red]invalid answer:[/] {error}"),
                max_attempts=3,
            )
        except WizardAborted:
            console.print("[red]no valid answer after 3 attempts; aborting without writing artifacts[/]")
            raise typer.Exit(2) from None

    chosen_output = chosen.get("output") or ""
    _emit_manifest(
        chosen["pack_id"],
        chosen["target"],
        chosen["task"],
        project_root,
        Path(chosen_output) if chosen_output else None,
    )


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
        console.out(dumps_profile_pack_render_plan(plan), end="")


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
        console.out(dumps_profile_pack_dry_run(dry_run_artifact), end="")


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
            console.out(dumps_profile_pack_validation_report(report), end="")
        return

    for error in report["errors"]:
        console.print(f"[red]Validation error: {error}[/]")
    if output is not None:
        console.print(f"[yellow]Validation report written to {output}[/]")
    raise typer.Exit(1)


if __name__ == "__main__":
    profile_pack_app()
