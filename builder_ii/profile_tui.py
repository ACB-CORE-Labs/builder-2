"""profile_tui.py — Profile pack inspection surface for builder-II.

Covers the 4-artifact lifecycle pipeline:
  manifest → render_plan → dry_run → validation_report

And cross-cutting concerns:
  • lifecycle stage flags (planned/rendered/dry_run/validated/executed/authorized/promoted)
  • lifecycle binding digest verification
  • render plan steps
  • dry-run diff (output_files / slots / deltas)
  • validation report (per-rule results)
  • profile resolution chain
  • pack history (all packs discovered under .builder/)

Shares the palette/glyph/theme contract from tui.py / agent_tui.py / hitl_tui.py.

Command surface
---------------
  builder profile status                  — active pack overview
  builder profile lifecycle [id]          — 7-flag lifecycle stage pipeline
  builder profile validate [id]           — validation report detail
  builder profile render-plan [id]        — render plan steps
  builder profile dry-run [id]            — dry-run output diff
  builder profile resolve [profile]       — profile resolution chain
  builder profile history                 — all packs under .builder/
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Palette — theme-aware, shares contract with tui.py / agent_tui.py / hitl_tui.py
# ---------------------------------------------------------------------------

_IS_TTY = sys.stdout.isatty()

try:
    from builder_ii.tui_theme import theme_palette as _theme_palette
    _C = _theme_palette()
except Exception:
    _C = {
        "pass":   "#4ade80",
        "warn":   "#fbbf24",
        "fail":   "#f87171",
        "hint":   "#94a3b8",
        "active": "#38bdf8",
        "dim":    "#475569",
        "bold":   "#f1f5f9",
        "accent": "#818cf8",
    }


def _ansi(code: str, text: str) -> str:
    if not _IS_TTY:
        return text
    return f"\033[{code}m{text}\033[0m"


def _hex_to_ansi(hex_colour: str, text: str) -> str:
    """Best-effort 24-bit ANSI fg from #rrggbb. Falls back to plain text if not TTY."""
    if not _IS_TTY:
        return text
    h = hex_colour.lstrip("#")
    if len(h) != 6:
        return text
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"\033[38;2;{r};{g};{b}m{text}\033[0m"
    except ValueError:
        return text


# Semantic colour helpers using active theme palette
def _pass(t: str) -> str:   return _hex_to_ansi(_C["pass"],   t)
def _warn(t: str) -> str:   return _hex_to_ansi(_C["warn"],   t)
def _fail(t: str) -> str:   return _hex_to_ansi(_C["fail"],   t)
def _hint(t: str) -> str:   return _hex_to_ansi(_C["hint"],   t)
def _active(t: str) -> str: return _hex_to_ansi(_C["active"], t)
def _dim(t: str) -> str:    return _hex_to_ansi(_C["dim"],    t)
def _bold(t: str) -> str:   return _hex_to_ansi(_C["bold"],   t)
def _accent(t: str) -> str: return _hex_to_ansi(_C["accent"], t)


# ---------------------------------------------------------------------------
# Glyphs
# ---------------------------------------------------------------------------

GLYPH = {
    "pass":    _pass("✔"),
    "fail":    _fail("✘"),
    "warn":    _warn("⚠"),
    "pending": _warn("◉"),
    "skip":    _dim("–"),
    "pack":    _accent("▣"),
    "arrow":   _dim("→"),
    "bullet":  _dim("·"),
    "stage":   _active("●"),
    "locked":  _dim("○"),
}


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------

def _builder_dir() -> Path:
    return Path(os.environ.get("BUILDER_DIR", ".builder"))


def _short(digest: str, n: int = 14) -> str:
    if not digest:
        return _dim("—")
    return digest[:n]


def _ts(ts: Any) -> str:
    if not ts:
        return _dim("—")
    s = str(ts)
    return s[:19].replace("T", " ") if "T" in s else s[:19]


def _col(text: str, width: int) -> str:
    import re
    plain = re.sub(r"\033\[[0-9;]*m", "", text)
    deficit = max(0, width - len(plain))
    return text + " " * deficit


def _hr(char: str = "─", width: int = 72) -> str:
    return _dim(char * width)


def _section(title: str) -> None:
    print()
    print(_accent(title))
    print(_hr())


def _kv(key: str, value: str, key_w: int = 24) -> None:
    print(f"  {_col(_dim(key), key_w + 9)}  {value}")


def _row(*cells: tuple[str, int]) -> str:
    return "  " + "  ".join(_col(text, w) for text, w in cells)


def _stage_glyph(flag: bool | None) -> str:
    return GLYPH["stage"] if flag else GLYPH["locked"]


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def _load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, f"not found: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return (data, "") if isinstance(data, dict) else (None, f"not a JSON object: {path}")
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {path}: {exc}"
    except Exception as exc:
        return None, f"failed to read {path}: {exc}"


def _glob_json(directory: Path, pattern: str = "*.json") -> list[Path]:
    return sorted(directory.glob(pattern)) if directory.exists() else []


def _find_packs(base: Path) -> list[Path]:
    """Discover profile pack JSON files under .builder/."""
    packs: list[Path] = []
    for subdir in (base / "packs", base / "profile", base / "profile_packs", base):
        if subdir.exists():
            for p in _glob_json(subdir):
                data, _ = _load_json(p)
                if data and "profile_pack" in data.get("kind", ""):
                    packs.append(p)
    seen: set[Path] = set()
    result: list[Path] = []
    for p in packs:
        rp = p.resolve()
        if rp not in seen:
            seen.add(rp)
            result.append(p)
    return result


def _find_by_id(base: Path, target: str) -> list[tuple[Path, dict]]:
    """Find pack(s) matching target (id fragment, filename, or path)."""
    packs = _find_packs(base)
    matches: list[tuple[Path, dict]] = []
    for p in packs:
        data, _ = _load_json(p)
        if data is None:
            continue
        if (
            target in p.name
            or target in str(p)
            or target in str(data.get("pack_id", ""))
            or target in str(data.get("target_profile", ""))
        ):
            matches.append((p, data))
    return matches


# ---------------------------------------------------------------------------
# Lifecycle pipeline renderer
# ---------------------------------------------------------------------------

LIFECYCLE_STAGES = [
    ("planned",    "Planned",    True),
    ("rendered",   "Rendered",   True),
    ("dry_run",    "Dry-run",    True),
    ("validated",  "Validated",  True),
    ("executed",   "Executed",   False),
    ("authorized", "Authorized", False),
    ("promoted",   "Promoted",   False),
]


def _render_lifecycle(lifecycle: dict[str, Any]) -> None:
    print()
    print(f"  {_bold('Lifecycle stages')}")
    stages = [s for s, _, _ in LIFECYCLE_STAGES]
    flags = [lifecycle.get(s) for s, _, _ in LIFECYCLE_STAGES]
    labels = [l for _, l, _ in LIFECYCLE_STAGES]
    required = [r for _, _, r in LIFECYCLE_STAGES]

    # Pipeline bar
    bar_parts: list[str] = []
    for i, (flag, label) in enumerate(zip(flags, labels)):
        if flag:
            bar_parts.append(_pass(label))
        elif required[i]:
            bar_parts.append(_fail(label))
        else:
            bar_parts.append(_dim(label))
        if i < len(labels) - 1:
            bar_parts.append(_dim(" → "))
    print("  " + "".join(bar_parts))
    print()

    # Detail rows
    for (stage, label, req), flag in zip(LIFECYCLE_STAGES, flags):
        g = GLYPH["stage"] if flag else (GLYPH["fail"] if req else GLYPH["locked"])
        status_txt = _pass("DONE") if flag else (_fail("MISSING") if req else _dim("pending"))
        print(f"    {g}  {_col(_dim(label), 14)}  {status_txt}")


# ---------------------------------------------------------------------------
# Binding digest renderer
# ---------------------------------------------------------------------------

def _render_bindings(bindings: dict[str, Any], *, verbose: bool) -> None:
    if not isinstance(bindings, dict):
        print(f"  {GLYPH['fail']}  {_fail('lifecycle_bindings missing or invalid')}")
        return
    print()
    print(f"  {_bold('Digest bindings')}")
    checks = [
        ("manifest_sha256",                  "manifest"),
        ("render_plan_sha256",               "render_plan"),
        ("dry_run_sha256",                   "dry_run"),
        ("validation_report_sha256",         "validation_report"),
        ("render_plan_manifest_sha256",      "render_plan → manifest"),
        ("dry_run_manifest_sha256",          "dry_run → manifest"),
        ("dry_run_render_plan_sha256",       "dry_run → render_plan"),
        ("validation_report_subject_sha256", "report → subject"),
    ]
    all_ok = True
    for field, label in checks:
        val = bindings.get(field, "")
        ok = isinstance(val, str) and len(val) == 64 and all(c in "0123456789abcdef" for c in val)
        if not ok:
            all_ok = False
        g = GLYPH["pass"] if ok else GLYPH["fail"]
        if verbose or not ok:
            print(f"    {g}  {_col(_dim(label), 32)}  {_short(val)}")
    if not verbose:
        g = GLYPH["pass"] if all_ok else GLYPH["fail"]
        label = _pass("all binding digests valid") if all_ok else _fail("binding digest errors")
        print(f"    {g}  {label}  {_dim('(-v for detail)')  if all_ok else ''}")


# ---------------------------------------------------------------------------
# Ref row renderer
# ---------------------------------------------------------------------------

def _render_ref_row(field: str, ref: Any, *, verbose: bool) -> None:
    label = field.replace("_ref", "").replace("_", " ")
    if not isinstance(ref, dict):
        print(f"  {GLYPH['fail']}  {_col(_dim(label), 22)}  {_fail('MISSING')}")
        return
    digest = _short(ref.get("sha256", ""))
    path_s = ref.get("path", _dim("—"))
    print(f"  {GLYPH['pass']}  {_col(_dim(label), 22)}  {_pass('BOUND')}  {digest}")
    if verbose:
        print(f"       {_dim('path')}  {path_s}")
        print(f"       {_dim('kind')}  {_dim(ref.get('kind', ''))}")


# ---------------------------------------------------------------------------
# builder profile status
# ---------------------------------------------------------------------------

def cmd_profile_status(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()
    packs = _find_packs(base)

    _section("Profile Pack Status")

    if not packs:
        print(f"  {GLYPH['skip']}  {_dim('No profile packs found under')} {base}")
        print()
        return 0

    print(_row(
        (_dim("  G"), 3),
        (_dim("Pack ID"), 32),
        (_dim("Target Profile"), 22),
        (_dim("State"), 14),
        (_dim("Lifecycle"), 30),
        (_dim("Valid"), 8),
    ))
    print(f"  {_hr('─', 114)}")

    any_fail = False
    for path in packs:
        data, err = _load_json(path)
        if err or data is None:
            print(_row((GLYPH["fail"], 3), (_fail(path.name[:30]), 32)))
            any_fail = True
            continue

        pack_id = str(data.get("pack_id") or _dim("—"))[:30]
        target = str(data.get("target_profile") or _dim("—"))[:20]
        state = str(data.get("pack_state") or _dim("—"))[:12]
        lifecycle = data.get("lifecycle") or {}

        # Validate against schema
        try:
            from builder_ii.profile_pack import validate_profile_pack
            errors = validate_profile_pack(data)
        except Exception:
            errors = []

        required_stages = [s for s, _, r in LIFECYCLE_STAGES if r]
        done_required = all(lifecycle.get(s) for s in required_stages)
        optional_stages = [s for s, _, r in LIFECYCLE_STAGES if not r]
        done_optional = sum(1 for s in optional_stages if lifecycle.get(s))

        stage_bar = "".join(
            _pass("●") if lifecycle.get(s) else (_fail("○") if r else _dim("○"))
            for s, _, r in LIFECYCLE_STAGES
        )
        stage_label = f"{stage_bar}  {done_optional}/{len(optional_stages)} optional"

        ok = done_required and not errors
        if not ok:
            any_fail = True
        g = GLYPH["pass"] if ok else (GLYPH["warn"] if done_required else GLYPH["fail"])
        valid_txt = _pass("VALID") if not errors else _fail(f"{len(errors)} err")

        print(_row(
            (g, 3),
            (pack_id, 32),
            (target, 22),
            (_active(state)[:12], 14),
            (stage_label, 30),
            (valid_txt, 8),
        ))
        if verbose and errors:
            for e in errors[:5]:
                print(f"       {GLYPH['fail']}  {_fail(e)}")

    print()
    return 1 if any_fail else 0


# ---------------------------------------------------------------------------
# builder profile lifecycle [id]
# ---------------------------------------------------------------------------

def cmd_profile_lifecycle(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    if not id_args:
        packs = _find_packs(base)
        if not packs:
            print(f"{GLYPH['skip']}  {_dim('No profile packs found.')}")
            return 0
        rc = 0
        for p in packs:
            data, err = _load_json(p)
            if err or data is None:
                print(f"{GLYPH['fail']}  {_fail(err)}")
                rc = 1
                continue
            _render_pack_lifecycle(p, data, verbose=verbose)
        return rc

    matches = _find_by_id(base, id_args[0])
    if not matches:
        print(f"{GLYPH['fail']}  {_fail(f'No pack found matching: {id_args[0]}')}")
        return 1
    rc = 0
    for p, data in matches:
        r = _render_pack_lifecycle(p, data, verbose=verbose)
        if r != 0:
            rc = r
    return rc


def _render_pack_lifecycle(path: Path, data: dict, *, verbose: bool) -> int:
    _section(f"Pack Lifecycle  {_dim(path.name)}")
    _kv("pack_id",        str(data.get("pack_id") or _dim("—")))
    _kv("target_profile", str(data.get("target_profile") or _dim("—")))
    _kv("task",           str(data.get("task") or _dim("—")))
    _kv("pack_state",     _active(str(data.get("pack_state") or _dim("—"))))

    lifecycle = data.get("lifecycle") or {}
    _render_lifecycle(lifecycle)

    print(f"  {_bold('Artifact refs')}")
    for ref_field in ("manifest_ref", "render_plan_ref", "dry_run_ref", "validation_report_ref"):
        _render_ref_row(ref_field, data.get(ref_field), verbose=verbose)

    _render_bindings(data.get("lifecycle_bindings") or {}, verbose=verbose)
    print()
    return 0


# ---------------------------------------------------------------------------
# builder profile validate [id]
# ---------------------------------------------------------------------------

def cmd_profile_validate(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    targets = _find_by_id(base, id_args[0]) if id_args else [(p, d) for p in _find_packs(base) for d, _ in [_load_json(p)] if d]

    if not targets:
        print(f"{GLYPH['skip']}  {_dim('No profile packs found.')}")
        return 0

    _section("Profile Pack Validation")
    rc = 0
    for path, data in targets:
        try:
            from builder_ii.profile_pack import validate_profile_pack
            errors = validate_profile_pack(data)
        except Exception as exc:
            errors = [str(exc)]

        g = GLYPH["pass"] if not errors else GLYPH["fail"]
        label = _pass("VALID") if not errors else _fail(f"{len(errors)} error(s)")
        print(f"  {g}  {_dim(path.name)}  {label}")
        if errors:
            rc = 1
            for e in errors:
                print(f"       {GLYPH['fail']}  {_fail(e)}")

        # Also render embedded validation_report if present
        vr_path_s = (data.get("validation_report_ref") or {}).get("path", "")
        if vr_path_s and verbose:
            vr_path = Path(vr_path_s) if Path(vr_path_s).is_absolute() else (_builder_dir() / vr_path_s)
            vr_data, vr_err = _load_json(vr_path)
            if vr_data:
                _render_validation_report(vr_data)

    print()
    return rc


def _render_validation_report(data: dict) -> None:
    print()
    print(f"  {_bold('Validation report')}  {_dim(str(data.get('subject_kind', '')))}")
    valid = data.get("valid")
    status = data.get("status", "")
    g = GLYPH["pass"] if valid else GLYPH["fail"]
    print(f"    {g}  valid={valid}  status={status}")
    rules = data.get("rules") or data.get("checks") or []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        name = rule.get("name") or rule.get("rule") or "?"
        result = str(rule.get("result") or rule.get("status") or "?").upper()
        rg = GLYPH["pass"] if result in ("PASS", "PASSED", "OK") else GLYPH["fail"]
        msg = rule.get("message") or rule.get("detail") or ""
        print(f"      {rg}  {_dim(name)}  {msg}")


# ---------------------------------------------------------------------------
# builder profile render-plan [id]
# ---------------------------------------------------------------------------

def cmd_profile_render_plan(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    targets = _find_by_id(base, id_args[0]) if id_args else [(p, d) for p in _find_packs(base) for d, _ in [_load_json(p)] if d]
    if not targets:
        print(f"{GLYPH['skip']}  {_dim('No profile packs found.')}")
        return 0

    _section("Render Plan")
    for path, pack in targets:
        rp_ref = pack.get("render_plan_ref") or {}
        rp_path_s = rp_ref.get("path", "")
        rp_path = Path(rp_path_s) if rp_path_s and Path(rp_path_s).is_absolute() else (base / rp_path_s if rp_path_s else None)
        if rp_path is None or not rp_path.exists():
            print(f"  {GLYPH['skip']}  {_dim(path.name)}  render_plan artifact not found")
            continue

        rp_data, err = _load_json(rp_path)
        if err or rp_data is None:
            print(f"  {GLYPH['fail']}  {_fail(err)}")
            continue

        print(f"  {GLYPH['pack']}  {_bold(str(pack.get('pack_id', '')))}  →  {_dim(str(pack.get('target_profile', '')))}")
        steps = rp_data.get("steps") or rp_data.get("plan_steps") or []
        if not steps:
            print(f"    {GLYPH['skip']}  {_dim('No steps in render plan')}")
            continue
        for i, step in enumerate(steps, 1):
            if isinstance(step, str):
                print(f"    {_dim(str(i) + '.')}  {step}")
                continue
            label = step.get("label") or step.get("name") or step.get("step") or f"step {i}"
            result = str(step.get("result") or step.get("status") or "").upper()
            g = _status_glyph(result) if result else _dim(str(i) + ".")
            detail = step.get("detail") or step.get("description") or ""
            print(f"    {g}  {_col(_bold(label), 28)}  {_dim(detail) if verbose else ''}")

    print()
    return 0


# ---------------------------------------------------------------------------
# builder profile dry-run [id]
# ---------------------------------------------------------------------------

def cmd_profile_dry_run(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    targets = _find_by_id(base, id_args[0]) if id_args else [(p, d) for p in _find_packs(base) for d, _ in [_load_json(p)] if d]
    if not targets:
        print(f"{GLYPH['skip']}  {_dim('No profile packs found.')}")
        return 0

    _section("Dry-Run Output")
    for path, pack in targets:
        dr_ref = pack.get("dry_run_ref") or {}
        dr_path_s = dr_ref.get("path", "")
        dr_path = Path(dr_path_s) if dr_path_s and Path(dr_path_s).is_absolute() else (base / dr_path_s if dr_path_s else None)
        if dr_path is None or not dr_path.exists():
            print(f"  {GLYPH['skip']}  {_dim(path.name)}  dry_run artifact not found")
            continue

        dr_data, err = _load_json(dr_path)
        if err or dr_data is None:
            print(f"  {GLYPH['fail']}  {_fail(err)}")
            continue

        print(f"  {GLYPH['pack']}  {_bold(str(pack.get('pack_id', '')))}")

        # Output files
        output_files = dr_data.get("output_files") or dr_data.get("outputs") or []
        if output_files:
            print(f"    {_dim('output files')}  ({len(output_files)})")
            for f in output_files:
                if isinstance(f, dict):
                    p_s = f.get("path") or f.get("file") or "?"
                    action = f.get("action") or f.get("operation") or ""
                    size = f.get("size") or ""
                    print(f"      {GLYPH['arrow']}  {p_s}  {_dim(action)}  {_dim(str(size)) if size else ''}")
                else:
                    print(f"      {GLYPH['arrow']}  {f}")

        # Slots / context
        slots = dr_data.get("slots") or dr_data.get("context_slots") or {}
        if slots and verbose:
            print(f"    {_dim('context slots')}")
            for k, v in (slots.items() if isinstance(slots, dict) else []):
                print(f"      {_dim(k + ':')}  {str(v)[:80]}")

        # Deltas
        deltas = dr_data.get("deltas") or dr_data.get("changes") or []
        if deltas:
            added = sum(1 for d in deltas if isinstance(d, dict) and d.get("op") in ("add", "+"))
            removed = sum(1 for d in deltas if isinstance(d, dict) and d.get("op") in ("remove", "-"))
            modified = len(deltas) - added - removed
            print(f"    {_dim('deltas')}  {_pass('+' + str(added))}  {_fail('-' + str(removed))}  {_dim('~' + str(modified))}")
            if verbose:
                for d in deltas:
                    if isinstance(d, dict):
                        op = d.get("op") or "~"
                        target = d.get("target") or d.get("path") or "?"
                        print(f"      {_dim(op)}  {target}")

    print()
    return 0


# ---------------------------------------------------------------------------
# builder profile resolve [profile]
# ---------------------------------------------------------------------------

def cmd_profile_resolve(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()

    _section("Profile Resolution")

    # Try profile_resolution module first
    try:
        import importlib
        pr = importlib.import_module("builder_ii.profile_resolution")
        if id_args:
            result = pr.resolve_profile(id_args[0])
        else:
            result = pr.resolve_active_profile()
        if isinstance(result, dict):
            _render_resolution_dict(result, verbose=verbose)
            print()
            return 0
    except Exception:
        pass

    # Fall back to reading .builder/profile_resolution.json or packs
    resolution_paths = [
        base / "profile_resolution.json",
        base / "profile" / "resolution.json",
    ]
    for rp in resolution_paths:
        data, err = _load_json(rp)
        if data:
            _render_resolution_dict(data, verbose=verbose)
            print()
            return 0

    # Last resort: show target_profile from all packs
    packs = _find_packs(base)
    if not packs:
        print(f"  {GLYPH['skip']}  {_dim('No profile resolution data found.')}")
        print()
        return 0

    for p in packs:
        data, _ = _load_json(p)
        if not data:
            continue
        target = data.get("target_profile") or _dim("—")
        pack_id = data.get("pack_id") or p.name
        print(f"  {GLYPH['pack']}  {_bold(str(pack_id))}  {GLYPH['arrow']}  {_active(str(target))}")
    print()
    return 0


def _render_resolution_dict(data: dict, *, verbose: bool) -> None:
    profile = data.get("profile") or data.get("resolved_profile") or data.get("target_profile") or _dim("—")
    base_profiles = data.get("base_profiles") or data.get("extends") or []
    overrides = data.get("overrides") or {}
    source = data.get("source") or data.get("source_file") or _dim("—")

    _kv("resolved profile", _active(str(profile)))
    _kv("source",           _dim(str(source)))
    if base_profiles:
        print(f"  {_dim('base profiles')}")
        for bp in base_profiles:
            print(f"    {GLYPH['arrow']}  {bp}")
    if overrides and verbose:
        print(f"  {_dim('overrides')}")
        for k, v in (overrides.items() if isinstance(overrides, dict) else []):
            print(f"    {_dim(k + ':')}  {v}")


# ---------------------------------------------------------------------------
# builder profile history
# ---------------------------------------------------------------------------

def cmd_profile_history(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()
    packs = _find_packs(base)

    _section("Profile Pack History")

    if not packs:
        print(f"  {GLYPH['skip']}  {_dim('No profile packs found.')}")
        print()
        return 0

    print(_row(
        (_dim("  G"), 3),
        (_dim("Pack ID"), 32),
        (_dim("Target"), 22),
        (_dim("Task"), 32),
        (_dim("State"), 14),
    ))
    print(f"  {_hr('─', 106)}")

    for path in packs:
        data, err = _load_json(path)
        if err or data is None:
            print(_row((GLYPH["fail"], 3), (_fail(path.name[:30]), 32)))
            continue
        pack_id = str(data.get("pack_id") or _dim("—"))[:30]
        target = str(data.get("target_profile") or _dim("—"))[:20]
        task = str(data.get("task") or _dim("—"))[:30]
        state = str(data.get("pack_state") or _dim("—"))[:12]
        lifecycle = data.get("lifecycle") or {}
        done_required = all(lifecycle.get(s) for s, _, r in LIFECYCLE_STAGES if r)
        g = GLYPH["pass"] if done_required else GLYPH["warn"]
        print(_row(
            (g, 3), (pack_id, 32), (target, 22), (task, 32), (_active(state), 14)
        ))
        if verbose:
            print(f"       {_dim('path:')}  {path}")

    print()
    return 0


# ---------------------------------------------------------------------------
# Shared status glyph
# ---------------------------------------------------------------------------

def _status_glyph(status: str) -> str:
    s = status.upper()
    if s in ("PASS", "PASSED", "OK", "DONE", "VALID"):
        return GLYPH["pass"]
    if s in ("FAIL", "FAILED", "INVALID", "ERROR"):
        return GLYPH["fail"]
    if s in ("WARN", "WARNING", "PARTIAL"):
        return GLYPH["warn"]
    return GLYPH["skip"]


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_COMMANDS: dict[str, Any] = {
    "status":      cmd_profile_status,
    "lifecycle":   cmd_profile_lifecycle,
    "validate":    cmd_profile_validate,
    "render-plan": cmd_profile_render_plan,
    "dry-run":     cmd_profile_dry_run,
    "resolve":     cmd_profile_resolve,
    "history":     cmd_profile_history,
}


def _usage() -> None:
    print(_bold("builder profile") + "  —  Profile pack inspection surface")
    print()
    cmds = [
        ("status",          "Active pack overview (id / target / lifecycle / validity)"),
        ("lifecycle [id]",   "7-flag lifecycle stage pipeline"),
        ("validate [id]",    "Validation report detail"),
        ("render-plan [id]", "Render plan steps"),
        ("dry-run [id]",     "Dry-run output diff (files / slots / deltas)"),
        ("resolve [profile]","Profile resolution chain"),
        ("history",         "All packs discovered under .builder/"),
    ]
    for cmd, desc in cmds:
        print(f"  {_active('builder profile ' + cmd):<46}  {_dim(desc)}")
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
        print(f"{GLYPH['fail']}  {_fail(f'Unknown subcommand: {sub}')}")
        _usage()
        return 1
    try:
        return handler(rest)
    except Exception as exc:
        print(f"{GLYPH['fail']}  {_fail(f'Unhandled error in profile {sub}: {exc}')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
