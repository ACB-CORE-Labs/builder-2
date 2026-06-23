from __future__ import annotations

import subprocess
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from core_agent.backends import check_health, list_start_command, start_backend_process
from core_agent.benchmark import format_benchmark_report, run_benchmark, write_benchmark_report
from core_agent.compliance import run_compliance_checks
from core_agent.config import BACKENDS, MODEL_TIERS, load_settings
from core_agent.goose_launcher import goose_status, launch_goose_session
from core_agent.harness import format_verify_report, run_verification
from core_agent.init_content import CORE_INIT_SYSTEM_PROMPT, estimate_tokens

app = typer.Typer(
    name="core-agent",
    help="Local CORE coding agent: Goose + Gemma 4 MLX",
    no_args_is_help=True,
)
console = Console()


@app.command("start")
def start(
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume last Goose session"),
    no_backend: bool = typer.Option(False, "--no-backend", help="Skip backend auto-start"),
) -> None:
    """One-command morning startup: MLX backend + Goose session with CORE recipe."""
    settings = load_settings()
    console.print(f"[bold]CORE Agent[/] backend={settings.backend} tier={settings.model_tier}")
    console.print(goose_status())

    if not no_backend:
        ok, msg = check_health(settings)
        if ok:
            console.print(f"[green]Backend ready[/] {msg}")
        else:
            console.print(f"[yellow]Starting backend[/] ({msg})")
            cmd = list(list_start_command(settings))
            console.print(f"  {' '.join(cmd)}")
            subprocess.Popen(cmd)
            for _ in range(30):
                time.sleep(2)
                ok, msg = check_health(settings)
                if ok:
                    console.print(f"[green]Backend ready[/] {msg}")
                    break
            else:
                console.print("[red]Backend did not become ready in 60s[/]")
                raise typer.Exit(1)

    console.print(f"CORE repo: {settings.core_repo}")
    console.print(f"Init prompt: ~{estimate_tokens(CORE_INIT_SYSTEM_PROMPT)} tokens")
    proc = launch_goose_session(settings, resume=resume)
    proc.wait()


@app.command("verify")
def verify(
    module: Optional[str] = typer.Argument(None, help="Module path e.g. algebra/versor.py"),
    suite: Optional[str] = typer.Option(None, "--suite", "-s", help="Override suite alias"),
) -> None:
    """Run CORE verification harness for a module or suite."""
    settings = load_settings()
    result = run_verification(settings, module=module, suite=suite)
    console.print(format_verify_report(result))
    raise typer.Exit(0 if result.passed else 1)


@app.command("benchmark")
def benchmark(
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Write report file"),
) -> None:
    """Benchmark TTFT, tool-calling, compliance, and memory (<5 min)."""
    settings = load_settings()
    report = run_benchmark(settings)
    text = format_benchmark_report(report)
    console.print(text)
    if output:
        write_benchmark_report(report, output)
        console.print(f"Wrote {output}")
    raise typer.Exit(0)


@app.command("switch-model")
def switch_model(
    tier: str = typer.Argument(..., help="primary (12B) or fast (E4B)"),
    backend: Optional[str] = typer.Option(None, "--backend", "-b", help="rapid-mlx|mlx-lm|ollama"),
) -> None:
    """Print env changes to switch model tier/backend (edit .env then restart)."""
    if tier not in MODEL_TIERS:
        console.print(f"tier must be one of {MODEL_TIERS}")
        raise typer.Exit(1)
    if backend and backend not in BACKENDS:
        console.print(f"backend must be one of {BACKENDS}")
        raise typer.Exit(1)
    lines = [f"CORE_AGENT_MODEL_TIER={tier}"]
    if backend:
        lines.append(f"CORE_AGENT_BACKEND={backend}")
    lines.append("# Restart: core-agent start")
    console.print("\n".join(lines))


@app.command("status")
def status() -> None:
    """Show backend, goose, and compliance status."""
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


@app.command("init-prompt")
def init_prompt() -> None:
    """Print the CORE governed system prompt (for inspection)."""
    console.print(CORE_INIT_SYSTEM_PROMPT)
    console.print(f"\n# ~{estimate_tokens(CORE_INIT_SYSTEM_PROMPT)} tokens")


if __name__ == "__main__":
    app()