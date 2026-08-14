"""builder-II TUI/UX display engine.

Design contract
---------------
* Every public function writes to a Rich Console and returns None.
* Every function accepts ``verbose: bool = False``.
* No function raises — errors are printed as structured WARN/FAIL rows.
* Color = semantic signal only.  No decoration without meaning.
* Left-aligned glyph column: ● PASS  ◐ WARN  ○ FAIL  → hint  ─ separator
* Stdout is always parseable when piped (Rich strips markup for non-TTYs).
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

# ---------------------------------------------------------------------------
# Palette — 8 semantic tokens, nothing more
# ---------------------------------------------------------------------------
_C = {
    "pass": "#4ade80",  # green
    "warn": "#fbbf24",  # amber
    "fail": "#f87171",  # red
    "hint": "#94a3b8",  # slate
    "active": "#38bdf8",  # sky
    "dim": "#475569",  # muted slate
    "bold": "#f1f5f9",  # near-white
    "accent": "#818cf8",  # indigo
}

# Glyphs
_G_PASS = f"[{_C['pass']}]●[/]"
_G_WARN = f"[{_C['warn']}]◐[/]"
_G_FAIL = f"[{_C['fail']}]○[/]"
_G_HINT = f"[{_C['hint']}]→[/]"
_G_DIM = f"[{_C['dim']}]─[/]"
_G_ACT = f"[{_C['active']}]◆[/]"

console = Console(highlight=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _glyph(result: str) -> str:
    r = result.upper()
    if r in ("PASS", "OK", "COMPLETE", "TRUE", "YES", "1"):
        return _G_PASS
    if r in ("WARN", "WARNING", "PARTIAL", "RESUMABLE"):
        return _G_WARN
    if r in ("FAIL", "FAILED", "ERROR", "MISSING", "DOWN", "FALSE", "0"):
        return _G_FAIL
    return _G_DIM


def _label(text: str, width: int = 22) -> str:
    return f"[{_C['dim']}]{text:<{width}}[/]"


def _value(text: str) -> str:
    return f"[{_C['bold']}]{text}[/]"


def _hint(text: str) -> str:
    return f"  {_G_HINT} [{_C['hint']}]{text}[/]"


def _active_badge() -> str:
    return f" [{_C['active']}]active[/]"


def _section(title: str) -> None:
    console.print()
    console.print(Rule(f"[{_C['accent']}]{title}[/]", style=_C["dim"]))


def _git_branch() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL,
            timeout=2,
        )
        return out.decode().strip()
    except Exception:
        return "?"


def _cache_bar(size_gb: float, expected_gb: float, width: int = 12) -> str:
    """Compact inline progress bar for model cache completeness."""
    if expected_gb <= 0:
        return f"[{_C['dim']}]{'?':>{width}}[/]"
    ratio = min(size_gb / expected_gb, 1.0)
    filled = round(ratio * width)
    bar = "█" * filled + "░" * (width - filled)
    color = _C["pass"] if ratio >= 0.98 else (_C["warn"] if ratio > 0.1 else _C["fail"])
    return f"[{color}]{bar}[/] {size_gb:.1f}/{expected_gb:.0f}GB"


# ---------------------------------------------------------------------------
# Platform header
# ---------------------------------------------------------------------------


def render_header(title: str = "builder-II", subtitle: str = "") -> None:
    """Print the platform header with live context (branch, cwd)."""
    branch = _git_branch()
    cwd = Path.cwd().name
    backend = os.environ.get("CORE_AGENT_BACKEND", "mlx")
    model = os.environ.get("CORE_AGENT_MODEL_ALIAS", os.environ.get("CORE_AGENT_MODEL_TIER", "—"))

    inner = (
        f"[{_C['bold']} bold]{title}[/]  "
        f"[{_C['dim']}]{cwd}[/] "
        f"[{_C['accent']}]git:{branch}[/]  "
        f"[{_C['dim']}]{backend}[/] "
        f"[{_C['active']}]{model}[/]"
    )
    if subtitle:
        inner += f"\n[{_C['hint']}]{subtitle}[/]"
    console.print(Panel(inner, border_style=_C["dim"], padding=(0, 2)))


# ---------------------------------------------------------------------------
# Platform status
# ---------------------------------------------------------------------------


def render_platform_status(
    settings: Any,
    *,
    verbose: bool = False,
) -> None:
    """Full platform status panel — all vitals, one screen."""
    from builder_ii.adapters.goose.goose_launcher import goose_status
    from builder_ii.adapters.goose.goose_recipe_validation import validate_recipes
    from builder_ii.governance.authority.compliance import run_compliance_checks
    from builder_ii.routing.backends import check_health, check_serves_active_model

    render_header(subtitle="platform status")

    _section("Runtime")
    table = Table.grid(padding=(0, 2))
    table.add_column(justify="left", no_wrap=True, min_width=4)
    table.add_column(justify="left", no_wrap=True, min_width=22)
    table.add_column(justify="left")

    # Backend
    ok, msg = check_health(settings)
    table.add_row(_glyph("pass" if ok else "warn"), _label("backend"), _value(msg if ok else f"DOWN — {msg}"))
    if ok:
        m_ok, m_msg = check_serves_active_model(settings)
        table.add_row(_glyph("pass" if m_ok else "warn"), _label("served model"), _value(m_msg))
    else:
        table.add_row(_G_WARN, _label("served model"), f"[{_C['hint']}]backend not running[/]")

    # Goose
    gs = goose_status()
    gs_ok = "not found" not in gs.lower() and "unavailable" not in gs.lower()
    table.add_row(_glyph("pass" if gs_ok else "warn"), _label("goose"), _value(gs))

    # Compliance
    comp = run_compliance_checks()
    c_ok = comp.init_literals_ok and comp.refusal_probe_ok
    table.add_row(
        _glyph("pass" if c_ok else "fail"),
        _label("compliance"),
        _value(
            f"literals={'OK' if comp.init_literals_ok else 'FAIL'}  refusal={'OK' if comp.refusal_probe_ok else 'FAIL'}"
        ),
    )

    # Recipes
    recipes = validate_recipes(settings)
    if recipes:
        r_ok = all(ok for _, ok, _ in recipes)
        r_n = sum(ok for _, ok, _ in recipes)
        table.add_row(
            _glyph("pass" if r_ok else "warn"),
            _label("recipes"),
            _value(f"{r_n}/{len(recipes)} valid"),
        )
        if verbose and not r_ok:
            for path, ok, msg in recipes:
                if not ok:
                    table.add_row(_G_HINT, _label(f"  {Path(path).name}"), f"[{_C['fail']}]{msg}[/]")
    else:
        table.add_row(_G_WARN, _label("recipes"), f"[{_C['hint']}]goose unavailable — skipped[/]")

    console.print(table)

    # Models
    _section("Model roster")
    render_model_roster(settings, verbose=verbose)

    console.print()


# ---------------------------------------------------------------------------
# Doctor
# ---------------------------------------------------------------------------


def render_doctor(
    settings: Any,
    *,
    verbose: bool = False,
) -> list[str]:
    """Structured readiness check. Returns list of failure strings."""
    import shutil

    from builder_ii.adapters.goose.goose_launcher import find_goose_binary, goose_status
    from builder_ii.adapters.goose.goose_recipe_validation import validate_recipes
    from builder_ii.core.models import model_status_report
    from builder_ii.governance.authority.compliance import run_compliance_checks
    from builder_ii.routing.backends import check_health, check_serves_active_model

    render_header(subtitle="doctor — local readiness")

    failures: list[str] = []
    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True, min_width=4)
    table.add_column(no_wrap=True, min_width=22)
    table.add_column()

    def row(result: str, label: str, detail: str, hint: str = "") -> None:
        table.add_row(_glyph(result), _label(label), _value(detail))
        if hint and (verbose or result.upper() not in ("PASS", "OK")):
            table.add_row("", "", _hint(hint))

    # CORE repo
    core_ok = settings.target_repo.exists() and (settings.target_repo / ".git").exists()
    row(
        "pass" if core_ok else "fail",
        "target repo",
        str(settings.target_repo),
        hint="" if core_ok else "set BUILDER_TARGET_REPO or CORE_REPO_PATH",
    )
    if not core_ok:
        failures.append(f"target repo missing: {settings.target_repo}")

    # Goose
    goose_ok = find_goose_binary() is not None
    row(
        "pass" if goose_ok else "warn",
        "goose",
        goose_status(),
        hint="run: pip install goose-ai" if not goose_ok else "",
    )

    # Backend
    b_ok, b_msg = check_health(settings)
    row("pass" if b_ok else "warn", "backend", b_msg, hint="run: builder start --no-backend" if not b_ok else "")
    if b_ok:
        s_ok, s_msg = check_serves_active_model(settings)
        row(
            "pass" if s_ok else "warn",
            "served model",
            s_msg,
            hint="run: builder switch-model <alias>" if not s_ok else "",
        )

    # Compliance
    comp = run_compliance_checks()
    c_ok = comp.init_literals_ok and comp.refusal_probe_ok
    row(
        "pass" if c_ok else "fail",
        "compliance",
        f"literals={'OK' if comp.init_literals_ok else 'FAIL'}  refusal={'OK' if comp.refusal_probe_ok else 'FAIL'}",
    )
    if not c_ok:
        failures.append("governed prompt/refusal compliance check failed")

    # Recipes
    recipe_results = validate_recipes(settings)
    if recipe_results:
        r_ok = all(ok for _, ok, _ in recipe_results)
        r_n = sum(ok for _, ok, _ in recipe_results)
        row("pass" if r_ok else "fail", "recipes", f"{r_n}/{len(recipe_results)} valid")
        if not r_ok:
            failures.append("one or more Goose recipes failed validation")
    else:
        row("warn", "recipes", "goose unavailable — validation skipped")

    # Active model
    active_status = next((m for m in model_status_report(settings) if m.alias == settings.model_alias), None)
    if active_status:
        m_ok = active_status.likely_complete
        row(
            "pass" if m_ok else "warn",
            "active model",
            f"{settings.model_alias} — {active_status.size_gb:.1f}GB / ~{active_status.expected_gb:.0f}GB",
            hint=active_status.resume_hint if not m_ok else "",
        )

    # HF CLI
    hf_bin = shutil.which("hf")
    row(
        "pass" if hf_bin else "warn",
        "hf cli",
        hf_bin or "not found",
        hint="pip install huggingface_hub[cli]" if not hf_bin else "",
    )

    console.print(table)

    if failures:
        console.print()
        for f in failures:
            console.print(f"  {_G_FAIL} [{_C['fail']}]{f}[/]")

    console.print()
    return failures


# ---------------------------------------------------------------------------
# Model roster
# ---------------------------------------------------------------------------


def render_model_roster(
    settings: Any,
    *,
    verbose: bool = False,
) -> None:
    """Compact model roster with inline cache bars."""
    from builder_ii.core.models import model_definitions, model_status_report

    status_by_alias = {m.alias: m for m in model_status_report(settings)}
    table = Table(
        box=None,
        padding=(0, 2),
        show_header=True,
        header_style=f"{_C['dim']}",
    )
    table.add_column("", no_wrap=True, min_width=2)
    table.add_column("alias", no_wrap=True, min_width=22)
    table.add_column("tier", no_wrap=True, min_width=10)
    table.add_column("cache", no_wrap=True, min_width=28)
    table.add_column("policy", no_wrap=True, min_width=12)
    if verbose:
        table.add_column("repo", no_wrap=True)

    for dfn in model_definitions(settings):
        st = status_by_alias.get(dfn.alias)
        if not st:
            continue
        is_active = dfn.alias == settings.model_alias
        glyph = _G_ACT if is_active else _glyph("pass" if st.likely_complete else ("warn" if st.cache_dir else "fail"))
        alias_txt = (
            f"[{_C['active']} bold]{dfn.alias}[/]{_active_badge()}" if is_active else f"[{_C['bold']}]{dfn.alias}[/]"
        )
        cache_txt = _cache_bar(st.size_gb, dfn.expected_gb)
        if st.has_incomplete:
            cache_txt += f" [{_C['warn']}]resumable[/]"
        tier_txt = f"[{_C['accent']}]{dfn.tier}[/]"
        policy_txt = f"[{_C['dim']}]{dfn.policy}[/]"
        row_args = [glyph, alias_txt, tier_txt, cache_txt, policy_txt]
        if verbose:
            row_args.append(f"[{_C['hint']}]{dfn.hf_repo}[/]")
        table.add_row(*row_args)
        if verbose and dfn.note:
            table.add_row("", "", "", f"[{_C['hint']}]{dfn.note}[/]", "", *([""] if verbose else []))

    console.print(table)
    console.print()
    console.print(_hint("Download: bash scripts/pull-roster.sh recommended | <alias> | all-safe"))


# ---------------------------------------------------------------------------
# Capability gates
# ---------------------------------------------------------------------------


def render_capability_gates(
    gates: Iterable[Any],
    *,
    verbose: bool = False,
) -> bool:
    """Render capability gate grid. Returns True if all gates pass."""
    all_pass = True
    table = Table(box=None, padding=(0, 2), show_header=True, header_style=f"{_C['dim']}")
    table.add_column("", no_wrap=True, min_width=2)
    table.add_column("gate", no_wrap=True, min_width=28)
    table.add_column("result", no_wrap=True, min_width=8)
    table.add_column("detail")

    for gate in gates:
        r = gate.result.upper()
        if r == "FAIL":
            all_pass = False
        detail_txt = gate.details if (verbose or r != "PASS") else ""
        table.add_row(
            _glyph(r),
            f"[{_C['bold']}]{gate.name}[/]",
            f"[{_C['pass'] if r == 'PASS' else _C['warn'] if r == 'WARN' else _C['fail']}]{r}[/]",
            f"[{_C['hint']}]{detail_txt}[/]",
        )

    console.print(table)
    return all_pass


# ---------------------------------------------------------------------------
# Session header (pre-launch banner)
# ---------------------------------------------------------------------------


def render_session_header(
    mode: str,
    model_alias: str,
    model_tier: str,
    backend: str,
    model_id: str,
    routing_explanation: str,
    *,
    verbose: bool = False,
) -> None:
    """Print session context before Goose launch."""
    _section("session")
    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True, min_width=4)
    table.add_column(no_wrap=True, min_width=22)
    table.add_column()

    table.add_row(_G_ACT, _label("mode"), _value(mode))
    table.add_row(_G_ACT, _label("alias"), _value(model_alias))
    table.add_row(_G_ACT, _label("tier"), _value(model_tier))
    table.add_row(_G_ACT, _label("backend"), _value(backend))
    table.add_row(_G_ACT, _label("model id"), _value(model_id))
    if verbose:
        table.add_row(_G_DIM, _label("routing"), f"[{_C['hint']}]{routing_explanation}[/]")
    console.print(table)

    console.print()
    console.print(
        f"  [{_C['dim']}]slash[/] "
        + "  ".join(
            f"[{_C['accent']}]/{cmd}[/]"
            for cmd in ["explore", "implement", "review", "verify", "handoff", "plan", "coding", "platform"]
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# HITL gate banner
# ---------------------------------------------------------------------------


def render_hitl_banner(
    gate_label: str,
    apply_command: str,
    rollback_command: str,
    evidence_path: Optional[str] = None,
    *,
    verbose: bool = False,
) -> None:
    """Print a HITL approval gate banner with apply/rollback commands."""
    console.print()
    console.print(
        Panel(
            f"[{_C['warn']} bold]{gate_label}[/]\n"
            f"\n  [{_C['dim']}]apply   [/] [{_C['pass']}]{apply_command}[/]"
            f"\n  [{_C['dim']}]rollback[/] [{_C['fail']}]{rollback_command}[/]"
            + (f"\n\n  [{_C['hint']}]evidence: {evidence_path}[/]" if evidence_path and verbose else ""),
            border_style=_C["warn"],
            title=f"[{_C['warn']}]HITL gate[/]",
            padding=(1, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Handoff summary
# ---------------------------------------------------------------------------


def render_handoff_summary(
    note: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render a handoff note artifact as a compact summary panel."""
    title = getattr(note, "title", None) or note.get("title", "Handoff") if hasattr(note, "get") else "Handoff"
    summary = getattr(note, "summary", None) or note.get("summary", "") if hasattr(note, "get") else ""
    branch = getattr(note, "branch", None) or note.get("branch", "") if hasattr(note, "get") else ""
    next_steps = (getattr(note, "next_steps", None) or note.get("next_steps", [])) if hasattr(note, "get") else []

    lines = [f"[{_C['bold']} bold]{title}[/]"]
    if branch:
        lines.append(f"[{_C['hint']}]branch: {branch}[/]")
    if summary:
        lines.append(f"\n{summary}")
    if next_steps and verbose:
        lines.append(f"\n[{_C['dim']}]next steps:[/]")
        for step in next_steps:
            lines.append(f"  {_G_HINT} [{_C['hint']}]{step}[/]")

    console.print(
        Panel(
            "\n".join(lines),
            border_style=_C["accent"],
            title=f"[{_C['accent']}]handoff[/]",
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# Golden path summary
# ---------------------------------------------------------------------------


def render_golden_path_summary(
    report: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render a golden path report as a tiered status list."""
    _section("golden path")
    if hasattr(report, "get"):
        steps = report.get("steps", [])
        target = report.get("target_profile", "—")
        valid = report.get("valid", False)
    else:
        steps = getattr(report, "steps", [])
        target = getattr(report, "target_profile", "—")
        valid = getattr(report, "valid", False)

    glyph = _G_PASS if valid else _G_FAIL
    console.print(
        f"  {glyph} [{_C['bold']}]{target}[/]  [{_C['hint']}]{'all steps passed' if valid else 'steps failed'}[/]"
    )

    if steps and verbose:
        console.print()
        table = Table.grid(padding=(0, 2))
        table.add_column(no_wrap=True, min_width=2)
        table.add_column(no_wrap=True, min_width=30)
        table.add_column()
        for step in steps:
            s_label = step.get("label", "") if isinstance(step, dict) else str(step)
            s_result = step.get("result", "") if isinstance(step, dict) else ""
            s_detail = step.get("detail", "") if isinstance(step, dict) else ""
            table.add_row(
                _glyph(s_result or "dim"),
                f"[{_C['bold']}]{s_label}[/]",
                f"[{_C['hint']}]{s_detail}[/]",
            )
        console.print(table)

    console.print()


# ---------------------------------------------------------------------------
# Backend pulse (non-spammy single-line poller)
# ---------------------------------------------------------------------------


def pulse_backend(
    check_fn,
    *,
    max_wait: float = 180.0,
    interval: float = 2.0,
    label: str = "backend",
) -> bool:
    """Poll `check_fn()` returning (ok, msg) until ready or timeout.
    Overwrites a single status line. Returns True on success.
    """
    deadline = time.monotonic() + max_wait
    with console.status(
        f"[{_C['warn']}]waiting[/] [{_C['dim']}]{label}[/]",
        spinner="dots",
        spinner_style=_C["warn"],
    ) as status:
        while time.monotonic() < deadline:
            ok, msg = check_fn()
            if ok:
                status.stop()
                console.print(f"  {_G_PASS} [{_C['pass']}]{label} ready[/]  [{_C['hint']}]{msg}[/]")
                return True
            status.update(f"[{_C['warn']}]waiting[/] [{_C['dim']}]{label}[/]  [{_C['hint']}]{msg}[/]")
            time.sleep(interval)
    console.print(f"  {_G_FAIL} [{_C['fail']}]{label} did not become ready in {max_wait:.0f}s[/]")
    return False


# ---------------------------------------------------------------------------
# Error surface
# ---------------------------------------------------------------------------


def render_errors(errors: Sequence[str], title: str = "errors") -> None:
    """Structured error list — never raw tracebacks."""
    if not errors:
        return
    console.print(
        Panel(
            "\n".join(f"  {_G_FAIL} [{_C['fail']}]{e}[/]" for e in errors),
            border_style=_C["fail"],
            title=f"[{_C['fail']}]{title}[/]",
            padding=(0, 2),
        )
    )


# ---------------------------------------------------------------------------
# `builder tui` sub-command group
# ---------------------------------------------------------------------------

try:
    import typer as _typer

    tui_app = _typer.Typer(
        name="tui",
        help="Rich TUI panels for builder-II platform visibility.",
        no_args_is_help=True,
    )

    @tui_app.command("status")
    def tui_status(
        verbose: bool = _typer.Option(False, "--verbose", "-v", help="Show full detail."),
    ) -> None:
        """Full platform status panel."""
        from builder_ii.core.config import load_settings

        render_platform_status(load_settings(), verbose=verbose)

    @tui_app.command("roster")
    def tui_roster(
        verbose: bool = _typer.Option(False, "--verbose", "-v", help="Show HF repos and notes."),
    ) -> None:
        """Model roster with inline cache bars."""
        from builder_ii.core.config import load_settings

        render_header(subtitle="model roster")
        render_model_roster(load_settings(), verbose=verbose)

    @tui_app.command("gates")
    def tui_gates(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
        chat: bool = _typer.Option(False, "--chat", help="Run live chat smoke test."),
    ) -> None:
        """Capability gate grid."""
        from builder_ii.core.config import load_settings
        from builder_ii.governance.authority import CommandAuthorityError, enforce_command_authority
        from builder_ii.governance.authority.capabilities import capability_gates

        try:
            enforce_command_authority(
                "builder tui gates",
                requested_effects=("model_execution",) if chat else (),
            )
        except CommandAuthorityError as exc:
            render_errors([str(exc)], title="command authority")
            raise _typer.Exit(1) from None
        render_header(subtitle="capability gates")
        settings = load_settings()
        gates = capability_gates(settings, run_chat_smoke=chat)
        ok = render_capability_gates(gates, verbose=verbose)
        raise _typer.Exit(0 if ok else 1)

    @tui_app.command("hitl")
    def tui_hitl(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Show pending HITL gate queue."""
        from builder_ii.core.config import load_settings
        from builder_ii.governance.hitl.hitl_execution_records import load_pending_hitl_records

        render_header(subtitle="HITL queue")
        settings = load_settings()
        try:
            records = load_pending_hitl_records(settings)
        except Exception:
            records = []
        if not records:
            console.print(f"  {_G_PASS} [{_C['hint']}]no pending HITL gates[/]")
            return
        for rec in records:
            render_hitl_banner(
                gate_label=rec.get("label", "pending gate"),
                apply_command=rec.get("apply_command", "—"),
                rollback_command=rec.get("rollback_command", "—"),
                evidence_path=rec.get("evidence_path"),
                verbose=verbose,
            )

    @tui_app.command("handoff")
    def tui_handoff(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Latest handoff note summary."""
        from builder_ii.core.config import load_settings
        from builder_ii.core.handoff_notes import load_latest_handoff_note

        render_header(subtitle="handoff")
        settings = load_settings()
        try:
            note = load_latest_handoff_note(settings)
        except Exception:
            note = None
        if note is None:
            console.print(f"  {_G_HINT} [{_C['hint']}]no handoff note found[/]")
            return
        render_handoff_summary(note, verbose=verbose)

    @tui_app.command("golden")
    def tui_golden(
        target: str = _typer.Option(..., "--target", "-t", help="Target profile."),
        output_dir: str = _typer.Option(..., "--output-dir", "-o", help="Output directory."),
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Golden path summary."""
        from pathlib import Path as _Path

        from builder_ii.lifecycle.setup.operator_golden_path import (
            create_operator_golden_path_report,
            validate_operator_golden_path_report,
        )

        render_header(subtitle="golden path")
        report = create_operator_golden_path_report(
            target_profile=target,
            output_dir=_Path(output_dir).resolve(),
        )
        errors = validate_operator_golden_path_report(report)
        if errors:
            render_errors(errors, title="golden path validation")
            raise _typer.Exit(1)
        render_golden_path_summary(report, verbose=verbose)

except ImportError:
    tui_app = None  # type: ignore[assignment]
