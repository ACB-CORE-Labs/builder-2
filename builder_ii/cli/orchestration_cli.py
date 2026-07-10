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


@orchestration_app.command("lane-policy")
def lane_policy(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write the lane policy artifact JSON to this path"),
) -> None:
    """Render the governed orchestration lane policy artifact (derived from the fixed lane table)."""
    from builder_ii.orchestration_lane_policy import (
        create_orchestration_lane_policy_artifact,
        dumps_orchestration_lane_policy_artifact,
        validate_discharge_mechanisms_against_registry,
        validate_orchestration_lane_policy_artifact,
    )

    artifact = create_orchestration_lane_policy_artifact()
    errors = validate_orchestration_lane_policy_artifact(artifact)
    errors += validate_discharge_mechanisms_against_registry()
    if errors:
        for error in errors:
            console.print(f"[red]Lane policy error: {error}[/]")
        raise typer.Exit(1)

    serialized = dumps_orchestration_lane_policy_artifact(artifact)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        console.print(f"[green]Lane policy written to {output}[/]")
    else:
        console.out(serialized, end="")


@orchestration_app.command("validate-lane-policy")
def validate_lane_policy(
    path: Path = typer.Argument(..., help="Path to an orchestration lane policy JSON file"),
) -> None:
    """Validate a governed orchestration lane policy artifact file (schema + live registry linkage)."""
    from builder_ii.orchestration_lane_policy import (
        validate_discharge_mechanisms_against_registry,
        validate_orchestration_lane_policy_artifact_file,
    )

    errors = validate_orchestration_lane_policy_artifact_file(path)
    errors += validate_discharge_mechanisms_against_registry()
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Orchestration lane policy {path} is valid.[/]")


@orchestration_app.command("mint-obligation")
def mint_obligation(
    obligation_kind: str = typer.Option(
        ..., "--obligation-kind", help="planning_step | interactive_ops | model_call | mutation | verification"
    ),
    task: str = typer.Option(..., "--task", help="What the delegated subagent must do (<= 2000 chars)"),
    expected_kind: str = typer.Option(..., "--expected-kind", help="output_contract.expected_kind the discharge must produce"),
    subagent_profile: str = typer.Option(..., "--subagent-profile", help="Profile of the subagent that will hold this obligation"),
    lane_policy_path: Path = typer.Option(
        ...,
        "--lane-policy",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the lane policy artifact this obligation is minted under",
    ),
    seal_digest: Optional[str] = typer.Option(
        None, "--seal-digest", help="Root seal digest; mutually exclusive with --parent-obligation-digest"
    ),
    parent_obligation_digest: Optional[str] = typer.Option(
        None, "--parent-obligation-digest", help="Parent obligation digest; mutually exclusive with --seal-digest"
    ),
    lane: Optional[str] = typer.Option(
        None, "--lane", help="Override lane; if omitted, derived from the lane policy for --obligation-kind"
    ),
    required_evidence: Optional[str] = typer.Option(
        None, "--required-evidence", help="Comma-separated evidence kinds the discharge must attach"
    ),
    denied_action: Optional[str] = typer.Option(
        None, "--denied-action", help="Comma-separated actions denied to the subagent"
    ),
    refused_lane: Optional[str] = typer.Option(
        None, "--refused-lane", help="Comma-separated lanes explicitly refused (negative space)"
    ),
    file_ref: Optional[list[str]] = typer.Option(
        None, "--file-ref", help="Repeatable path=sha256 citation (never dump content)"
    ),
    briefing_bytes: int = typer.Option(
        0, "--briefing-bytes", help="Recorded serialized briefing size in bytes (must be <= --max-output-bytes)"
    ),
    max_subagents: int = typer.Option(0, "--max-subagents", help="Budget partition: max subagents this obligation may mint"),
    max_events: int = typer.Option(0, "--max-events", help="Budget partition: max ledger events"),
    max_output_bytes: int = typer.Option(0, "--max-output-bytes", help="Budget partition: max output bytes"),
    max_human_gates: int = typer.Option(0, "--max-human-gates", help="Budget partition: max human gates"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write the obligation JSON to this path"),
) -> None:
    """Mint a governed orchestration obligation artifact (Law 1: no speech without a ticket).

    The obligation is validated before it is emitted; the lane is derived from (and checked
    against) the supplied lane policy, and its digest is pinned into the obligation. No runtime
    enforcement of the budget envelope happens here — that is the seal/runner's job (PR-4).
    """
    from builder_ii.orchestration_lane_policy import (
        LanePolicyViolation,
        lane_for_obligation_kind,
        require_lane_match,
        validate_orchestration_lane_policy_artifact,
    )
    from builder_ii.orchestration_obligation import (
        create_orchestration_obligation,
        validate_orchestration_obligation,
    )

    if seal_digest is not None and parent_obligation_digest is not None:
        console.print("[red]--seal-digest and --parent-obligation-digest are mutually exclusive[/]")
        raise typer.Exit(1)
    if seal_digest is not None:
        parent_ref: dict[str, str] = {"seal_digest": seal_digest}
    elif parent_obligation_digest is not None:
        parent_ref = {"obligation_digest": parent_obligation_digest}
    else:
        console.print("[red]exactly one of --seal-digest or --parent-obligation-digest is required[/]")
        raise typer.Exit(1)

    policy = _read_json(lane_policy_path)
    policy_errors = validate_orchestration_lane_policy_artifact(policy)
    if policy_errors:
        for error in policy_errors:
            console.print(f"[red]invalid lane policy: {error}[/]")
        raise typer.Exit(1)
    lane_policy_digest = policy["lane_policy_digest"]

    try:
        resolved_lane = lane if lane is not None else lane_for_obligation_kind(obligation_kind)
        require_lane_match(obligation_kind, resolved_lane)
    except LanePolicyViolation as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    refs: list[dict[str, str]] = []
    for raw in file_ref or []:
        if "=" not in raw:
            console.print(f"[red]--file-ref must be path=sha256, got: {raw!r}[/]")
            raise typer.Exit(1)
        path_part, _, sha_part = raw.partition("=")
        refs.append({"path": path_part.strip(), "sha256": sha_part.strip()})

    def _split(raw: Optional[str]) -> list[str]:
        return [part.strip() for part in raw.split(",") if part.strip()] if raw else []

    try:
        obligation = create_orchestration_obligation(
            lane=resolved_lane,
            obligation_kind=obligation_kind,
            task=task,
            output_contract_expected_kind=expected_kind,
            output_contract_required_evidence_kinds=_split(required_evidence),
            denied_actions=_split(denied_action),
            refused_lanes=_split(refused_lane),
            file_refs=refs,
            briefing_bytes=briefing_bytes,
            budget_partition={
                "max_subagents": max_subagents,
                "max_events": max_events,
                "max_output_bytes": max_output_bytes,
                "max_human_gates": max_human_gates,
            },
            parent_ref=parent_ref,
            lane_policy_digest=lane_policy_digest,
            subagent_profile=subagent_profile,
        )
    except (ValueError, TypeError) as exc:
        console.print(f"[red]Error minting obligation: {exc}[/]")
        raise typer.Exit(1)

    errors = validate_orchestration_obligation(obligation)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error in minted obligation: {error}[/]")
        raise typer.Exit(1)

    serialized = json_lib.dumps(obligation, indent=2, sort_keys=True) + "\n"
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized, encoding="utf-8")
        console.print(f"[green]Obligation written to {output}[/]")
    else:
        console.out(serialized, end="")


@orchestration_app.command("validate-obligation")
def validate_obligation(
    path: Path = typer.Argument(..., help="Path to an orchestration obligation JSON file"),
) -> None:
    """Validate a governed orchestration obligation artifact file."""
    from builder_ii.orchestration_obligation import validate_orchestration_obligation_file

    errors = validate_orchestration_obligation_file(path)
    if errors:
        for error in errors:
            console.print(f"[red]Validation error: {error}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Orchestration obligation {path} is valid.[/]")


@orchestration_app.command("status")
def status(
    run_output_dir: Path = typer.Argument(
        ..., help="Output directory produced by `builder-deepagents run-approved --obligation ...`"
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write the status board as JSON to this path"),
) -> None:
    """Deterministic read-only obligation status board for one delegation run (Law 2 belief board).

    One row per obligation: board state (OPEN / SATISFIED / UNVERIFIED / VIOLATED / BLOCKED) plus
    the granted budget partition. No model, no execution, no writes. Exits non-zero on a broken or
    tampered event chain, or on missing run artifacts.
    """
    from builder_ii.orchestration_status import build_obligation_board, render_status_table

    try:
        board = build_obligation_board(run_output_dir)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_lib.dumps(board, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        console.print(f"[green]Status board written to {output}[/]")
    else:
        # A wide, un-color local console: the board can have long digests/kinds, and the shared
        # `console` defaults to a narrow width that wraps/truncates table cells unpredictably.
        Console(width=200).print(render_status_table(board))

    if not board["chain_valid"]:
        for error in board["chain_errors"]:
            console.print(f"[red]{error}[/]")
        raise typer.Exit(1)


@orchestration_app.command("why")
def why(
    artifact_path: Path = typer.Argument(
        ...,
        help="Path to one obligation lifecycle event JSON "
        "(obligation_minted / obligation_mint_refused / obligation_consumed) under a run's events/ directory",
    ),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write the belief trace as JSON to this path"),
) -> None:
    """Deterministic read-only belief trace for one obligation (Law 2: no belief without discharge).

    No model, no execution, no writes. Exits non-zero unless the obligation is CONTRACT_SATISFIED
    with an intact event chain.
    """
    from builder_ii.orchestration_status import build_belief_trace

    try:
        trace = build_belief_trace(artifact_path)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_lib.dumps(trace, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    # soft_wrap: the verdict line must stay a single unbroken line regardless of terminal width.
    console.print(trace["verdict_line"], soft_wrap=True)

    if not trace["chain_valid"]:
        for error in trace["chain_errors"]:
            console.print(f"[red]{error}[/]")
        raise typer.Exit(1)
    if not trace["believed"]:
        raise typer.Exit(1)


if __name__ == "__main__":
    orchestration_app()
