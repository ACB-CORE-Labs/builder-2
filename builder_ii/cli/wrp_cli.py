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
    help="WRP control plane (passive): classify, plan, allocate, gate, evaluate, replay, validate.",
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
