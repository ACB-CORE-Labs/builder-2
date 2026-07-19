"""The GETTING_STARTED keymap must assign each STRATUM panel to the key the code actually binds.

TUI/UX red-team audit H11 (Orchestration shown under W while the code binds it to Y, and W conflated
Workflow with the Goose hand-off, which is G). `builder-platform audit-docs` is docs-only and does
not cover TUI key labels, so nothing mechanical caught this. app.py BINDINGS is the source of truth;
this pins both that the code binds the drift-prone panels to the expected keys, and that the doc's
keymap table has not drifted from them.
"""

from __future__ import annotations

import re
from pathlib import Path

from builder_ii.tui.app import StratumApp

ROOT = Path(__file__).resolve().parents[1]

#: key letter -> the action the code must bind it to, for the panels whose key assignment drifted (or
#: could). Verified against the live BINDINGS so a silent key reassignment fails here.
_EXPECTED_BINDINGS = {
    "m": "toggle_memory",
    "o": "toggle_models",
    "u": "toggle_agents",
    "c": "toggle_platform_audit",
    "w": "toggle_workflow",
    "y": "toggle_orchestration",
    "b": "toggle_code_vault",
    "e": "toggle_quality_gates",
    "t": "toggle_tooling",
    "g": "launch_goose",
}

#: doc keymap row letter -> a panel word the row must carry (friendly names as the doc writes them).
_DOC_KEYMAP = {
    "W": "Workflow",
    "Y": "Orchestration",
    "G": "Goose",
    "M": "Memory",
    "O": "Models",
    "C": "Platform audit",
    "B": "CodeVault",
    "T": "Tooling",
}


def _bindings() -> list[tuple[str, str]]:
    """(key, action) for every Binding-style entry in StratumApp.BINDINGS (raw tuple entries, if
    any, are skipped -- app.py uses Binding objects, but BINDINGS is typed to allow bare tuples)."""
    pairs: list[tuple[str, str]] = []
    for b in StratumApp.BINDINGS:
        key = getattr(b, "key", None)
        action = getattr(b, "action", None)
        if isinstance(key, str) and isinstance(action, str):
            pairs.append((key, action))
    return pairs


def test_app_binds_each_panel_to_its_expected_key() -> None:
    pairs = _bindings()
    keys = [key for key, _ in pairs]
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    assert not dupes, f"duplicate STRATUM key bindings (one key, two panels is how keymap drift starts): {dupes}"

    by_key = dict(pairs)
    for key, action in _EXPECTED_BINDINGS.items():
        assert by_key.get(key) == action, f"key {key!r} must bind {action!r}, got {by_key.get(key)!r}"

    # Guard the pin itself: if BINDINGS were emptied/renamed, the loop above could pass vacuously.
    assert len(keys) > 15, f"only {len(keys)} bindings scanned -- is StratumApp.BINDINGS intact?"


def test_getting_started_keymap_rows_name_the_correct_panel_for_each_key() -> None:
    text = (ROOT / "docs" / "GETTING_STARTED.md").read_text(encoding="utf-8")
    for key, label in _DOC_KEYMAP.items():
        row = re.search(rf"^\|\s*\*\*{re.escape(key)}\*\*\s*\|\s*([^|]+)\|", text, re.MULTILINE)
        assert row, f"GETTING_STARTED keymap has no row for key {key!r}"
        assert label.lower() in row.group(1).lower(), (
            f"key {key!r} row says {row.group(1).strip()!r}; it must name {label!r} (matches app.py BINDINGS)"
        )
