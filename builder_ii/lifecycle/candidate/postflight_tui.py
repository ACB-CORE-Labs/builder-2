"""postflight_tui.py — Execution postflight & verification inspection surface.

Two artifact kinds from execution_postflight_records.py:

  execution_postflight_record
      postflight_state: NOT_RUN | RUN_COMPLETE
      ref chain: request_ref → receipt_ref → preflight_ref → approval_ref
      performed_actions: []  (NOT_RUN) or non-empty (RUN_COMPLETE)
      governance: 9 DISABLED caps + artifact_is_authority:false

  execution_verification_record
      verification_state: NOT_RUN | PASS | FAIL
      ref chain: request_ref → receipt_ref → postflight_ref
      evidence_refs: list[str]
      verification_summary: str
      performed_actions: [] (always)

Governance note:
  postflight_tui.py is read-only. Writing postflight artifacts or
  triggering postflight execution requires explicit HITL invocation.
  Autonomous shell execution is DISABLED; the governance block enforces this.

Command surface
---------------
  builder postflight status           — full pipeline: postflight + verification
  builder postflight record [id]      — postflight artifact detail
  builder postflight verify [id]      — verification record detail
  builder postflight governance       — governance block audit (all 9 caps)
  builder postflight actions [id]     — performed_actions list
  builder postflight refs [id]        — full ref chain display
  builder postflight validate         — schema validation
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

# ---------------------------------------------------------------------------
# Palette — theme-aware, shares contract with tui.py / hitl_tui.py / promote_tui.py
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
    "run": _p("▶"),
    "lock": _d("□"),
    "disabled": _d("■"),
    "ref": _act("↳"),
    "action": _acc("●"),
    "evidence": _act("◊"),
    "bullet": _d("·"),
    "arrow": _d("→"),
}

# ---------------------------------------------------------------------------
# Governance capability names (from execution_postflight_records.py)
# ---------------------------------------------------------------------------

_GOV_CAPS = (
    "runtime_execution",
    "shell_execution",
    "command_execution",
    "model_execution",
    "source_writes",
    "git_mutation",
    "network_access",
    "goose_runtime_activation",
    "deepagents_runtime",
)

# ---------------------------------------------------------------------------
# State display maps
# ---------------------------------------------------------------------------

POSTFLIGHT_STATES = {
    "NOT_RUN": (_d("NOT_RUN"), G["pending"]),
    "RUN_COMPLETE": (_p("RUN_COMPLETE"), G["run"]),
}

VERIF_STATES = {
    "NOT_RUN": (_d("NOT_RUN"), G["pending"]),
    "PASS": (_p("PASS"), G["pass"]),
    "FAIL": (_f("FAIL"), G["fail"]),
}


def _pf_state(state: str) -> tuple[str, str]:
    return POSTFLIGHT_STATES.get(str(state).upper(), (_w(str(state)), G["warn"]))


def _vr_state(state: str) -> tuple[str, str]:
    return VERIF_STATES.get(str(state).upper(), (_w(str(state)), G["warn"]))


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


def _kv(key: str, value: str, kw: int = 32) -> None:
    print(f"  {_col(_d(key), kw + 9)}  {value}")


def _ts(ts: Any) -> str:
    if not ts:
        return _d("—")
    s = str(ts)
    return s[:19].replace("T", " ") if "T" in s else s[:19]


def _short(s: str, n: int = 16) -> str:
    return s[:n] if s else _d("—")


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> tuple[dict | None, str]:
    return _shared_load_json_object(path)


def _find_artifact(base: Path, *candidates: str) -> tuple[Path | None, dict | None]:
    return _shared_find_artifact(base, *candidates)


def _glob_kind(base: Path, kind_fragment: str, *subdirs: str) -> list[tuple[Path, dict]]:
    return _shared_glob_kind(base, kind_fragment, *subdirs)


def _record_matches(target: str, path: Path, data: dict) -> bool:
    return _shared_lookup_matches(
        target,
        path.name,
        path,
        (data.get("target") or {}).get("name", ""),
    )


# ---------------------------------------------------------------------------
# Validation helpers (thin wrapper over the records module)
# ---------------------------------------------------------------------------


def _validate_artifact(data: dict) -> list[str]:
    kind = str(data.get("kind", ""))
    try:
        from builder_ii.lifecycle.candidate.execution_postflight_records import (
            EXECUTION_POSTFLIGHT_RECORD_KIND,
            EXECUTION_VERIFICATION_RECORD_KIND,
            validate_execution_postflight_record,
            validate_execution_verification_record,
        )

        if kind == EXECUTION_POSTFLIGHT_RECORD_KIND:
            return validate_execution_postflight_record(data)
        if kind == EXECUTION_VERIFICATION_RECORD_KIND:
            return validate_execution_verification_record(data)
        return [f"unknown kind: {kind}"]
    except ImportError:
        return ["execution_postflight_records module unavailable"]


# ---------------------------------------------------------------------------
# Governance block renderer
# ---------------------------------------------------------------------------


def _render_governance(gov: dict, *, verbose: bool) -> None:
    for cap in _GOV_CAPS:
        val = gov.get(cap, "?")
        if str(val).upper() == "DISABLED":
            glyph = G["disabled"]
            label = _d("DISABLED")
        elif str(val).upper() == "ENABLED":
            glyph = G["warn"]
            label = _w("ENABLED")
        else:
            glyph = G["warn"]
            label = _w(str(val))
        if verbose or str(val).upper() != "DISABLED":
            print(f"    {glyph}  {_col(_d(cap), 36)}  {label}")

    authority = gov.get("artifact_is_authority")
    coupling = gov.get("core_workbench_coupling", "?")
    if authority is False:
        print(f"    {G['pass']}  {_col(_d('artifact_is_authority'), 36)}  {_p('false')}")
    else:
        print(f"    {G['fail']}  {_col(_d('artifact_is_authority'), 36)}  {_f(str(authority))}")
    coupling_label = _p(str(coupling)) if str(coupling).upper() == "NONE" else _w(str(coupling))
    print(f"    {G['lock']}  {_col(_d('core_workbench_coupling'), 36)}  {coupling_label}")


# ---------------------------------------------------------------------------
# Ref chain renderer
# ---------------------------------------------------------------------------

_POSTFLIGHT_REFS = ["request_ref", "receipt_ref", "preflight_ref", "approval_ref"]
_VERIF_REFS = ["request_ref", "receipt_ref", "postflight_ref"]


def _render_refs(data: dict, ref_chain: list[str]) -> None:
    for i, ref_key in enumerate(ref_chain):
        val = str(data.get(ref_key) or "")
        connector = G["ref"] if i > 0 else " "
        if val:
            print(f"    {connector}  {_col(_d(ref_key), 20)}  {_act(_short(val, 48))}")
        else:
            print(f"    {connector}  {_col(_d(ref_key), 20)}  {_d('— (empty)')}")


# ---------------------------------------------------------------------------
# builder postflight status
# ---------------------------------------------------------------------------


def cmd_postflight_status(args: list[str]) -> int:
    base = _builder_dir()

    _section("Execution Postflight Status")

    # --- Postflight records ---
    pf_records = _glob_kind(base, "execution_postflight_record", "postflight", "exec")
    if not pf_records:
        _, pf = _find_artifact(
            base,
            "execution_postflight_record.json",
            "postflight/execution_postflight_record.json",
        )
        if pf:
            pf_records = [(base / "execution_postflight_record.json", pf)]

    print(f"  {_b('Postflight Records')}  ({len(pf_records)})")
    pf_complete = False
    for path, data in pf_records:
        state = str(data.get("postflight_state") or "NOT_RUN").upper()
        target_name = str((data.get("target") or {}).get("name") or _d("—"))
        actions = data.get("performed_actions") or []
        state_txt, g = _pf_state(state)
        ts = _ts(data.get("timestamp") or data.get("created_at") or "")
        print(f"    {g}  {_col(_b(target_name), 22)}  {state_txt}  {_d(str(len(actions)) + ' action(s)')}  {_d(ts)}")
        if state == "RUN_COMPLETE":
            pf_complete = True

    if not pf_records:
        print(f"    {G['skip']}  {_d('No execution_postflight_record artifacts found.')}")

    # --- Verification records ---
    print()
    print(f"  {_b('Verification Records')}")
    vr_records = _glob_kind(base, "execution_verification_record", "postflight", "exec", "verification")
    if not vr_records:
        _, vr = _find_artifact(
            base,
            "execution_verification_record.json",
            "postflight/execution_verification_record.json",
        )
        if vr:
            vr_records = [(base / "execution_verification_record.json", vr)]

    vr_pass = False
    for path, data in vr_records:
        state = str(data.get("verification_state") or "NOT_RUN").upper()
        summary = str(data.get("verification_summary") or "")[:60]
        evidence = data.get("evidence_refs") or []
        state_txt, g = _vr_state(state)
        print(f"    {g}  {state_txt}  {_d(str(len(evidence)) + ' evidence ref(s)')}")
        if summary:
            print(f"       {_h(summary)}")
        if state == "PASS":
            vr_pass = True

    if not vr_records:
        print(f"    {G['skip']}  {_d('No execution_verification_record artifacts found.')}")

    # --- Pipeline bar ---
    print()
    print(f"  {_b('Pipeline')}")
    stages = [
        ("Postflight", pf_complete),
        ("Verification", vr_pass),
    ]
    parts: list[str] = []
    for label, done in stages:
        parts.append(_p(label) if done else _d(label))
        parts.append(_d(" → "))
    print("    " + "".join(parts[:-1]))

    print()
    if not pf_records and not vr_records:
        return 0
    return 0 if (pf_complete and vr_pass) else 1


# ---------------------------------------------------------------------------
# builder postflight record [id]
# ---------------------------------------------------------------------------


def cmd_postflight_record(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    _section("Execution Postflight Record")

    records = _glob_kind(base, "execution_postflight_record", "postflight", "exec")
    if not records:
        _, pf = _find_artifact(base, "execution_postflight_record.json")
        if pf:
            records = [(base / "execution_postflight_record.json", pf)]

    if id_args:
        target = id_args[0]
        records = [(p, d) for p, d in records if _record_matches(target, p, d)]

    if not records:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('execution postflight record', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No execution_postflight_record artifacts found.')}")
        return 0

    rc = 0
    for path, data in records:
        state = str(data.get("postflight_state") or "NOT_RUN").upper()
        target_d = data.get("target") or {}
        target_name = str(target_d.get("name") or _d("—"))
        target_repo = str(target_d.get("repo") or _d("—"))
        target_desc = str(target_d.get("description") or "")
        actions = data.get("performed_actions") or []
        state_txt, g = _pf_state(state)
        authority = data.get("artifact_is_authority", "?")

        print(f"  {g}  {_b(target_name)}")
        _kv("postflight_state", state_txt)
        _kv("target.name", _act(target_name))
        _kv("target.repo", _d(target_repo))
        if target_desc:
            _kv("target.description", _h(target_desc[:60]))
        _kv("artifact_is_authority", _p("false") if authority is False else _f(str(authority)))
        _kv("performed_actions", _d(str(len(actions)) + " action(s)"))
        _kv("kind", _d(str(data.get("kind", ""))))

        # Refs
        print()
        print(f"  {_b('Ref chain')}")
        _render_refs(data, _POSTFLIGHT_REFS)

        # Governance summary (compact when not verbose)
        gov = data.get("governance") or {}
        if gov:
            print()
            print(f"  {_b('Governance')}  ({'verbose' if verbose else 'compact — use -v for full'})")
            if verbose:
                _render_governance(gov, verbose=True)
            else:
                enabled = [cap for cap in _GOV_CAPS if str(gov.get(cap, "")).upper() != "DISABLED"]
                if enabled:
                    for cap in enabled:
                        print(f"    {G['warn']}  {_col(_d(cap), 36)}  {_w(str(gov[cap]))}")
                else:
                    print(f"    {G['pass']}  {_p('All 9 governance caps: DISABLED')}")

        # Validation
        errors = _validate_artifact(data)
        if errors:
            print()
            print(f"  {_b('Validation errors')}  ({len(errors)})")
            for err in errors:
                print(f"    {G['fail']}  {_f(err)}")
            rc = 1

        if state != "RUN_COMPLETE":
            rc = 1
        print()

    return rc


# ---------------------------------------------------------------------------
# builder postflight verify [id]
# ---------------------------------------------------------------------------


def cmd_postflight_verify(args: list[str]) -> int:
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    _section("Execution Verification Record")

    records = _glob_kind(base, "execution_verification_record", "postflight", "exec", "verification")
    if not records:
        _, vr = _find_artifact(base, "execution_verification_record.json")
        if vr:
            records = [(base / "execution_verification_record.json", vr)]

    if id_args:
        target = id_args[0]
        records = [(p, d) for p, d in records if _record_matches(target, p, d)]

    if not records:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('execution verification record', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No execution_verification_record artifacts found.')}")
        return 0

    rc = 0
    for path, data in records:
        state = str(data.get("verification_state") or "NOT_RUN").upper()
        summary = str(data.get("verification_summary") or "")
        evidence = data.get("evidence_refs") or []
        target_d = data.get("target") or {}
        state_txt, g = _vr_state(state)
        authority = data.get("artifact_is_authority", "?")

        print(f"  {g}  {_b(str(target_d.get('name') or path.name))}")
        _kv("verification_state", state_txt)
        _kv("verification_summary", _h(summary[:72]) if summary else _d("—"))
        _kv("evidence_refs", _d(str(len(evidence)) + " ref(s)"))
        _kv("artifact_is_authority", _p("false") if authority is False else _f(str(authority)))
        _kv("kind", _d(str(data.get("kind", ""))))

        # Evidence refs
        if evidence:
            print()
            print(f"  {_b('Evidence refs')}  ({len(evidence)})")
            for ref in evidence:
                print(f"    {G['evidence']}  {_act(_short(str(ref), 72))}")

        # Refs
        print()
        print(f"  {_b('Ref chain')}")
        _render_refs(data, _VERIF_REFS)

        # Validation
        errors = _validate_artifact(data)
        if errors:
            print()
            print(f"  {_b('Validation errors')}  ({len(errors)})")
            for err in errors:
                print(f"    {G['fail']}  {_f(err)}")
            rc = 1

        if state not in ("PASS",):
            rc = 1
        print()

    return rc


# ---------------------------------------------------------------------------
# builder postflight governance
# ---------------------------------------------------------------------------


def cmd_postflight_governance(args: list[str]) -> int:
    base = _builder_dir()

    _section("Governance Block Audit")
    print(f"  {_h('9 capability gates; all must be DISABLED or NOT_AUTHORIZED in valid postflight artifacts.')}")
    print()

    all_records = _glob_kind(base, "execution_postflight_record", "postflight", "exec") + _glob_kind(
        base, "execution_verification_record", "postflight", "exec", "verification"
    )

    if not all_records:
        print(f"  {G['skip']}  {_d('No postflight artifacts found.')}")
        print()
        return 0

    rc = 0
    for path, data in all_records:
        kind = str(data.get("kind", "")).split(".")[-1]
        target_name = str((data.get("target") or {}).get("name") or path.name)
        gov = data.get("governance") or {}
        print(f"  {_b(target_name)}  {_d('(' + kind + ')')}")
        if not gov:
            print(f"    {G['fail']}  {_f('governance block missing')}")
            rc = 1
        else:
            _render_governance(gov, verbose=True)
            # Check for any enabled caps
            enabled = [cap for cap in _GOV_CAPS if str(gov.get(cap, "")).upper() != "DISABLED"]
            if enabled:
                rc = 1
            authority = gov.get("artifact_is_authority")
            if authority is not False:
                rc = 1
        print()

    return rc


# ---------------------------------------------------------------------------
# builder postflight actions [id]
# ---------------------------------------------------------------------------


def cmd_postflight_actions(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    _section("Performed Actions")

    records = _glob_kind(base, "execution_postflight_record", "postflight", "exec")
    if not records:
        _, pf = _find_artifact(base, "execution_postflight_record.json")
        if pf:
            records = [(base / "execution_postflight_record.json", pf)]

    if id_args:
        target = id_args[0]
        records = [(p, d) for p, d in records if _record_matches(target, p, d)]

    if not records:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('execution postflight record', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No execution_postflight_record artifacts found.')}")
        return 0

    for path, data in records:
        state = str(data.get("postflight_state") or "NOT_RUN").upper()
        actions = data.get("performed_actions") or []
        target_name = str((data.get("target") or {}).get("name") or path.name)
        state_txt, g = _pf_state(state)

        print(f"  {g}  {_b(target_name)}  —  {state_txt}  ({len(actions)} action(s))")
        if not actions:
            print(f"    {G['skip']}  {_d('performed_actions is empty (expected for NOT_RUN state).')}")
        else:
            for i, action in enumerate(actions):
                if isinstance(action, str):
                    print(f"    {G['action']}  [{i}]  {_acc(action[:80])}")
                elif isinstance(action, dict):
                    name = action.get("name") or action.get("action") or action.get("type") or f"action_{i}"
                    ts = _ts(action.get("timestamp") or "")
                    result = str(action.get("result") or action.get("status") or "")
                    result_label = (
                        _p(result) if result.upper() in ("OK", "PASS", "SUCCESS") else _w(result) if result else _d("")
                    )
                    print(f"    {G['action']}  [{i}]  {_col(_acc(str(name)[:48]), 52)}  {result_label}  {_d(ts)}")
                    if verbose:
                        for k, v in action.items():
                            if k not in ("name", "action", "type", "timestamp", "result", "status"):
                                print(f"           {_d(k + ':')}  {str(v)[:60]}")
                else:
                    print(f"    {G['action']}  [{i}]  {_d(repr(action)[:60])}")
        print()

    return 0


# ---------------------------------------------------------------------------
# builder postflight refs [id]
# ---------------------------------------------------------------------------


def cmd_postflight_refs(args: list[str]) -> int:
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    _section("Execution Ref Chain")

    all_records = _glob_kind(base, "execution_postflight_record", "postflight", "exec") + _glob_kind(
        base, "execution_verification_record", "postflight", "exec", "verification"
    )

    if id_args:
        target = id_args[0]
        all_records = [(p, d) for p, d in all_records if _record_matches(target, p, d)]

    if not all_records:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('postflight artifact', id_args[0]))}")
            print()
            return 1
        print(f"  {G['skip']}  {_d('No postflight artifacts found.')}")
        print()
        return 0

    for path, data in all_records:
        kind = str(data.get("kind", "")).split(".")[-1]
        target_name = str((data.get("target") or {}).get("name") or path.name)
        print(f"  {_b(target_name)}  {_d('(' + kind + ')')}")
        if "postflight" in kind:
            _render_refs(data, _POSTFLIGHT_REFS)
        else:
            _render_refs(data, _VERIF_REFS)
        print()

    return 0


# ---------------------------------------------------------------------------
# builder postflight validate
# ---------------------------------------------------------------------------


def cmd_postflight_validate(args: list[str]) -> int:
    base = _builder_dir()

    _section("Schema Validation")

    all_records = _glob_kind(base, "execution_postflight_record", "postflight", "exec") + _glob_kind(
        base, "execution_verification_record", "postflight", "exec", "verification"
    )

    if not all_records:
        print(f"  {G['skip']}  {_d('No postflight artifacts found to validate.')}")
        print()
        return 0

    rc = 0
    for path, data in all_records:
        kind = str(data.get("kind", "")).split(".")[-1]
        target_name = str((data.get("target") or {}).get("name") or path.name)
        errors = _validate_artifact(data)
        if errors:
            print(f"  {G['fail']}  {_b(target_name)}  {_d('(' + kind + ')')}")
            for err in errors:
                print(f"    {G['fail']}  {_f(err)}")
            rc = 1
        else:
            print(f"  {G['pass']}  {_b(target_name)}  {_d('(' + kind + ')')}  {_p('— valid')}")
        print()

    return rc


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_COMMANDS: dict[str, Any] = {
    "status": cmd_postflight_status,
    "record": cmd_postflight_record,
    "verify": cmd_postflight_verify,
    "governance": cmd_postflight_governance,
    "actions": cmd_postflight_actions,
    "refs": cmd_postflight_refs,
    "validate": cmd_postflight_validate,
}


def _usage() -> None:
    print(_b("builder postflight") + "  —  Execution postflight & verification surface  (read-only)")
    print()
    cmds = [
        ("status", "Full pipeline: postflight + verification state"),
        ("record [id]", "Postflight record detail (state, refs, governance, validation)"),
        ("verify [id]", "Verification record detail (state, summary, evidence refs)"),
        ("governance", "Full governance block audit — all 9 capability gates"),
        ("actions [id]", "Performed actions list from a completed postflight record"),
        ("refs [id]", "Full ref chain: request → receipt → preflight → approval"),
        ("validate", "Schema validation against both artifact kinds"),
    ]
    for cmd, desc in cmds:
        print(f"  {_act('builder postflight ' + cmd):<52}  {_d(desc)}")
    print()
    print(_d("  Note: postflight execution requires explicit HITL invocation. All 9 governance caps are DISABLED."))
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
        print(f"{G['fail']}  {_f(f'Unhandled error in postflight {sub}: {exc}')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
