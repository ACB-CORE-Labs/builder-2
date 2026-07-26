from __future__ import annotations

import json as json_lib
import os
from pathlib import Path

import typer
from rich.console import Console

from builder_ii.cli.config_cli import _override_map
from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.core.config_sources import resolve_config_sources
from builder_ii.governance.hitl.hitl_patch_approval import APPROVAL_CONFIRMATION_PREFIX_LENGTH
from builder_ii.governance.ledger.ratification_ledger import (
    EVENT_AUTO_ACCEPTED,
    EVENT_MANUAL_RATIFIED,
    append_ratification_event,
)
from builder_ii.governance.ratification_grants import (
    APPROVAL_MODE_STANDING_GRANT,
    consult_ratification_grant,
    resolve_ratification_root,
)
from builder_ii.lifecycle.setup.onboarding_intent import validate_onboarding_intent_report_file
from builder_ii.lifecycle.setup.setup_apply import SetupApplyError, apply_setup_overlay
from builder_ii.lifecycle.setup.setup_onboarding import run_onboarding_pipeline
from builder_ii.lifecycle.setup.setup_overlay import (
    create_setup_overlay_plan,
    dumps_setup_overlay_plan,
    validate_setup_overlay_plan_artifact,
    validate_setup_overlay_plan_file,
    write_setup_overlay_plan,
)
from builder_ii.lifecycle.setup.setup_plan import (
    create_setup_plan,
    dumps_setup_plan,
    validate_setup_plan_artifact,
    validate_setup_plan_file,
    write_setup_plan,
)
from builder_ii.lifecycle.setup.setup_receipt import validate_setup_receipt_file
from builder_ii.lifecycle.setup.setup_rollback import (
    create_setup_rollback_snapshot,
    dumps_setup_rollback_snapshot,
    validate_setup_rollback_snapshot_artifact,
    validate_setup_rollback_snapshot_file,
    write_setup_rollback_snapshot,
)
from builder_ii.lifecycle.setup.setup_rollback_execute import SetupRollbackError, execute_setup_rollback
from builder_ii.lifecycle.setup.setup_rollback_receipt import validate_setup_rollback_receipt_file

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


def _interactive_digest_approval(digest: str, digest_label: str) -> str:
    """Digest-prefix confirmation grammar shared with the HITL patch approvals (plan item 1.1).

    The command renders the full digest and the operator must type its first
    ``APPROVAL_CONFIRMATION_PREFIX_LENGTH`` characters back; the process that renders the
    digest never harvests the confirmation for the operator. A mismatch refuses with no
    writes and no receipt.
    """
    if not digest:
        console.out(f"artifact has no {digest_label}; cannot approve\n", end="")
        raise typer.Exit(1)
    expected_prefix = digest[:APPROVAL_CONFIRMATION_PREFIX_LENGTH]
    console.out(f"{digest_label}: {digest}\n", end="")
    console.out(
        f"To approve, type the first {APPROVAL_CONFIRMATION_PREFIX_LENGTH} characters "
        f"of the {digest_label} shown above.\n",
        end="",
    )
    typed = typer.prompt("digest prefix").strip()
    if typed != expected_prefix:
        console.out("Prefix did not match. No approval granted; nothing was written.\n", end="")
        raise typer.Exit(1)
    return digest


def _record_ratification(point_id: str, command: str, *, event: str, because: str, grant_digest: str | None) -> None:
    """Append one ratification ledger event, but only into a store the operator already created.

    Deliberately not `mkdir(parents=True)`: apply must not conjure a ratification store inside
    every repository it touches. Where no store exists no grant can exist either, and the receipt
    already records `interactive_digest_prefix_confirmation` -- so nothing is lost, and the ledger
    remains what it claims to be, a cross-command view of a store the operator opted into.
    """
    root = resolve_ratification_root(None)
    if not root.is_dir():
        return
    append_ratification_event(
        root,
        event=event,
        point_id=point_id,
        command=command,
        actor=os.environ.get("USER", "unknown"),
        because=because,
        grant_digest=grant_digest,
    )


def _digest_approval(digest: str, digest_label: str, *, point_id: str, command: str) -> tuple[str, str]:
    """Satisfy a digest confirmation by standing grant if one is in force, else by typed prefix.

    Returns ``(approved_digest, approval_mode)``. The two modes are never conflated: a receipt
    saying `interactive_digest_prefix_confirmation` means a human typed the prefix, and a receipt
    saying `standing_ratification_grant` means one did not. Naming the grant in stdout is not
    decoration -- a confirmation that silently stops appearing is indistinguishable from one that
    was never required.
    """
    consultation = consult_ratification_grant(point_id)
    if consultation.satisfied:
        if not digest:
            console.out(f"artifact has no {digest_label}; cannot approve\n", end="")
            raise typer.Exit(1)
        console.out(f"{digest_label}: {digest}\n", end="")
        console.out(f"Auto-accepted under {consultation.because}.\n", end="")
        console.out("Revoke with `builder-govern revoke`; audit with `builder-govern trace`.\n", end="")
        _record_ratification(
            point_id,
            command,
            event=EVENT_AUTO_ACCEPTED,
            because=consultation.because,
            grant_digest=consultation.grant_digest,
        )
        return digest, APPROVAL_MODE_STANDING_GRANT

    approved = _interactive_digest_approval(digest, digest_label)
    _record_ratification(
        point_id,
        command,
        event=EVENT_MANUAL_RATIFIED,
        because=f"operator typed the {digest_label} prefix",
        grant_digest=None,
    )
    return approved, "interactive_digest_prefix_confirmation"


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
    echo_stdout(dumps_setup_plan(plan_artifact))
    errors = validate_setup_plan_artifact(plan_artifact)
    if errors:
        raise typer.Exit(1)


@setup_app.command("validate-plan")
def validate_plan(
    path: Path = typer.Argument(..., help="Setup plan JSON artifact path."),
) -> None:
    """Validate a passive setup plan artifact."""
    errors = validate_setup_plan_file(path)
    echo_stdout(_validation_report(errors))
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
        echo_stdout(_validation_report(plan_errors))
        raise typer.Exit(1)
    overlay_artifact = create_setup_overlay_plan(_load_json_file(setup_plan_path))
    errors = validate_setup_overlay_plan_artifact(overlay_artifact)
    if errors:
        echo_stdout(_overlay_validation_report(errors))
        raise typer.Exit(1)
    if output is not None:
        write_setup_overlay_plan(overlay_artifact, output)
    echo_stdout(dumps_setup_overlay_plan(overlay_artifact))


@setup_app.command("validate-overlay-plan")
def validate_overlay_plan(
    path: Path = typer.Argument(..., help="Setup overlay plan JSON artifact path."),
) -> None:
    """Validate a passive setup overlay plan artifact."""
    errors = validate_setup_overlay_plan_file(path)
    echo_stdout(_overlay_validation_report(errors))
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
        echo_stdout(_overlay_validation_report(overlay_errors))
        raise typer.Exit(1)
    snapshot_artifact = create_setup_rollback_snapshot(_load_json_file(setup_overlay_path))
    errors = validate_setup_rollback_snapshot_artifact(snapshot_artifact)
    if errors:
        echo_stdout(_rollback_validation_report(errors))
        raise typer.Exit(1)
    if output is not None:
        write_setup_rollback_snapshot(snapshot_artifact, output)
    echo_stdout(dumps_setup_rollback_snapshot(snapshot_artifact))


@setup_app.command("validate-rollback-snapshot")
def validate_rollback_snapshot(
    path: Path = typer.Argument(..., help="Setup rollback snapshot JSON artifact path."),
) -> None:
    """Validate a passive setup rollback snapshot artifact."""
    errors = validate_setup_rollback_snapshot_file(path)
    echo_stdout(_rollback_validation_report(errors))
    if errors:
        raise typer.Exit(1)


@setup_app.command("apply")
def apply(
    setup_overlay_path: Path = typer.Argument(..., help="Setup overlay plan JSON artifact path."),
    rollback_snapshot: Path = typer.Option(
        ..., "--rollback-snapshot", help="Required rollback snapshot artifact path."
    ),
    approve_digest: str | None = typer.Option(
        None,
        "--approve-digest",
        help=(
            "Digest-bound approval matching overlay_plan_digest (scripted flows). "
            "When omitted, apply shows the digest and prompts for a typed digest prefix."
        ),
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Required explicit setup receipt output path."),
) -> None:
    """Apply only digest-approved declared setup writes and emit a setup receipt."""
    overlay_errors = validate_setup_overlay_plan_file(setup_overlay_path)
    rollback_errors = validate_setup_rollback_snapshot_file(rollback_snapshot)
    if overlay_errors or rollback_errors:
        echo_stdout(_overlay_validation_report(overlay_errors))
        echo_stdout(_rollback_validation_report(rollback_errors))
        raise typer.Exit(1)
    overlay = _load_json_file(setup_overlay_path)
    approval_mode = "explicit_digest_bound_cli_flag"
    if approve_digest is None:
        approve_digest, approval_mode = _digest_approval(
            str(overlay.get("overlay_plan_digest", "")),
            "overlay_plan_digest",
            point_id="setup.apply.overlay_digest",
            command="builder-setup apply",
        )
    try:
        receipt = apply_setup_overlay(
            overlay,
            _load_json_file(rollback_snapshot),
            approve_digest=approve_digest,
            receipt_output=output,
            approval_mode=approval_mode,
        )
    except SetupApplyError as exc:
        if exc.receipt is not None:
            echo_stdout(json_lib.dumps(exc.receipt, indent=2, sort_keys=True) + "\n")
        else:
            echo_stdout(str(exc) + "\n")
        raise typer.Exit(1)
    echo_stdout(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n")


@setup_app.command("validate-receipt")
def validate_receipt(
    path: Path = typer.Argument(..., help="Setup apply receipt JSON artifact path."),
) -> None:
    """Validate a setup apply receipt artifact."""
    errors = validate_setup_receipt_file(path)
    echo_stdout(_receipt_validation_report(errors))
    if errors:
        raise typer.Exit(1)


@setup_app.command("rollback")
def rollback(
    setup_receipt_path: Path = typer.Argument(..., help="Setup apply receipt JSON artifact path."),
    rollback_snapshot: Path = typer.Option(
        ..., "--rollback-snapshot", help="Required rollback snapshot artifact path."
    ),
    approve_digest: str | None = typer.Option(
        None,
        "--approve-digest",
        help=(
            "Digest-bound approval matching setup receipt digest (scripted flows). "
            "When omitted, rollback shows the digest and prompts for a typed digest prefix."
        ),
    ),
    output: Path = typer.Option(..., "--output", "-o", help="Required explicit setup rollback receipt output path."),
) -> None:
    """Rollback digest-approved setup writes and emit a setup rollback receipt."""
    receipt_errors = validate_setup_receipt_file(setup_receipt_path)
    rollback_errors = validate_setup_rollback_snapshot_file(rollback_snapshot)
    if receipt_errors or rollback_errors:
        echo_stdout(_receipt_validation_report(receipt_errors))
        echo_stdout(_rollback_validation_report(rollback_errors))
        raise typer.Exit(1)
    setup_receipt = _load_json_file(setup_receipt_path)
    approval_mode = "explicit_digest_bound_cli_flag"
    if approve_digest is None:
        approve_digest, approval_mode = _digest_approval(
            str(setup_receipt.get("receipt_digest", "")),
            "receipt_digest",
            point_id="setup.rollback.receipt_digest",
            command="builder-setup rollback",
        )
    try:
        receipt = execute_setup_rollback(
            setup_receipt,
            _load_json_file(rollback_snapshot),
            approve_digest=approve_digest,
            receipt_output=output,
            approval_mode=approval_mode,
        )
    except SetupRollbackError as exc:
        if exc.receipt is not None:
            echo_stdout(json_lib.dumps(exc.receipt, indent=2, sort_keys=True) + "\n")
        else:
            echo_stdout(str(exc) + "\n")
        raise typer.Exit(1)
    echo_stdout(json_lib.dumps(receipt, indent=2, sort_keys=True) + "\n")


@setup_app.command("validate-rollback-receipt")
def validate_rollback_receipt(
    path: Path = typer.Argument(..., help="Setup rollback receipt JSON artifact path."),
) -> None:
    """Validate a setup rollback receipt artifact."""
    errors = validate_setup_rollback_receipt_file(path)
    echo_stdout(_rollback_receipt_validation_report(errors))
    if errors:
        raise typer.Exit(1)


@setup_app.command("validate-onboarding-intent")
def validate_onboarding_intent(
    path: Path = typer.Argument(..., help="Onboarding intent report JSON artifact path."),
) -> None:
    """Validate an onboarding intent report artifact."""
    errors = validate_onboarding_intent_report_file(path)
    echo_stdout(_onboarding_intent_validation_report(errors))
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
        echo_stdout(json_lib.dumps(result.summary_dict(), indent=2, sort_keys=True) + "\n")
        raise typer.Exit(1)

    echo_stdout(json_lib.dumps(result.summary_dict(), indent=2, sort_keys=True) + "\n")
    echo_stdout("\nExact next commands:\n")
    echo_stdout(f"  {result.onboarding_intent['apply_command']}\n")
    echo_stdout(f"  {result.onboarding_intent['validate_receipt_command']}\n")


def setup_wizard_step_definitions():
    """The ``builder-setup wizard`` decisions: registry-rendered, prompt-validated (Ladder 5 PR-2).

    PR-1 ported these steps as-is, lie and all: the backend question transcribed 3 of the 8
    live registry backends and nothing was validated at the prompt, so ``openai`` was
    accepted while never offered and garbage surfaced late as an invalid artifact. Now the
    prompts render from the live registries at prompt time and every answer is validated at
    the prompt boundary by :func:`~builder_ii.init_decisions.validate_decision_value`,
    exactly as ``builder init`` has always done.

    Presentation decision, made deliberately: ``MODEL_ALIASES`` has 50 entries, and the
    alias question renders none of them (``render_options_in_question=False``). A truncated
    enumeration would be a subset claim -- the exact defect class this ladder fixes -- and a
    full enumeration is unusable on a prompt line. The registry is the source of truth
    either way: the step references it through ``options_provider``, a wrong answer is
    refused at the prompt with the full registry named in the error, and a ninth alias is
    offered/accepted with no wizard code change. ``builder init`` still enumerates all 50
    (pre-existing, characterized behavior); harmonizing it is an operator decision outside
    this PR.
    """
    from builder_ii.lifecycle.setup.init_decisions import prompted_decision_options_provider, validate_decision_value
    from builder_ii.lifecycle.setup.wizard_framework import WizardStep

    return (
        WizardStep(
            id="output_dir",
            question="Enter output directory for onboarding artifacts",
            validator=lambda value: validate_decision_value("output_dir", value),
            default=".builder/setup-artifacts",
            free_form=True,
        ),
        WizardStep(
            id="target_profile",
            question="Select target profile",
            options_provider=prompted_decision_options_provider("target_profile"),
            validator=lambda value: validate_decision_value("target_profile", value),
            default="generic",
        ),
        WizardStep(
            id="model_backend",
            question="Select local model backend",
            options_provider=prompted_decision_options_provider("model_backend"),
            validator=lambda value: validate_decision_value("model_backend", value),
            default="rapid-mlx",
        ),
        WizardStep(
            id="model_alias",
            question="Select primary model alias",
            options_provider=prompted_decision_options_provider("model_alias"),
            validator=lambda value: validate_decision_value("model_alias", value),
            default="phi-reasoning",
            render_options_in_question=False,
        ),
    )


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
    from builder_ii.lifecycle.setup.wizard_framework import WizardAborted, WizardEngine, run_typer_prompt_loop

    engine = WizardEngine(steps=setup_wizard_step_definitions())
    for step_id, provided in (
        ("output_dir", str(output_dir) if output_dir else None),
        ("target_profile", target_profile),
        ("model_backend", model_backend),
        ("model_alias", model_alias),
    ):
        if provided:
            engine.preanswer(step_id, provided)
    # strip_answers=False: this wizard has always taken prompt answers exactly as typed.
    # Prompt-boundary validation mirrors builder init: three attempts per step, every
    # rejection echoing the full registry, then a fail-closed abort with no artifacts.
    try:
        answers, _prompted_any = run_typer_prompt_loop(
            engine,
            prompt_fn=typer.prompt,
            invalid_echo=lambda error: console.print(f"[red]invalid answer:[/] {error}"),
            max_attempts=3,
            strip_answers=False,
        )
    except WizardAborted:
        console.print("[red]no valid answer after 3 attempts; aborting without writing artifacts[/]")
        raise typer.Exit(2) from None
    out_path = output_dir if output_dir else Path(answers["output_dir"])

    result = run_onboarding_pipeline(
        output_dir=out_path,
        onboarding_mode="wizard",
        root=root,
        target_profile=answers["target_profile"],
        model_backend=answers["model_backend"],
        model_alias=answers["model_alias"],
    )
    if not result.valid:
        echo_stdout(json_lib.dumps(result.summary_dict(), indent=2, sort_keys=True) + "\n")
        raise typer.Exit(1)

    echo_stdout(f"\nOnboarding Plan Generated Successfully!\nOutput Directory: {out_path}\n")
    echo_stdout(f"Setup Plan Digest:        {result.setup_plan['plan_digest']}\n")
    echo_stdout(f"Overlay Plan Digest:      {result.overlay_plan['overlay_plan_digest']}\n")
    echo_stdout(f"Rollback Snapshot Digest: {result.rollback_snapshot['snapshot_id']}\n")
    echo_stdout(
        f"\nExact next commands:\n  {result.onboarding_intent['apply_command']}\n  {result.onboarding_intent['validate_receipt_command']}\n"
    )
    echo_stdout("\nTo apply, run the printed builder-setup apply command after reviewing the overlay digest.\n")


if __name__ == "__main__":
    setup_app()
