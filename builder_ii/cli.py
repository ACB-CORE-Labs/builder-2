from __future__ import annotations

import json
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
from builder_ii.config import BACKENDS, MODEL_TIERS, load_settings
from builder_ii.goose_launcher import (
    goose_status,
    launch_goose_session,
    pull_models,
)
from builder_ii.goose_setup import run_full_setup, validate_recipes
from builder_ii.harness import format_verify_report, run_verification
from builder_ii.init_content import CORE_INIT_SYSTEM_PROMPT, estimate_tokens
from builder_ii.model_router import SESSION_MODES, plan_session

app = typer.Typer(
    name="builder",
    help="Local CORE coding platform: Goose + Gemma 4 MLX on M1",
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
    console.print("\nNext: [bold]builder pull[/] then [bold]builder start[/]")


@app.command("pull")
def pull() -> None:
    """Pre-download Gemma models (Rapid-MLX)."""
    settings = load_settings()
    console.print(f"Pulling models for backend={settings.backend}...")
    lines = pull_models(settings)
    for line in lines:
        console.print(line)
    if not lines:
        console.print("No pull commands run (requires rapid-mlx backend).")


@app.command("start")
def start(
    mode: str = typer.Option(
        "orchestrator",
        "--mode",
        "-m",
        help="orchestrator|quick|deep|coding",
    ),
    resume: bool = typer.Option(False, "--resume", "-r"),
    no_backend: bool = typer.Option(False, "--no-backend"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Goose session name"),
) -> None:
    """Start MLX backend + Goose session with CORE platform recipe and subagents."""
    if mode not in SESSION_MODES:
        console.print(f"mode must be one of {SESSION_MODES}")
        raise typer.Exit(1)

    settings = load_settings()
    session = plan_session(mode)
    console.print(
        f"[bold]Builder[/] mode={session.mode} tier={session.model_tier} "
        f"recipe={session.recipe_name} backend={settings.backend}"
    )
    console.print(goose_status())

    # Apply tier from mode (override .env for this session's backend start).
    import os
    os.environ["CORE_AGENT_MODEL_TIER"] = session.model_tier
    settings = load_settings()

    run_full_setup(settings)
    _ensure_backend(settings, no_backend)

    console.print(f"CORE repo: {settings.core_repo}")
    console.print(f"Slash commands: /explore /implement /review /verify /handoff /plan")
    console.print(f"Skills: core-governed-coding, core-verify-loop, core-pre-edit-sweep, core-handoff")
    proc = launch_goose_session(settings, resume=resume, session=session, name=name)
    proc.wait()


@app.command("verify")
def verify(
    module: Optional[str] = typer.Argument(None),
    suite: Optional[str] = typer.Option(None, "--suite", "-s"),
) -> None:
    """Run CORE verification harness."""
    settings = load_settings()
    result = run_verification(settings, module=module, suite=suite)
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
    tier: str = typer.Argument(..., help="primary (12B) or fast (4B)"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b"),
) -> None:
    """Show .env lines to switch model tier (restart backend after)."""
    if tier not in MODEL_TIERS:
        console.print(f"tier must be one of {MODEL_TIERS}")
        raise typer.Exit(1)
    if backend and backend not in BACKENDS:
        console.print(f"backend must be one of {BACKENDS}")
        raise typer.Exit(1)
    lines = [f"CORE_AGENT_MODEL_TIER={tier}"]
    if backend:
        lines.append(f"CORE_AGENT_BACKEND={backend}")
    lines.append("# Then: builder start --mode quick|deep")
    console.print("\n".join(lines))


@app.command("status")
def status() -> None:
    """Backend, Goose, compliance, and recipe status."""
    settings = load_settings()
    ok, msg = check_health(settings)
    compliance = run_compliance_checks()
    console.print(f"backend={settings.backend} tier={settings.model_tier} url={settings.base_url}")
    console.print(f"health: {'OK' if ok else 'DOWN'} — {msg}")
    console.print(goose_status())
    console.print(
        f"compliance: literals={'PASS' if compliance.init_literals_ok else 'FAIL'} "
        f"refusal={'PASS' if compliance.refusal_probe_ok else 'FAIL'}"
    )
    validations = validate_recipes(settings)
    ok_count = sum(1 for _p, ok, _m in validations if ok)
    console.print(f"recipes: {ok_count}/{len(validations)} valid")


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