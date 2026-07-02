from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import hashlib
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.backends import check_health, check_serves_active_model, list_start_command
from builder_ii.benchmark import format_benchmark_report, run_benchmark, write_benchmark_report
from builder_ii.capabilities import capability_gates
from builder_ii.command_authority import enforce_command_authority
from builder_ii.compliance import run_compliance_checks
from builder_ii.config import BACKENDS, MODEL_TIERS, load_settings, normalize_model_alias
from builder_ii.goose_launcher import (
    find_goose_binary,
    goose_status,
    launch_goose_session,
    pull_models,
)
from builder_ii.goose_recipe_validation import validate_recipes
from builder_ii.goose_setup import (
    legacy_setup_redirect_payload,
    render_legacy_setup_redirect_text,
)
from builder_ii.harness import format_verify_report, run_verification
from builder_ii.init_content import CORE_INIT_SYSTEM_PROMPT, estimate_tokens
from builder_ii.model_router import SESSION_MODES, explain_plan, plan_session, tier_for_alias
from builder_ii.models import model_definitions, model_status_report
from builder_ii.model_client_registry import create_model_client_registry
from builder_ii.model_execution_gateway import ModelExecutionGateway
from builder_ii.model_routing_policy import create_model_execution_policy
from builder_ii.ledger_cli import ledger_app
from builder_ii.workflow_cli import workflow_app
from builder_ii.tools_cli import tools_app
from builder_ii.mcp_cli import mcp_app

app = typer.Typer(
    name="builder",
    help="builder-II — Generic governed platform for local agent-assisted development.",
    no_args_is_help=True,
)
console = Console()

app.add_typer(workflow_app, name="workflow")
app.add_typer(ledger_app, name="ledger")
app.add_typer(tools_app, name="tools")
app.add_typer(mcp_app, name="mcp")


def _backend_ready_for_selected_model(settings) -> tuple[bool, str]:
    ok, msg = check_health(settings)
    if not ok:
        return False, msg

    model_ok, model_msg = check_serves_active_model(settings)
    if not model_ok:
        return False, model_msg

    return True, f"{msg}; {model_msg}"


def _ensure_backend(settings, no_backend: bool) -> None:
    if no_backend:
        return

    health_ok, health_msg = check_health(settings)
    if health_ok:
        model_ok, model_msg = check_serves_active_model(settings)
        if model_ok:
            console.print(f"[green]Backend ready[/] {health_msg}; {model_msg}")
            return
        console.print(f"[red]Backend model mismatch[/] {model_msg}")
        raise typer.Exit(1)

    console.print(f"[yellow]Starting backend[/] ({health_msg})")
    cmd = list(list_start_command(settings))
    console.print(f"  {' '.join(cmd)}")
    subprocess.Popen(cmd)
    last_msg = health_msg
    for _ in range(90):
        time.sleep(2)
        ready, msg = _backend_ready_for_selected_model(settings)
        last_msg = msg
        if ready:
            console.print(f"[green]Backend ready[/] {msg}")
            return
    console.print(f"[red]Backend did not become ready in 180s[/] {last_msg}")
    raise typer.Exit(1)


@app.command("setup")
def setup() -> None:
    """Legacy compatibility wrapper for the governed R1 setup path."""
    settings = load_settings()
    console.out(render_legacy_setup_redirect_text(settings), end="")
    raise typer.Exit(1)


@app.command("onboarding")
def onboarding(
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Output directory for onboarding artifacts."),
    root: Path = typer.Option(Path.cwd(), "--root", help="Project root for configuration resolution."),
    target_profile: Optional[str] = typer.Option(None, "--target-profile", help="Target profile override."),
    model_backend: Optional[str] = typer.Option(None, "--model-backend", help="Model backend override."),
    model_alias: Optional[str] = typer.Option(None, "--model-alias", help="Model alias override."),
) -> None:
    """Interactive guided onboarding wizard flow (delegates to builder-setup wizard)."""
    from builder_ii.setup_cli import setup_wizard
    setup_wizard(
        output_dir=output_dir,
        root=root,
        target_profile=target_profile,
        model_backend=model_backend,
        model_alias=model_alias,
    )



@app.command("pull")
def pull(
    tier: str = typer.Option("recommended", "--tier", "-t", help="recommended|fast|primary|all-safe|status|legacy"),
) -> None:
    """Download/cache local models. Prefer scripts/pull-roster.sh for MLX-LM."""
    enforce_command_authority("builder pull", requested_effects=("external_tool", "state_write"))
    settings = load_settings()
    script = settings.project_root / "scripts" / "pull-roster.sh"
    if script.exists() and tier != "legacy":
        proc = subprocess.run(["bash", str(script), tier])
        raise typer.Exit(proc.returncode)
    for line in pull_models(settings):
        console.print(line)


@app.command("start")
def start(
    mode: str = typer.Option("orchestrator", "--mode", "-m", help="orchestrator|quick|deep|coding"),
    task_hint: Optional[str] = typer.Option(None, "--task", "--task-hint", help="Free-text task used to choose the M1-safe model alias for this session"),
    model_alias: Optional[str] = typer.Option(None, "--model", help="Explicit model alias override; see `builder models`"),
    resume: bool = typer.Option(False, "--resume", "-r"),
    no_backend: bool = typer.Option(False, "--no-backend"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Goose session name"),
) -> None:
    """Start MLX backend + Goose session with governed CORE recipes."""
    enforce_command_authority("builder start", requested_effects=("runtime_start", "state_write", "external_tool"))
    if mode not in SESSION_MODES:
        console.print(f"mode must be one of {SESSION_MODES}")
        raise typer.Exit(1)

    session = plan_session(mode, task_hint or "")
    selected_alias = normalize_model_alias(model_alias or session.model_alias, tier_fallback=session.model_tier)

    os.environ["CORE_AGENT_MODEL_TIER"] = session.model_tier
    os.environ["CORE_AGENT_MODEL_ALIAS"] = selected_alias
    settings = load_settings()

    console.print("[bold]Builder routing[/]")
    console.print(explain_plan(session))
    if selected_alias != session.model_alias:
        console.print(f"Model override : {selected_alias}")
    console.print(f"[bold]Builder[/] mode={session.mode} alias={settings.model_alias} tier={session.model_tier} backend={settings.backend} model={settings.active_model_id}")
    console.print(goose_status())

    _ensure_backend(settings, no_backend)

    console.print(f"CORE repo: {settings.core_repo}")
    console.print("Slash commands: /explore /implement /review /verify /handoff /plan /coding /platform")
    console.print("Skills: core-governed-coding, core-verify-loop, core-pre-edit-sweep, core-handoff")
    proc = launch_goose_session(settings, resume=resume, session=session, name=name)
    proc.wait()


@app.command("ask")
def ask(
    prompt: str = typer.Option(..., "--prompt", "-p", help="Prompt for the selected local model"),
    model_alias: Optional[str] = typer.Option(None, "--model", help="Explicit model alias; see `builder models`"),
    system_prompt: str = typer.Option("You are a local builder-II review assistant. Answer from the prompt only and state uncertainty clearly.", "--system"),
    max_tokens: int = typer.Option(512, "--max-tokens", min=1, max=4096),
    timeout: float = typer.Option(120.0, "--timeout", min=1.0),
    no_backend: bool = typer.Option(False, "--no-backend"),
) -> None:
    """Ask the selected local model directly through /v1/chat/completions."""
    enforce_command_authority("builder ask", requested_effects=("model_execution", "artifact_write"))
    if model_alias:
        selected_alias = normalize_model_alias(model_alias)
        os.environ["CORE_AGENT_MODEL_ALIAS"] = selected_alias
        os.environ["CORE_AGENT_MODEL_TIER"] = tier_for_alias(selected_alias)

    settings = load_settings()
    console.print(f"[bold]Builder ask[/] alias={settings.model_alias} backend={settings.backend} model={settings.active_model_id}")
    _ensure_backend(settings, no_backend)

    registry = create_model_client_registry()
    active_model = settings.active_model_id
    active_client = None
    for client in registry["clients"]:
        if client.get("model_id") == active_model:
            client["enabled"] = True
            active_client = client
            break
    if active_client is None:
        console.print(f"[red]Active model is not registered[/] {active_model}")
        raise typer.Exit(1)

    recommendation = {
        "kind": "builder_ii.model_routing_recommendation",
        "recommended_candidates": [
            {
                "model_id": active_model,
                "provider_id": active_client.get("provider_id"),
                "client_id": active_client.get("client_id"),
                "risk_classification": active_client.get("risk_classification"),
            }
        ],
    }
    execution_policy = create_model_execution_policy(recommendation, max_tokens=max_tokens)
    ask_root = settings.project_root / ".builder" / "ask"
    session_id = hashlib.sha256(f"{time.time_ns()}:{prompt}".encode("utf-8")).hexdigest()[:16]
    envelope_path = ask_root / f"{session_id}.envelope.json"
    receipt_path = ask_root / f"{session_id}.receipt.json"

    try:
        _envelope, receipt = ModelExecutionGateway(settings, registry, execution_policy).run_model_call(
            model_id=active_model,
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=None,
            envelope_path=envelope_path,
            receipt_path=receipt_path,
        )
    except Exception as exc:
        console.print(f"[red]Governed ask failed[/] {exc}")
        raise typer.Exit(1)
    console.print(receipt.get("response_text", ""))


@app.command("verify")
def verify(module: Optional[str] = typer.Argument(None), suite: Optional[str] = typer.Option(None, "--suite", "-s"), fail_fast: bool = typer.Option(False, "--fail-fast", "-x")) -> None:
    """Run CORE verification harness."""
    enforce_command_authority("builder verify", requested_effects=("readonly_subprocess", "external_tool"))
    settings = load_settings()
    result = run_verification(settings, module=module, suite=suite, fail_fast=fail_fast)
    console.print(format_verify_report(result))
    raise typer.Exit(0 if result.passed else 1)


@app.command("benchmark")
def benchmark(output: Optional[Path] = typer.Option(None, "--output", "-o")) -> None:
    """Benchmark TTFT, tool-calling, compliance, memory."""
    effects = ("model_execution", "external_tool") + (("artifact_write",) if output else ())
    enforce_command_authority("builder benchmark", requested_effects=effects)
    settings = load_settings()
    report = run_benchmark(settings)
    console.print(format_benchmark_report(report))
    if output:
        write_benchmark_report(report, output)
    raise typer.Exit(0)


@app.command("capabilities")
def capabilities(chat: bool = typer.Option(False, "--chat", help="Run a live /v1/chat/completions smoke")) -> None:
    """Check local model capability gates without modifying CORE."""
    effects = ("external_tool",) + (("model_execution",) if chat else ())
    enforce_command_authority("builder capabilities", requested_effects=effects)
    settings = load_settings()
    table = Table("Gate", "Result", "Details")
    gates = capability_gates(settings, run_chat_smoke=chat)
    for gate in gates:
        table.add_row(gate.name, gate.result, gate.details)
    console.print(table)
    raise typer.Exit(1 if any(gate.result == "FAIL" for gate in gates) else 0)


@app.command("switch-model")
def switch_model(alias: str = typer.Argument(..., help="Model alias or legacy tier; run `builder models`"), backend: Optional[str] = typer.Option(None, "--backend", "-b")) -> None:
    """Print .env lines to switch model alias/tier. Restart backend after."""
    enforce_command_authority("builder switch-model")
    if alias in MODEL_TIERS:
        normalized = normalize_model_alias(None, tier_fallback=alias)
        tier = alias
    else:
        normalized = normalize_model_alias(alias)
        tier = "fast" if normalized in {"phi-reasoning", "gemma-fast"} else "primary"
    if backend and backend not in BACKENDS:
        console.print(f"backend must be one of {BACKENDS}")
        raise typer.Exit(1)
    lines = [f"CORE_AGENT_MODEL_ALIAS={normalized}", f"CORE_AGENT_MODEL_TIER={tier}"]
    if backend:
        lines.append(f"CORE_AGENT_BACKEND={backend}")
    lines.append("# Then: builder start --task 'describe the work'  (or restart backend/session)")
    console.print("\n".join(lines))


@app.command("models")
def models() -> None:
    """Show the configured model roster and cache status."""
    enforce_command_authority("builder models", requested_effects=("readonly_subprocess",))
    settings = load_settings()
    status_by_alias = {m.alias: m for m in model_status_report(settings)}
    table = Table("Alias", "Tier", "Policy", "Repo", "Cache", "Expected", "Note")
    for definition in model_definitions(settings):
        status = status_by_alias[definition.alias]
        cache = "COMPLETE" if status.likely_complete else ("PARTIAL" if status.cache_dir else "MISSING")
        if status.has_incomplete:
            cache += "/RESUMABLE"
        table.add_row(definition.alias, definition.tier, definition.policy, definition.hf_repo, f"{cache} {status.size_gb}GB", f"~{definition.expected_gb}GB", definition.note)
    console.print(table)
    console.print("\nDownload: bash scripts/pull-roster.sh recommended | alias <name> | all-safe | candidates")


@app.command("doctor")
def doctor() -> None:
    """Run a local platform readiness check without editing CORE."""
    enforce_command_authority("builder doctor", requested_effects=("readonly_subprocess", "external_tool"))
    settings = load_settings()
    failures: list[str] = []
    table = Table("Check", "Result", "Details")

    core_ok = settings.core_repo.exists() and (settings.core_repo / ".git").exists()
    table.add_row("CORE repo", "PASS" if core_ok else "FAIL", str(settings.core_repo))
    if not core_ok:
        failures.append("CORE repo path is missing or not a git repository")

    goose_ok = find_goose_binary() is not None
    table.add_row("Goose", "PASS" if goose_ok else "WARN", goose_status())

    backend_ok, backend_msg = check_health(settings)
    table.add_row("Backend", "PASS" if backend_ok else "WARN", backend_msg)

    if backend_ok:
        served_ok, served_msg = check_serves_active_model(settings)
        table.add_row("Served model", "PASS" if served_ok else "WARN", served_msg)
    else:
        table.add_row("Served model", "WARN", "backend not running; run builder start to serve selected model")

    compliance = run_compliance_checks()
    compliance_ok = compliance.init_literals_ok and compliance.refusal_probe_ok
    table.add_row("Compliance", "PASS" if compliance_ok else "FAIL", f"literals={compliance.init_literals_ok} refusal={compliance.refusal_probe_ok}")
    if not compliance_ok:
        failures.append("governed prompt/refusal compliance check failed")

    recipe_results = validate_recipes(settings)
    if recipe_results:
        recipe_ok = all(ok for _path, ok, _msg in recipe_results)
        table.add_row("Recipes", "PASS" if recipe_ok else "FAIL", f"{sum(ok for _p, ok, _m in recipe_results)}/{len(recipe_results)} valid")
        if not recipe_ok:
            failures.append("one or more Goose recipes failed validation")
    else:
        table.add_row("Recipes", "WARN", "goose unavailable; validation skipped")

    active_status = next((m for m in model_status_report(settings) if m.alias == settings.model_alias), None)
    if active_status:
        model_ok = active_status.likely_complete
        table.add_row("Active model", "PASS" if model_ok else "WARN", f"{settings.model_alias}: {active_status.size_gb}GB; {active_status.resume_hint}")

    hf_bin = shutil.which("hf") or str(settings.project_root / ".venv" / "bin" / "hf")
    table.add_row("HF CLI", "PASS" if Path(hf_bin).exists() or shutil.which("hf") else "WARN", hf_bin)

    console.print(table)
    if failures:
        for failure in failures:
            console.print(f"[red]FAIL[/] {failure}")
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command("status")
def status() -> None:
    """Backend, Goose, compliance, recipe, and model status."""
    enforce_command_authority("builder status", requested_effects=("readonly_subprocess", "external_tool"))
    settings = load_settings()
    ok, msg = check_health(settings)
    served_ok, served_msg = check_serves_active_model(settings) if ok else (False, "backend down")
    compliance = run_compliance_checks()
    console.print(f"backend={settings.backend} alias={settings.model_alias} tier={settings.model_tier} model={settings.active_model_id} url={settings.base_url}")
    console.print(f"health: {'OK' if ok else 'DOWN'} — {msg}")
    console.print(f"served-model: {'OK' if served_ok else 'WARN'} — {served_msg}")
    console.print(goose_status())
    console.print(f"compliance: literals={'PASS' if compliance.init_literals_ok else 'FAIL'} refusal={'PASS' if compliance.refusal_probe_ok else 'FAIL'}")
    validations = validate_recipes(settings)
    ok_count = sum(1 for _p, ok, _m in validations if ok)
    console.print(f"recipes: {ok_count}/{len(validations)} valid")
    for m in model_status_report(settings):
        flag = "COMPLETE" if m.likely_complete else ("PARTIAL" if m.cache_dir else "MISSING")
        inc = " (resumable)" if m.has_incomplete else ""
        active = " *active*" if m.alias == settings.model_alias else ""
        console.print(f"model {m.alias}: {flag} {m.size_gb}GB / ~{m.expected_gb}GB{inc}{active}")
        if not m.likely_complete:
            console.print(f"  → {m.resume_hint}")


@app.command("config")
def config_dump() -> None:
    """Print passive config and legacy setup reconciliation metadata as JSON."""
    enforce_command_authority("builder config")
    settings = load_settings()
    payload = legacy_setup_redirect_payload(settings)
    payload["settings"] = {
        "project_root": str(settings.project_root),
        "target_repo": str(settings.core_repo),
        "backend": settings.backend,
        "model_alias": settings.model_alias,
        "model_tier": settings.model_tier,
        "active_model_id": settings.active_model_id,
    }
    console.out(json.dumps(payload, indent=2) + "\n", end="")


@app.command("init-prompt")
def init_prompt() -> None:
    """Print governed system prompt."""
    enforce_command_authority("builder init-prompt")
    console.print(CORE_INIT_SYSTEM_PROMPT)
    console.print(f"\n# ~{estimate_tokens(CORE_INIT_SYSTEM_PROMPT)} tokens")


if __name__ == "__main__":
    app()
