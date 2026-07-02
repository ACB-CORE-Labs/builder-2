from __future__ import annotations

import json as json_lib
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.config_cli import _override_map
from builder_ii.config_sources import resolve_config_sources
from builder_ii.onboarding_intent import validate_onboarding_intent_report_file
from builder_ii.setup_apply import SetupApplyError, apply_setup_overlay
from builder_ii.setup_onboarding import run_onboarding_pipeline
from builder_ii.setup_overlay import (
    create_setup_overlay_plan,
    dumps_setup_overlay_plan,
    validate_setup_overlay_plan_artifact,
    validate_setup_overlay_plan_file,
    write_setup_overlay_plan,
)
from builder_ii.setup_plan import (
    create_setup_plan,
    dumps_setup_plan,
    validate_setup_plan_artifact,
    validate_setup_plan_file,
    write_setup_plan,
)
from builder_ii.setup_receipt import validate_setup_receipt_file
from builder_ii.setup_rollback import (
    create_setup_rollback_snapshot,
    dumps_setup_rollback_snapshot,
    validate_setup_rollback_snapshot_artifact,
    validate_setup_rollback_snapshot_file,
    write_setup_rollback_snapshot,
)
from builder_ii.setup_rollback_execute import SetupRollbackError, execute_setup_rollback
from builder_ii.setup_rollback_receipt import validate_setup_rollback_receipt_file

setup_app = typer.Typer(
    help="Create, validate, and digest-apply governed setup artifacts.",
    no_args_is_help=True,
)
console = Console()


def _validation_report(errors: list[str]) -> str:
    return (
        json_lib.dumps(
            {
                "kind": "builder_ii.setup_plan_validation_report",
                "valid": not errors,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _overlay_validation_report(errors: list[str]) -> str:
    return (
        json_lib.dumps(
            {
                "kind": "builder_ii.setup_overlay_plan_validation_report",
                "valid": not errors,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _receipt_validation_report(errors: list[str]) -> str:
    return (
        json_lib.dumps(
            {
                "kind": "builder_ii.setup_receipt_validation_report",
                "valid": not errors,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _rollback_validation_report(errors: list[str]) -> str:
    return (
        json_lib.dumps(
            {
                "kind": "builder_ii.setup_rollback_snapshot_validation_report",
                "valid": not errors,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _rollback_receipt_validation_report(errors: list[str]) -> str:
    return (
        json_lib.dumps(
            {
                "kind": "builder_ii.setup_rollback_receipt_validation_report",
                "valid": not errors,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _onboarding_intent_validation_report(errors: list[str]) -> str:
    return (
        json_lib.dumps(
            {
                "kind": "builder_ii.onboarding_intent_validation_report",
                "valid": not errors,
                "errors": errors,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _load_json_file(path: Path) -> dict:
    return json_lib.loads(path.read_text(encoding="utf-8"))


@setup_app.command("plan")
def plan(
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional explicit setup plan artifact path."),
    root: Path = typer.Option(Path("."), "--root", help="Project root for relative paths and .env lookup."),
    config_file: Path | None = typer.Option(None, "--config-file", help="Optional builder config JSON/YAML file."),
    target_repo: Path | None = typer.Option(None, "--target-repo", help="CLI override for BUILDER_TARGET_REPO."),
    artifact_root: Path | None = typer.Option(None, "--artifact-root", help="CLI override for BUILDER_ARTIFACT_ROOT."),
    target_profile: str | None = typer.Option(
        None, "--target-profile", help="CLI override for BUILDER_TARGET_PROFILE."
    ),
    agent_profile: str | None = typer.Option(None, "--agent-profile", help="CLI override for BUILDER_AGENT_PROFILE."),
    verification_profile: str | None = typer.Option(
        None, "--verification-profile", help="CLI override for BUILDER_VERIFICATION_PROFILE."
    ),
    model_backend: str | None = typer.Option(None, "--model-backend", help="CLI override for BUILDER_MODEL_BACKEND."),
    model_alias: str | None = typer.Option(None, "--model-alias", help="CLI override for BUILDER_MODEL_ALIAS."),
    runtime_mode: str | None = typer.Option(None, "--runtime-mode", help="CLI override for BUILDER_RUNTIME_MODE."),
    allow_artifact_root_inside_target: bool | None = typer.Option(
        None,
        "--allow-artifact-root-inside-target/--no-allow-artifact-root-inside-target",
        help="Explicit path policy override for artifact roots under target source paths.",
    ),
) -> None:
    """Create a passive setup plan artifact. This never applies the plan."""
    resolution = resolve_config_sources(
        project_root=root,
        builder_config_file=config_file,
        cli_overrides=_override_map(
            target_repo=target_repo,
            artifact_root=artifact_root,
            target_profile=target_profile,
            agent_profile=agent_profile,
            verification_profile=verification_profile,
            model_backend=model_backend,
            model_alias=model_alias,
            runtime_mode=runtime_mode,
            allow_artifact_root_inside_target=allow_artifact_root_inside_target,
        ),
    )
    plan_artifact = create_setup_plan(resolution)
    if output is not None:
        write_setup_plan(plan_artifact, output)
    console.out(dumps_setup_plan(plan_artifact), end="")
    errors = validate_setup_plan_artifact(plan_artifact)
    if errors:
        raise typer.Exit(1)


@setup_app.command("validate-plan")
def validate_plan(
    path: Path = typer.Argument(..., help="Setup plan JSON artifact path."),
) -> None:
    """Validate a passive setup plan artifact."""
    errors = validate_setup_plan_file(path)
    console.out(_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


@setup_app.command("overlay-plan")
def overlay_plan(
    setup_plan_path: Path = typer.Argument(..., help="Setup plan JSON artifact path."),
    output: Path | None = typer.Option(None, "--output", "-o", help="Optional explicit setup overlay artifact path."),
) -> None:
    """Create a passive setup overlay plan artifact. This never applies setup."""
    plan_errors = validate_setup_plan_file(setup_plan_path)
    if plan_errors:
        console.out(_validation_report(plan_errors), end="")
        raise typer.Exit(1)
    overlay_artifact = create_setup_overlay_plan(_load_json_file(setup_plan_path))
    errors = validate_setup_overlay_plan_artifact(overlay_artifact)
    if errors:
        console.out(_overlay_validation_report(errors), end="")
        raise typer.Exit(1)
    if output is not None:
        write_setup_overlay_plan(overlay_artifact, output)
    console.out(dumps_setup_overlay_plan(overlay_artifact), end="")


@setup_app.command("validate-overlay-plan")
def validate_overlay_plan(
    path: Path = typer.Argument(..., help="Setup overlay plan JSON artifact path."),
) -> None:
    """Validate a passive setup overlay plan artifact."""
    errors = validate_setup_overlay_plan_file(path)
    console.out(_overlay_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


@setup_app.command("rollback-snapshot")
def rollback_snapshot(
    setup_overlay_path: Path = typer.Argument(..., help="Setup overlay plan JSON artifact path."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Optional explicit rollback snapshot artifact path."
    ),
) -> None:
    """Create a passive rollback snapshot artifact. This never executes rollback."""
    overlay_errors = validate_setup_overlay_plan_file(setup_overlay_path)
    if overlay_errors:
        console.out(_overlay_validation_report(overlay_errors), end="")
        raise typer.Exit(1)
    snapshot_artifact = create_setup_rollback_snapshot(_load_json_file(setup_overlay_path))
    errors = validate_setup_rollback_snapshot_artifact(snapshot_artifact)
    if errors:
        console.out(_rollback_validation_report(errors), end="")
        raise typer.Exit(1)
    if output is not None:
        write_setup_rollback_snapshot(snapshot_artifact, output)
    console.out(dumps_setup_rollback_snapshot(snapshot_artifact), end="")


@setup_app.command("validate-rollback-snapshot")
def validate_rollback_snapshot(
    path: Path = typer.Argument(..., help="Setup rollback snapshot JSON artifact path."),
) -> None:
    """Validate a passive setup rollback snapshot artifact."""
    errors = validate_setup_rollback_snapshot_file(path)
    console.out(_rollback_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


@setup_app.command("apply")
def apply(
    setup_overlay_path: Path = typer.Argument(..., help="Setup overlay plan JSON artifact path."),
    rollback_snapshot: Path = typer.Option(
        ..., "--rollback-snapshot", help="Required rollback snapshot artifact path."
    ),
    approve_digest: str = typer.Option(
        ..., "--approve-digest", help="Required digest-bound approval matching overlay_plan_digest."
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Required explicit setup receipt output path."),
) -> None:
    """Apply only digest-approved declared setup writes and emit a setup receipt."""
    overlay_errors = validate_setup_overlay_plan_file(setup_overlay_path)
    rollback_errors = validate_setup_rollback_snapshot_file(rollback_snapshot)
    if overlay_errors or rollback_errors:
        console.out(_overlay_validation_report(overlay_errors), end="")
        console.out(_rollback_validation_report(rollback_errors), end="")
        raise typer.Exit(1)
    try:
        receipt = apply_setup_overlay(
            _load_json_file(setup_overlay_path),
            _load_json_file(rollback_snapshot),
            approve_digest=approve_digest,
            receipt_output=output,
        )
    except SetupApplyError as exc:
        if exc.receipt is not None:
            console.out(json_lib.dumps(exc.receipt, indent=2, sort_keys=True) + "\n", end="")
        else:
            console.out(str(exc) + "\n", end="")
        raise typer.Exit(1)
    console.out(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n", end="")


@setup_app.command("validate-receipt")
def validate_receipt(
    path: Path = typer.Argument(..., help="Setup apply receipt JSON artifact path."),
) -> None:
    """Validate a setup apply receipt artifact."""
    errors = validate_setup_receipt_file(path)
    console.out(_receipt_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


@setup_app.command("rollback")
def rollback(
    setup_receipt_path: Path = typer.Argument(..., help="Setup apply receipt JSON artifact path."),
    rollback_snapshot: Path = typer.Option(
        ..., "--rollback-snapshot", help="Required rollback snapshot artifact path."
    ),
    approve_digest: str = typer.Option(
        ..., "--approve-digest", help="Required digest-bound approval matching setup receipt digest."
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Required explicit setup rollback receipt output path."),
) -> None:
    """Rollback digest-approved setup writes and emit a setup rollback receipt."""
    receipt_errors = validate_setup_receipt_file(setup_receipt_path)
    rollback_errors = validate_setup_rollback_snapshot_file(rollback_snapshot)
    if receipt_errors or rollback_errors:
        console.out(_receipt_validation_report(receipt_errors), end="")
        console.out(_rollback_validation_report(rollback_errors), end="")
        raise typer.Exit(1)
    try:
        receipt = execute_setup_rollback(
            _load_json_file(setup_receipt_path),
            _load_json_file(rollback_snapshot),
            approve_digest=approve_digest,
            receipt_output=output,
        )
    except SetupRollbackError as exc:
        if exc.receipt is not None:
            console.out(json_lib.dumps(exc.receipt, indent=2, sort_keys=True) + "\n", end="")
        else:
            console.out(str(exc) + "\n", end="")
        raise typer.Exit(1)
    console.out(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n", end="")


@setup_app.command("validate-rollback-receipt")
def validate_rollback_receipt(
    path: Path = typer.Argument(..., help="Setup rollback receipt JSON artifact path."),
) -> None:
    """Validate a setup rollback receipt artifact."""
    errors = validate_setup_rollback_receipt_file(path)
    console.out(_rollback_receipt_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


@setup_app.command("validate-onboarding-intent")
def validate_onboarding_intent(
    path: Path = typer.Argument(..., help="Onboarding intent report JSON artifact path."),
) -> None:
    """Validate an onboarding intent report artifact."""
    errors = validate_onboarding_intent_report_file(path)
    console.out(_onboarding_intent_validation_report(errors), end="")
    if errors:
        raise typer.Exit(1)


@setup_app.command("init")
def setup_init(
    output_dir: Path = typer.Option(..., "--output-dir", help="Required output directory for onboarding artifacts."),
    root: Path = typer.Option(Path.cwd(), "--root", help="Project root for configuration resolution."),
    config_file: Path | None = typer.Option(None, "--config-file", help="Optional builder config file path."),
    target_repo: Path | None = typer.Option(None, "--target-repo", help="Target repository override."),
    artifact_root: Path | None = typer.Option(None, "--artifact-root", help="Platform artifact root override."),
    target_profile: str | None = typer.Option(
        None, "--target-profile", help="Target profile override (generic|builder|core)."
    ),
    agent_profile: str | None = typer.Option(None, "--agent-profile", help="Agent profile override."),
    verification_profile: str | None = typer.Option(
        None, "--verification-profile", help="Verification profile override."
    ),
    model_backend: str | None = typer.Option(None, "--model-backend", help="Model backend override."),
    model_alias: str | None = typer.Option(None, "--model-alias", help="Model alias override."),
) -> None:
    """Non-interactive governed onboarding UX wrapper."""
    result = run_onboarding_pipeline(
        output_dir=output_dir,
        onboarding_mode="init",
        root=root,
        config_file=config_file,
        target_repo=target_repo,
        artifact_root=artifact_root,
        target_profile=target_profile,
        agent_profile=agent_profile,
        verification_profile=verification_profile,
        model_backend=model_backend,
        model_alias=model_alias,
    )
    if not result.valid:
        console.out(json_lib.dumps(result.summary_dict(), indent=2, sort_keys=True) + "\n", end="")
        raise typer.Exit(1)

    console.out(json_lib.dumps(result.summary_dict(), indent=2, sort_keys=True) + "\n", end="")
    console.out("\nExact next commands:\n", end="")
    console.out(f"  {result.onboarding_intent['apply_command']}\n", end="")
    console.out(f"  {result.onboarding_intent['validate_receipt_command']}\n", end="")


@setup_app.command("wizard")
def setup_wizard(
    output_dir: Path | None = typer.Option(None, "--output-dir", help="Output directory for onboarding artifacts."),
    root: Path = typer.Option(Path.cwd(), "--root", help="Project root for configuration resolution."),
    target_profile: str | None = typer.Option(
        None, "--target-profile", help="Target profile override (generic|builder|core)."
    ),
    model_backend: str | None = typer.Option(None, "--model-backend", help="Model backend override."),
    model_alias: str | None = typer.Option(None, "--model-alias", help="Model alias override."),
) -> None:
    """Interactive guided onboarding wizard flow."""
    out_path = output_dir or Path(
        typer.prompt("Enter output directory for onboarding artifacts", default=".builder/setup-artifacts")
    )
    profile = target_profile or typer.prompt("Select target profile (generic, builder, core)", default="generic")
    backend = model_backend or typer.prompt(
        "Select local model backend (rapid-mlx, mlx-lm, ollama)", default="rapid-mlx"
    )
    alias = model_alias or typer.prompt("Select primary model alias", default="phi-reasoning")

    result = run_onboarding_pipeline(
        output_dir=out_path,
        onboarding_mode="wizard",
        root=root,
        target_profile=profile,
        model_backend=backend,
        model_alias=alias,
    )
    if not result.valid:
        console.out(json_lib.dumps(result.summary_dict(), indent=2, sort_keys=True) + "\n", end="")
        raise typer.Exit(1)

    console.out(f"\nOnboarding Plan Generated Successfully!\nOutput Directory: {out_path}\n", end="")
    console.out(f"Setup Plan Digest:        {result.setup_plan['plan_digest']}\n", end="")
    console.out(f"Overlay Plan Digest:      {result.overlay_plan['overlay_plan_digest']}\n", end="")
    console.out(f"Rollback Snapshot Digest: {result.rollback_snapshot['snapshot_id']}\n", end="")
    console.out(
        f"\nExact next commands:\n  {result.onboarding_intent['apply_command']}\n  {result.onboarding_intent['validate_receipt_command']}\n",
        end="",
    )
    console.out("\nTo apply, run the printed builder-setup apply command after reviewing the overlay digest.\n", end="")


if __name__ == "__main__":
    setup_app()
