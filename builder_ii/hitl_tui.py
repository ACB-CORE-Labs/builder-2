"""hitl_tui.py — Consolidated HITL inspection surface for builder-II.

Covers the full 8-slot chain binding pipeline:
  proposal → approval → preflight → request → receipt
  → postflight → verification → evidence_bundle

Shares the 8-token palette and glyph contract from tui.py / agent_tui.py.

All renderers:
  - exit 0 (success) or 1 (error/not-found)
  - never raise; errors become structured FAIL rows
  - strip markup for non-TTY stdout (pipe-safe)
  - suppress verbose detail unless --verbose / -v

Command surface:
  builder hitl status                    — active chain bindings summary
  builder hitl chain <id>                — full 8-slot pipeline for one chain
  builder hitl pending                   — pending approval requests
  builder hitl approval <id>             — approval record detail
  builder hitl evidence <id>             — evidence bundle detail
  builder hitl execution                 — HITL execution records
  builder hitl promote status            — promotion readiness + decision pipeline
  builder hitl replay [--n N] [--agent A] [--kind K]
                                         — filtered event ledger replay
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Palette — identical token names as tui.py / agent_tui.py
# ---------------------------------------------------------------------------

_IS_TTY = sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    if not _IS_TTY:
        return text
    return f"\033[{code}m{text}\033[0m"


def sky(t: str) -> str:    return _c("96", t)
def amber(t: str) -> str:  return _c("33", t)
def green(t: str) -> str:  return _c("32", t)
def red(t: str) -> str:    return _c("31", t)
def dim(t: str) -> str:    return _c("2", t)
def bold(t: str) -> str:   return _c("1", t)
def cyan(t: str) -> str:   return _c("36", t)
def magenta(t: str) -> str: return _c("35", t)


# ---------------------------------------------------------------------------
# Glyphs
# ---------------------------------------------------------------------------

GLYPH = {
    "pass":    green("✔"),
    "fail":    red("✘"),
    "warn":    amber("⚠"),
    "pending": amber("◉"),
    "skip":    dim("–"),
    "chain":   cyan("⛓"),
    "evidence":magenta("🔍"),
    "bullet":  dim("·"),
    "arrow":   dim("→"),
}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _builder_dir() -> Path:
    return Path(os.environ.get("BUILDER_DIR", ".builder"))


def _short(digest: str, n: int = 14) -> str:
    if not digest:
        return dim("—")
    return digest[:n]


def _ts(ts: Any) -> str:
    if not ts:
        return dim("—")
    s = str(ts)
    return s[:19].replace("T", " ") if "T" in s else s[:19]


def _status_glyph(status: str) -> str:
    s = str(status).upper()
    if s in ("PASS", "PASSED", "APPROVED", "COMPLETE", "VERIFIED", "BOUND_ONLY"):
        return GLYPH["pass"]
    if s in ("FAIL", "FAILED", "REJECTED", "DENIED"):
        return GLYPH["fail"]
    if s in ("PENDING", "AWAITING", "IN_PROGRESS"):
        return GLYPH["pending"]
    if s in ("WARN", "WARNING", "PARTIAL"):
        return GLYPH["warn"]
    return GLYPH["skip"]


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Load a JSON file; return (data, error_message)."""
    if not path.exists():
        return None, f"not found: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None, f"not a JSON object: {path}"
        return data, ""
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: {exc}"
    except Exception as exc:
        return None, f"failed to read {path}: {exc}"


def _glob_json(directory: Path, pattern: str = "*.json") -> list[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob(pattern))


def _col(text: str, width: int, pad: str = " ") -> str:
    """Left-align text in a fixed column, stripping ANSI for width calc."""
    import re
    plain = re.sub(r"\033\[[0-9;]*m", "", text)
    deficit = max(0, width - len(plain))
    return text + pad * deficit


def _hr(char: str = "─", width: int = 72) -> str:
    return dim(char * width)


def _section(title: str) -> None:
    print()
    print(bold(title))
    print(_hr())


def _kv(key: str, value: str, key_w: int = 22) -> None:
    print(f"  {_col(dim(key), key_w + 9)}  {value}")


def _row(*cells: tuple[str, int]) -> str:
    return "  " + "  ".join(_col(text, w) for text, w in cells)


# ---------------------------------------------------------------------------
# SLOT PIPELINE constants
# ---------------------------------------------------------------------------

SLOTS = [
    "proposal",
    "approval",
    "preflight",
    "request",
    "receipt",
    "postflight",
    "verification",
    "evidence_bundle",  # optional
]

SLOT_LABELS = {
    "proposal":       "Proposal",
    "approval":       "Approval",
    "preflight":      "Preflight",
    "request":        "Request",
    "receipt":        "Receipt",
    "postflight":     "Postflight",
    "verification":   "Verification",
    "evidence_bundle":"Evidence Bundle",
}


# ---------------------------------------------------------------------------
# Chain binding helpers
# ---------------------------------------------------------------------------

def _find_chain_bindings(base: Path) -> list[Path]:
    """Discover chain binding JSON files under .builder/hitl/."""
    hitl_dir = base / "hitl"
    bindings: list[Path] = []
    if hitl_dir.exists():
        bindings.extend(_glob_json(hitl_dir, "*chain_binding*.json"))
        bindings.extend(_glob_json(hitl_dir, "*hitl_chain*.json"))
    # also check top-level .builder/
    bindings.extend(_glob_json(base, "*chain_binding*.json"))
    # deduplicate preserving order
    seen: set[Path] = set()
    result: list[Path] = []
    for p in bindings:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            result.append(p)
    return result


def _render_slot_row(slot: str, ref: dict[str, Any] | None, *, verbose: bool) -> None:
    label = _col(SLOT_LABELS.get(slot, slot), 18)
    is_optional = slot == "evidence_bundle"
    if ref is None:
        glyph = GLYPH["skip"] if is_optional else GLYPH["fail"]
        status = dim("optional") if is_optional else red("MISSING")
        print(_row((glyph, 3), (label, 20), (status, 12)))
        return
    digest = _short(ref.get("sha256", ""))
    path_str = ref.get("path", dim("—"))
    kind = ref.get("kind", dim("—"))
    glyph = GLYPH["pass"]
    print(_row((glyph, 3), (label, 20), (green("BOUND"), 10), (digest, 18)))
    if verbose:
        print(f"       {dim('path')}  {path_str}")
        print(f"       {dim('kind')}  {dim(kind)}")


def _render_chain(path: Path, *, verbose: bool) -> int:
    data, err = _load_json(path)
    if err:
        print(f"{GLYPH['fail']} {red(err)}")
        return 1

    chain_state = data.get("chain_state", dim("—"))
    schema_v = data.get("schema_version", "?")
    governance = data.get("governance", {})

    _section(f"HITL Chain Binding  {dim(path.name)}")
    _kv("chain_state",    f"{_status_glyph(chain_state)}  {sky(chain_state)}")
    _kv("schema_version", str(schema_v))

    # governance quick-check
    gov_keys = [
        "runtime_execution", "model_execution", "shell_execution",
        "source_writes", "memory_mutation", "goose_runtime_start",
        "command_execution", "git_mutation", "commit_push",
        "network_access", "goose_runtime_activation", "deepagents_runtime",
    ]
    all_disabled = all(governance.get(k) == "DISABLED" for k in gov_keys)
    art_auth = governance.get("artifact_is_authority", None)
    cwc = governance.get("core_workbench_coupling", dim("—"))
    gov_glyph = GLYPH["pass"] if (all_disabled and art_auth is False and cwc == "NONE") else GLYPH["fail"]
    _kv("governance", f"{gov_glyph}  {'all caps DISABLED' if all_disabled else red('VIOLATION')}")
    if verbose:
        for k in gov_keys:
            v = governance.get(k, dim("—"))
            g = GLYPH["pass"] if v == "DISABLED" else GLYPH["fail"]
            print(f"         {g}  {dim(k + ':')}  {v}")
        _kv("artifact_is_authority", f"{GLYPH['pass'] if art_auth is False else GLYPH['fail']}  {art_auth}")
        _kv("core_workbench_coupling", f"{GLYPH['pass'] if cwc == 'NONE' else GLYPH['fail']}  {cwc}")

    print()
    print(f"  {bold('Slot')}")
    # header
    print(_row((dim("  G"), 3), (dim("Slot"), 20), (dim("Status"), 10), (dim("SHA256[:14]"), 18)))
    print(f"  {_hr('─', 60)}")

    for slot in SLOTS:
        field = f"{slot}_ref"
        ref = data.get(field)
        _render_slot_row(slot, ref, verbose=verbose)

    return 0


# ---------------------------------------------------------------------------
# builder hitl status
# ---------------------------------------------------------------------------

def cmd_hitl_status(args: list[str]) -> int:
    """Show summary of all chain bindings found under .builder/hitl/."""
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()
    bindings = _find_chain_bindings(base)

    _section("HITL Chain Binding Status")

    if not bindings:
        print(f"  {GLYPH['skip']}  {dim('No chain binding artifacts found under')} {base}")
        print()
        return 0

    print(_row(
        (dim("  G"), 3),
        (dim("File"), 36),
        (dim("State"), 14),
        (dim("Slots filled"), 14),
        (dim("Governance"), 12),
    ))
    print(f"  {_hr('─', 80)}")

    any_fail = False
    for path in bindings:
        data, err = _load_json(path)
        if err:
            print(_row((GLYPH["fail"], 3), (red(path.name), 36), (red("ERROR"), 14)))
            any_fail = True
            continue

        chain_state = data.get("chain_state", "")
        governance = data.get("governance", {})
        gov_keys = [
            "runtime_execution", "model_execution", "shell_execution",
            "source_writes", "memory_mutation", "goose_runtime_start",
            "command_execution", "git_mutation", "commit_push",
            "network_access", "goose_runtime_activation", "deepagents_runtime",
        ]
        all_disabled = all(governance.get(k) == "DISABLED" for k in gov_keys)
        art_auth = governance.get("artifact_is_authority", None)
        cwc = governance.get("core_workbench_coupling", "")
        gov_ok = all_disabled and art_auth is False and cwc == "NONE"

        required_slots = [s for s in SLOTS if s != "evidence_bundle"]
        filled = sum(1 for s in required_slots if f"{s}_ref" in data and data[f"{s}_ref"] is not None)
        total_required = len(required_slots)
        ev = "✔" if "evidence_bundle_ref" in data else "—"
        slots_str = f"{filled}/{total_required} +ev:{ev}"
        ok = filled == total_required and gov_ok

        glyph = GLYPH["pass"] if ok else (GLYPH["warn"] if filled > 0 else GLYPH["fail"])
        if not ok:
            any_fail = True
        gov_disp = green("OK") if gov_ok else red("VIOLATION")
        state_disp = sky(chain_state) if chain_state else dim("—")

        print(_row(
            (glyph, 3),
            (path.name[:34], 36),
            (state_disp, 14),
            (slots_str, 14),
            (gov_disp, 12),
        ))
        if verbose:
            print(f"       {dim('path:')}  {path}")

    print()
    return 1 if any_fail else 0


# ---------------------------------------------------------------------------
# builder hitl chain <id>
# ---------------------------------------------------------------------------

def cmd_hitl_chain(args: list[str]) -> int:
    """Render full 8-slot pipeline for a specific chain binding."""
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    if not id_args:
        # no id given — render all
        bindings = _find_chain_bindings(base)
        if not bindings:
            print(f"{GLYPH['skip']}  {dim('No chain binding artifacts found.')}")
            return 0
        rc = 0
        for p in bindings:
            r = _render_chain(p, verbose=verbose)
            if r != 0:
                rc = r
        return rc

    chain_id = id_args[0]
    bindings = _find_chain_bindings(base)
    # match by name fragment or full path
    matches = [p for p in bindings if chain_id in p.name or chain_id in str(p)]
    if not matches:
        # try direct path
        direct = Path(chain_id)
        if direct.exists():
            return _render_chain(direct, verbose=verbose)
        print(f"{GLYPH['fail']}  {red(f'No chain binding found matching: {chain_id}')}")
        return 1
    rc = 0
    for p in matches:
        r = _render_chain(p, verbose=verbose)
        if r != 0:
            rc = r
    return rc


# ---------------------------------------------------------------------------
# builder hitl pending  — approval requests without a receipt
# ---------------------------------------------------------------------------

def _find_records(base: Path, subdir: str, kind_fragment: str) -> list[tuple[Path, dict]]:
    """Find JSON records under base/subdir matching kind_fragment."""
    results: list[tuple[Path, dict]] = []
    d = base / subdir
    if not d.exists():
        return results
    for p in _glob_json(d):
        data, err = _load_json(p)
        if err or data is None:
            continue
        kind = data.get("kind", "")
        if kind_fragment in kind:
            results.append((p, data))
    return results


def cmd_hitl_pending(args: list[str]) -> int:
    """List pending HITL approval requests (requests without a receipt)."""
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()

    _section("HITL Pending Approvals")

    # gather approval records
    approval_dirs = [base / "approvals", base / "hitl", base / "hitl" / "approvals"]
    approvals: list[tuple[Path, dict]] = []
    for d in approval_dirs:
        if d.exists():
            for p in _glob_json(d):
                data, err = _load_json(p)
                if err or data is None:
                    continue
                if "approval" in data.get("kind", "").lower():
                    approvals.append((p, data))

    # gather execution receipts to identify completed items
    receipt_dirs = [base / "receipts", base / "hitl", base / "hitl" / "receipts"]
    receipt_ids: set[str] = set()
    for d in receipt_dirs:
        if d.exists():
            for p in _glob_json(d):
                data, err = _load_json(p)
                if data is None:
                    continue
                if "receipt" in data.get("kind", "").lower():
                    for key in ("approval_id", "request_id", "session_id", "id"):
                        v = data.get(key)
                        if v:
                            receipt_ids.add(str(v))

    if not approvals:
        print(f"  {GLYPH['skip']}  {dim('No approval records found.')}")
        print()
        return 0

    print(_row(
        (dim("  G"), 3),
        (dim("ID"), 28),
        (dim("Agent"), 20),
        (dim("Status"), 12),
        (dim("Timestamp"), 22),
    ))
    print(f"  {_hr('─', 88)}")

    pending_count = 0
    for path, data in approvals:
        rec_id = data.get("id") or data.get("approval_id") or path.stem
        agent = data.get("agent") or data.get("agent_profile") or dim("—")
        status = data.get("status") or data.get("decision") or "PENDING"
        ts = _ts(data.get("timestamp") or data.get("created_at") or "")
        has_receipt = str(rec_id) in receipt_ids
        effective_status = "COMPLETE" if has_receipt else status
        glyph = _status_glyph(effective_status)
        if effective_status.upper() in ("PENDING", "AWAITING"):
            pending_count += 1

        print(_row(
            (glyph, 3),
            (str(rec_id)[:26], 28),
            (str(agent)[:18], 20),
            (sky(effective_status) if effective_status.upper() == "PENDING" else dim(effective_status), 12),
            (dim(ts), 22),
        ))
        if verbose:
            print(f"       {dim('path:')}  {path}")
            for k in ("kind", "capability", "command", "reason"):
                v = data.get(k)
                if v:
                    print(f"       {dim(k + ':')}  {v}")

    print()
    if pending_count > 0:
        print(f"  {GLYPH['pending']}  {amber(str(pending_count))} approval(s) pending human review")
    else:
        print(f"  {GLYPH['pass']}  {green('No approvals awaiting review')}")
    print()
    return 0


# ---------------------------------------------------------------------------
# builder hitl approval <id>
# ---------------------------------------------------------------------------

def cmd_hitl_approval(args: list[str]) -> int:
    """Show detail for a specific approval record."""
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    search_dirs = [base / "approvals", base / "hitl", base / "hitl" / "approvals"]
    records: list[tuple[Path, dict]] = []
    for d in search_dirs:
        if d.exists():
            for p in _glob_json(d):
                data, err = _load_json(p)
                if data is None:
                    continue
                if "approval" in data.get("kind", "").lower():
                    records.append((p, data))

    if not id_args:
        # show all
        _section("All Approval Records")
        if not records:
            print(f"  {GLYPH['skip']}  {dim('No approval records found.')}")
            return 0
        for path, data in records:
            _render_approval_detail(path, data, verbose=verbose)
        return 0

    target = id_args[0]
    matches = [(p, d) for p, d in records
               if target in str(d.get("id", "")) or target in p.name or target in str(p)]
    if not matches:
        print(f"{GLYPH['fail']}  {red(f'No approval record found matching: {target}')}")
        return 1
    for path, data in matches:
        _render_approval_detail(path, data, verbose=verbose)
    return 0


def _render_approval_detail(path: Path, data: dict, *, verbose: bool) -> None:
    _section(f"Approval  {dim(path.name)}")
    fields = [
        ("id",              data.get("id") or dim("—")),
        ("kind",            dim(data.get("kind", "—"))),
        ("agent",           data.get("agent") or data.get("agent_profile") or dim("—")),
        ("capability",      data.get("capability") or dim("—")),
        ("decision",        data.get("decision") or data.get("status") or dim("—")),
        ("approved_by",     data.get("approved_by") or dim("—")),
        ("timestamp",       _ts(data.get("timestamp") or data.get("created_at") or "")),
        ("reason",          data.get("reason") or dim("—")),
    ]
    for k, v in fields:
        _kv(k, str(v))
    if verbose:
        print()
        print(f"  {dim('raw path:')}  {path}")
        extra_keys = [k for k in data if k not in {f for f, _ in fields} | {"schema_version", "governance"}]
        for k in extra_keys:
            print(f"  {dim(k + ':')}  {data[k]}")
    print()


# ---------------------------------------------------------------------------
# builder hitl evidence <id>
# ---------------------------------------------------------------------------

def cmd_hitl_evidence(args: list[str]) -> int:
    """Show evidence bundle detail."""
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    evidence_dirs = [base / "evidence", base / "hitl", base / "hitl" / "evidence"]
    records: list[tuple[Path, dict]] = []
    for d in evidence_dirs:
        if d.exists():
            for p in _glob_json(d):
                data, err = _load_json(p)
                if data is None:
                    continue
                if "evidence" in data.get("kind", "").lower():
                    records.append((p, data))

    if not id_args:
        _section("All Evidence Bundles")
        if not records:
            print(f"  {GLYPH['skip']}  {dim('No evidence bundles found.')}")
            return 0
        for path, data in records:
            _render_evidence_detail(path, data, verbose=verbose)
        return 0

    target = id_args[0]
    matches = [(p, d) for p, d in records
               if target in str(d.get("id", "")) or target in p.name or target in str(p)]
    if not matches:
        print(f"{GLYPH['fail']}  {red(f'No evidence bundle found matching: {target}')}")
        return 1
    for path, data in matches:
        _render_evidence_detail(path, data, verbose=verbose)
    return 0


def _render_evidence_detail(path: Path, data: dict, *, verbose: bool) -> None:
    _section(f"Evidence Bundle  {dim(path.name)}")
    _kv("id",          str(data.get("id") or dim("—")))
    _kv("kind",        dim(data.get("kind", "—")))
    _kv("agent",       str(data.get("agent") or data.get("agent_profile") or dim("—")))
    _kv("timestamp",   _ts(data.get("timestamp") or data.get("created_at") or ""))

    artifacts = data.get("artifacts") or data.get("entries") or []
    if artifacts:
        print()
        print(f"  {bold('Artifacts')}  ({len(artifacts)} item(s))")
        for item in artifacts:
            if isinstance(item, dict):
                kind = item.get("kind", dim("—"))
                path_s = item.get("path", dim("—"))
                sha = _short(item.get("sha256", ""))
                print(f"    {GLYPH['bullet']}  {dim(kind)}  {path_s}  {sha}")
            else:
                print(f"    {GLYPH['bullet']}  {dim(str(item))}")

    checks = data.get("checks") or []
    if checks:
        print()
        print(f"  {bold('Checks')}")
        for chk in checks:
            if isinstance(chk, dict):
                name = chk.get("name", dim("—"))
                result = chk.get("result") or chk.get("status") or "?"
                g = _status_glyph(result)
                print(f"    {g}  {name}  {dim(result)}")

    if verbose:
        print()
        print(f"  {dim('raw path:')}  {path}")
        shown = {"id", "kind", "agent", "agent_profile", "timestamp", "created_at",
                 "artifacts", "entries", "checks", "schema_version", "governance"}
        for k in data:
            if k not in shown:
                print(f"  {dim(k + ':')}  {data[k]}")
    print()


# ---------------------------------------------------------------------------
# builder hitl execution
# ---------------------------------------------------------------------------

def cmd_hitl_execution(args: list[str]) -> int:
    """Show HITL execution request/receipt records."""
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()

    exec_dirs = [base / "hitl", base / "hitl" / "execution", base / "execution"]
    requests: list[tuple[Path, dict]] = []
    receipts: list[tuple[Path, dict]] = []

    for d in exec_dirs:
        if not d.exists():
            continue
        for p in _glob_json(d):
            data, err = _load_json(p)
            if data is None:
                continue
            kind = data.get("kind", "")
            if "request" in kind.lower():
                requests.append((p, data))
            elif "receipt" in kind.lower():
                receipts.append((p, data))

    _section("HITL Execution Records")

    if not requests and not receipts:
        print(f"  {GLYPH['skip']}  {dim('No HITL execution records found.')}")
        print()
        return 0

    if requests:
        print(f"  {bold('Requests')}  ({len(requests)})")
        print(_row(
            (dim("  G"), 3),
            (dim("ID"), 28),
            (dim("Agent"), 20),
            (dim("Command[:30]"), 32),
            (dim("Timestamp"), 22),
        ))
        print(f"  {_hr('─', 108)}")
        for path, data in requests:
            rec_id = str(data.get("id") or data.get("request_id") or path.stem)[:26]
            agent = str(data.get("agent") or data.get("agent_profile") or dim("—"))[:18]
            cmd = str(data.get("command") or data.get("commands") or dim("—"))[:30]
            ts = _ts(data.get("timestamp") or data.get("created_at") or "")
            status = data.get("status") or "PENDING"
            glyph = _status_glyph(status)
            print(_row(
                (glyph, 3), (rec_id, 28), (agent, 20), (cmd, 32), (dim(ts), 22)
            ))
            if verbose:
                print(f"       {dim('path:')}  {path}")
        print()

    if receipts:
        print(f"  {bold('Receipts')}  ({len(receipts)})")
        print(_row(
            (dim("  G"), 3),
            (dim("ID"), 28),
            (dim("Agent"), 20),
            (dim("Exit"), 8),
            (dim("Tokens"), 10),
            (dim("Timestamp"), 22),
        ))
        print(f"  {_hr('─', 94)}")
        for path, data in receipts:
            rec_id = str(data.get("id") or data.get("receipt_id") or path.stem)[:26]
            agent = str(data.get("agent") or data.get("agent_profile") or dim("—"))[:18]
            exit_code = str(data.get("exit_code") or data.get("status") or dim("—"))[:6]
            tokens = str(data.get("total_tokens") or data.get("tokens") or dim("—"))[:8]
            ts = _ts(data.get("timestamp") or data.get("created_at") or "")
            ok = str(exit_code) in ("0", "PASS", "PASSED", "dim(—)")
            glyph = GLYPH["pass"] if ok else GLYPH["fail"]
            print(_row(
                (glyph, 3), (rec_id, 28), (agent, 20), (exit_code, 8), (tokens, 10), (dim(ts), 22)
            ))
            if verbose:
                print(f"       {dim('path:')}  {path}")
        print()

    return 0


# ---------------------------------------------------------------------------
# builder hitl promote status  — promotion readiness + decision pipeline
# ---------------------------------------------------------------------------

def cmd_hitl_promote(args: list[str]) -> int:
    """Show promotion readiness checks and decision pipeline."""
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()

    _section("Promotion Pipeline")

    # -- Readiness records --
    ready_dirs = [base / "promotion", base / "hitl" / "promotion", base]
    readiness: list[tuple[Path, dict]] = []
    decisions: list[tuple[Path, dict]] = []

    for d in ready_dirs:
        if not d.exists():
            continue
        for p in _glob_json(d):
            data, err = _load_json(p)
            if data is None:
                continue
            kind = data.get("kind", "")
            if "readiness" in kind.lower():
                readiness.append((p, data))
            elif "decision" in kind.lower():
                decisions.append((p, data))

    # Readiness
    if readiness:
        print(f"  {bold('Readiness Checks')}  ({len(readiness)})")
        print(_row(
            (dim("  G"), 3),
            (dim("File"), 36),
            (dim("Status"), 14),
            (dim("Checks Pass"), 14),
            (dim("Timestamp"), 22),
        ))
        print(f"  {_hr('─', 92)}")
        for path, data in readiness:
            status = data.get("status") or data.get("readiness_status") or "?"
            checks = data.get("checks") or []
            passed = sum(1 for c in checks if isinstance(c, dict) and
                         c.get("result", c.get("status", "")).upper() in ("PASS", "PASSED", "OK"))
            ts = _ts(data.get("timestamp") or data.get("created_at") or "")
            glyph = _status_glyph(status)
            checks_str = f"{passed}/{len(checks)}" if checks else dim("—")
            print(_row(
                (glyph, 3),
                (path.name[:34], 36),
                (sky(status)[:12], 14),
                (checks_str, 14),
                (dim(ts), 22),
            ))
            if verbose:
                for chk in checks:
                    if isinstance(chk, dict):
                        n = chk.get("name", "?")
                        r = chk.get("result") or chk.get("status") or "?"
                        g = _status_glyph(r)
                        print(f"       {g}  {dim(n)}  {r}")
        print()
    else:
        print(f"  {GLYPH['skip']}  {dim('No readiness records found.')}")

    # Decisions
    if decisions:
        print(f"  {bold('Promotion Decisions')}  ({len(decisions)})")
        print(_row(
            (dim("  G"), 3),
            (dim("File"), 36),
            (dim("Decision"), 14),
            (dim("Compatible"), 12),
            (dim("Timestamp"), 22),
        ))
        print(f"  {_hr('─', 90)}")
        for path, data in decisions:
            decision = data.get("decision") or data.get("status") or "?"
            compat = data.get("compatible") or data.get("compatibility") or dim("—")
            ts = _ts(data.get("timestamp") or data.get("created_at") or "")
            glyph = _status_glyph(decision)
            compat_g = GLYPH["pass"] if str(compat).upper() in ("TRUE", "COMPATIBLE", "YES") else GLYPH["warn"]
            print(_row(
                (glyph, 3),
                (path.name[:34], 36),
                (sky(decision)[:12], 14),
                (f"{compat_g} {compat}", 12),
                (dim(ts), 22),
            ))
            if verbose:
                print(f"       {dim('path:')}  {path}")
        print()
    else:
        print(f"  {GLYPH['skip']}  {dim('No decision records found.')}")

    print()
    return 0


# ---------------------------------------------------------------------------
# builder hitl replay
# ---------------------------------------------------------------------------

def cmd_hitl_replay(args: list[str]) -> int:
    """Replay HITL-relevant events from the event ledger."""
    verbose = "-v" in args or "--verbose" in args
    n = 30
    agent_filter: str | None = None
    kind_filter: str | None = None

    i = 0
    positional = [a for a in args if not a.startswith("-")]
    while i < len(args):
        a = args[i]
        if a in ("--n", "-n") and i + 1 < len(args):
            try:
                n = int(args[i + 1])
            except ValueError:
                pass
            i += 2
            continue
        if a in ("--agent", "-a") and i + 1 < len(args):
            agent_filter = args[i + 1]
            i += 2
            continue
        if a in ("--kind", "-k") and i + 1 < len(args):
            kind_filter = args[i + 1]
            i += 2
            continue
        i += 1

    base = _builder_dir()
    ledger_paths = [
        base / "event_ledger.jsonl",
        base / "ledger" / "events.jsonl",
        base / "hitl" / "events.jsonl",
    ]
    ledger_path: Path | None = None
    for lp in ledger_paths:
        if lp.exists():
            ledger_path = lp
            break

    _section(f"HITL Event Replay  {dim(f'(last {n}' + (f', agent={agent_filter}' if agent_filter else '') + (f', kind={kind_filter}' if kind_filter else '') + ')')}")

    if ledger_path is None:
        print(f"  {GLYPH['skip']}  {dim('No event ledger found.')}")
        print()
        return 0

    hitl_kinds = {
        "approval", "hitl", "preflight", "postflight", "evidence",
        "proposal", "verification", "promotion", "request", "receipt",
    }

    events: list[dict] = []
    try:
        for line in ledger_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = str(ev.get("kind") or ev.get("event_kind") or "").lower()
            # only HITL-relevant events unless kind_filter overrides
            if kind_filter:
                if kind_filter.lower() not in kind:
                    continue
            else:
                if not any(hk in kind for hk in hitl_kinds):
                    continue
            if agent_filter:
                ag = str(ev.get("agent") or ev.get("agent_profile") or "").lower()
                if agent_filter.lower() not in ag:
                    continue
            events.append(ev)
    except Exception as exc:
        print(f"  {GLYPH['fail']}  {red(f'Failed to read ledger: {exc}')}")
        return 1

    tail = events[-n:]
    if not tail:
        print(f"  {GLYPH['skip']}  {dim('No matching HITL events found.')}")
        print()
        return 0

    print(_row(
        (dim("  G"), 3),
        (dim("Timestamp"), 22),
        (dim("Kind"), 36),
        (dim("Agent"), 22),
        (dim("Status"), 12),
    ))
    print(f"  {_hr('─', 98)}")

    for ev in tail:
        ts = _ts(ev.get("timestamp") or ev.get("ts") or "")
        kind = str(ev.get("kind") or ev.get("event_kind") or dim("—"))[:34]
        agent = str(ev.get("agent") or ev.get("agent_profile") or dim("—"))[:20]
        status = str(ev.get("status") or ev.get("result") or "")
        glyph = _status_glyph(status) if status else GLYPH["bullet"]
        print(_row(
            (glyph, 3), (dim(ts), 22), (kind, 36), (agent, 22), (dim(status) if status else dim("—"), 12)
        ))
        if verbose:
            for k in ev:
                if k not in {"timestamp", "ts", "kind", "event_kind", "agent",
                              "agent_profile", "status", "result"}:
                    print(f"       {dim(k + ':')}  {ev[k]}")

    print()
    return 0


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_COMMANDS: dict[str, Any] = {
    "status":    cmd_hitl_status,
    "chain":     cmd_hitl_chain,
    "pending":   cmd_hitl_pending,
    "approval":  cmd_hitl_approval,
    "evidence":  cmd_hitl_evidence,
    "execution": cmd_hitl_execution,
    "promote":   cmd_hitl_promote,
    "replay":    cmd_hitl_replay,
}


def _usage() -> None:
    print(bold("builder hitl") + "  —  HITL inspection surface")
    print()
    cmds = [
        ("status",              "Active chain bindings summary"),
        ("chain [id]",          "Full 8-slot pipeline for one (or all) chain binding(s)"),
        ("pending",             "Pending approval requests"),
        ("approval [id]",       "Approval record detail"),
        ("evidence [id]",       "Evidence bundle detail"),
        ("execution",           "HITL execution request/receipt records"),
        ("promote",             "Promotion readiness + decision pipeline"),
        ("replay",              "HITL event ledger replay (--n N --agent A --kind K)"),
    ]
    for cmd, desc in cmds:
        print(f"  {sky('builder hitl ' + cmd):<42}  {dim(desc)}")
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
        print(f"{GLYPH['fail']}  {red(f'Unknown subcommand: {sub}')}")
        _usage()
        return 1
    try:
        return handler(rest)
    except Exception as exc:
        print(f"{GLYPH['fail']}  {red(f'Unhandled error in hitl {sub}: {exc}')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
