"""promote_tui.py — Promotion pipeline inspection surface for builder-II.

Covers the five-layer promotion stack:

  promotion_readiness   — gate checks that must pass before promotion is offered
  hitl_promotion        — the HITL-gated promotion artifact (pending / authorized / rejected)
  promotion_decision    — recorded human decision (approve / reject / defer)
  promotion_compatibility — cross-artifact compatibility report
  promotion history     — all decision records under .builder/

Governance note:
  • promote_tui.py is read-only. It never writes promotion artifacts.
  • Creating a promotion decision requires explicit HITL invocation
    (builder hitl promote ... or hitl_promotion_cli.py).
  • This module only surfaces current state and surfaces gate failures.

Command surface
---------------
  builder promote status              — full pipeline state: readiness + pending + decision
  builder promote readiness           — all readiness gate checks
  builder promote artifact [id]       — HITL promotion artifact detail
  builder promote decision [id]       — promotion decision record detail
  builder promote compatibility [id]  — compatibility report
  builder promote history             — all promotion decision records
  builder promote gates               — blocked gate summary (failures only)
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from builder_ii.core.tui_contract import (
    builder_dir as _shared_builder_dir,
)
from builder_ii.core.tui_contract import (
    col as _shared_col,
)
from builder_ii.core.tui_contract import (
    explicit_lookup_miss as _shared_lookup_miss,
)
from builder_ii.core.tui_contract import (
    find_artifact as _shared_find_artifact,
)
from builder_ii.core.tui_contract import (
    glob_kind as _shared_glob_kind,
)
from builder_ii.core.tui_contract import (
    hex_ansi as _shared_hex_ansi,
)
from builder_ii.core.tui_contract import (
    load_json_object as _shared_load_json_object,
)
from builder_ii.core.tui_contract import (
    load_palette,
)
from builder_ii.core.tui_contract import (
    lookup_matches as _shared_lookup_matches,
)
from builder_ii.core.tui_contract import (
    row as _shared_row,
)

# ---------------------------------------------------------------------------
# Palette — theme-aware, shares contract with tui.py / hitl_tui.py
# ---------------------------------------------------------------------------

_IS_TTY = sys.stdout.isatty()

_C = load_palette()


def _hex_ansi(hex_colour: str, text: str) -> str:
    return _shared_hex_ansi(hex_colour, text, _IS_TTY)


def _p(t):
    return _hex_ansi(_C["pass"], t)


def _w(t):
    return _hex_ansi(_C["warn"], t)


def _f(t):
    return _hex_ansi(_C["fail"], t)


def _h(t):
    return _hex_ansi(_C["hint"], t)


def _act(t):
    return _hex_ansi(_C["active"], t)


def _d(t):
    return _hex_ansi(_C["dim"], t)


def _b(t):
    return _hex_ansi(_C["bold"], t)


def _acc(t):
    return _hex_ansi(_C["accent"], t)


G = {
    "pass": _p("✔"),
    "fail": _f("✘"),
    "warn": _w("⚠"),
    "skip": _d("–"),
    "pending": _w("◉"),
    "promote": _p("▲"),
    "reject": _f("▼"),
    "defer": _d("●"),
    "gate": _act("▣"),
    "arrow": _d("→"),
    "lock": _d("○"),
    "bullet": _d("·"),
}

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _builder_dir() -> Path:
    return _shared_builder_dir()


def _col(text: str, width: int) -> str:
    return _shared_col(text, width)


def _hr(w: int = 72) -> str:
    return _d("─" * w)


def _section(title: str) -> None:
    print()
    print(_acc(title))
    print(_hr())


def _kv(key: str, value: str, kw: int = 30) -> None:
    print(f"  {_col(_d(key), kw + 9)}  {value}")


def _row(*cells: tuple[str, int]) -> str:
    return _shared_row(*cells)


def _short(s: str, n: int = 14) -> str:
    if not s or not isinstance(s, str):
        return _d("—")
    return s[:n]


def _ts(ts: Any) -> str:
    if not ts:
        return _d("—")
    s = str(ts)
    return s[:19].replace("T", " ") if "T" in s else s[:19]


# ---------------------------------------------------------------------------
# Decision state helpers
# ---------------------------------------------------------------------------

DECISION_STATES = {
    "APPROVED": (_p("APPROVED"), G["promote"]),
    "PROMOTED": (_p("PROMOTED"), G["promote"]),
    "AUTHORIZED": (_act("AUTHORIZED"), G["gate"]),
    "PENDING": (_w("PENDING"), G["pending"]),
    "REJECTED": (_f("REJECTED"), G["reject"]),
    "DEFERRED": (_d("DEFERRED"), G["defer"]),
}


def _decision_display(state: str) -> tuple[str, str]:
    s = str(state).upper()
    return DECISION_STATES.get(s, (_w(s), G["warn"]))


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> tuple[dict | None, str]:
    return _shared_load_json_object(path)


def _find_artifact(base: Path, *candidates: str) -> tuple[Path | None, dict | None]:
    return _shared_find_artifact(base, *candidates)


def _glob_kind(base: Path, kind_fragment: str, *subdirs: str) -> list[tuple[Path, dict]]:
    return _shared_glob_kind(base, kind_fragment, *subdirs)


def _promote_matches(target: str, path: Path, data: dict) -> bool:
    return _shared_lookup_matches(
        target,
        path.name,
        path,
        data.get("subject", ""),
        data.get("pack_id", ""),
        data.get("artifact_id", ""),
    )


# ---------------------------------------------------------------------------
# Readiness gate renderer
# ---------------------------------------------------------------------------

READINESS_REQUIRED_GATES = [
    "profile_pack_valid",
    "lifecycle_complete",
    "validation_report_valid",
    "hitl_approval_present",
    "governance_clean",
    "no_active_authority_claims",
]


def _render_readiness(data: dict, *, verbose: bool, failures_only: bool = False) -> int:
    """Render a promotion_readiness artifact. Returns 0 if ready, 1 if not."""
    gates = data.get("gates") or data.get("checks") or data.get("readiness_gates") or {}
    overall = data.get("ready") or data.get("promotion_ready") or data.get("all_gates_passed")
    label = data.get("label") or data.get("subject") or _d("—")

    _kv("subject", _b(str(label)))
    _kv("ready", _p("YES") if overall else _f("NO"))
    ts = data.get("timestamp") or data.get("created_at") or ""
    if ts:
        _kv("evaluated", _d(_ts(ts)))

    if isinstance(gates, dict):
        gate_items = gates.items()
    elif isinstance(gates, list):
        gate_items = (
            (g.get("name", g.get("gate", f"gate_{i}")), g.get("passed", g.get("result")))
            for i, g in enumerate(gates)
            if isinstance(g, dict)
        )
    else:
        gate_items = iter([])

    all_pass = True
    evaluated = 0
    for name, passed in gate_items:
        evaluated += 1
        if not passed:
            all_pass = False
        if failures_only and passed:
            continue
        g = G["pass"] if passed else G["fail"]
        label_t = _d(str(name))
        status_t = _p("PASS") if passed else _f("FAIL")
        print(f"    {g}  {_col(label_t, 40)}  {status_t}")
        if verbose and isinstance(gates, list):
            # try to print detail from list-form gate objects
            pass

    # Absence of gates is not readiness: all([]) is vacuously True, which would green a promotion
    # that evaluated nothing. A gate-derived READY therefore requires at least one gate to have been
    # evaluated. An artifact's own explicit ready/promotion_ready/all_gates_passed flag is still
    # honored -- that is the artifact's stated claim to render, not a verdict this renderer invents.
    # No gates and no flag -> NOT ready, mirroring the Third Door's absence-is-not-satisfaction rule.
    gates_ready = all_pass and evaluated > 0
    return 0 if (overall or gates_ready) else 1


# ---------------------------------------------------------------------------
# builder promote status
# ---------------------------------------------------------------------------


def cmd_promote_status(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()

    _section("Promotion Pipeline Status")

    # --- Readiness ---
    _, readiness = _find_artifact(
        base,
        "promotion_readiness.json",
        "promote/promotion_readiness.json",
        "promotion/readiness.json",
    )
    print(f"  {_b('Readiness')}")
    if readiness is None:
        print(f"    {G['skip']}  {_d('No promotion_readiness.json found.')}")
        readiness_ok = False
    else:
        readiness_ok = _render_readiness(readiness, verbose=verbose) == 0

    # --- Pending HITL promotion artifacts ---
    print()
    print(f"  {_b('HITL Promotion Artifacts')}")
    hitl_prom = _glob_kind(base, "hitl_promotion", "promote", "promotion", "hitl")
    if not hitl_prom:
        # Also try hitl_promotion_cli output filenames
        _, hp = _find_artifact(
            base,
            "hitl_promotion.json",
            "promote/hitl_promotion.json",
            "promotion/hitl_promotion.json",
        )
        if hp:
            hitl_prom = [(base / "hitl_promotion.json", hp)]

    if not hitl_prom:
        print(f"    {G['skip']}  {_d('No HITL promotion artifacts found.')}")
    else:
        for path, data in hitl_prom:
            _render_hitl_promo_row(path, data)

    # --- Latest decision ---
    print()
    print(f"  {_b('Latest Decision')}")
    decisions = _glob_kind(base, "promotion_decision", "promote", "promotion")
    if not decisions:
        _, dec = _find_artifact(
            base,
            "promotion_decision.json",
            "promote/promotion_decision.json",
        )
        if dec:
            decisions = [(base / "promotion_decision.json", dec)]

    if not decisions:
        print(f"    {G['skip']}  {_d('No promotion decision records found.')}")
    else:
        # Sort by timestamp if available, show most recent
        latest_path, latest = decisions[-1]
        _render_decision_row(latest_path, latest, verbose=verbose)

    # --- Pipeline state summary ---
    print()
    print(f"  {_b('Pipeline Gate')}")
    _render_pipeline_bar(readiness, hitl_prom, decisions)

    print()
    if readiness is None and not hitl_prom and not decisions:
        return 0
    return 0 if readiness_ok else 1


def _render_hitl_promo_row(path: Path, data: dict) -> None:
    state = str(data.get("promotion_state") or data.get("state") or "?").upper()
    subject = str(data.get("subject") or data.get("pack_id") or data.get("artifact_id") or path.name)[:36]
    state_txt, g = _decision_display(state)
    ts = _ts(data.get("timestamp") or data.get("created_at") or "")
    print(f"    {g}  {_col(_b(subject), 38)}  {state_txt}  {_d(ts)}")


def _render_decision_row(path: Path, data: dict, *, verbose: bool) -> None:
    decision = str(data.get("decision") or data.get("outcome") or "?").upper()
    subject = str(data.get("subject") or data.get("pack_id") or data.get("artifact_id") or path.name)[:36]
    operator = str(data.get("operator") or data.get("decided_by") or _d("—"))[:20]
    ts = _ts(data.get("timestamp") or data.get("decided_at") or "")
    dec_txt, g = _decision_display(decision)
    print(f"    {g}  {_col(_b(subject), 38)}  {dec_txt}  {_d(operator)}  {_d(ts)}")
    if verbose and data.get("rationale"):
        print(f"       {_h(str(data['rationale'])[:80])}")


def _render_pipeline_bar(readiness: dict | None, hitl_prom: list, decisions: list) -> None:
    stages = [
        (
            "Readiness",
            readiness is not None
            and bool(readiness.get("ready") or readiness.get("promotion_ready") or readiness.get("all_gates_passed")),
        ),
        ("HITL Gate", bool(hitl_prom)),
        ("Decision", bool(decisions)),
        (
            "Promoted",
            any(
                str(d.get("decision") or d.get("outcome") or "").upper() in ("APPROVED", "PROMOTED")
                for _, d in decisions
            )
            if decisions
            else False,
        ),
    ]
    parts: list[str] = []
    for label, done in stages:
        parts.append(_p(label) if done else _d(label))
        parts.append(_d(" → "))
    print("    " + "".join(parts[:-1]))  # strip trailing arrow


# ---------------------------------------------------------------------------
# builder promote readiness
# ---------------------------------------------------------------------------


def cmd_promote_readiness(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()

    _, readiness = _find_artifact(
        base,
        "promotion_readiness.json",
        "promote/promotion_readiness.json",
        "promotion/readiness.json",
    )

    _section("Promotion Readiness Gates")

    if readiness is None:
        # Try readiness_records module
        try:
            from builder_ii.lifecycle.candidate.promotion_readiness_records import evaluate_promotion_readiness

            readiness = evaluate_promotion_readiness(base)
        except Exception:
            pass

    if readiness is None:
        print(f"  {G['skip']}  {_d('No promotion_readiness.json found and live evaluation unavailable.')}")
        print(f"  {_h('hint: builder-promotion record  to create a passive readiness record')}")
        print()
        return 1

    rc = _render_readiness(readiness, verbose=verbose)

    # Verbose: show blocking details
    if verbose:
        details = readiness.get("details") or readiness.get("gate_details") or {}
        if details:
            print()
            print(f"  {_b('Gate details')}")
            for k, v in details.items() if isinstance(details, dict) else []:
                print(f"    {_d(k + ':')}  {str(v)[:80]}")

    print()
    return rc


# ---------------------------------------------------------------------------
# builder promote artifact [id]
# ---------------------------------------------------------------------------


def cmd_promote_artifact(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    _section("HITL Promotion Artifact")

    artifacts = _glob_kind(base, "hitl_promotion", "promote", "promotion", "hitl")
    if not artifacts:
        _, hp = _find_artifact(base, "hitl_promotion.json", "promote/hitl_promotion.json")
        if hp:
            artifacts = [(base / "hitl_promotion.json", hp)]

    if id_args:
        target = id_args[0]
        artifacts = [(p, d) for p, d in artifacts if _promote_matches(target, p, d)]

    if not artifacts:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('HITL promotion artifact', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No HITL promotion artifacts found.')}")
        return 0

    rc = 0
    for path, data in artifacts:
        state = str(data.get("promotion_state") or data.get("state") or "?").upper()
        subject = str(data.get("subject") or data.get("pack_id") or path.name)
        state_txt, g = _decision_display(state)

        print(f"  {g}  {_b(subject)}")
        _kv("promotion_state", state_txt)
        _kv("kind", _d(str(data.get("kind", ""))))
        _kv("created_at", _d(_ts(data.get("created_at") or data.get("timestamp") or "")))
        _kv("operator", _d(str(data.get("operator") or _d("—"))))

        # Gate list
        gates = data.get("gates") or data.get("required_gates") or []
        if gates:
            print(f"  {_b('Required gates')}  ({len(gates)})")
            for gate in gates:
                if isinstance(gate, str):
                    print(f"    {G['gate']}  {_d(gate)}")
                elif isinstance(gate, dict):
                    name = gate.get("name") or gate.get("gate") or "?"
                    passed = gate.get("passed", gate.get("result"))
                    gg = G["pass"] if passed else G["fail"]
                    print(f"    {gg}  {_d(str(name))}")

        # Governance
        gov = data.get("governance") or {}
        if gov and verbose:
            print(f"  {_b('Governance')}")
            for k, v in gov.items():
                flag = _p("true") if v is True else (_act(str(v)) if v == "AUTHORIZED" else _d(str(v)))
                print(f"    {G['lock']}  {_col(_d(k), 34)}  {flag}")

        # Subject ref
        subject_ref = data.get("subject_ref") or {}
        if subject_ref and verbose:
            _kv("subject_ref.sha256", _short(subject_ref.get("sha256", "")))

        if state not in ("APPROVED", "PROMOTED", "AUTHORIZED"):
            rc = 1
        print()

    return rc


# ---------------------------------------------------------------------------
# builder promote decision [id]
# ---------------------------------------------------------------------------


def cmd_promote_decision(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    _section("Promotion Decision Records")

    decisions = _glob_kind(base, "promotion_decision", "promote", "promotion")
    if not decisions:
        _, dec = _find_artifact(base, "promotion_decision.json", "promote/promotion_decision.json")
        if dec:
            decisions = [(base / "promotion_decision.json", dec)]

    if id_args:
        target = id_args[0]
        decisions = [(p, d) for p, d in decisions if _promote_matches(target, p, d)]

    if not decisions:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('promotion decision record', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No promotion decision records found.')}")
        return 0

    rc = 0
    for path, data in decisions:
        decision = str(data.get("decision") or data.get("outcome") or "?").upper()
        subject = str(data.get("subject") or data.get("pack_id") or path.name)
        operator = str(data.get("operator") or data.get("decided_by") or _d("—"))
        ts = _ts(data.get("decided_at") or data.get("timestamp") or "")
        rationale = str(data.get("rationale") or "")
        dec_txt, g = _decision_display(decision)

        print(f"  {g}  {_b(subject)}")
        _kv("decision", dec_txt)
        _kv("operator", _d(operator))
        _kv("decided_at", _d(ts))
        if rationale:
            _kv("rationale", _h(rationale[:80]))

        # Constraints recorded with this decision
        constraints = data.get("constraints") or []
        if constraints and verbose:
            print(f"  {_b('Constraints')}")
            for c in constraints:
                print(f"    {G['warn']}  {_w(str(c)[:80])}")

        # Promotion ref
        prom_ref = data.get("promotion_ref") or data.get("hitl_promotion_ref") or {}
        if prom_ref and verbose:
            _kv("promotion_ref.sha256", _short(prom_ref.get("sha256", "")))

        if decision not in ("APPROVED", "PROMOTED", "AUTHORIZED"):
            rc = 1
        print()

    return rc


# ---------------------------------------------------------------------------
# builder promote compatibility [id]
# ---------------------------------------------------------------------------


def cmd_promote_compatibility(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()
    target = id_args[0] if id_args else None

    _section("Promotion Compatibility")

    # Try module first
    try:
        from builder_ii.lifecycle.candidate.promotion_compatibility import check_promotion_compatibility

        result = check_promotion_compatibility(base)
        if isinstance(result, dict):
            if target is None or _shared_lookup_matches(target, result.get("subject", ""), result.get("pack_id", "")):
                _render_compat_report(result, verbose=verbose)
                print()
                return 0 if result.get("compatible") else 1
    except Exception:
        pass

    # Fallback: look for compatibility artifact on disk
    compat_paths = [
        base / "promotion_compatibility.json",
        base / "promote" / "compatibility.json",
        base / "promotion" / "compatibility.json",
    ]
    for cp in compat_paths:
        data, _ = _load_json(cp)
        if data and (
            target is None
            or _shared_lookup_matches(target, cp.name, cp, data.get("subject", ""), data.get("pack_id", ""))
        ):
            _render_compat_report(data, verbose=verbose)
            print()
            return 0 if data.get("compatible") else 1

    if target is not None:
        print(f"  {G['fail']}  {_f(_shared_lookup_miss('promotion compatibility artifact', target))}")
        print()
        return 1

    print(f"  {G['skip']}  {_d('No promotion_compatibility artifact found.')}")
    print(f"  {_h('hint: builder-promotion record  to create passive promotion readiness evidence')}")
    print()
    return 0


def _render_compat_report(data: dict, *, verbose: bool) -> None:
    compat = data.get("compatible")
    issues = data.get("issues") or data.get("incompatibilities") or []
    warnings = data.get("warnings") or []
    subject = str(data.get("subject") or data.get("pack_id") or "")

    if subject:
        _kv("subject", _b(subject))
    _kv("compatible", _p("YES") if compat else _f("NO"))
    if issues:
        print(f"  {_b('Issues')}  ({len(issues)})")
        for issue in issues:
            print(f"    {G['fail']}  {_f(str(issue)[:80])}")
    if warnings:
        print(f"  {_b('Warnings')}  ({len(warnings)})")
        for w in warnings:
            print(f"    {G['warn']}  {_w(str(w)[:80])}")
    if compat and not issues and not warnings:
        print(f"    {G['pass']}  {_p('No compatibility issues found.')}")
    if verbose:
        checks = data.get("checks") or []
        if checks:
            print(f"  {_b('Checks')}")
            for c in checks:
                if isinstance(c, dict):
                    name = c.get("name") or c.get("check") or "?"
                    passed = c.get("passed", c.get("result"))
                    gg = G["pass"] if passed else G["fail"]
                    print(f"    {gg}  {_d(str(name))}")


# ---------------------------------------------------------------------------
# builder promote history
# ---------------------------------------------------------------------------


def cmd_promote_history(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()

    _section("Promotion History")

    decisions = _glob_kind(base, "promotion_decision", "promote", "promotion")
    if not decisions:
        _, dec = _find_artifact(base, "promotion_decision.json", "promote/promotion_decision.json")
        if dec:
            decisions = [(base / "promotion_decision.json", dec)]

    if not decisions:
        print(f"  {G['skip']}  {_d('No promotion decision records found.')}")
        print()
        return 0

    print(
        _row(
            (_d("  G"), 3),
            (_d("Subject"), 38),
            (_d("Decision"), 14),
            (_d("Operator"), 22),
            (_d("Decided At"), 20),
        )
    )
    print(f"  {_d('─' * 100)}")

    for path, data in decisions:
        decision = str(data.get("decision") or data.get("outcome") or "?").upper()
        subject = str(data.get("subject") or data.get("pack_id") or path.name)[:36]
        operator = str(data.get("operator") or data.get("decided_by") or _d("—"))[:20]
        ts = _ts(data.get("decided_at") or data.get("timestamp") or "")
        dec_txt, g = _decision_display(decision)
        print(_row((g, 3), (_b(subject), 38), (dec_txt, 14), (_d(operator), 22), (_d(ts), 20)))
        if verbose:
            print(f"       {_d('path:')}  {path}")

    print()
    return 0


# ---------------------------------------------------------------------------
# builder promote gates  (failures only)
# ---------------------------------------------------------------------------


def cmd_promote_gates(args: list[str]) -> int:
    """Show only the failing/blocking gates — useful for quick CI-style checks."""
    base = _builder_dir()

    _, readiness = _find_artifact(
        base,
        "promotion_readiness.json",
        "promote/promotion_readiness.json",
        "promotion/readiness.json",
    )

    _section("Blocked Promotion Gates")

    if readiness is None:
        print(f"  {G['skip']}  {_d('No promotion_readiness.json found.')}")
        return 1

    overall = readiness.get("ready") or readiness.get("promotion_ready") or readiness.get("all_gates_passed")
    if overall:
        print(f"  {G['pass']}  {_p('All promotion gates pass. Ready to promote.')}")
        print()
        return 0

    rc = _render_readiness(readiness, verbose=False, failures_only=True)
    print()
    return rc


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_COMMANDS: dict[str, Any] = {
    "status": cmd_promote_status,
    "readiness": cmd_promote_readiness,
    "artifact": cmd_promote_artifact,
    "decision": cmd_promote_decision,
    "compatibility": cmd_promote_compatibility,
    "history": cmd_promote_history,
    "gates": cmd_promote_gates,
}


def _usage() -> None:
    print(_b("builder promote") + "  —  Promotion pipeline inspection surface  (read-only)")
    print()
    cmds = [
        ("status", "Full pipeline state: readiness + HITL artifact + decision"),
        ("readiness", "All readiness gate checks"),
        ("artifact [id]", "HITL promotion artifact detail"),
        ("decision [id]", "Promotion decision record detail"),
        ("compatibility [id]", "Compatibility report"),
        ("history", "All promotion decision records"),
        ("gates", "Blocked gate summary (failures only)"),
    ]
    for cmd, desc in cmds:
        print(f"  {_act('builder promote ' + cmd):<46}  {_d(desc)}")
    print()
    print(_d("  Note: creating a promotion decision requires explicit HITL invocation."))
    print()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        _usage()
        return 0
    sub = args[0]
    rest = args[1:]
    handler = _COMMANDS.get(sub)
    if handler is None:
        print(f"{G['fail']}  {_f(f'Unknown subcommand: {sub}')}")
        _usage()
        return 1
    try:
        return handler(rest)
    except Exception as exc:
        print(f"{G['fail']}  {_f(f'Unhandled error in promote {sub}: {exc}')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
