"""Passive WRP control-plane CLI — recommend/plan/validate only."""

from __future__ import annotations

import json as json_lib
from pathlib import Path
from typing import Any

import typer
from rich.console import Console

from builder_ii.cli.plain_stdout import echo_stdout
from builder_ii.wrp.adjoint_operator import adjoint_correct, simulate_epochs, validate_adjoint_correction
from builder_ii.wrp.allocation_optimizer import allocate_fleet, validate_fleet_allocation
from builder_ii.wrp.artifacts import write_wrp
from builder_ii.wrp.collaboration_planner import plan_collaboration, validate_collaboration_topology
from builder_ii.wrp.evaluator import create_proof_record, evaluate_trajectory, validate_trajectory_evaluation
from builder_ii.wrp.exchange import create_maker_candidate_manifest, write_exchange_package
from builder_ii.wrp.experience_store import create_experience_store, validate_experience_store
from builder_ii.wrp.forward_operator import forward_route, validate_forward_route
from builder_ii.wrp.governance_router import (
    create_default_msda_policy,
    evaluate_msda_gate,
    validate_msda_gate_decision,
    validate_msda_policy,
)
from builder_ii.wrp.patterns import sequential_chain
from builder_ii.wrp.subtask_graph import (
    create_subtask_graph,
    replay_graph_digests,
    validate_replay_report,
    validate_subtask_graph,
)
from builder_ii.wrp.workload_classifier import (
    classify_workload,
    score_classifier_fixtures,
    validate_workload_classification,
)

wrp_app = typer.Typer(
    help=(
        "WRP control plane: classify/plan/allocate/gate (passive) + "
        "S2 HITL live lane (run-approved) + P4 HITL R* φ apply (apply-rstar-approved)."
    ),
)
console = Console()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json_lib.loads(path.read_text(encoding="utf-8"))
    except json_lib.JSONDecodeError as exc:
        console.print(f"[red]invalid JSON in {path}: {exc}[/]")
        raise typer.Exit(1) from exc
    if not isinstance(data, dict):
        console.print(f"[red]{path} must contain a JSON object[/]")
        raise typer.Exit(1)
    return data


def _emit(data: dict[str, Any], output: Path | None) -> None:
    text = json_lib.dumps(data, indent=2, sort_keys=True) + "\n"
    if output is not None:
        write_wrp(data, output)
        console.print(f"[green]Wrote {output}[/]")
    else:
        echo_stdout(text)


@wrp_app.command("classify")
def classify_cmd(
    text: str = typer.Option(..., "--text", "-t", help="Free-text task to classify"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W0: classify workload → tier recommendation (no model execution)."""
    art = classify_workload(text=text)
    _emit(art, output)


@wrp_app.command("score-classifier")
def score_classifier_cmd(
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W0 acceptance: score golden fixtures (≥95% required)."""
    report = score_classifier_fixtures()
    _emit(report, output)
    if not report["meets_w0_threshold"]:
        console.print(f"[red]W0 threshold missed: accuracy={report['accuracy']:.3f}[/]")
        raise typer.Exit(1)
    console.print(f"[green]W0 accuracy={report['accuracy']:.3f} ({report['correct']}/{report['total']})[/]")


@wrp_app.command("plan-collab")
def plan_collab_cmd(
    task: str = typer.Option(..., "--task", "-t"),
    mode: str = typer.Option("standard", "--mode"),
    priority: int = typer.Option(1, "--priority"),
    security_sensitive: bool = typer.Option(False, "--security-sensitive"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W1: collaboration topology plan (UNBOUND)."""
    art = plan_collaboration(
        task=task,
        mode=mode,
        priority=priority,
        security_sensitive=security_sensitive,
    )
    _emit(art, output)


@wrp_app.command("allocate")
def allocate_cmd(
    tier: str = typer.Option("primary", "--tier"),
    token_budget: float = typer.Option(20.0, "--token-budget"),
    max_risk: str = typer.Option("local_network", "--max-risk"),
    non_trivial: bool = typer.Option(False, "--non-trivial"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W2: constrained fleet allocation recommendation."""
    art = allocate_fleet(
        task_tier=tier,
        token_budget=token_budget,
        max_risk=max_risk,
        non_trivial=non_trivial,
    )
    _emit(art, output)


@wrp_app.command("gate")
def gate_cmd(
    tool: str = typer.Option(..., "--tool"),
    data_domain: str = typer.Option(..., "--domain", "--data-domain"),
    policy: Path | None = typer.Option(None, "--policy", exists=True, dir_okay=False),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W3: MSDA access gate decision (validation only; never executes)."""
    pol = _read_json(policy) if policy else create_default_msda_policy()
    art = evaluate_msda_gate(tool=tool, data_domain=data_domain, policy=pol)
    _emit(art, output)
    if art["decision"]["effect"] == "deny":
        console.print("[yellow]gate decision: deny[/]")
    else:
        console.print("[green]gate decision: allow (still no execution authority)[/]")


@wrp_app.command("msda-policy")
def msda_policy_cmd(
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Emit default MSDA deny-by-default policy artifact."""
    _emit(create_default_msda_policy(), output)


@wrp_app.command("route")
def route_cmd(
    text: str = typer.Option(..., "--text", "-t"),
    token_budget: float = typer.Option(20.0, "--token-budget"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Compose forward operator R recommendation."""
    art = forward_route(text=text, token_budget=token_budget)
    _emit(art, output)


@wrp_app.command("evaluate")
def evaluate_cmd(
    trajectory_id: str = typer.Option(..., "--id"),
    success: bool = typer.Option(True, "--success/--fail"),
    safety_ok: bool = typer.Option(True, "--safety-ok/--safety-fail"),
    sequence_ok: bool = typer.Option(True, "--sequence-ok/--sequence-fail"),
    cost: float = typer.Option(1.0, "--cost"),
    budget: float = typer.Option(10.0, "--budget"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Evaluate a trajectory (validation artifact)."""
    art = evaluate_trajectory(
        trajectory_id=trajectory_id,
        success=success,
        safety_ok=safety_ok,
        sequence_ok=sequence_ok,
        cost_units=cost,
        budget_units=budget,
    )
    _emit(art, output)


@wrp_app.command("simulate-epochs")
def simulate_epochs_cmd(
    epochs: int = typer.Option(5, "--epochs"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W4: synthetic adjoint epoch harness."""
    report = simulate_epochs(epochs=epochs)
    # strip heavy store if writing summary only — keep store for validation demos
    payload = {
        "epoch_error_rates": report["epoch_error_rates"],
        "relative_reduction": report["relative_reduction"],
        "meets_w4_threshold": report["meets_w4_threshold"],
        "store_digest": report["store"]["digest"],
    }
    _emit(payload, output)
    if not report["meets_w4_threshold"]:
        console.print(f"[red]W4 threshold missed: reduction={report['relative_reduction']:.3f}[/]")
        raise typer.Exit(1)
    console.print(f"[green]W4 reduction={report['relative_reduction']:.3f}[/]")


@wrp_app.command("replay")
def replay_cmd(
    plan: Path = typer.Option(..., "--plan", exists=True, dir_okay=False),
    observed: Path = typer.Option(..., "--observed", exists=True, dir_okay=False, help="JSON list of {node_id,digest}"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W5: reconstructive replay validation."""
    planned = _read_json(plan)
    obs_raw = json_lib.loads(observed.read_text(encoding="utf-8"))
    if not isinstance(obs_raw, list):
        console.print("[red]observed must be a JSON list[/]")
        raise typer.Exit(1)
    art = replay_graph_digests(planned=planned, observed_chain=obs_raw)
    _emit(art, output)
    if not art.get("perfect_match"):
        console.print("[red]replay perfect_match=false[/]")
        raise typer.Exit(1)


@wrp_app.command("graph")
def graph_cmd(
    task: str = typer.Option(..., "--task", "-t"),
    nodes: str = typer.Option("maker_structural,maker_unit,governor_architecture", "--nodes"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Emit a planned subtask graph artifact."""
    node_list = [n.strip() for n in nodes.split(",") if n.strip()]
    art = create_subtask_graph(sequential_chain(node_list), task=task)
    _emit(art, output)


@wrp_app.command("plan-live")
def plan_live_cmd(
    task: str = typer.Option(..., "--task", "-t"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """S2: emit digest-bound live run plan (requires approve-live + run-approved)."""
    from builder_ii.wrp.allocation_optimizer import allocate_fleet
    from builder_ii.wrp.live_lane import build_live_run_plan
    from builder_ii.wrp.workload_classifier import classify_workload

    clf = classify_workload(text=task)
    fleet = allocate_fleet(task_tier=clf["classification"]["tier"] if clf["classification"]["tier"] != "primary_constrained" else "primary", token_budget=100.0)
    art = build_live_run_plan(
        task=task,
        fleet_binding=fleet.get("fleet_binding"),
        wrp_binding={
            "tier": clf["classification"]["tier"],
            "recommended_model_alias": clf["recommended_model_alias"],
            "classification_digest": clf["digest"],
        },
    )
    _emit(art, output)


@wrp_app.command("approve-live")
def approve_live_cmd(
    plan: Path = typer.Option(..., "--plan", exists=True, dir_okay=False),
    approved_by: str = typer.Option(..., "--approved-by"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """S2: emit HITL approval bound to plan digest (not authority by itself)."""
    from builder_ii.wrp.live_lane import build_live_run_approval

    plan_art = _read_json(plan)
    art = build_live_run_approval(plan=plan_art, approved_by=approved_by, approved=True)
    _emit(art, output)


@wrp_app.command("run-approved")
def run_approved_cmd(
    plan: Path = typer.Option(..., "--plan", exists=True, dir_okay=False),
    approval: Path = typer.Option(..., "--approval", exists=True, dir_okay=False),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """S2: run HITL live lane under approval + forced MSDA preflight (graph noop/record only)."""
    from builder_ii.wrp.live_lane import LiveLaneError, run_approved

    plan_art = _read_json(plan)
    approval_art = _read_json(approval)
    try:
        receipt = run_approved(plan=plan_art, approval=approval_art)
    except LiveLaneError as exc:
        console.print(f"[red]live lane refused: {exc}[/]")
        raise typer.Exit(1) from exc
    _emit(receipt, output)


@wrp_app.command("phi-policy-init")
def phi_policy_init_cmd(
    policy_id: str = typer.Option("default", "--policy-id"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """P4: emit version-0 φ-policy artifact (DEFAULT_PHI; not live routing)."""
    from builder_ii.wrp.rstar_apply import create_phi_policy

    _emit(create_phi_policy(policy_id=policy_id), output)


@wrp_app.command("corrections-from-receipts")
def corrections_from_receipts_cmd(
    store_path: Path = typer.Option(..., "--store", exists=True, dir_okay=False),
    receipts: Path = typer.Option(..., "--receipts", exists=True, dir_okay=False, help="JSON list of receipts"),
    store_out: Path | None = typer.Option(None, "--store-out"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write corrections JSON list"),
) -> None:
    """P4: map real receipts → experience store + R* correction artifacts (no φ apply)."""
    from builder_ii.wrp.rstar_apply import RStarApplyError, corrections_from_receipts

    store = _read_json(store_path)
    raw = json_lib.loads(receipts.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        console.print("[red]receipts must be a JSON list[/]")
        raise typer.Exit(1)
    try:
        updated, corrections = corrections_from_receipts(store, raw)
    except (RStarApplyError, ValueError) as exc:
        console.print(f"[red]receipt R* path refused: {exc}[/]")
        raise typer.Exit(1) from exc
    if store_out is not None:
        write_wrp(updated, store_out)
    payload = {
        "store_digest": updated.get("digest"),
        "store_version": updated.get("version"),
        "correction_count": len(corrections),
        "corrections": corrections,
    }
    _emit(payload, output)


@wrp_app.command("plan-rstar-apply")
def plan_rstar_apply_cmd(
    base_policy: Path = typer.Option(..., "--base-policy", exists=True, dir_okay=False),
    corrections: Path = typer.Option(
        ...,
        "--corrections",
        exists=True,
        dir_okay=False,
        help="JSON list of adjoint_correction artifacts (or object with corrections key)",
    ),
    experience_store: Path | None = typer.Option(None, "--store", exists=True, dir_okay=False),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """P4: emit digest-bound R* apply plan (requires approve-rstar-apply + apply-rstar-approved)."""
    from builder_ii.wrp.rstar_apply import RStarApplyError, build_rstar_apply_plan

    base = _read_json(base_policy)
    raw = json_lib.loads(corrections.read_text(encoding="utf-8"))
    if isinstance(raw, dict) and isinstance(raw.get("corrections"), list):
        corr_list = raw["corrections"]
    elif isinstance(raw, list):
        corr_list = raw
    else:
        console.print("[red]corrections must be a JSON list or object with corrections[][/]")
        raise typer.Exit(1)
    store = _read_json(experience_store) if experience_store is not None else None
    try:
        art = build_rstar_apply_plan(base_policy=base, corrections=corr_list, experience_store=store)
    except RStarApplyError as exc:
        console.print(f"[red]plan refused: {exc}[/]")
        raise typer.Exit(1) from exc
    _emit(art, output)


@wrp_app.command("approve-rstar-apply")
def approve_rstar_apply_cmd(
    plan: Path = typer.Option(..., "--plan", exists=True, dir_okay=False),
    approved_by: str = typer.Option(..., "--approved-by"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """P4: emit HITL approval bound to R* apply plan digest (not authority by itself)."""
    from builder_ii.wrp.rstar_apply import RStarApplyError, build_rstar_apply_approval

    plan_art = _read_json(plan)
    try:
        art = build_rstar_apply_approval(plan=plan_art, approved_by=approved_by, approved=True)
    except RStarApplyError as exc:
        console.print(f"[red]approval refused: {exc}[/]")
        raise typer.Exit(1) from exc
    _emit(art, output)


@wrp_app.command("apply-rstar-approved")
def apply_rstar_approved_cmd(
    plan: Path = typer.Option(..., "--plan", exists=True, dir_okay=False),
    approval: Path = typer.Option(..., "--approval", exists=True, dir_okay=False),
    policy_out: Path | None = typer.Option(None, "--policy-out", help="Write new versioned phi_policy"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write apply receipt"),
) -> None:
    """P4: apply HITL-approved R* plan → new versioned phi_policy (never mutates DEFAULT_PHI)."""
    from builder_ii.wrp.rstar_apply import RStarApplyError, apply_approved

    plan_art = _read_json(plan)
    approval_art = _read_json(approval)
    try:
        new_policy, receipt = apply_approved(plan=plan_art, approval=approval_art)
    except RStarApplyError as exc:
        console.print(f"[red]R* apply refused: {exc}[/]")
        raise typer.Exit(1) from exc
    if policy_out is not None:
        write_wrp(new_policy, policy_out)
    _emit(receipt, output)


@wrp_app.command("package-exchange")
def package_exchange_cmd(
    wave: str = typer.Option(..., "--wave"),
    branch: str = typer.Option("feat/wrp-control-plane", "--branch"),
    summary: str = typer.Option(..., "--summary"),
    root: Path = typer.Option(Path("artifacts/wrp_exchange"), "--root"),
    test_command: list[str] = typer.Option([], "--test-command"),
) -> None:
    """Write Maker exchange package for Antigravity Governor review."""
    manifest = create_maker_candidate_manifest(
        wave=wave,
        branch=branch,
        summary=summary,
        artifact_digests={},
        test_commands=test_command or ["uv run pytest tests/test_wrp_*.py -q"],
    )
    path = write_exchange_package(root, wave=wave, maker_manifest=manifest)
    console.print(f"[green]Exchange package at {path}[/]")


@wrp_app.command("validate")
def validate_cmd(
    path: Path = typer.Argument(..., exists=True, dir_okay=False, readable=True),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Validate any WRP artifact by kind."""
    data = _read_json(path)
    kind = data.get("kind")
    validators = {
        "builder_ii.wrp.workload_classification": validate_workload_classification,
        "builder_ii.wrp.collaboration_topology": validate_collaboration_topology,
        "builder_ii.wrp.fleet_allocation": validate_fleet_allocation,
        "builder_ii.wrp.msda_policy": validate_msda_policy,
        "builder_ii.wrp.msda_gate_decision": validate_msda_gate_decision,
        "builder_ii.wrp.experience_store": validate_experience_store,
        "builder_ii.wrp.subtask_graph": validate_subtask_graph,
        "builder_ii.wrp.trajectory_evaluation": validate_trajectory_evaluation,
        "builder_ii.wrp.forward_route": validate_forward_route,
        "builder_ii.wrp.adjoint_correction": validate_adjoint_correction,
        "builder_ii.wrp.replay_report": validate_replay_report,
        "builder_ii.wrp.live_run_plan": __import__(
            "builder_ii.wrp.live_lane", fromlist=["validate_live_run_plan"]
        ).validate_live_run_plan,
        "builder_ii.wrp.live_run_approval": __import__(
            "builder_ii.wrp.live_lane", fromlist=["validate_live_run_approval"]
        ).validate_live_run_approval,
        "builder_ii.wrp.live_run_receipt": __import__(
            "builder_ii.wrp.live_lane", fromlist=["validate_live_run_receipt"]
        ).validate_live_run_receipt,
        "builder_ii.wrp.phi_policy": __import__(
            "builder_ii.wrp.rstar_apply", fromlist=["validate_phi_policy"]
        ).validate_phi_policy,
        "builder_ii.wrp.rstar_apply_plan": __import__(
            "builder_ii.wrp.rstar_apply", fromlist=["validate_rstar_apply_plan"]
        ).validate_rstar_apply_plan,
        "builder_ii.wrp.rstar_apply_approval": __import__(
            "builder_ii.wrp.rstar_apply", fromlist=["validate_rstar_apply_approval"]
        ).validate_rstar_apply_approval,
        "builder_ii.wrp.rstar_apply_receipt": __import__(
            "builder_ii.wrp.rstar_apply", fromlist=["validate_rstar_apply_receipt"]
        ).validate_rstar_apply_receipt,
    }
    validator = validators.get(str(kind))
    if validator is None:
        # generic envelope via experience store's envelope helper
        from builder_ii.wrp.artifacts import validate_wrp_artifact_envelope

        errors = validate_wrp_artifact_envelope(data)
    else:
        errors = validator(data)

    report = {"valid": len(errors) == 0, "subject_kind": kind, "subject_path": str(path), "errors": errors}
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json_lib.dumps(report, indent=2) + "\n", encoding="utf-8")
    if errors:
        for err in errors:
            console.print(f"[red]Validation error: {err}[/]")
        raise typer.Exit(1)
    console.print(f"[green]Artifact {path} ({kind}) is valid.[/]")


@wrp_app.command("proof")
def proof_cmd(
    proof_class: str = typer.Option(..., "--class", help="R | D | U"),
    claim: str = typer.Option(..., "--claim"),
    held: bool = typer.Option(True, "--held/--not-held"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Emit a Class R/D/U proof record (validation only)."""
    art = create_proof_record(proof_class=proof_class, claim=claim, held=held)
    _emit(art, output)


@wrp_app.command("experience-init")
def experience_init_cmd(
    store_id: str = typer.Option("default", "--store-id"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Create an empty experience store artifact."""
    _emit(create_experience_store(store_id=store_id), output)


@wrp_app.command("adjoint")
def adjoint_cmd(
    store_path: Path = typer.Option(..., "--store", exists=True, dir_okay=False),
    trajectory_id: str = typer.Option(..., "--trajectory-id"),
    success: bool = typer.Option(True, "--success/--fail"),
    error_signal: float = typer.Option(0.0, "--error-signal"),
    store_out: Path | None = typer.Option(None, "--store-out"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """Record R* adjoint correction (does not update live routing)."""
    store = _read_json(store_path)
    updated, correction = adjoint_correct(
        store=store,
        trajectory_id=trajectory_id,
        success=success,
        error_signal=error_signal,
    )
    if store_out is not None:
        write_wrp(updated, store_out)
    _emit(correction, output)
