"""model_tui.py — Model routing inspection surface for builder-II.

Covers the three-artifact routing stack:

  model_routing_policy        — rules, risk caps, RECOMMENDATION_ONLY governance
  model_routing_recommendation — ranked candidate list produced from policy + registry
  model_execution_policy      — bounded AUTHORIZED envelope (executes_model=True)

Command surface
---------------
  builder model routing show              — active policy rules overview
  builder model routing simulate [intent] — dry-run recommendation for a task intent
  builder model routing candidates        — full ranked candidate list (last recommendation)
  builder model routing policy            — raw policy governance flags + rule detail
  builder model routing execution-policy  — execution policy envelope (if present)
  builder model routing validate          — validate all three artifacts on disk
  builder model registry show             — model client registry overview
  builder model registry diff             — compare active registry against a target
"""

from __future__ import annotations

import json
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
    find_artifact as _shared_find_artifact,
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
    row as _shared_row,
)

# ---------------------------------------------------------------------------
# Palette — theme-aware
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


# Glyphs
G = {
    "pass": _p("✔"),
    "fail": _f("✘"),
    "warn": _w("⚠"),
    "skip": _d("–"),
    "bullet": _d("·"),
    "arrow": _d("→"),
    "rank": _acc("▣"),
    "rule": _act("●"),
    "lock": _d("○"),
    "cap": _w("▲"),
}

# ---------------------------------------------------------------------------
# Risk hierarchy (mirrors model_routing_policy._RISK_HIERARCHY)
# ---------------------------------------------------------------------------

RISK_HIERARCHY = {
    "local_offline": 1,
    "local_network": 2,
    "cloud_external": 3,
}

RISK_LABEL = {
    "local_offline": _p("local_offline"),
    "local_network": _w("local_network"),
    "cloud_external": _f("cloud_external"),
}

# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


def _builder_dir() -> Path:
    return _shared_builder_dir()


def _short(digest: str, n: int = 14) -> str:
    if not digest or not isinstance(digest, str):
        return _d("—")
    return digest[:n]


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


def _risk_color(label: str) -> str:
    return RISK_LABEL.get(label, _d(str(label)))


def _gov_flag(key: str, value: Any) -> None:
    if value == "DISABLED":
        print(f"    {G['lock']}  {_col(_d(key), 36)}  {_d('DISABLED')}")
    elif value is False:
        print(f"    {G['lock']}  {_col(_d(key), 36)}  {_d('false')}")
    elif value == "ENABLED_UNDER_ENVELOPE":
        print(f"    {G['rule']}  {_col(_d(key), 36)}  {_act('ENABLED_UNDER_ENVELOPE')}")
    elif value is True:
        print(f"    {G['pass']}  {_col(_d(key), 36)}  {_p('true')}")
    else:
        print(f"    {G['warn']}  {_col(_d(key), 36)}  {_w(str(value))}")


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> tuple[dict | None, str]:
    return _shared_load_json_object(path)


def _find_artifact(base: Path, *candidates: str) -> tuple[Path | None, dict | None]:
    return _shared_find_artifact(base, *candidates)


# ---------------------------------------------------------------------------
# builder model routing show
# ---------------------------------------------------------------------------


def cmd_routing_show(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()

    policy_path, policy = _find_artifact(
        base,
        "model_routing_policy.json",
        "routing/model_routing_policy.json",
        "model/routing_policy.json",
    )

    _section("Model Routing Policy")

    if policy is None:
        print(f"  {G['skip']}  {_d('No model_routing_policy.json found under')} {base}")
        print(f"  {_h('hint: builder-model-policy dry-run  to emit passive routing artifacts')}")
        print()
        return 0

    _kv("kind", _d(policy.get("kind", "")))
    _kv("policy_name", _b(str(policy.get("policy_name", _d("—")))))
    _kv("policy_state", _act(str(policy.get("policy_state", ""))))
    _kv("executes_model", _p("false") if policy.get("executes_model") is False else _f("true"))
    _kv("grants_authority", _p("false") if policy.get("grants_authority") is False else _f("true"))
    _kv("HITL required", _p("yes") if policy.get("requires_human_promotion_for_execution") else _f("no"))

    rules = policy.get("rules") or []
    if rules:
        print()
        print(f"  {_b('Routing rules')}  ({len(rules)})")
        print(
            _row(
                (_d("  "), 3),
                (_d("Rule ID"), 30),
                (_d("Intent"), 16),
                (_d("Max Risk"), 18),
                (_d("Tools"), 7),
                (_d("Preferred Model"), 50),
            )
        )
        print(f"  {_hr(126)}")
        for rule in rules:
            rule_id = str(rule.get("rule_id") or _d("—"))[:28]
            intent = str(rule.get("task_intent") or _d("—"))[:14]
            risk = rule.get("max_risk_classification") or ""
            tools = rule.get("requires_tool_use")
            model_id = str(rule.get("preferred_model_id") or rule.get("preferred_model_family") or _d("—"))[:48]
            tools_txt = _p("yes") if tools else _d("no")
            print(
                _row(
                    (G["rule"], 3),
                    (_b(rule_id), 30),
                    (_act(intent), 16),
                    (_risk_color(risk), 18),
                    (tools_txt, 7),
                    (_d(model_id), 50),
                )
            )
            if verbose and rule.get("rationale"):
                print(f"       {_h(rule['rationale'])}")

    # Governance summary
    if verbose:
        gov = policy.get("governance") or {}
        print()
        print(f"  {_b('Governance')}")
        for k, v in gov.items():
            _gov_flag(k, v)

    print()
    return 0


def _row(*cells: tuple[str, int]) -> str:
    return _shared_row(*cells)


# ---------------------------------------------------------------------------
# builder model routing simulate [intent]
# ---------------------------------------------------------------------------


def cmd_routing_simulate(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    intent_args = [a for a in args if not a.startswith("-")]
    task_intent = intent_args[0] if intent_args else "coding"
    risk = intent_args[1] if len(intent_args) > 1 else "local_network"
    tools_flag = "--tools" in args or "-t" in args

    base = _builder_dir()
    _, policy = _find_artifact(
        base,
        "model_routing_policy.json",
        "routing/model_routing_policy.json",
    )
    _, registry = _find_artifact(
        base,
        "model_client_registry.json",
        "routing/model_client_registry.json",
        "model/client_registry.json",
    )

    _section(f"Routing Simulation  {_d('intent=' + task_intent)}  {_d('risk=' + risk)}")

    if policy is None:
        print(f"  {G['fail']}  {_f('model_routing_policy.json not found')}")
        return 1
    if registry is None:
        print(f"  {G['fail']}  {_f('model_client_registry.json not found')}")
        return 1

    try:
        from builder_ii.model_routing_policy import create_model_routing_recommendation

        request = {
            "task_intent": task_intent,
            "max_risk_classification": risk,
            "requires_tool_use": tools_flag,
        }
        rec = create_model_routing_recommendation(policy, registry, request)
        _render_recommendation(rec, verbose=verbose)
        return 0
    except Exception as exc:
        print(f"  {G['fail']}  {_f(str(exc))}")
        return 1


# ---------------------------------------------------------------------------
# builder model routing candidates
# ---------------------------------------------------------------------------


def cmd_routing_candidates(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()

    rec_path, rec = _find_artifact(
        base,
        "model_routing_recommendation.json",
        "routing/model_routing_recommendation.json",
        "model/routing_recommendation.json",
    )

    _section("Routing Recommendation — Candidates")

    if rec is None:
        print(f"  {G['skip']}  {_d('No routing recommendation artifact found.')}")
        print(f"  {_h('hint: builder model routing simulate <intent>')}")
        print()
        return 0

    _render_recommendation(rec, verbose=verbose)
    return 0


def _render_recommendation(rec: dict, *, verbose: bool) -> None:
    state = rec.get("recommendation_state", "")
    executes = rec.get("executes_model")
    request = rec.get("request") or {}

    _kv("state", _act(str(state)))
    _kv("executes_model", _p("false") if executes is False else _f("true"))
    _kv("HITL required", _p("yes") if rec.get("requires_human_promotion_for_execution") else _f("no"))
    _kv("request.intent", _b(str(request.get("task_intent", _d("—")))))
    _kv("request.risk", _risk_color(str(request.get("max_risk_classification", ""))))
    _kv("request.tools", _p("yes") if request.get("requires_tool_use") else _d("no"))

    # Source refs
    if verbose:
        for ref_field in ("source_policy_ref", "source_registry_ref"):
            ref = rec.get(ref_field) or {}
            _kv(ref_field, _short(ref.get("sha256", "")))

    candidates = rec.get("recommended_candidates") or []
    if not candidates:
        print(f"  {G['skip']}  {_d('No candidates in recommendation.')}")
        return

    print()
    print(f"  {_b('Ranked candidates')}  ({len(candidates)})")
    print(
        _row(
            (_d("Rank"), 5),
            (_d("Model ID"), 50),
            (_d("Alias"), 20),
            (_d("Risk"), 18),
            (_d("Provider"), 16),
        )
    )
    print(f"  {_hr(114)}")

    for cand in candidates:
        rank = str(cand.get("rank", "?"))
        model = str(cand.get("model_id") or _d("—"))[:48]
        alias = str(cand.get("model_alias") or _d("—"))[:18]
        risk = str(cand.get("risk_classification") or "")
        prov = str(cand.get("provider_id") or _d("—"))[:14]
        is_top = cand.get("rank") == 1

        rank_g = G["rank"] if is_top else _d(rank)
        model_t = _act(model) if is_top else _b(model)
        print(
            _row(
                (rank_g, 5),
                (model_t, 50),
                (_d(alias), 20),
                (_risk_color(risk), 18),
                (_d(prov), 16),
            )
        )
        if verbose:
            for reason in cand.get("reasons") or []:
                print(f"       {G['bullet']}  {_h(reason)}")
            for constraint in cand.get("constraints") or []:
                print(f"       {G['cap']}  {_w(constraint)}")


# ---------------------------------------------------------------------------
# builder model routing policy
# ---------------------------------------------------------------------------


def cmd_routing_policy(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()
    _, policy = _find_artifact(base, "model_routing_policy.json", "routing/model_routing_policy.json")

    _section("Routing Policy Detail")
    if policy is None:
        print(f"  {G['skip']}  {_d('No model_routing_policy.json found.')}")
        return 0

    # Full governance block
    gov = policy.get("governance") or {}
    print(f"  {_b('Governance flags')}")
    for k, v in gov.items():
        _gov_flag(k, v)

    # Rules detail
    rules = policy.get("rules") or []
    for i, rule in enumerate(rules, 1):
        print()
        print(f"  {G['rule']}  {_b('Rule ' + str(i))}  {_d(rule.get('rule_id', ''))}")
        _kv("task_intent", _act(str(rule.get("task_intent", ""))), kw=28)
        _kv("max_risk_classification", _risk_color(str(rule.get("max_risk_classification", ""))), kw=28)
        _kv("requires_tool_use", _p("yes") if rule.get("requires_tool_use") else _d("no"), kw=28)
        _kv("preferred_model_id", _d(str(rule.get("preferred_model_id") or "—")), kw=28)
        _kv("preferred_model_family", _d(str(rule.get("preferred_model_family") or "—")), kw=28)
        if verbose and rule.get("rationale"):
            _kv("rationale", _h(rule["rationale"]), kw=28)

    print()
    return 0


# ---------------------------------------------------------------------------
# builder model routing execution-policy
# ---------------------------------------------------------------------------


def cmd_routing_execution_policy(args: list[str]) -> int:
    base = _builder_dir()
    _, ep = _find_artifact(
        base,
        "model_execution_policy.json",
        "routing/model_execution_policy.json",
        "model/execution_policy.json",
    )

    _section("Model Execution Policy")

    if ep is None:
        print(f"  {G['skip']}  {_d('No model_execution_policy.json found.')}")
        print(f"  {_h('Execution policy is only created after human promotion of a routing recommendation.')}")
        print()
        return 0

    state = ep.get("policy_state", "")
    executes = ep.get("executes_model")
    grants = ep.get("grants_authority")
    max_tok = ep.get("max_tokens")

    # State traffic light
    if state == "AUTHORIZED":
        state_txt = _act(state)
    else:
        state_txt = _w(state)

    _kv("policy_state", state_txt)
    _kv("executes_model", _act("true") if executes else _d("false"))
    _kv("grants_authority", _f("true") if grants else _p("false"))
    _kv("max_tokens", _b(str(max_tok)) if max_tok else _d("—"))
    _kv("HITL required", _p("yes") if ep.get("requires_human_promotion_for_execution") else _f("no"))

    # Allowed models
    allowed = ep.get("allowed_models") or []
    if allowed:
        print()
        print(f"  {_b('Allowed models')}  ({len(allowed)})")
        for m in allowed:
            print(f"    {G['rule']}  {_act(m)}")

    # Recommendation ref
    rec_ref = ep.get("source_recommendation_ref") or {}
    if rec_ref:
        print()
        _kv("source_recommendation_ref", _short(rec_ref.get("sha256", "")))

    # Governance
    gov = ep.get("governance") or {}
    if gov:
        print()
        print(f"  {_b('Governance')}")
        for k, v in gov.items():
            _gov_flag(k, v)

    print()
    return 0


# ---------------------------------------------------------------------------
# builder model routing validate
# ---------------------------------------------------------------------------


def cmd_routing_validate(args: list[str]) -> int:
    base = _builder_dir()
    rc = 0
    _section("Routing Artifact Validation")

    checks = [
        (
            "model_routing_policy",
            _find_artifact(base, "model_routing_policy.json", "routing/model_routing_policy.json"),
            "builder_ii.model_routing_policy",
            "validate_model_routing_policy",
        ),
        (
            "model_routing_recommendation",
            _find_artifact(base, "model_routing_recommendation.json", "routing/model_routing_recommendation.json"),
            "builder_ii.model_routing_policy",
            "validate_model_routing_recommendation",
        ),
        (
            "model_execution_policy",
            _find_artifact(base, "model_execution_policy.json", "routing/model_execution_policy.json"),
            "builder_ii.model_routing_policy",
            "validate_model_execution_policy",
        ),
    ]

    for label, (path, data), mod_name, fn_name in checks:
        if data is None:
            print(f"  {G['skip']}  {_col(_d(label), 36)}  {_d('not found')}")
            continue
        try:
            import importlib

            mod = importlib.import_module(mod_name)
            fn = getattr(mod, fn_name)
            errors = fn(data)
        except Exception as exc:
            errors = [str(exc)]

        g = G["pass"] if not errors else G["fail"]
        txt = _p("VALID") if not errors else _f(f"{len(errors)} error(s)")
        print(f"  {g}  {_col(_b(label), 36)}  {txt}")
        for e in errors:
            print(f"       {G['fail']}  {_f(e)}")
        if errors:
            rc = 1

    print()
    return rc


# ---------------------------------------------------------------------------
# builder model registry show
# ---------------------------------------------------------------------------


def cmd_registry_show(args: list[str]) -> int:
    verbose = "-v" in args or "--verbose" in args
    base = _builder_dir()
    _, registry = _find_artifact(
        base,
        "model_client_registry.json",
        "routing/model_client_registry.json",
        "model/client_registry.json",
    )

    _section("Model Client Registry")

    if registry is None:
        print(f"  {G['skip']}  {_d('No model_client_registry.json found.')}")
        return 0

    clients = registry.get("clients") or []
    enabled = [c for c in clients if c.get("enabled")]
    disabled = [c for c in clients if not c.get("enabled")]

    _kv("total clients", _b(str(len(clients))))
    _kv("enabled", _p(str(len(enabled))))
    _kv("disabled", _d(str(len(disabled))))

    if clients:
        print()
        print(f"  {_b('Client roster')}")
        print(
            _row(
                (_d("  "), 3),
                (_d("Model ID"), 50),
                (_d("Alias"), 20),
                (_d("Provider"), 16),
                (_d("Risk"), 18),
                (_d("Tools"), 7),
                (_d("Cost"), 10),
            )
        )
        print(f"  {_hr(126)}")
        for c in sorted(clients, key=lambda x: (not x.get("enabled"), x.get("risk_classification", ""))):
            en = c.get("enabled")
            g = G["rule"] if en else G["lock"]
            model = str(c.get("model_id") or _d("—"))[:48]
            alias = str(c.get("model_alias") or _d("—"))[:18]
            prov = str(c.get("provider_id") or _d("—"))[:14]
            risk = str(c.get("risk_classification") or "")
            tools = _p("yes") if c.get("tool_use_supported") else _d("no")
            cost = str(c.get("cost_class") or _d("—"))[:8]
            model_t = _act(model) if en else _d(model)
            print(
                _row(
                    (g, 3),
                    (model_t, 50),
                    (_d(alias), 20),
                    (_d(prov), 16),
                    (_risk_color(risk), 18),
                    (tools, 7),
                    (_d(cost), 10),
                )
            )
            if verbose and c.get("notes"):
                print(f"       {_h(c['notes'])}")

    print()
    return 0


# ---------------------------------------------------------------------------
# builder model registry diff
# ---------------------------------------------------------------------------


def cmd_registry_diff(args: list[str]) -> int:
    """Compare the active registry against a target path or second registry file."""
    file_args = [a for a in args if not a.startswith("-")]
    base = _builder_dir()
    _, reg_a = _find_artifact(base, "model_client_registry.json", "routing/model_client_registry.json")

    _section("Registry Diff")

    if reg_a is None:
        print(f"  {G['fail']}  {_f('Active model_client_registry.json not found.')}")
        return 1

    if not file_args:
        print(f"  {G['skip']}  {_d('No target registry path supplied.')}")
        print(f"  {_h('Usage: builder model registry diff <target_registry.json>')}")
        return 0

    reg_b, err = _load_json(Path(file_args[0]))
    if reg_b is None:
        print(f"  {G['fail']}  {_f(err)}")
        return 1

    clients_a = {c.get("model_id"): c for c in (reg_a.get("clients") or [])}
    clients_b = {c.get("model_id"): c for c in (reg_b.get("clients") or [])}

    added = set(clients_b) - set(clients_a)
    removed = set(clients_a) - set(clients_b)
    common = set(clients_a) & set(clients_b)
    changed = [
        m for m in common if json.dumps(clients_a[m], sort_keys=True) != json.dumps(clients_b[m], sort_keys=True)
    ]

    print(f"  {_p(f'+{len(added)} added')}  {_f(f'-{len(removed)} removed')}  {_d(f'~{len(changed)} modified')}")

    for m in sorted(added):
        print(f"    {_p('+')}  {_act(m)}")
    for m in sorted(removed):
        print(f"    {_f('-')}  {_d(m)}")
    for m in sorted(changed):
        ca = clients_a[m]
        cb = clients_b[m]
        print(f"    {_w('~')}  {_b(m)}")
        for field in set(list(ca.keys()) + list(cb.keys())):
            va, vb = ca.get(field), cb.get(field)
            if va != vb:
                print(f"         {_d(field + ':')}  {_f(str(va))} {_d('->')} {_p(str(vb))}")

    print()
    return 0


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

_ROUTING_COMMANDS = {
    "show": cmd_routing_show,
    "simulate": cmd_routing_simulate,
    "candidates": cmd_routing_candidates,
    "policy": cmd_routing_policy,
    "execution-policy": cmd_routing_execution_policy,
    "validate": cmd_routing_validate,
}

_REGISTRY_COMMANDS = {
    "show": cmd_registry_show,
    "diff": cmd_registry_diff,
}


def _usage() -> None:
    print(_b("builder model") + "  —  Model routing inspection surface")
    print()
    print(_acc("routing"))
    for cmd, desc in [
        ("routing show", "Active policy rules overview"),
        ("routing simulate [intent]", "Dry-run recommendation for a task intent"),
        ("routing candidates", "Full ranked candidate list (last recommendation)"),
        ("routing policy", "Raw policy governance flags + rule detail"),
        ("routing execution-policy", "Execution policy envelope (if present)"),
        ("routing validate", "Validate all three routing artifacts on disk"),
    ]:
        print(f"  {_act('builder model ' + cmd):<50}  {_d(desc)}")
    print()
    print(_acc("registry"))
    for cmd, desc in [
        ("registry show", "Model client registry overview"),
        ("registry diff", "Compare active registry against a target file"),
    ]:
        print(f"  {_act('builder model ' + cmd):<50}  {_d(desc)}")
    print()


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        _usage()
        return 0

    group = args[0]
    rest = args[1:]

    if group == "routing":
        if not rest:
            return cmd_routing_show([])
        sub = rest[0]
        handler = _ROUTING_COMMANDS.get(sub)
        if handler is None:
            print(f"{G['fail']}  {_f(f'Unknown routing subcommand: {sub}')}")
            _usage()
            return 1
        return handler(rest[1:])

    if group == "registry":
        if not rest:
            return cmd_registry_show([])
        sub = rest[0]
        handler = _REGISTRY_COMMANDS.get(sub)
        if handler is None:
            print(f"{G['fail']}  {_f(f'Unknown registry subcommand: {sub}')}")
            _usage()
            return 1
        return handler(rest[1:])

    # Fallback: treat first arg as routing subcommand (convenience)
    handler = _ROUTING_COMMANDS.get(group)
    if handler:
        return handler(rest)

    print(f"{G['fail']}  {_f(f'Unknown subcommand group: {group}')}")
    _usage()
    return 1


if __name__ == "__main__":
    sys.exit(main())
