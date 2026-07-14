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
    planned_commit: str | None = typer.Option(None, "--planned-commit", help="W5 planned commit_id override"),
    planned_tree: str | None = typer.Option(None, "--planned-tree", help="W5 planned tree_hash override"),
    observed_commit: str | None = typer.Option(None, "--observed-commit", help="W5 observed commit_id"),
    observed_tree: str | None = typer.Option(None, "--observed-tree", help="W5 observed tree_hash"),
    bind_repo: bool = typer.Option(False, "--bind-repo/--no-bind-repo", help="Capture cwd git state as observed"),
) -> None:
    """W5: reconstructive replay validation (digests + optional repo commit/tree)."""
    planned = _read_json(plan)
    obs_raw = json_lib.loads(observed.read_text(encoding="utf-8"))
    if not isinstance(obs_raw, list):
        console.print("[red]observed must be a JSON list[/]")
        raise typer.Exit(1)

    planned_repo: dict[str, Any] | None = None
    if planned_commit is not None or planned_tree is not None:
        planned_repo = {
            "commit_id": planned_commit,
            "tree_hash": planned_tree,
            "is_git_tree": bool(planned_commit or planned_tree),
            "source": "cli",
        }

    observed_repo: dict[str, Any] | None = None
    if bind_repo:
        from builder_ii.wrp.repo_state import capture_repo_state

        observed_repo = capture_repo_state()
    elif observed_commit is not None or observed_tree is not None:
        observed_repo = {
            "commit_id": observed_commit,
            "tree_hash": observed_tree,
            "is_git_tree": bool(observed_commit or observed_tree),
            "source": "cli",
        }

    art = replay_graph_digests(
        planned=planned,
        observed_chain=obs_raw,
        planned_repo_state=planned_repo,
        observed_repo_state=observed_repo,
    )
    _emit(art, output)
    if not art.get("perfect_match"):
        console.print(
            f"[red]replay perfect_match=false "
            f"(digest_ok={art.get('digest_sequence_ok')} "
            f"repo_match={art.get('repo_state_match')} mode={art.get('repo_state_mode')})[/]"
        )
        raise typer.Exit(1)
    console.print(
        f"[green]replay perfect_match=true mode={art.get('repo_state_mode')}[/]"
    )


@wrp_app.command("graph")
def graph_cmd(
    task: str = typer.Option(..., "--task", "-t"),
    nodes: str = typer.Option("maker_structural,maker_unit,governor_architecture", "--nodes"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    bind_repo: bool = typer.Option(False, "--bind-repo/--no-bind-repo", help="Embed cwd commit_id/tree_hash"),
) -> None:
    """Emit a planned subtask graph artifact (optional W5 repo-state bind)."""
    node_list = [n.strip() for n in nodes.split(",") if n.strip()]
    repo_state = None
    if bind_repo:
        from builder_ii.wrp.repo_state import capture_repo_state

        repo_state = capture_repo_state()
    art = create_subtask_graph(sequential_chain(node_list), task=task, repo_state=repo_state)
    _emit(art, output)


@wrp_app.command("langgraph-project")
def langgraph_project_cmd(
    nodes: str = typer.Option("a,b,c", "--nodes"),
    output: Path | None = typer.Option(None, "--output", "-o"),
    compile_graph: bool = typer.Option(False, "--compile/--project-only", help="Opt-in compile (needs env+pkg)"),
) -> None:
    """P6: pure LangGraph-shaped projection (optional compile is fail-closed)."""
    from builder_ii.wrp.langgraph_adapter import BackendUnavailableError, OptionalLangGraphAdapter
    from builder_ii.wrp.patterns import sequential_chain

    node_list = [n.strip() for n in nodes.split(",") if n.strip()]
    adapter = OptionalLangGraphAdapter()
    graph = sequential_chain(node_list)
    if compile_graph:
        try:
            art = adapter.compile(graph)
        except BackendUnavailableError as exc:
            console.print(f"[red]langgraph compile fail-closed: {exc}[/]")
            raise typer.Exit(1) from exc
    else:
        art = adapter.project(graph)
    _emit(art, output)


@wrp_app.command("vllm-profile")
def vllm_profile_cmd(
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """P6: emit vLLM research profile status (never starts an engine)."""
    from builder_ii.wrp.vllm_profile import profile_status

    art = profile_status()
    _emit(art, output)
    if art.get("default_runtime") is not False:
        console.print("[red]vLLM profile incorrectly claims default runtime[/]")
        raise typer.Exit(1)
    console.print("[green]vLLM research profile status (stub; not default runtime)[/]")


@wrp_app.command("opa-eval")
def opa_eval_cmd(
    tool: str = typer.Option(..., "--tool"),
    data_domain: str = typer.Option(..., "--domain", "--data-domain"),
    policy: Path | None = typer.Option(None, "--policy", exists=True, dir_okay=False),
    backend: str = typer.Option("python", "--backend", help="python | opa"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """P6: MSDA eval via pure Python (default) or optional opa binary."""
    from builder_ii.wrp.opa_adapter import BackendUnavailableError, OpaEvalAdapter, eval_msda_python

    pol = _read_json(policy) if policy else create_default_msda_policy()
    request = {"tool": tool, "data_domain": data_domain, "risk": "local_offline"}
    if backend == "python":
        art = eval_msda_python(pol, request)
    elif backend == "opa":
        try:
            art = OpaEvalAdapter().eval(pol, request)
        except BackendUnavailableError as exc:
            console.print(f"[red]opa backend fail-closed: {exc}[/]")
            raise typer.Exit(1) from exc
    else:
        console.print("[red]--backend must be python or opa[/]")
        raise typer.Exit(1)
    _emit(art, output)


@wrp_app.command("embed-status")
def embed_status_cmd(
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """P6: report active embedder resolution (hash default; modernbert opt-in)."""
    from builder_ii.wrp.embedding_backend import (
        MODERNBERT_ENV,
        MODERNBERT_ENV_VALUE,
        modernbert_opt_in_enabled,
        resolve_embedder,
    )

    backend = resolve_embedder()
    art = {
        "backend_name": backend.name,
        "modernbert_opt_in": modernbert_opt_in_enabled(),
        "env": MODERNBERT_ENV,
        "env_value_for_opt_in": MODERNBERT_ENV_VALUE,
        "is_default_hashing": backend.name == "hashing",
        "grants_authority": False,
    }
    _emit(art, output)


@wrp_app.command("repo-state")
def repo_state_cmd(
    cwd: Path | None = typer.Option(None, "--cwd", exists=True, file_okay=False),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W5: capture commit_id + tree_hash (honest nulls when not a git tree)."""
    from builder_ii.wrp.repo_state import capture_repo_state

    art = capture_repo_state(cwd)
    _emit(art, output)


@wrp_app.command("handoff-measure")
def handoff_measure_cmd(
    iterations: int = typer.Option(20, "--iterations", min=1, max=200),
    threshold_ms: float = typer.Option(50.0, "--threshold-ms"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """W1: measure pure local handoff overhead (zero-loss + &lt;50ms local path)."""
    from builder_ii.wrp.collaboration_planner import measure_handoff_overhead

    art = measure_handoff_overhead(iterations=iterations, threshold_ms=threshold_ms)
    _emit(art, output)
    if not art.get("meets_threshold"):
        console.print(
            f"[red]handoff median_ms={art.get('median_ms')} "
            f">= threshold_ms={threshold_ms} (scope={art.get('scope')})[/]"
        )
        raise typer.Exit(1)
    console.print(
        f"[green]handoff median_ms={art.get('median_ms')} "
        f"p95={art.get('p95_ms')} zero_loss={art.get('zero_loss')}[/]"
    )


@wrp_app.command("plan-agent-lifecycle")
def plan_agent_lifecycle_cmd(
    roles: str = typer.Option(
        "maker_structural,governor_architecture",
        "--roles",
        help="Comma-separated agent roles (plan only; spawn_permitted=false)",
    ),
    action: str = typer.Option("register_plan", "--action", help="register_plan | retire_plan"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """AgentFactory: emit lifecycle plan only (no spawn)."""
    from builder_ii.wrp.agent_factory import plan_agent_lifecycle
    from builder_ii.wrp.spaces import AgentPoint

    role_list = [r.strip() for r in roles.split(",") if r.strip()]
    if not role_list:
        console.print("[red]--roles must be non-empty[/]")
        raise typer.Exit(1)
    agents = [
        AgentPoint(
            role=role,
            reasoning_coverage=0.7,
            tool_coverage=0.5,
            model_family="plan-only",
            platform="maker" if role.startswith("maker") else "governor",
        )
        for role in role_list
    ]
    try:
        art = plan_agent_lifecycle(agents=agents, action=action)
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(1) from exc
    _emit(art, output)
    if art.get("spawn_permitted") is not False:
        console.print("[red]spawn_permitted must be false[/]")
        raise typer.Exit(1)


@wrp_app.command("msda-status")
def msda_status_cmd(
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """H9 honesty: report global MSDA preflight env state (default off; live lane forced)."""
    from builder_ii.wrp.msda_preflight import msda_preflight_status

    art = msda_preflight_status()
    _emit(art, output)
    if art.get("global_env_enabled"):
        console.print("[yellow]MSDA preflight env is ON (global opt-in)[/]")
    else:
        console.print(
            "[green]MSDA preflight env is OFF (default); live lane / gateway nodes still force on[/]"
        )


@wrp_app.command("backends")
def backends_cmd(
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """P6.1: list WRP backend inventory (defaults + opt-in; no engine start)."""
    from builder_ii.wrp.backend_registry import list_backends

    art = {
        "kind": "builder_ii.wrp.backend_inventory",
        "schema_version": 1,
        "grants_authority": False,
        "s4_promoted": False,
        "backends": list_backends(),
    }
    _emit(art, output)
    console.print(f"[green]backends listed: {len(art['backends'])} (inventory only)[/]")


@wrp_app.command("doctor-backends")
def doctor_backends_cmd(
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """P6.1: doctor WRP backends (M1 defaults must be healthy; opt-in may be unavailable)."""
    from builder_ii.wrp.backend_registry import doctor_backends

    art = doctor_backends()
    _emit(art, output)
    if not art.get("ok"):
        console.print("[red]doctor-backends: default runtime path unhealthy[/]")
        raise typer.Exit(1)
    console.print(
        f"[green]doctor-backends ok={art.get('ok')} "
        f"defaults={art.get('defaults')} unavailable_opt_in={art.get('unavailable')}[/]"
    )


@wrp_app.command("plan-live")
def plan_live_cmd(
    task: str = typer.Option(..., "--task", "-t"),
    s2_version: str = typer.Option("v1", "--s2-version", help="v1 graph-only | v2 gateway nodes"),
    gateway_mode: str = typer.Option("record", "--gateway-mode", help="record | stub_tool (v2 only)"),
    output: Path | None = typer.Option(None, "--output", "-o"),
) -> None:
    """S2: emit digest-bound live run plan (requires approve-live + run-approved)."""
    from builder_ii.wrp.allocation_optimizer import allocate_fleet
    from builder_ii.wrp.live_lane import LiveLaneError, build_live_run_plan
    from builder_ii.wrp.workload_classifier import classify_workload

    clf = classify_workload(text=task)
    fleet = allocate_fleet(task_tier=clf["classification"]["tier"] if clf["classification"]["tier"] != "primary_constrained" else "primary", token_budget=100.0)
    try:
        art = build_live_run_plan(
            task=task,
            fleet_binding=fleet.get("fleet_binding"),
            wrp_binding={
                "tier": clf["classification"]["tier"],
                "recommended_model_alias": clf["recommended_model_alias"],
                "classification_digest": clf["digest"],
            },
            s2_version=s2_version,
            gateway_mode=gateway_mode,
        )
    except LiveLaneError as exc:
        console.print(f"[red]plan refused: {exc}[/]")
        raise typer.Exit(1) from exc
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


@wrp_app.command("benchmark")
def benchmark_cmd(
    proof_class: str = typer.Option("u", "--class", help="Only 'u' (Class U) is supported"),
    target: str = typer.Option("builder", "--target", help="builder | generic | core"),
    iterations: int = typer.Option(1, "--iterations", min=1, max=20),
    output: Path | None = typer.Option(None, "--output", "-o", help="Write class_u_report JSON"),
    proof_out: Path | None = typer.Option(None, "--proof-out", help="Write proof_record U JSON"),
    measurements_out: Path | None = typer.Option(
        None, "--measurements-out", help="Write performance_measurement list JSON"
    ),
) -> None:
    """P5: Class U engineering-utility harness (measured numbers; no S3 enablement)."""
    from builder_ii.wrp.class_u_harness import run_class_u_harness

    if str(proof_class).strip().lower() not in {"u", "class_u", "class-u"}:
        console.print("[red]Only --class u is supported for builder-wrp benchmark[/]")
        raise typer.Exit(1)
    try:
        result = run_class_u_harness(target=target, iterations=iterations)
    except ValueError as exc:
        console.print(f"[red]benchmark refused: {exc}[/]")
        raise typer.Exit(1) from exc

    report = result["report"]
    _emit(report, output)
    if proof_out is not None:
        write_wrp(result["proof"], proof_out)
    if measurements_out is not None:
        measurements_out.parent.mkdir(parents=True, exist_ok=True)
        measurements_out.write_text(
            json_lib.dumps(result["measurements"], indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    summary = report.get("summary") or {}
    held = summary.get("proof_u_held")
    console.print(
        f"[cyan]Class U[/] pass_ratio={summary.get('pass_ratio')} "
        f"record_ms={summary.get('record_wall_ms_median')} "
        f"stub_ms={summary.get('stub_wall_ms_median')} "
        f"peak_rss_mb={summary.get('peak_rss_mb')} "
        f"proof_u_held={held}"
    )
    if not result.get("utility_ok"):
        console.print("[red]Class U utility thresholds not met (report still written)[/]")
        raise typer.Exit(1)
    console.print("[green]Class U utility_ok=true[/]")


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
        "builder_ii.wrp.class_u_report": __import__(
            "builder_ii.wrp.class_u_harness", fromlist=["validate_class_u_report"]
        ).validate_class_u_report,
        "builder_ii.wrp.agent_factory_plan": __import__(
            "builder_ii.wrp.agent_factory", fromlist=["validate_agent_factory_plan"]
        ).validate_agent_factory_plan,
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
