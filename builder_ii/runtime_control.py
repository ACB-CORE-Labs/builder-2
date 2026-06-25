from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Iterable

import psutil
import typer
from rich.console import Console
from rich.table import Table

from builder_ii.backend_state import backend_marker_path, check_backend_marker, clear_backend_marker
from builder_ii.backends import check_health, check_serves_active_model
from builder_ii.config import Settings, load_settings

runtime_app = typer.Typer(help="Inspect and control the local MLX runtime process.")
console = Console()


@dataclass(frozen=True)
class RuntimeProcess:
    pid: int
    name: str
    cmdline: tuple[str, ...]

    @property
    def command(self) -> str:
        return " ".join(self.cmdline) if self.cmdline else self.name


def _candidate_listener_pids(settings: Settings) -> set[int]:
    command = ["lsof", "-nP", f"-iTCP:{settings.port}", "-sTCP:LISTEN", "-Fp"]
    try:
        result = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        return set()
    if result.returncode not in {0, 1}:
        return set()

    pids: set[int] = set()
    for line in result.stdout.splitlines():
        if not line.startswith("p"):
            continue
        try:
            pids.add(int(line[1:]))
        except ValueError:
            continue
    return pids


def _looks_like_builder_runtime(process: psutil.Process) -> bool:
    try:
        cmdline = tuple(process.cmdline())
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return False
    return "mlx_lm.server" in " ".join(cmdline)


def _runtime_process_from_pid(pid: int) -> RuntimeProcess | None:
    try:
        process = psutil.Process(pid)
        name = process.name()
        try:
            cmdline = tuple(process.cmdline())
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            cmdline = ()
        return RuntimeProcess(process.pid, name, cmdline)
    except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
        return None


def find_runtime_processes(settings: Settings, *, include_foreign: bool = False) -> list[RuntimeProcess]:
    matches: list[RuntimeProcess] = []
    for pid in sorted(_candidate_listener_pids(settings)):
        try:
            process = psutil.Process(pid)
            if not include_foreign and not _looks_like_builder_runtime(process):
                continue
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            if not include_foreign:
                continue
        runtime_process = _runtime_process_from_pid(pid)
        if runtime_process is not None:
            matches.append(runtime_process)
    return matches


def terminate_runtime_processes(processes: Iterable[RuntimeProcess], *, timeout: float = 5.0) -> list[int]:
    stopped: list[int] = []
    live: list[psutil.Process] = []
    for runtime_process in processes:
        try:
            process = psutil.Process(runtime_process.pid)
            process.terminate()
            live.append(process)
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    gone, alive = psutil.wait_procs(live, timeout=timeout)
    stopped.extend(process.pid for process in gone)
    for process in alive:
        try:
            process.kill()
            stopped.append(process.pid)
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
    return stopped


@runtime_app.command("status")
def runtime_status() -> None:
    """Show local runtime health, served-model state, marker, and listener process."""
    settings = load_settings()
    health_ok, health_msg = check_health(settings)
    served_ok, served_msg = check_serves_active_model(settings) if health_ok else (False, "runtime down")
    marker = check_backend_marker(settings)
    processes = find_runtime_processes(settings, include_foreign=True)

    table = Table("Check", "Result", "Details")
    table.add_row("runtime", "PASS" if health_ok else "DOWN", health_msg)
    table.add_row("served model", "PASS" if served_ok else "WARN", served_msg)
    table.add_row("marker", "PASS" if marker.ok else "WARN", marker.message)
    table.add_row("marker path", "INFO", str(backend_marker_path(settings)))
    if processes:
        table.add_row("listener", "INFO", "; ".join(f"pid={p.pid} {p.command}" for p in processes))
    else:
        table.add_row("listener", "DOWN", f"no listener on {settings.host}:{settings.port}")
    console.print(table)


@runtime_app.command("clear-marker")
def runtime_clear_marker() -> None:
    """Clear the recorded runtime marker without touching any process."""
    settings = load_settings()
    clear_backend_marker(settings)
    console.print(f"[green]Cleared runtime marker[/] {backend_marker_path(settings)}")


@runtime_app.command("stop")
def runtime_stop(
    force_foreign: bool = typer.Option(False, "--force-foreign", help="Also stop non-builder processes listening on the configured port."),
    keep_marker: bool = typer.Option(False, "--keep-marker", help="Do not clear the runtime marker after stopping."),
) -> None:
    """Stop the local MLX runtime process on the configured port and clear its marker."""
    settings = load_settings()
    processes = find_runtime_processes(settings, include_foreign=force_foreign)
    if not processes:
        console.print(f"[yellow]No matching runtime listener found[/] {settings.host}:{settings.port}")
    else:
        stopped = terminate_runtime_processes(processes)
        console.print(f"[green]Stopped runtime process(es)[/] {', '.join(str(pid) for pid in stopped) or 'none'}")
    if not keep_marker:
        clear_backend_marker(settings)
        console.print(f"[green]Cleared runtime marker[/] {backend_marker_path(settings)}")


@runtime_app.command("reset")
def runtime_reset(
    force_foreign: bool = typer.Option(False, "--force-foreign", help="Also stop non-builder processes listening on the configured port."),
) -> None:
    """Stop the local runtime if present and clear the marker."""
    runtime_stop(force_foreign=force_foreign, keep_marker=False)
