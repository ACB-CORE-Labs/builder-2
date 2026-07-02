"""goose_tui.py — Goose session manifest inspection surface for builder-II.

Covers the builder_ii.goose_session_manifest artifact kind.

Key schema facts (from goose_session.py):
  kind:                   builder_ii.goose_session_manifest
  schema_version:         1
  task:                   str
  target:                 {name, repo, description}
  agent_profile:          {name, description, authority}
  verification_profile:   nested profile artifact
  requested_runtime_mode: "disabled" | "read_only"
  current_runtime_state:  "DISABLED"  (always)
  manifest_starts_goose:  False       (always)
  links:                  {target_bundle, verification_profile, quality_gate,
                            research_plan, handoff, context_pack}
  expected_audit_artifact: str
  allowed_actions:        list[str]  (3 items)
  denied_actions:         list[str]  (12 items)
  approval_requirements:  list[str]  (4 items)
  governance:             10 DISABLED caps + file_writes special + authority + coupling

Governance note:
  goose_tui.py is read-only. It never writes manifests, starts Goose
  sessions, or promotes runtime_mode. manifest_starts_goose is always
  false; activating Goose requires explicit operator promotion through
  the governed execution pipeline.

Command surface
---------------
  builder goose status        — runtime state, agent, verification, governance summary
  builder goose manifest [id] — full manifest detail
  builder goose links [id]    — 6-slot link table
  builder goose actions [id]  — allowed vs denied action sets
  builder goose governance    — full governance block audit
  builder goose validate      — schema validation
  builder goose approval      — approval_requirements list
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from builder_ii.tui_contract import (
    builder_dir as _shared_builder_dir,
)
from builder_ii.tui_contract import (
    col as _shared_col,
)
from builder_ii.tui_contract import (
    explicit_lookup_miss as _shared_lookup_miss,
)
from builder_ii.tui_contract import (
    find_artifact as _shared_find_artifact,
)
from builder_ii.tui_contract import (
    glob_kind as _shared_glob_kind,
)
from builder_ii.tui_contract import (
    hex_ansi as _shared_hex_ansi,
)
from builder_ii.tui_contract import (
    load_json_object as _shared_load_json_object,
)
from builder_ii.tui_contract import (
    load_palette,
)
from builder_ii.tui_contract import (
    lookup_matches as _shared_lookup_matches,
)

# ---------------------------------------------------------------------------
# Palette — shared contract with tui.py / hitl_tui.py / promote_tui.py / postflight_tui.py
# ---------------------------------------------------------------------------

_IS_TTY = sys.stdout.isatty()

_C = load_palette()


def _hex_ansi(hex_colour: str, text: str) -> str:
    return _shared_hex_ansi(hex_colour, text, _IS_TTY)


def _p(t):
    return _hex_ansi(_C["pass"],   t)
def _w(t):
    return _hex_ansi(_C["warn"],   t)
def _f(t):
    return _hex_ansi(_C["fail"],   t)
def _h(t):
    return _hex_ansi(_C["hint"],   t)
def _act(t):
    return _hex_ansi(_C["active"], t)
def _d(t):
    return _hex_ansi(_C["dim"],    t)
def _b(t):
    return _hex_ansi(_C["bold"],   t)
def _acc(t):
    return _hex_ansi(_C["accent"], t)

G = {
    "pass":      _p("✔"),
    "fail":      _f("✘"),
    "warn":      _w("⚠"),
    "skip":      _d("–"),
    "disabled":  _d("■"),
    "enabled":   _w("■"),
    "allowed":   _p("▷"),
    "denied":    _f("◁"),
    "link":      _act("↳"),
    "empty":     _d("·"),
    "agent":     _acc("◆"),
    "lock":      _d("□"),
    "bullet":    _d("·"),
    "mode":      _act("◎"),
}

# ---------------------------------------------------------------------------
# Governance cap names from goose_session.py
# ---------------------------------------------------------------------------

_GOV_HARD_DISABLED = (
    "runtime_execution",
    "goose_runtime_start",
    "model_execution",
    "agent_construction",
    "shell_execution",
    "command_execution",
    "source_writes",
    "memory_mutation",
    "commit_push",
)
_GOV_FILE_WRITES_SPECIAL = "file_writes"  # value: DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH
_GOV_FILE_WRITES_EXPECTED = "DISABLED_EXCEPT_EXPLICIT_ARTIFACT_OUTPUT_PATH"

# ---------------------------------------------------------------------------
# Link slot names
# ---------------------------------------------------------------------------

_LINK_SLOTS = (
    "target_bundle",
    "verification_profile",
    "quality_gate",
    "research_plan",
    "handoff",
    "context_pack",
)

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


def _ts(ts: Any) -> str:
    if not ts:
        return _d("—")
    s = str(ts)
    return s[:19].replace("T", " ") if "T" in s else s[:19]


def _short(s: str, n: int = 48) -> str:
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


def _manifest_matches(target: str, path: Path, data: dict) -> bool:
    return _shared_lookup_matches(
        target,
        path.name,
        path,
        (data.get("target") or {}).get("name", ""),
        (data.get("agent_profile") or {}).get("name", ""),
    )


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

def _validate_manifest(data: dict) -> list[str]:
    try:
        from builder_ii.goose_session import validate_goose_session_manifest
        return validate_goose_session_manifest(data)
    except ImportError:
        return ["goose_session module unavailable"]


# ---------------------------------------------------------------------------
# Runtime mode display
# ---------------------------------------------------------------------------

def _runtime_mode_label(requested: str, current: str) -> tuple[str, str]:
    req = str(requested).lower()
    cur = str(current).upper()
    if cur == "DISABLED":
        g = G["disabled"]
        label = _d("DISABLED")
    else:
        g = G["warn"]
        label = _w(cur)
    mode_hint = _h(f"(requested: {req})") if req != "disabled" else _d("")
    return g, f"{label}  {mode_hint}".strip()


# ---------------------------------------------------------------------------
# Governance renderer
# ---------------------------------------------------------------------------

def _render_governance(gov: dict, *, verbose: bool) -> int:
    """Render governance block. Returns 0 if all caps clean, 1 if any violations."""
    rc = 0
    for cap in _GOV_HARD_DISABLED:
        val = gov.get(cap, "?")
        if str(val).upper() == "DISABLED":
            if verbose:
                print(f"    {G['disabled']}  {_col(_d(cap), 36)}  {_d('DISABLED')}")
        else:
            print(f"    {G['fail']}    {_col(_d(cap), 36)}  {_f(str(val))}")
            rc = 1

    # file_writes has a special expected value
    fw_val = gov.get(_GOV_FILE_WRITES_SPECIAL, "?")
    if str(fw_val) == _GOV_FILE_WRITES_EXPECTED:
        if verbose:
            print(f"    {G['lock']}  {_col(_d(_GOV_FILE_WRITES_SPECIAL), 36)}  {_h(_short(_GOV_FILE_WRITES_EXPECTED, 50))}")
    else:
        print(f"    {G['warn']}  {_col(_d(_GOV_FILE_WRITES_SPECIAL), 36)}  {_w(str(fw_val)[:60])}")
        rc = 1

    cap_state = gov.get("capability_state", "?")
    cap_label = _d(str(cap_state)) if str(cap_state) == "artifact_only" else _w(str(cap_state))
    if verbose:
        print(f"    {G['lock']}  {_col(_d('capability_state'), 36)}  {cap_label}")

    authority = gov.get("artifact_is_authority")
    coupling  = gov.get("core_workbench_coupling", "?")
    if authority is False:
        if verbose:
            print(f"    {G['pass']}  {_col(_d('artifact_is_authority'), 36)}  {_p('false')}")
    else:
        print(f"    {G['fail']}  {_col(_d('artifact_is_authority'), 36)}  {_f(str(authority))}")
        rc = 1
    coupling_label = _p(str(coupling)) if str(coupling).upper() == "NONE" else _w(str(coupling))
    if verbose:
        print(f"    {G['lock']}  {_col(_d('core_workbench_coupling'), 36)}  {coupling_label}")

    return rc


# ---------------------------------------------------------------------------
# builder goose status
# ---------------------------------------------------------------------------

def cmd_goose_status(args: list[str]) -> int:
    base    = _builder_dir()

    manifests = _glob_kind(base, "goose_session_manifest", "goose", "sessions")
    if not manifests:
        _, m = _find_artifact(
            base,
            "goose_session_manifest.json",
            "goose/session.json",
            "sessions/goose_session_manifest.json",
        )
        if m:
            manifests = [(base / "goose_session_manifest.json", m)]

    _section("Goose Session Status")

    if not manifests:
        print(f"  {G['skip']}  {_d('No goose_session_manifest artifacts found.')}")
        print(f"  {_h('hint: builder-goose manifest  to create a passive session manifest')}")
        print()
        return 0

    rc = 0
    for path, data in manifests:
        target_d  = data.get("target") or {}
        agent_d   = data.get("agent_profile") or {}
        req_mode  = str(data.get("requested_runtime_mode") or "disabled")
        cur_state = str(data.get("current_runtime_state") or "DISABLED")
        task      = str(data.get("task") or "")[:72]
        starts    = data.get("manifest_starts_goose", "?")
        links     = data.get("links") or {}
        gov       = data.get("governance") or {}

        g_rt, rt_label = _runtime_mode_label(req_mode, cur_state)

        print(f"  {G['agent']}  {_b(str(agent_d.get('name') or _d('—')))}  {_d('—')}  {_b(str(target_d.get('name') or _d('—')))}")
        if task:
            print(f"     {_h(task)}")
        _kv("current_runtime_state", rt_label)
        _kv("requested_runtime_mode", _d(req_mode))
        _kv("manifest_starts_goose",  _p("false") if starts is False else _f(str(starts)))
        _kv("target.repo",            _d(str(target_d.get("repo") or _d("—"))))
        _kv("agent.authority",        _h(str(agent_d.get("authority") or _d("—")))[:60])

        # Links summary
        filled  = sum(1 for k in _LINK_SLOTS if links.get(k))
        total   = len(_LINK_SLOTS)
        link_label = _p(f"{filled}/{total}") if filled == total else _w(f"{filled}/{total}")
        _kv("links", link_label + _d("  slots filled"))

        # Governance summary
        enabled_caps = [
            cap for cap in _GOV_HARD_DISABLED
            if str(gov.get(cap, "")).upper() != "DISABLED"
        ]
        fw = gov.get(_GOV_FILE_WRITES_SPECIAL, "")
        if str(fw) != _GOV_FILE_WRITES_EXPECTED:
            enabled_caps.append(_GOV_FILE_WRITES_SPECIAL)
        if enabled_caps:
            _kv("governance", _f(f"{len(enabled_caps)} cap(s) NOT DISABLED — run: builder goose governance"))
            rc = 1
        else:
            _kv("governance", _p("All caps: DISABLED"))

        # Validation errors count
        errors = _validate_manifest(data)
        if errors:
            _kv("validation", _f(f"{len(errors)} error(s) — run: builder goose validate"))
            rc = 1
        else:
            _kv("validation", _p("valid"))

        if cur_state != "DISABLED" or starts is not False:
            rc = 1
        print()

    return rc


# ---------------------------------------------------------------------------
# builder goose manifest [id]
# ---------------------------------------------------------------------------

def cmd_goose_manifest(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    id_args = [a for a in args if not a.startswith("-")]
    base    = _builder_dir()

    manifests = _glob_kind(base, "goose_session_manifest", "goose", "sessions")
    if not manifests:
        _, m = _find_artifact(base, "goose_session_manifest.json")
        if m:
            manifests = [(base / "goose_session_manifest.json", m)]

    if id_args:
        target = id_args[0]
        manifests = [(p, d) for p, d in manifests if _manifest_matches(target, p, d)]

    _section("Goose Session Manifest")

    if not manifests:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('goose session manifest', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No goose_session_manifest artifacts found.')}")
        return 0

    rc = 0
    for path, data in manifests:
        target_d  = data.get("target") or {}
        agent_d   = data.get("agent_profile") or {}
        verif_d   = data.get("verification_profile") or {}
        req_mode  = str(data.get("requested_runtime_mode") or "disabled")
        cur_state = str(data.get("current_runtime_state") or "DISABLED")
        task      = str(data.get("task") or "")
        starts    = data.get("manifest_starts_goose", "?")
        audit_art = str(data.get("expected_audit_artifact") or _d("—"))

        g_rt, rt_label = _runtime_mode_label(req_mode, cur_state)

        print(f"  {G['agent']}  {_b(str(agent_d.get('name') or 'unknown'))}")
        if task:
            _kv("task", _h(task[:80]))

        # Target
        print(f"  {_b('Target')}")
        _kv("  name",        _act(str(target_d.get("name") or _d("—"))))
        _kv("  repo",        _d(str(target_d.get("repo") or _d("—"))))
        if target_d.get("description"):
            _kv("  description", _h(str(target_d["description"])[:60]))

        # Agent
        print(f"  {_b('Agent Profile')}")
        _kv("  name",        _acc(str(agent_d.get("name") or _d("—"))))
        _kv("  description", _h(str(agent_d.get("description") or "")[:60]))
        _kv("  authority",   _h(str(agent_d.get("authority") or "")[:60]))

        # Runtime
        print(f"  {_b('Runtime')}")
        _kv("  current_runtime_state",  rt_label)
        _kv("  requested_runtime_mode", _d(req_mode))
        _kv("  manifest_starts_goose",  _p("false") if starts is False else _f(str(starts)))
        _kv("  expected_audit_artifact",_d(_short(audit_art, 60)))

        # Verification profile summary
        if verif_d and verbose:
            print(f"  {_b('Verification Profile')}")
            vp_kind = str(verif_d.get("kind") or verif_d.get("profile") or _d("—"))[:48]
            _kv("  kind", _d(vp_kind))
            vp_state = str(verif_d.get("state") or verif_d.get("status") or _d("—"))
            _kv("  state", _p(vp_state) if "pass" in vp_state.lower() else _w(vp_state))

        # Governance compact
        gov = data.get("governance") or {}
        enabled = [c for c in _GOV_HARD_DISABLED if str(gov.get(c, "")).upper() != "DISABLED"]
        fw = gov.get(_GOV_FILE_WRITES_SPECIAL, "")
        if str(fw) != _GOV_FILE_WRITES_EXPECTED:
            enabled.append(_GOV_FILE_WRITES_SPECIAL)
        print(f"  {_b('Governance')}")
        if enabled:
            for cap in enabled:
                print(f"    {G['fail']}  {_col(_d(cap), 36)}  {_f(str(gov.get(cap, '?')))}")
            rc = 1
        else:
            print(f"    {G['pass']}  {_p('All 9 hard-DISABLED caps clean + file_writes special OK')}")

        # Validation
        errors = _validate_manifest(data)
        if errors:
            print(f"  {_b('Validation errors')}  ({len(errors)})")
            for err in errors:
                print(f"    {G['fail']}  {_f(err)}")
            rc = 1
        else:
            print(f"  {G['pass']}  {_p('Manifest valid')}")

        if cur_state != "DISABLED" or starts is not False:
            rc = 1
        print()

    return rc


# ---------------------------------------------------------------------------
# builder goose links [id]
# ---------------------------------------------------------------------------

def cmd_goose_links(args: list[str]) -> int:
    id_args = [a for a in args if not a.startswith("-")]
    base    = _builder_dir()

    manifests = _glob_kind(base, "goose_session_manifest", "goose", "sessions")
    if not manifests:
        _, m = _find_artifact(base, "goose_session_manifest.json")
        if m:
            manifests = [(base / "goose_session_manifest.json", m)]

    if id_args:
        target = id_args[0]
        manifests = [(p, d) for p, d in manifests if _manifest_matches(target, p, d)]

    _section("Goose Session Links")

    if not manifests:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('goose session manifest', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No goose_session_manifest artifacts found.')}")
        return 0

    for path, data in manifests:
        agent_name = str((data.get("agent_profile") or {}).get("name") or path.name)
        links = data.get("links") or {}
        filled = sum(1 for k in _LINK_SLOTS if links.get(k))

        print(f"  {G['agent']}  {_b(agent_name)}  {_d('links: ' + str(filled) + '/' + str(len(_LINK_SLOTS)))}")
        for slot in _LINK_SLOTS:
            val = str(links.get(slot) or "")
            if val:
                print(f"    {G['link']}  {_col(_d(slot), 26)}  {_act(_short(val, 50))}")
            else:
                print(f"    {G['empty']}  {_col(_d(slot), 26)}  {_d('— (empty)')}")
        print()

    return 0


# ---------------------------------------------------------------------------
# builder goose actions [id]
# ---------------------------------------------------------------------------

def cmd_goose_actions(args: list[str]) -> int:
    id_args = [a for a in args if not a.startswith("-")]
    base    = _builder_dir()

    manifests = _glob_kind(base, "goose_session_manifest", "goose", "sessions")
    if not manifests:
        _, m = _find_artifact(base, "goose_session_manifest.json")
        if m:
            manifests = [(base / "goose_session_manifest.json", m)]

    if id_args:
        target = id_args[0]
        manifests = [(p, d) for p, d in manifests if _manifest_matches(target, p, d)]

    _section("Allowed / Denied Actions")

    if not manifests:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('goose session manifest', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No goose_session_manifest artifacts found.')}")
        return 0

    rc = 0
    for path, data in manifests:
        agent_name = str((data.get("agent_profile") or {}).get("name") or path.name)
        allowed  = data.get("allowed_actions") or []
        denied   = data.get("denied_actions") or []
        approval = data.get("approval_requirements") or []

        print(f"  {G['agent']}  {_b(agent_name)}")

        # Allowed
        print(f"  {_p('Allowed actions')}  ({len(allowed)})")
        for a in allowed:
            print(f"    {G['allowed']}  {_p(str(a))}")

        # Denied
        print(f"  {_f('Denied actions')}  ({len(denied)})")
        for a in denied:
            print(f"    {G['denied']}  {_d(str(a))}")

        # Check completeness vs known denied set
        try:
            from builder_ii.goose_session import _DENIED_ACTIONS as _REQUIRED_DENIED
            missing = [a for a in _REQUIRED_DENIED if a not in denied]
            if missing:
                print(f"  {G['warn']}  {_w('Missing required denied actions:')}")
                for m in missing:
                    print(f"    {G['warn']}  {_w(m)}")
                rc = 1
        except ImportError:
            pass

        # Approval requirements
        if approval:
            print(f"  {_w('Approval requirements')}  ({len(approval)})")
            for req in approval:
                print(f"    {G['warn']}  {_w(str(req)[:80])}")

        print()

    return rc


# ---------------------------------------------------------------------------
# builder goose governance
# ---------------------------------------------------------------------------

def cmd_goose_governance(args: list[str]) -> int:
    base    = _builder_dir()

    manifests = _glob_kind(base, "goose_session_manifest", "goose", "sessions")
    if not manifests:
        _, m = _find_artifact(base, "goose_session_manifest.json")
        if m:
            manifests = [(base / "goose_session_manifest.json", m)]

    _section("Goose Governance Block Audit")
    print(f"  {_h('9 hard-DISABLED caps + file_writes special + capability_state + authority + coupling.')}")
    print()

    if not manifests:
        print(f"  {G['skip']}  {_d('No goose_session_manifest artifacts found.')}")
        print()
        return 0

    rc = 0
    for path, data in manifests:
        agent_name  = str((data.get("agent_profile") or {}).get("name") or path.name)
        target_name = str((data.get("target") or {}).get("name") or path.name)
        gov         = data.get("governance") or {}

        print(f"  {G['agent']}  {_b(agent_name)}  {_d('—')}  {_d(target_name)}")
        if not gov:
            print(f"    {G['fail']}  {_f('governance block missing')}")
            rc = 1
        else:
            gov_rc = _render_governance(gov, verbose=True)
            if gov_rc:
                rc = 1
        print()

    return rc


# ---------------------------------------------------------------------------
# builder goose validate
# ---------------------------------------------------------------------------

def cmd_goose_validate(args: list[str]) -> int:
    base = _builder_dir()

    manifests = _glob_kind(base, "goose_session_manifest", "goose", "sessions")
    if not manifests:
        _, m = _find_artifact(base, "goose_session_manifest.json")
        if m:
            manifests = [(base / "goose_session_manifest.json", m)]

    _section("Schema Validation")

    if not manifests:
        print(f"  {G['skip']}  {_d('No goose_session_manifest artifacts found.')}")
        print()
        return 0

    rc = 0
    for path, data in manifests:
        agent_name = str((data.get("agent_profile") or {}).get("name") or path.name)
        errors     = _validate_manifest(data)
        if errors:
            print(f"  {G['fail']}  {_b(agent_name)}")
            for err in errors:
                print(f"    {G['fail']}  {_f(err)}")
            rc = 1
        else:
            print(f"  {G['pass']}  {_b(agent_name)}  {_p('— valid')}")
        print()

    return rc


# ---------------------------------------------------------------------------
# builder goose approval
# ---------------------------------------------------------------------------

def cmd_goose_approval(args: list[str]) -> int:
    id_args = [a for a in args if not a.startswith("-")]
    base    = _builder_dir()

    manifests = _glob_kind(base, "goose_session_manifest", "goose", "sessions")
    if not manifests:
        _, m = _find_artifact(base, "goose_session_manifest.json")
        if m:
            manifests = [(base / "goose_session_manifest.json", m)]

    if id_args:
        target = id_args[0]
        manifests = [(p, d) for p, d in manifests if _manifest_matches(target, p, d)]

    _section("Approval Requirements")
    print(f"  {_h('Each requirement must be cleared before Goose runtime can be activated.')}")
    print()

    if not manifests:
        if id_args:
            print(f"  {G['fail']}  {_f(_shared_lookup_miss('goose session manifest', id_args[0]))}")
            return 1
        print(f"  {G['skip']}  {_d('No goose_session_manifest artifacts found.')}")
        return 0

    for path, data in manifests:
        agent_name = str((data.get("agent_profile") or {}).get("name") or path.name)
        approval   = data.get("approval_requirements") or []
        cur_state  = str(data.get("current_runtime_state") or "DISABLED")
        req_mode   = str(data.get("requested_runtime_mode") or "disabled")

        print(f"  {G['agent']}  {_b(agent_name)}")
        _kv("current_runtime_state",  _d(cur_state))
        _kv("requested_runtime_mode", _d(req_mode))
        print()

        if not approval:
            print(f"    {G['skip']}  {_d('No approval_requirements recorded.')}")
        else:
            for i, req in enumerate(approval):
                print(f"    {G['warn']}  [{i+1}]  {_w(str(req)[:80])}")
        print()

    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_COMMANDS: dict[str, Any] = {
    "status":     cmd_goose_status,
    "manifest":   cmd_goose_manifest,
    "links":      cmd_goose_links,
    "actions":    cmd_goose_actions,
    "governance": cmd_goose_governance,
    "validate":   cmd_goose_validate,
    "approval":   cmd_goose_approval,
}


def _usage() -> None:
    print(_b("builder goose") + "  —  Goose session manifest inspection surface  (read-only)")
    print()
    cmds = [
        ("status",       "Runtime state, agent, verification, governance summary"),
        ("manifest [id]","Full manifest detail — target, agent, runtime, links, governance"),
        ("links [id]",   "6-slot link table: bundle, verif profile, gate, plan, handoff, pack"),
        ("actions [id]", "Allowed (3) vs denied (12) action sets + approval requirements"),
        ("governance",   "Full governance block audit — 10 caps + file_writes special"),
        ("validate",     "Schema validation via goose_session.validate_goose_session_manifest"),
        ("approval",     "Approval requirements that must be cleared before runtime activation"),
    ]
    for cmd, desc in cmds:
        print(f"  {_act('builder goose ' + cmd):<48}  {_d(desc)}")
    print()
    print(_d("  Note: manifest_starts_goose is always false. Activating Goose requires"))
    print(_d("        explicit operator promotion through the governed execution pipeline."))
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
        print(f"{G['fail']}  {_f(f'Unhandled error in goose {sub}: {exc}')}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
