from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from builder_ii.backends import check_health, list_start_command
from builder_ii.benchmark import format_benchmark_report, run_benchmark, write_benchmark_report
from builder_ii.compliance import run_compliance_checks
from builder_ii.config import BACKENDS, MODEL_ALIASES, MODEL_TIERS, load_settings, normalize_model_alias
from builder_ii.goose_launcher import (
    find_goose_binary,
    goose_status,
    launch_goose_session,
    pull_models,
)
from builder_ii.goose_setup import run_full_setup, validate_recipes
from builder_ii.harness import format_verify_report, run_verification
from builder_ii.init_content import CORE_INIT_SYSTEM_PROMPT, estimate_tokens
from builder_ii.model_router import SESSION_MODES, explain_plan, plan_session
from builder_ii.models import model_definitions, model_status_report

app = typer.Typer(
    name="builder",
    help="Local CORE coding platform: Goose + MLX models on Apple Silicon",
    no_args_is_help=True,
)
console = Console()


def _ensure_backend(settings, no_backend: bool) -> None:
    if no_backend:
        return
    ok, msg = check_health(settings)
    if ok:
        console.print(f"[green]Backend ready[/] {msg}")
        return
    console.print(f"[yellow]Starting backend[/] ({msg})")
    cmd = list(list_start_command(settings))
    console.print(f"  {' '.join(cmd)}")
    subprocess.Popen(cmd)
    for _ in range(90):
        time.sleep(2)
        ok, msg = check_health(settings)
        if ok:
            console.print(f"[green]Backend ready[/] {msg}")
            return
    console.print("[red]Backend did not become ready in 180s (model may still be downloading)[/]")
    raise typer.Exit(1)


@app.command("setup")
def setup() -> None:
    """One-shot setup: Goose config, skills, hints, MOIM context, validate recipes."""
    settings = load_settings()
    console.print("[bold]Builder setup[/]")
    console.print(goose_status())
    result = run_full_setup(settings)
    table = Table("Artifact", "Path")
    table.add_row("goose config", result["goose_config"])
    table.add_row(".goosehints", result["goosehints"])
    table.add_row("MOIM context", result["moim_context"])
    console.print(table)
    if result["skills_installed"]:
        console.print(f"Skills installed to CORE: {len(result['skills_installed'])}")
    for item in result["recipe_validation"]:
        mark = "[green]OK[/]" if item["ok"] else "[red]FAIL[/]"
        console.print(f"{mark} {item['path']}")
    console.print("\nNext: [bold]./scripts/pull-roster.sh recommended[/] then [bold]builder start --task '...'[/]")


@app.command("pull")
def pull(
    tier: str = typer.Option("recommended", "--tier", "-t", help="recommended|fast|primary|all-safe|status|legacy"),
) -> None:
    """Download/cache local models. Prefer scripts/pull-roster.sh for MLX-LM."""
    settings = load_settings()
    script = settings.project_root / "scripts" / "pull-roster.sh"
    if script.exists() and tier != "legacy":
        proc = subprocess.run(["bash", str(script), tier])
        raise typer.Exit(proc.returncode)
    for line in pull_models(settings):
        console.print(line)


@app.command("start")
def start(
    mode: str = typer.Option(
        "orchestrator",
        "--mode",
        "-m",
        help="orchestrator|quick|deep|coding",
    ),
    task_hint: Optional[str] = typer.Option(
        None,
        "--task",
        "--task-hint",
        help="Free-text task used to choose the M1-safe model alias for this session",
    ),
    model_alias: Optional[str] = typer.Option(
        None,
        "--model",
        help="Explicit model alias override; see `builder models`",
    ),
    resume: bool = typer.Option(False, "--resume", "-r"),
    no_backend: bool = typer.Option(False, "--no-backend"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Goose session name"),
) -> None:
    """Start MLX backend + Goose session with governed CORE recipes."""
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
    console.print(
        f"[bold]Builder[/] mode={session.mode} alias={settings.model_alias} "
        f"tier={session.model_tier} backend={settings.backend} model={settings.active_model_id}"
    )
    console.print(goose_status())

    run_full_setup(settings)
    _ensure_backend(settings, no_backend)

    console.print(f"CORE repo: {settings.core_repo}")
    console.print("Slash commands: /explore /implement /review /verify /handoff /plan /coding /platform")
    console.print("Skills: core-governed-coding, core-verify-loop, core-pre-edit-sweep, core-handoff")
    proc = launch_goose_session(settings, resume=resume, session=session, name=name)
    proc.wait()


@app.command("verify")
def verify(
    module: Optional[str] = typer.Argument(None),
    suite: Optional[str] = typer.Option(None, "--suite", "-s"),
    fail_fast: bool = typer.Option(False, "--fail-fast", "-x"),
) -> None:
    """Run CORE verification harness."""
    settings = load_settings()
    result = run_verification(settings, module=module, suite=suite, fail_fast=fail_fast)
    console.print(format_verify_report(result))
    raise typer.Exit(0 if result.passed else 1)


@app.command("benchmark")
def benchmark(
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Benchmark TTFT, tool-calling, compliance, memory."""
    settings = load_settings()
    report = run_benchmark(settings)
    console.print(format_benchmark_report(report))
    if output:
        write_benchmark_report(report, output)
    raise typer.Exit(0)


@app.command("switch-model")
def switch_model(
    alias: str = typer.Argument(..., help="Model alias or legacy tier; run `builder models`"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b"),
) -> None:
    """Print .env lines to switch model alias/tier. Restart backend after."""
    if alias in MODEL_TIERS:
        normalized = normalize_model_alias(None, tier_fallback=alias)
        tier = alias
    else:
        normalized = normalize_model_alias(alias)
        tier = "fast" if normalized in {"phi-reasoning", "gemma-fast"} else "primary"
    if backend and backend not in BACKENDS:
        console.print(f"backend must be one of {BACKENDS}")
        raise typer.Exit(1)
    lines = [
        f"CORE_AGENT_MODEL_ALIAS={normalized}",
        f"CORE_AGENT_MODEL_TIER={tier}",
    ]
    if backend:
        lines.append(f"CORE_AGENT_BACKEND={backend}")
    lines.append("# Then: builder start --task 'describe the work'  (or restart backend/session)")
    console.print("\n".join(lines))


@app.command("models")
def models() -> None:
    """Show the configured model roster and cache status."""
    settings = load_settings()
    status_by_alias = {m.alias: m for m in model_status_report(settings)}
    table = Table("Alias", "Tier", "Policy", "Repo", "Cache", "Expected", "Note")
    for definition in model_definitions(settings):
        status = status_by_alias[definition.alias]
        cache = "COMPLETE" if status.likely_complete else ("PARTIAL" if status.cache_dir else "MISSING")
        if status.has_incomplete:
            cache += "/RESUMABLE"
        table.add_row(
            definition.alias,
            definition.tier,
            definition.policy,
            definition.hf_repo,
            f"{cache} {status.size_gb}GB",
            f"~{definition.expected_gb}GB",
            definition.note,
        )
    console.print(table)
    console.print("\nDownload: ./scripts/pull-roster.sh recommended | alias <name> | all-safe | candidates")


@app.command("doctor")
def doctor() -> None:
    """Run a local platform readiness check without editing CORE."""
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

    compliance = run_compliance_checks()
    compliance_ok = compliance.init_literals_ok and compliance.refusal_probe_ok
    table.add_row(
        "Compliance",
        "PASS" if compliance_ok else "FAIL",
        f"literals={compliance.init_literals_ok} refusal={compliance.refusal_probe_ok}",
    )
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
        table.add_row(
            "Active model",
            "PASS" if model_ok else "WARN",
            f"{settings.model_alias}: {active_status.size_gb}GB; {active_status.resume_hint}",
        )

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
    settings = load_settings()
    ok, msg = check_health(settings)
    compliance = run_compliance_checks()
    console.print(
        f"backend={settings.backend} alias={settings.model_alias} tier={settings.model_tier} "
        f"model={settings.active_model_id} url={settings.base_url}"
    )
    console.print(f"health: {'OK' if ok else 'DOWN'} — {msg}")
    console.print(goose_status())
    console.print(
        f"compliance: literals={'PASS' if compliance.init_literals_ok else 'FAIL'} "
        f"refusal={'PASS' if compliance.refusal_probe_ok else 'FAIL'}"
    )
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
    """Print effective Goose/session configuration as JSON."""
    settings = load_settings()
    result = run_full_setup(settings)
    console.print(json.dumps(result, indent=2))


@app.command("init-prompt")
def init_prompt() -> None:
    """Print governed system prompt."""
    console.print(CORE_INIT_SYSTEM_PROMPT)
    console.print(f"\n# ~{estimate_tokens(CORE_INIT_SYSTEM_PROMPT)} tokens")


if __name__ == "__main__":
    app()
