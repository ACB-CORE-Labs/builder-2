"""tui_theme.py — Theme registry for builder-II TUI.

Usage
-----
    export BUILDER_THEME=chargers   # San Diego Chargers powder-blue scheme
    export BUILDER_THEME=default    # slate/indigo/sky (original)

All themes expose the same 8 semantic token names:

    pass    — affirmative / success
    warn    — caution / needs attention
    fail    — error / blocked
    hint    — secondary / de-emphasised text
    active  — active item / highlight
    dim     — muted / separator
    bold    — primary foreground
    accent  — brand / structural accent

Only add tokens here when a semantic gap genuinely exists.
Do not add purely decorative colours.
"""
from __future__ import annotations

import os
from typing import TypedDict


class Palette(TypedDict):
    """The 8 semantic colour tokens every theme must supply."""
    passX: str   # 'pass' is a reserved keyword; key stored as 'pass' in dict
    warn:  str
    fail:  str
    hint:  str
    active: str
    dim:   str
    bold:  str
    accent: str


# ---------------------------------------------------------------------------
# Default theme  — original slate / indigo / sky
# ---------------------------------------------------------------------------
_DEFAULT: dict[str, str] = {
    "pass":   "#3fb950",
    "warn":   "#d29922",
    "fail":   "#f85149",
    "hint":   "#8b949e",
    "active": "#58a6ff",
    "dim":    "#484f58",
    "bold":   "#c9d1d9",
    "accent": "#d2a8ff",
}

# ---------------------------------------------------------------------------
# Chargers theme  — San Diego powder-blue
#
# Swatch reference
# ----------------
#   Powder Blue  #0080C6   — the iconic Chargers mid-blue (primary accent)
#   Deep Blue    #005A8E   — deep border / inactive
#   Muted Blue   #3399CC   — muted secondary blue
#   Navy         #002244   — background / dark base
#   Bolt Gold    #FFC20E   — warning / accent gold
#   White        #FFFFFF   — text / foreground
#
# Mapping rationale
# -----------------
#   pass   → Powder Blue   (affirmative = primary brand colour)
#   warn   → Bolt Gold     (caution = lightning bolt gold energy)
#   fail   → bright red    (failure stays red; universal danger signal)
#   hint   → Muted Blue    (secondary highlights / hover states)
#   active → Powder Blue   (active/highlight = same brand blue as pass)
#   dim    → Deep Blue     (borders, dimmed panels, inactive widgets)
#   bold   → White         (primary text on navy background)
#   accent → Bolt Gold     (alerts, key bindings, badges)
#
# Notes
# -----
#   - Navy (#002244) appears as border/panel hints via Rich markup when
#     callers use theme_panel_border() helper below.
#   - pass and active share Powder Blue intentionally; the glyph (not
#     colour alone) distinguishes them semantically.
#   - fail is kept at near-standard red (#f87171) because red = danger
#     is a cross-cultural convention we should not override.
# ---------------------------------------------------------------------------
_CHARGERS: dict[str, str] = {
    "pass":   "#0080C6",   # Powder Blue
    "warn":   "#FFC20E",   # Bolt Gold
    "fail":   "#f87171",   # red (universal danger; unchanged)
    "hint":   "#3399CC",   # Muted Blue
    "active": "#0080C6",   # Powder Blue
    "dim":    "#005A8E",   # Deep Blue
    "bold":   "#FFFFFF",   # White
    "accent": "#FFC20E",   # Bolt Gold
    # Extended tokens available via theme_extras() only:
    "_navy":  "#002244",   # Navy  — panel borders, deep backgrounds
    "_lgrey": "#3399CC",   # Muted Blue alias
}

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
_REGISTRY: dict[str, dict[str, str]] = {
    "default":  _DEFAULT,
    "chargers": _CHARGERS,
}


def active_theme_name() -> str:
    """Return the active theme name from BUILDER_THEME env var (default: 'default')."""
    return os.environ.get("BUILDER_THEME", "default").lower().strip()


def theme_palette() -> dict[str, str]:
    """Return the active 8-token palette dict.

    Always returns a dict with keys:
        pass, warn, fail, hint, active, dim, bold, accent
    Falls back to default for unknown theme names.
    """
    name = active_theme_name()
    return dict(_REGISTRY.get(name, _DEFAULT))


def theme_extras() -> dict[str, str]:
    """Return extended theme tokens (e.g. _navy) for the active theme.
    Returns empty dict for themes with no extras.
    """
    name = active_theme_name()
    palette = _REGISTRY.get(name, _DEFAULT)
    return {k: v for k, v in palette.items() if k.startswith("_")}


def theme_panel_border() -> str:
    """Return the recommended panel border colour for the active theme."""
    extras = theme_extras()
    # Chargers: use navy for panel borders
    if "_navy" in extras:
        return extras["_navy"]
    # Default: use dim
    return theme_palette()["dim"]


def theme_section_rule() -> str:
    """Return the recommended section rule colour for the active theme."""
    return theme_palette()["accent"]


def list_themes() -> list[str]:
    """Return sorted list of available theme names."""
    return sorted(_REGISTRY.keys())


# ---------------------------------------------------------------------------
# Rich Console factory
# ---------------------------------------------------------------------------

def make_console(**kwargs):
    """Return a Rich Console instance. Theme is ambient (applied via _C tokens)."""
    try:
        from rich.console import Console
        return Console(highlight=False, **kwargs)
    except ImportError as exc:
        raise ImportError("rich is required for builder-II TUI") from exc
