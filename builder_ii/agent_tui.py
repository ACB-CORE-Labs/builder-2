"""builder-II agent/orchestration/context/traceability TUI layer.

Design contract (same as tui.py)
---------------------------------
* Every public function writes to the shared Rich console and returns None.
* Every function accepts ``verbose: bool = False``.
* No function raises — errors are printed as structured WARN/FAIL rows.
* Color = semantic signal only. Left-aligned glyph column throughout.
* Stdout is always parseable when piped (Rich strips markup for non-TTYs).
"""
from __future__ import annotations

from typing import Any, Iterable, Optional, Sequence

from rich.panel import Panel
from rich.table import Table

# Re-use the palette and glyphs from tui.py
from builder_ii.tui_cli import (
    _C,
    _G_ACT,
    _G_DIM,
    _G_FAIL,
    _G_HINT,
    _G_PASS,
    _G_WARN,
    _glyph,
    _hint,
    _label,
    _section,
    _value,
    console,
    render_errors,
    render_header,
)

# ---------------------------------------------------------------------------
# Internal helpers (agent layer)
# ---------------------------------------------------------------------------

def _profile_glyph(profile: Any) -> str:
    enabled = getattr(profile, "enabled", True)
    if not enabled:
        return _G_DIM
    tier = (getattr(profile, "model_tier", None) or "").lower()
    if "fast" in tier:
        return f"[{_C['warn']}]\u25cf[/]"
    return _G_ACT


def _tier_badge(tier: str) -> str:
    color = _C["warn"] if "fast" in tier.lower() else _C["active"]
    return f"[{color}]{tier}[/]"


def _lane_badge(lane: str) -> str:
    return f"[{_C['accent']}]{lane}[/]"


def _pack_token_bar(token_count: int, budget: int, width: int = 14) -> str:
    if budget <= 0:
        return f"[{_C['dim']}]{token_count:>6}[/]"
    ratio = min(token_count / budget, 1.0)
    filled = round(ratio * width)
    bar = "\u2588" * filled + "\u2591" * (width - filled)
    color = _C["pass"] if ratio < 0.80 else (_C["warn"] if ratio < 0.95 else _C["fail"])
    return f"[{color}]{bar}[/] {token_count:>6}/{budget}"


# ---------------------------------------------------------------------------
# Agent profiles
# ---------------------------------------------------------------------------

def render_agent_profiles(
    profiles: Iterable[Any],
    *,
    verbose: bool = False,
) -> None:
    """Render agent profile roster with capability matrix."""
    _section("agent profiles")
    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",             no_wrap=True, min_width=2)
    table.add_column("name",         no_wrap=True, min_width=26)
    table.add_column("tier",         no_wrap=True, min_width=10)
    table.add_column("lane",         no_wrap=True, min_width=14)
    table.add_column("tools",        no_wrap=True, min_width=8)
    if verbose:
        table.add_column("persona",  no_wrap=False, min_width=40)

    for p in profiles:
        name    = getattr(p, "name",       None) or p.get("name",       "?") if hasattr(p, "get") else "?"
        tier    = getattr(p, "model_tier", None) or p.get("model_tier", "?") if hasattr(p, "get") else "?"
        lane    = getattr(p, "lane",       None) or p.get("lane",       "?") if hasattr(p, "get") else "?"
        tools   = getattr(p, "tools",      None) or p.get("tools",      [])  if hasattr(p, "get") else []
        persona = getattr(p, "persona",    None) or p.get("persona",    "")  if hasattr(p, "get") else ""
        enabled = getattr(p, "enabled",    True) if not hasattr(p, "get") else p.get("enabled", True)

        glyph_cell = _G_ACT if enabled else _G_DIM
        name_cell  = (
            f"[{_C['bold']} bold]{name}[/]"
            if enabled
            else f"[{_C['dim']}]{name}[/]"
        )
        tool_count = str(len(tools)) if isinstance(tools, (list, tuple)) else str(tools)
        row = [glyph_cell, name_cell, _tier_badge(str(tier)), _lane_badge(str(lane)), _value(tool_count)]
        if verbose:
            row.append(f"[{_C['hint']}]{str(persona)[:80]}[/]")
        table.add_row(*row)

        if verbose and isinstance(tools, (list, tuple)) and tools:
            tool_list = "  ".join(f"[{_C['accent']}]{t}[/]" for t in tools)
            table.add_row("", "", "", "", tool_list, *(["" ] if verbose else []))

    console.print(table)
    console.print()


def render_agent_profile_detail(
    profile: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render single agent profile as a structured deep-dive panel."""
    name    = getattr(profile, "name",       None) or profile.get("name",       "?") if hasattr(profile, "get") else "?"
    tier    = getattr(profile, "model_tier", None) or profile.get("model_tier", "?") if hasattr(profile, "get") else "?"
    lane    = getattr(profile, "lane",       None) or profile.get("lane",       "?") if hasattr(profile, "get") else "?"
    tools   = getattr(profile, "tools",      None) or profile.get("tools",      [])  if hasattr(profile, "get") else []
    persona = getattr(profile, "persona",    None) or profile.get("persona",    "")  if hasattr(profile, "get") else ""
    constraints = getattr(profile, "constraints", None) or profile.get("constraints", []) if hasattr(profile, "get") else []
    extensions  = getattr(profile, "extensions",  None) or profile.get("extensions",  []) if hasattr(profile, "get") else []

    lines = [
        f"[{_C['bold']} bold]{name}[/]  {_tier_badge(str(tier))}  {_lane_badge(str(lane))}",
    ]
    if persona:
        lines.append(f"\n[{_C['hint']}]{persona[:160]}[/]")
    if tools:
        lines.append(f"\n[{_C['dim']}]tools[/]  " + "  ".join(f"[{_C['accent']}]{t}[/]" for t in tools))
    if constraints and verbose:
        lines.append(f"\n[{_C['dim']}]constraints[/]")
        for c in constraints:
            lines.append(f"  {_G_DIM} [{_C['hint']}]{c}[/]")
    if extensions and verbose:
        lines.append(f"\n[{_C['dim']}]extensions[/]")
        for e in extensions:
            lines.append(f"  {_G_HINT} [{_C['accent']}]{e}[/]")

    console.print(
        Panel(
            "\n".join(lines),
            border_style=_C["accent"],
            title=f"[{_C['accent']}]agent profile[/]",
            padding=(1, 2),
        )
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def render_orchestration_assignment(
    assignment: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render orchestration assignment table — role/lane/tier per agent slot."""
    _section("orchestration assignment")
    slots = (
        assignment.get("slots", []) if hasattr(assignment, "get")
        else getattr(assignment, "slots", [])
    )
    if not slots:
        console.print(f"  {_G_DIM} [{_C['hint']}]no agent slots assigned[/]")
        return

    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",         no_wrap=True, min_width=2)
    table.add_column("slot",     no_wrap=True, min_width=6)
    table.add_column("agent",    no_wrap=True, min_width=24)
    table.add_column("role",     no_wrap=True, min_width=20)
    table.add_column("lane",     no_wrap=True, min_width=14)
    table.add_column("tier",     no_wrap=True, min_width=10)
    if verbose:
        table.add_column("task", no_wrap=False, min_width=36)

    for i, slot in enumerate(slots):
        agent  = slot.get("agent",  "") if hasattr(slot, "get") else getattr(slot, "agent",  "")
        role   = slot.get("role",   "") if hasattr(slot, "get") else getattr(slot, "role",   "")
        lane   = slot.get("lane",   "") if hasattr(slot, "get") else getattr(slot, "lane",   "")
        tier   = slot.get("tier",   "") if hasattr(slot, "get") else getattr(slot, "tier",   "")
        task   = slot.get("task",   "") if hasattr(slot, "get") else getattr(slot, "task",   "")
        status = slot.get("status", "") if hasattr(slot, "get") else getattr(slot, "status", "")
        row = [
            _glyph(status or "dim"),
            _value(str(i + 1)),
            f"[{_C['bold']}]{agent}[/]",
            f"[{_C['dim']}]{role}[/]",
            _lane_badge(str(lane)),
            _tier_badge(str(tier)),
        ]
        if verbose:
            row.append(f"[{_C['hint']}]{str(task)[:60]}[/]")
        table.add_row(*row)

    console.print(table)
    console.print()


def render_orchestration_plan(
    plan: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render orchestration plan step timeline."""
    _section("orchestration plan")
    steps = (
        plan.get("steps", []) if hasattr(plan, "get")
        else getattr(plan, "steps", [])
    )
    if not steps:
        console.print(f"  {_G_DIM} [{_C['hint']}]no steps[/]")
        return

    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True, min_width=2)
    table.add_column(no_wrap=True, min_width=5)
    table.add_column(no_wrap=True, min_width=30)
    table.add_column()

    for i, step in enumerate(steps):
        label  = step.get("label",  "") if hasattr(step, "get") else str(step)
        status = step.get("status", "") if hasattr(step, "get") else ""
        agent  = step.get("agent",  "") if hasattr(step, "get") else ""
        detail = step.get("detail", "") if hasattr(step, "get") else ""
        table.add_row(
            _glyph(status or "dim"),
            f"[{_C['dim']}]{i + 1:>2}[/]",
            f"[{_C['bold']}]{label}[/]"
            + (f"  [{_C['accent']}]{agent}[/]" if agent else ""),
            f"[{_C['hint']}]{detail[:80] if verbose else ''}[/]",
        )

    console.print(table)
    console.print()


def render_orchestration_dry_run(
    dry_run: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render orchestration dry-run diff summary."""
    _section("dry-run")
    changes = (
        dry_run.get("changes", []) if hasattr(dry_run, "get")
        else getattr(dry_run, "changes", [])
    )
    valid = (
        dry_run.get("valid", False) if hasattr(dry_run, "get")
        else getattr(dry_run, "valid", False)
    )
    g = _G_PASS if valid else _G_FAIL
    console.print(f"  {g} [{_C['bold']}]dry-run {'clean' if valid else 'has issues'}[/]  [{_C['hint']}]{len(changes)} changes[/]")
    if changes and verbose:
        for ch in changes[:20]:
            kind   = ch.get("kind",   "+") if hasattr(ch, "get") else "+"
            target = ch.get("target", "") if hasattr(ch, "get") else str(ch)
            note   = ch.get("note",   "") if hasattr(ch, "get") else ""
            color  = _C["pass"] if kind == "+" else (_C["fail"] if kind == "-" else _C["warn"])
            console.print(f"  [{color}]{kind}[/] [{_C['bold']}]{target}[/]  [{_C['hint']}]{note}[/]")
    console.print()


# ---------------------------------------------------------------------------
# deepagents
# ---------------------------------------------------------------------------

def render_deepagents_readiness(
    readiness: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render deepagents bridge + policy readiness grid."""
    _section("deepagents readiness")
    checks = (
        readiness.get("checks", []) if hasattr(readiness, "get")
        else getattr(readiness, "checks", [])
    )
    if not checks:
        # Try to iterate the object directly
        checks = list(readiness) if hasattr(readiness, "__iter__") else []

    if not checks:
        console.print(f"  {_G_HINT} [{_C['hint']}]no readiness checks available[/]")
        return

    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",        no_wrap=True, min_width=2)
    table.add_column("check",   no_wrap=True, min_width=30)
    table.add_column("result",  no_wrap=True, min_width=8)
    if verbose:
        table.add_column("detail", no_wrap=False)

    all_pass = True
    for check in checks:
        name   = check.get("name",   "") if hasattr(check, "get") else getattr(check, "name",   str(check))
        result = check.get("result", "") if hasattr(check, "get") else getattr(check, "result", "")
        detail = check.get("detail", "") if hasattr(check, "get") else getattr(check, "detail", "")
        if result.upper() not in ("PASS", "OK"):
            all_pass = False
        r_color = _C["pass"] if result.upper() in ("PASS", "OK") else (
            _C["warn"] if result.upper() == "WARN" else _C["fail"]
        )
        row = [
            _glyph(result),
            f"[{_C['bold']}]{name}[/]",
            f"[{r_color}]{result}[/]",
        ]
        if verbose:
            row.append(f"[{_C['hint']}]{detail}[/]")
        table.add_row(*row)

    console.print(table)
    if not all_pass:
        console.print(_hint("bridge is not fully ready; review policy and dependency smoke checks"))
    console.print()


def render_deepagents_policy(
    policy: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render deepagents policy gate table."""
    _section("deepagents policy")
    gates = (
        policy.get("gates", []) if hasattr(policy, "get")
        else getattr(policy, "gates", [])
    )
    if not gates:
        console.print(f"  {_G_HINT} [{_C['hint']}]no policy gates defined[/]")
        return

    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",       no_wrap=True, min_width=2)
    table.add_column("gate",   no_wrap=True, min_width=30)
    table.add_column("status", no_wrap=True, min_width=10)
    if verbose:
        table.add_column("rule", no_wrap=False)

    for gate in gates:
        name   = gate.get("name",   "") if hasattr(gate, "get") else str(gate)
        status = gate.get("status", "") if hasattr(gate, "get") else ""
        rule   = gate.get("rule",   "") if hasattr(gate, "get") else ""
        s_color = _C["pass"] if status.upper() in ("ENABLED", "OPEN", "PASS") else _C["warn"]
        row = [_glyph(status or "dim"), f"[{_C['bold']}]{name}[/]", f"[{s_color}]{status}[/]"]
        if verbose:
            row.append(f"[{_C['hint']}]{rule}[/]")
        table.add_row(*row)

    console.print(table)
    console.print()


def render_deepagents_work_queue(
    artifacts: Iterable[Any],
    *,
    verbose: bool = False,
) -> None:
    """Render pending deepagents work-artifact queue."""
    _section("deepagents work queue")
    items = list(artifacts)
    if not items:
        console.print(f"  {_G_PASS} [{_C['hint']}]queue empty[/]")
        return

    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",         no_wrap=True, min_width=2)
    table.add_column("id",       no_wrap=True, min_width=18)
    table.add_column("kind",     no_wrap=True, min_width=20)
    table.add_column("agent",    no_wrap=True, min_width=20)
    table.add_column("status",   no_wrap=True, min_width=10)
    if verbose:
        table.add_column("path", no_wrap=True)

    for art in items:
        art_id  = art.get("id",     "") if hasattr(art, "get") else getattr(art, "id",     "?")
        kind    = art.get("kind",   "") if hasattr(art, "get") else getattr(art, "kind",   "?")
        agent   = art.get("agent",  "") if hasattr(art, "get") else getattr(art, "agent",  "?")
        status  = art.get("status", "") if hasattr(art, "get") else getattr(art, "status", "?")
        path    = art.get("path",   "") if hasattr(art, "get") else getattr(art, "path",   "")
        row = [
            _glyph(status or "dim"),
            f"[{_C['dim']}]{str(art_id)[:16]}[/]",
            f"[{_C['accent']}]{kind}[/]",
            f"[{_C['bold']}]{agent}[/]",
            f"[{_C['pass'] if status.upper() == 'COMPLETE' else _C['warn']}]{status}[/]",
        ]
        if verbose:
            row.append(f"[{_C['hint']}]{path}[/]")
        table.add_row(*row)

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Event ledger replay
# ---------------------------------------------------------------------------

def render_event_replay(
    events: Sequence[Any],
    *,
    n: int = 20,
    agent_filter: Optional[str] = None,
    kind_filter: Optional[str] = None,
    verbose: bool = False,
) -> None:
    """Render chronological event ledger replay."""
    _section("event ledger replay")
    filtered = list(events)
    if agent_filter:
        filtered = [
            e for e in filtered
            if agent_filter.lower() in (
                (e.get("agent", "") if hasattr(e, "get") else getattr(e, "agent", "")).lower()
            )
        ]
    if kind_filter:
        filtered = [
            e for e in filtered
            if kind_filter.lower() in (
                (e.get("kind", "") if hasattr(e, "get") else getattr(e, "kind", "")).lower()
            )
        ]
    tail = filtered[-n:] if n > 0 else filtered
    total = len(filtered)
    shown = len(tail)

    console.print(f"  [{_C['dim']}]showing {shown} of {total} events[/]\n")

    for ev in tail:
        ts     = ev.get("ts",      ev.get("timestamp", "")) if hasattr(ev, "get") else getattr(ev, "ts", "")
        kind   = ev.get("kind",    "") if hasattr(ev, "get") else getattr(ev, "kind",    "")
        agent  = ev.get("agent",   "") if hasattr(ev, "get") else getattr(ev, "agent",   "")
        result = ev.get("result",  "") if hasattr(ev, "get") else getattr(ev, "result",  "")
        detail = ev.get("detail",  ev.get("message", "")) if hasattr(ev, "get") else getattr(ev, "detail", "")

        ts_str = str(ts)[:19] if ts else "                   "
        console.print(
            f"  {_glyph(result or 'dim')} "
            f"[{_C['dim']}]{ts_str}[/] "
            f"[{_C['accent']}]{kind:<24}[/] "
            f"[{_C['bold']}]{agent:<20}[/]"
            + (f"  [{_C['hint']}]{str(detail)[:80]}[/]" if verbose and detail else "")
        )

    console.print()


# ---------------------------------------------------------------------------
# Context engineering
# ---------------------------------------------------------------------------

def render_context_packs(
    packs: Iterable[Any],
    *,
    verbose: bool = False,
) -> None:
    """Render context-pack composition map with token budget bars."""
    _section("context packs")
    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",             no_wrap=True, min_width=2)
    table.add_column("pack",         no_wrap=True, min_width=26)
    table.add_column("sources",      no_wrap=True, min_width=8)
    table.add_column("token budget", no_wrap=True, min_width=30)
    if verbose:
        table.add_column("target",   no_wrap=True, min_width=16)

    for pack in packs:
        name    = pack.get("name",    "") if hasattr(pack, "get") else getattr(pack, "name",    "?")
        sources = pack.get("sources", []) if hasattr(pack, "get") else getattr(pack, "sources", [])
        tokens  = pack.get("token_count", 0) if hasattr(pack, "get") else getattr(pack, "token_count", 0)
        budget  = pack.get("token_budget", 0) if hasattr(pack, "get") else getattr(pack, "token_budget", 0)
        target  = pack.get("target",  "") if hasattr(pack, "get") else getattr(pack, "target",  "")
        valid   = pack.get("valid",   True) if hasattr(pack, "get") else getattr(pack, "valid",  True)

        bar = _pack_token_bar(int(tokens), int(budget))
        n_src = str(len(sources)) if isinstance(sources, (list, tuple)) else str(sources)
        row = [
            _glyph("pass" if valid else "warn"),
            f"[{_C['bold']}]{name}[/]",
            _value(n_src),
            bar,
        ]
        if verbose:
            row.append(f"[{_C['hint']}]{target}[/]")
        table.add_row(*row)

        if verbose and isinstance(sources, (list, tuple)) and sources:
            src_line = "  ".join(f"[{_C['dim']}]{s}[/]" for s in sources[:6])
            table.add_row("", "", src_line, "", "")

    console.print(table)
    console.print()


def render_context_pack_detail(
    pack: Any,
    *,
    verbose: bool = False,
) -> None:
    """Single context pack deep-dive."""
    name    = pack.get("name",    "") if hasattr(pack, "get") else getattr(pack, "name",    "?")
    sources = pack.get("sources", []) if hasattr(pack, "get") else getattr(pack, "sources", [])
    tokens  = pack.get("token_count", 0) if hasattr(pack, "get") else getattr(pack, "token_count", 0)
    budget  = pack.get("token_budget", 0) if hasattr(pack, "get") else getattr(pack, "token_budget", 0)
    notes   = pack.get("notes",  "") if hasattr(pack, "get") else getattr(pack, "notes",  "")

    bar = _pack_token_bar(int(tokens), int(budget), width=18)
    lines = [
        f"[{_C['bold']} bold]{name}[/]  {bar}",
    ]
    if notes:
        lines.append(f"\n[{_C['hint']}]{notes[:200]}[/]")
    if sources:
        lines.append(f"\n[{_C['dim']}]sources ({len(sources)})[/]")
        for s in sources:
            lines.append(f"  {_G_DIM} [{_C['hint']}]{s}[/]")

    console.print(
        Panel(
            "\n".join(lines),
            border_style=_C["accent"],
            title=f"[{_C['accent']}]context pack[/]",
            padding=(1, 2),
        )
    )


def render_recipe_context_projection(
    projection: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render recipe context projection (context sources → recipe slots)."""
    _section("recipe context projection")
    slots = (
        projection.get("slots", []) if hasattr(projection, "get")
        else getattr(projection, "slots", [])
    )
    if not slots:
        console.print(f"  {_G_HINT} [{_C['hint']}]no slots projected[/]")
        return

    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True, min_width=2)
    table.add_column(no_wrap=True, min_width=22)
    table.add_column(no_wrap=True, min_width=30)
    table.add_column()

    for slot in slots:
        slot_name = slot.get("slot",   "") if hasattr(slot, "get") else str(slot)
        source    = slot.get("source", "") if hasattr(slot, "get") else ""
        tokens    = slot.get("tokens", 0)  if hasattr(slot, "get") else 0
        valid     = slot.get("valid",  True) if hasattr(slot, "get") else True
        table.add_row(
            _glyph("pass" if valid else "warn"),
            f"[{_C['bold']}]{slot_name}[/]",
            f"[{_C['hint']}]{source[:40]}[/]",
            f"[{_C['dim']}]{tokens} tok[/]",
        )

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Traceability: artifact index + chain
# ---------------------------------------------------------------------------

def render_artifact_index(
    records: Iterable[Any],
    *,
    verbose: bool = False,
) -> None:
    """Render artifact index as a breadcrumb table."""
    _section("artifact index")
    items = list(records)
    if not items:
        console.print(f"  {_G_HINT} [{_C['hint']}]no artifacts indexed[/]")
        return

    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",       no_wrap=True, min_width=2)
    table.add_column("kind",   no_wrap=True, min_width=24)
    table.add_column("digest", no_wrap=True, min_width=16)
    table.add_column("ts",     no_wrap=True, min_width=19)
    if verbose:
        table.add_column("path", no_wrap=True)

    for rec in items:
        kind   = rec.get("kind",   "") if hasattr(rec, "get") else getattr(rec, "kind",   "?")
        digest = rec.get("digest", "") if hasattr(rec, "get") else getattr(rec, "digest", "?")
        ts     = rec.get("ts",     rec.get("timestamp", "")) if hasattr(rec, "get") else getattr(rec, "ts", "")
        path   = rec.get("path",   "") if hasattr(rec, "get") else getattr(rec, "path",   "")
        valid  = rec.get("valid",  True) if hasattr(rec, "get") else True
        row = [
            _glyph("pass" if valid else "warn"),
            f"[{_C['accent']}]{kind}[/]",
            f"[{_C['dim']}]{str(digest)[:14]}[/]",
            f"[{_C['hint']}]{str(ts)[:19]}[/]",
        ]
        if verbose:
            row.append(f"[{_C['hint']}]{path}[/]")
        table.add_row(*row)

    console.print(table)
    console.print()


def render_chain_summary(
    summaries: Iterable[Any],
    *,
    verbose: bool = False,
) -> None:
    """Render artifact chain summary digests."""
    _section("chain summary")
    items = list(summaries)
    if not items:
        console.print(f"  {_G_HINT} [{_C['hint']}]no chain summaries[/]")
        return

    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True, min_width=2)
    table.add_column(no_wrap=True, min_width=26)
    table.add_column(no_wrap=True, min_width=16)
    table.add_column()

    for s in items:
        label  = s.get("label",  "") if hasattr(s, "get") else str(s)
        digest = s.get("digest", "") if hasattr(s, "get") else ""
        valid  = s.get("valid",  True) if hasattr(s, "get") else True
        note   = s.get("note",   "") if hasattr(s, "get") else ""
        table.add_row(
            _glyph("pass" if valid else "warn"),
            f"[{_C['bold']}]{label}[/]",
            f"[{_C['dim']}]{str(digest)[:14]}[/]",
            f"[{_C['hint']}]{note[:60] if verbose else ''}[/]",
        )

    console.print(table)
    console.print()


def render_receipt_chain(
    receipts: Iterable[Any],
    *,
    verbose: bool = False,
) -> None:
    """Render model execution receipt chain."""
    _section("receipt chain")
    items = list(receipts)
    if not items:
        console.print(f"  {_G_HINT} [{_C['hint']}]no receipts[/]")
        return

    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",         no_wrap=True, min_width=2)
    table.add_column("session",  no_wrap=True, min_width=18)
    table.add_column("model",    no_wrap=True, min_width=22)
    table.add_column("tokens",   no_wrap=True, min_width=10)
    table.add_column("ts",       no_wrap=True, min_width=19)
    if verbose:
        table.add_column("path", no_wrap=True)

    for r in items:
        session = r.get("session_id", "") if hasattr(r, "get") else getattr(r, "session_id", "?")
        model   = r.get("model_id",   "") if hasattr(r, "get") else getattr(r, "model_id",   "?")
        tokens  = r.get("total_tokens", r.get("tokens", 0)) if hasattr(r, "get") else 0
        ts      = r.get("ts", r.get("timestamp", "")) if hasattr(r, "get") else ""
        path    = r.get("path", "") if hasattr(r, "get") else ""
        ok      = r.get("ok", True) if hasattr(r, "get") else True
        row = [
            _glyph("pass" if ok else "fail"),
            f"[{_C['dim']}]{str(session)[:16]}[/]",
            f"[{_C['bold']}]{model}[/]",
            f"[{_C['hint']}]{tokens:>7}[/]",
            f"[{_C['hint']}]{str(ts)[:19]}[/]",
        ]
        if verbose:
            row.append(f"[{_C['hint']}]{path}[/]")
        table.add_row(*row)

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Roles and lanes
# ---------------------------------------------------------------------------

def render_role_roster(
    roles: Iterable[Any],
    *,
    verbose: bool = False,
) -> None:
    """Render role roster with gate status."""
    _section("roles")
    table = Table(box=None, padding=(0, 2), show_header=True, header_style=_C["dim"])
    table.add_column("",          no_wrap=True, min_width=2)
    table.add_column("role",      no_wrap=True, min_width=24)
    table.add_column("lane",      no_wrap=True, min_width=14)
    table.add_column("gates",     no_wrap=True, min_width=8)
    if verbose:
        table.add_column("notes", no_wrap=False)

    for role in roles:
        name   = role.get("name",   "") if hasattr(role, "get") else getattr(role, "name",   str(role))
        lane   = role.get("lane",   "") if hasattr(role, "get") else getattr(role, "lane",   "")
        gates  = role.get("gates",  []) if hasattr(role, "get") else getattr(role, "gates",  [])
        notes  = role.get("notes",  "") if hasattr(role, "get") else getattr(role, "notes",  "")
        active = role.get("active", True) if hasattr(role, "get") else True
        g_count = str(len(gates)) if isinstance(gates, (list, tuple)) else str(gates)
        row = [
            _G_ACT if active else _G_DIM,
            f"[{_C['bold']}]{name}[/]",
            _lane_badge(str(lane)),
            _value(g_count),
        ]
        if verbose:
            row.append(f"[{_C['hint']}]{str(notes)[:60]}[/]")
        table.add_row(*row)

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# Handoff and notes
# ---------------------------------------------------------------------------

def render_handoff_bundle(
    bundle: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render handoff bundle record with artifact chain links."""
    _section("handoff bundle")
    name      = bundle.get("name",      "") if hasattr(bundle, "get") else getattr(bundle, "name",      "?")
    branch    = bundle.get("branch",    "") if hasattr(bundle, "get") else getattr(bundle, "branch",    "")
    artifacts = bundle.get("artifacts", []) if hasattr(bundle, "get") else getattr(bundle, "artifacts", [])
    valid     = bundle.get("valid",     True) if hasattr(bundle, "get") else True
    summary   = bundle.get("summary",   "") if hasattr(bundle, "get") else ""

    g = _G_PASS if valid else _G_WARN
    lines = [
        f"{g} [{_C['bold']} bold]{name}[/]" + (f"  [{_C['hint']}]branch: {branch}[/]" if branch else ""),
    ]
    if summary:
        lines.append(f"\n[{_C['hint']}]{summary[:200]}[/]")
    if artifacts and verbose:
        lines.append(f"\n[{_C['dim']}]artifacts ({len(artifacts)})[/]")
        for art in artifacts:
            art_label = art.get("kind", str(art)) if hasattr(art, "get") else str(art)
            art_path  = art.get("path", "")       if hasattr(art, "get") else ""
            lines.append(f"  {_G_HINT} [{_C['accent']}]{art_label}[/]  [{_C['hint']}]{art_path}[/]")

    console.print(
        Panel(
            "\n".join(lines),
            border_style=_C["accent"],
            title=f"[{_C['accent']}]handoff bundle[/]",
            padding=(1, 2),
        )
    )
    console.print()


# ---------------------------------------------------------------------------
# Research plans
# ---------------------------------------------------------------------------

def render_research_plan(
    plan: Any,
    *,
    verbose: bool = False,
) -> None:
    """Render research plan steps with status/owner/artifact."""
    _section("research plan")
    steps = (
        plan.get("steps", []) if hasattr(plan, "get")
        else getattr(plan, "steps", [])
    )
    title = (
        plan.get("title", "Research Plan") if hasattr(plan, "get")
        else getattr(plan, "title", "Research Plan")
    )
    console.print(f"  [{_C['bold']}]{title}[/]\n")

    if not steps:
        console.print(f"  {_G_HINT} [{_C['hint']}]no steps[/]")
        return

    table = Table.grid(padding=(0, 2))
    table.add_column(no_wrap=True, min_width=2)
    table.add_column(no_wrap=True, min_width=4)
    table.add_column(no_wrap=True, min_width=34)
    table.add_column(no_wrap=True, min_width=16)
    table.add_column()

    for i, step in enumerate(steps):
        label    = step.get("label",    "") if hasattr(step, "get") else str(step)
        status   = step.get("status",   "") if hasattr(step, "get") else ""
        owner    = step.get("owner",    "") if hasattr(step, "get") else ""
        artifact = step.get("artifact", "") if hasattr(step, "get") else ""
        table.add_row(
            _glyph(status or "dim"),
            f"[{_C['dim']}]{i + 1:>2}[/]",
            f"[{_C['bold']}]{label}[/]",
            f"[{_C['accent']}]{owner}[/]",
            f"[{_C['hint']}]{artifact[:40] if verbose else ''}[/]",
        )

    console.print(table)
    console.print()


# ---------------------------------------------------------------------------
# `builder agent` Typer sub-command group
# ---------------------------------------------------------------------------

try:
    import typer as _typer

    agent_app = _typer.Typer(
        name="agent",
        help="Agent profile and orchestration panels.",
        no_args_is_help=True,
    )

    @agent_app.command("profiles")
    def cmd_profiles(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Agent profile roster with capability matrix."""
        from builder_ii.agent_profiles import list_agent_profiles
        render_header(subtitle="agent profiles")
        try:
            profiles = list_agent_profiles()
        except Exception as exc:
            render_errors([str(exc)], title="agent profiles")
            raise _typer.Exit(1)
        render_agent_profiles(profiles, verbose=verbose)

    @agent_app.command("profile")
    def cmd_profile(
        name:    str  = _typer.Argument(..., help="Profile name."),
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Single agent profile deep-dive."""
        from builder_ii.agent_profiles import get_agent_profile
        render_header(subtitle=f"agent profile — {name}")
        try:
            profile = get_agent_profile(name)
        except Exception as exc:
            render_errors([str(exc)], title="agent profile")
            raise _typer.Exit(1)
        render_agent_profile_detail(profile, verbose=verbose)

    @agent_app.command("team")
    def cmd_team(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Orchestration assignment table."""
        from builder_ii.config import load_settings
        from builder_ii.orchestration_assignment import load_orchestration_assignment
        render_header(subtitle="agent team")
        settings = load_settings()
        try:
            assignment = load_orchestration_assignment(settings)
        except Exception as exc:
            render_errors([str(exc)], title="orchestration assignment")
            raise _typer.Exit(1)
        render_orchestration_assignment(assignment, verbose=verbose)

    @agent_app.command("plan")
    def cmd_plan(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Orchestration plan step timeline."""
        from builder_ii.config import load_settings
        from builder_ii.orchestration_plan import load_orchestration_plan
        render_header(subtitle="orchestration plan")
        settings = load_settings()
        try:
            plan = load_orchestration_plan(settings)
        except Exception as exc:
            render_errors([str(exc)], title="orchestration plan")
            raise _typer.Exit(1)
        render_orchestration_plan(plan, verbose=verbose)

    @agent_app.command("dry-run")
    def cmd_dry_run(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Orchestration dry-run diff summary."""
        from builder_ii.config import load_settings
        from builder_ii.orchestration_dry_run import run_orchestration_dry_run
        render_header(subtitle="orchestration dry-run")
        settings = load_settings()
        try:
            dry = run_orchestration_dry_run(settings)
        except Exception as exc:
            render_errors([str(exc)], title="dry-run")
            raise _typer.Exit(1)
        render_orchestration_dry_run(dry, verbose=verbose)

    # ----- deepagents -----

    deepagents_tui_app = _typer.Typer(
        name="deepagents",
        help="Deepagents bridge, policy, queue, and replay panels.",
        no_args_is_help=True,
    )

    @deepagents_tui_app.command("readiness")
    def da_readiness(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Bridge + policy readiness grid."""
        from builder_ii.deepagents_readiness import check_deepagents_readiness
        render_header(subtitle="deepagents readiness")
        try:
            readiness = check_deepagents_readiness()
        except Exception as exc:
            render_errors([str(exc)], title="deepagents readiness")
            raise _typer.Exit(1)
        render_deepagents_readiness(readiness, verbose=verbose)

    @deepagents_tui_app.command("policy")
    def da_policy(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Deepagents policy gate table."""
        from builder_ii.deepagents_policy import load_deepagents_policy
        render_header(subtitle="deepagents policy")
        try:
            policy = load_deepagents_policy()
        except Exception as exc:
            render_errors([str(exc)], title="deepagents policy")
            raise _typer.Exit(1)
        render_deepagents_policy(policy, verbose=verbose)

    @deepagents_tui_app.command("queue")
    def da_queue(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Pending work-artifact queue."""
        from builder_ii.config import load_settings
        from builder_ii.deepagents_work_artifacts import load_pending_work_artifacts
        render_header(subtitle="deepagents queue")
        settings = load_settings()
        try:
            arts = load_pending_work_artifacts(settings)
        except Exception as exc:
            render_errors([str(exc)], title="deepagents queue")
            raise _typer.Exit(1)
        render_deepagents_work_queue(arts, verbose=verbose)

    @deepagents_tui_app.command("replay")
    def da_replay(
        n:     int          = _typer.Option(20,   "--n",       help="Last N events."),
        agent: Optional[str] = _typer.Option(None, "--agent",   help="Filter by agent name."),
        kind:  Optional[str] = _typer.Option(None, "--kind",    help="Filter by event kind."),
        verbose: bool        = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Event ledger replay (tail)."""
        from builder_ii.config import load_settings
        from builder_ii.event_ledger import load_events
        render_header(subtitle="event ledger replay")
        settings = load_settings()
        try:
            events = load_events(settings)
        except Exception as exc:
            render_errors([str(exc)], title="event ledger")
            raise _typer.Exit(1)
        render_event_replay(events, n=n, agent_filter=agent, kind_filter=kind, verbose=verbose)

    # ----- context -----

    context_tui_app = _typer.Typer(
        name="context",
        help="Context pack composition, recipe projection, and summarizer panels.",
        no_args_is_help=True,
    )

    @context_tui_app.command("packs")
    def ctx_packs(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Context-pack composition map with token budget bars."""
        from builder_ii.config import load_settings
        from builder_ii.context_packs import list_context_packs
        render_header(subtitle="context packs")
        settings = load_settings()
        try:
            packs = list_context_packs(settings)
        except Exception as exc:
            render_errors([str(exc)], title="context packs")
            raise _typer.Exit(1)
        render_context_packs(packs, verbose=verbose)

    @context_tui_app.command("pack")
    def ctx_pack(
        name:    str  = _typer.Argument(..., help="Pack name."),
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Single context pack deep-dive."""
        from builder_ii.config import load_settings
        from builder_ii.context_packs import get_context_pack
        render_header(subtitle=f"context pack — {name}")
        settings = load_settings()
        try:
            pack = get_context_pack(settings, name)
        except Exception as exc:
            render_errors([str(exc)], title="context pack")
            raise _typer.Exit(1)
        render_context_pack_detail(pack, verbose=verbose)

    @context_tui_app.command("recipe")
    def ctx_recipe(
        name:    str  = _typer.Argument(..., help="Recipe name."),
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Recipe context projection."""
        from builder_ii.config import load_settings
        from builder_ii.goose_recipe_context_projection import project_recipe_context
        render_header(subtitle=f"recipe context — {name}")
        settings = load_settings()
        try:
            projection = project_recipe_context(settings, name)
        except Exception as exc:
            render_errors([str(exc)], title="recipe context")
            raise _typer.Exit(1)
        render_recipe_context_projection(projection, verbose=verbose)

    @context_tui_app.command("summarize")
    def ctx_summarize(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Context summarizer status."""
        from builder_ii.config import load_settings
        from builder_ii.context_summarizer import get_summarizer_status
        render_header(subtitle="context summarizer")
        settings = load_settings()
        try:
            status = get_summarizer_status(settings)
        except Exception as exc:
            render_errors([str(exc)], title="context summarizer")
            raise _typer.Exit(1)
        # Render as a simple grid
        _section("summarizer")
        for key, val in (status.items() if hasattr(status, "items") else vars(status).items()):
            console.print(f"  {_G_DIM} {_label(str(key))} {_value(str(val))}")
        console.print()

    # ----- trace -----

    trace_app = _typer.Typer(
        name="trace",
        help="Traceability: artifact index, chain, receipts, replay, notes.",
        no_args_is_help=True,
    )

    @trace_app.command("artifacts")
    def tr_artifacts(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Artifact index breadcrumb table."""
        from builder_ii.artifact_index_records import load_artifact_index
        from builder_ii.config import load_settings
        render_header(subtitle="artifact index")
        settings = load_settings()
        try:
            records = load_artifact_index(settings)
        except Exception as exc:
            render_errors([str(exc)], title="artifact index")
            raise _typer.Exit(1)
        render_artifact_index(records, verbose=verbose)

    @trace_app.command("chain")
    def tr_chain(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Artifact chain verification digest."""
        from builder_ii.chain_summary_records import load_chain_summaries
        from builder_ii.config import load_settings
        render_header(subtitle="chain summary")
        settings = load_settings()
        try:
            summaries = load_chain_summaries(settings)
        except Exception as exc:
            render_errors([str(exc)], title="chain summary")
            raise _typer.Exit(1)
        render_chain_summary(summaries, verbose=verbose)

    @trace_app.command("receipts")
    def tr_receipts(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Model execution receipt chain."""
        from builder_ii.config import load_settings
        from builder_ii.receipt_records import load_receipt_records
        render_header(subtitle="receipts")
        settings = load_settings()
        try:
            receipts = load_receipt_records(settings)
        except Exception as exc:
            render_errors([str(exc)], title="receipts")
            raise _typer.Exit(1)
        render_receipt_chain(receipts, verbose=verbose)

    @trace_app.command("replay")
    def tr_replay(
        n:     int           = _typer.Option(30,   "--n",       help="Last N events."),
        agent: Optional[str]  = _typer.Option(None, "--agent",   help="Filter by agent."),
        kind:  Optional[str]  = _typer.Option(None, "--kind",    help="Filter by event kind."),
        verbose: bool         = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Event ledger replay with agent/kind filters."""
        from builder_ii.config import load_settings
        from builder_ii.event_ledger import load_events
        render_header(subtitle="trace replay")
        settings = load_settings()
        try:
            events = load_events(settings)
        except Exception as exc:
            render_errors([str(exc)], title="trace replay")
            raise _typer.Exit(1)
        render_event_replay(events, n=n, agent_filter=agent, kind_filter=kind, verbose=verbose)

    @trace_app.command("notes")
    def tr_notes(
        verbose: bool = _typer.Option(False, "--verbose", "-v"),
    ) -> None:
        """Handoff notes and bundle records."""
        from builder_ii.config import load_settings
        from builder_ii.handoff_bundle_records import load_handoff_bundle_records
        from builder_ii.handoff_notes import load_latest_handoff_note
        render_header(subtitle="handoff notes")
        settings = load_settings()
        try:
            note = load_latest_handoff_note(settings)
            if note:
                from builder_ii.tui_cli import render_handoff_summary
                render_handoff_summary(note, verbose=verbose)
        except Exception:
            pass
        try:
            bundles = load_handoff_bundle_records(settings)
            for b in bundles:
                render_handoff_bundle(b, verbose=verbose)
        except Exception:
            pass

except ImportError:
    agent_app          = None  # type: ignore[assignment]
    deepagents_tui_app = None  # type: ignore[assignment]
    context_tui_app    = None  # type: ignore[assignment]
    trace_app          = None  # type: ignore[assignment]
